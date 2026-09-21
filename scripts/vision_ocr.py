"""Headless visual-model OCR: PDF or page images -> text + boxes.

Uses the same engine code as PPOCRLabel (libs/hunyuan_ocr.py, libs/qwen_ocr.py),
so behaviour and fixes stay identical between the GUI and this command line.
No GUI, no LM Studio, no PP-Structure.

Examples
--------
# one PDF, whole page read, pages 1-20
python scripts/vision_ocr.py --input book.pdf --pages 1-20 --outdir out/book

# a folder of page images, line-by-line boxes (box and text strictly 1:1)
python scripts/vision_ocr.py --input pages/ --lines --outdir out/pages

# vertical old print, model decides the layout, also write PPOCRLabel Label.txt
python scripts/vision_ocr.py --input book.pdf --engine qwen --layout model-auto \\
    --reading vertical --label-file --outdir out/vertical

# dialect dictionary with IPA: IPA-aware prompt, line by line (recommended for dense pages)
python scripts/vision_ocr.py --input pages/ --ipa --lines --outdir out/ipa
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.hunyuan_ocr import HunyuanLayout  # noqa: E402  (needs ROOT on sys.path)

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}
LOCK_PATH = ROOT / "tools" / "hunyuan" / "logs" / ".vision_ocr.lock"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Visual-model OCR (HunyuanOCR / Qwen) for PDFs or page images."
    )
    parser.add_argument("--input", required=True, nargs="+",
                        help="PDF file(s), one image, or a folder of page images.")
    parser.add_argument("--outdir", required=True, help="Output directory.")
    parser.add_argument("--engine", default="hunyuan", choices=("hunyuan", "qwen"),
                        help="Visual model to use (default: hunyuan).")
    parser.add_argument("--layout", default=HunyuanLayout.DEFAULT,
                        choices=tuple(HunyuanLayout.ORDER),
                        help="Layout mode (default: whole page, no column handling).")
    parser.add_argument("--reading", default="horizontal", choices=("horizontal", "vertical"),
                        help="Reading direction, used by the fallback and column modes.")
    parser.add_argument("--lines", action="store_true",
                        help="Recognise every printed line on its own (exact 1:1 boxes, ~2x slower).")
    parser.add_argument("--ipa", action="store_true",
                        help="IPA-aware prompt for dialect dictionaries: tone letters "
                             "˥˦˧˨˩ plus the IPA charset, no Zhuyin/pinyin substitutes "
                             "(recommended together with --lines).")
    parser.add_argument("--pages", default="",
                        help="PDF page range, e.g. 3,5-9 (1-based; default: all pages).")
    parser.add_argument("--dpi", type=int, default=200,
                        help="PDF rendering DPI (default: 200).")
    parser.add_argument("--label-file", action="store_true",
                        help="Also write PPOCRLabel Label.txt lines for the boxes.")
    parser.add_argument("--label-path-prefix", default="",
                        help="Override the image path prefix used in Label.txt.")
    parser.add_argument("--allow-shared-gpu", action="store_true",
                        help="Run even when another llama-server is already running.")
    parser.add_argument("--no-json", action="store_true", help="Skip per-page box JSON.")
    return parser.parse_args()


def natural_key(path: Path) -> list[Any]:
    return [
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", path.name)
    ]


def parse_pages(spec: str) -> list[int] | None:
    if not spec.strip():
        return None
    pages: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = (int(value) for value in part.split("-", 1))
            pages.extend(range(start, end + 1))
        else:
            pages.append(int(part))
    return sorted(dict.fromkeys(pages))


def find_pdftoppm() -> str:
    found = shutil.which("pdftoppm")
    if found:
        return found
    fallback = Path(r"C:\Program Files\MiKTeX\miktex\bin\x64\pdftoppm.exe")
    if fallback.exists():
        return str(fallback)
    raise SystemExit("pdftoppm not found; install poppler or MiKTeX.")


def render_pdf(pdf: Path, out_dir: Path, dpi: int, pages: list[int] | None) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    wanted = pages or [None]
    rendered: list[Path] = []
    for page in wanted:
        args = [find_pdftoppm(), "-png", "-r", str(dpi)]
        if page is not None:
            args += ["-f", str(page), "-l", str(page)]
        args += [str(pdf), str(out_dir / "page")]
        subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if page is None:
            rendered.extend(sorted(out_dir.glob("page-*.png"), key=natural_key))
        else:
            matches = sorted(out_dir.glob(f"page-{page:03d}.png")) or sorted(
                out_dir.glob(f"page-{page}*.png"), key=natural_key
            )
            if not matches:
                raise RuntimeError(f"page {page} of {pdf.name} was not rendered")
            rendered.append(matches[0])
    return rendered


def collect_pages(inputs: list[str]) -> tuple[list[Path], list[tuple[Path, Path]]]:
    """Return page images plus the PDFs that still need rendering."""
    pages: list[Path] = []
    pdfs: list[tuple[Path, Path]] = []
    for item in inputs:
        path = Path(item)
        if path.is_dir():
            pages.extend(sorted(
                (p for p in path.iterdir() if p.suffix.lower() in IMAGE_EXTS),
                key=natural_key,
            ))
        elif path.suffix.lower() == ".pdf":
            pdfs.append((path, path))
        elif path.suffix.lower() in IMAGE_EXTS:
            pages.append(path)
        else:
            raise SystemExit(f"unsupported input: {path}")
    return pages, pdfs


def gpu_report() -> str:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader"],
            capture_output=True, text=True, errors="replace", timeout=15,
        )
        return out.stdout.strip() or "nvidia-smi returned nothing"
    except Exception as exc:  # noqa: BLE001
        return f"nvidia-smi unavailable ({exc})"


def running_llama_servers() -> list[str]:
    try:
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq llama-server.exe", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, errors="replace", timeout=20,
        )
        return [line for line in out.stdout.splitlines() if "llama-server" in line]
    except Exception:  # noqa: BLE001
        return []


def acquire_lock(outdir: Path) -> None:
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    if LOCK_PATH.exists():
        try:
            pid = int(LOCK_PATH.read_text(encoding="utf-8").strip().split()[0])
        except Exception:  # noqa: BLE001
            pid = 0
        if pid and pid != os.getpid():
            alive = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, errors="replace", timeout=20,
            ).stdout
            if str(pid) in alive:
                raise SystemExit(
                    f"another vision_ocr run is active (pid {pid}); "
                    f"remove {LOCK_PATH} if that is stale"
                )
    LOCK_PATH.write_text(f"{os.getpid()} {outdir}", encoding="utf-8")


def release_lock() -> None:
    try:
        LOCK_PATH.unlink()
    except OSError:
        pass


def build_engine(name: str):
    if name == "hunyuan":
        from libs.hunyuan_ocr import HunyuanOCR
        return HunyuanOCR(), "HunyuanOCR"
    from libs.qwen_ocr import QwenOCR
    return QwenOCR(), "Qwen OCR"


def label_path_for(image: Path, prefix: str) -> str:
    if prefix:
        return prefix.rstrip("/") + "/" + image.name
    # PPOCRLabel stores "<image-dir-name>/<file>" relative to the label file's folder.
    return f"{image.parent.name}/{image.name}"


def safe_stem(source: str, page: Path, limit: int = 64) -> str:
    """Short, unique output name.

    Book scans often carry very long file names (vendor + ISBN + hash), and
    Windows rejects overly long path components, so keep the head (book) and the
    tail (page number) and append a short digest for uniqueness.
    """
    base = Path(source).stem
    raw = base if base == page.stem else f"{base[:24]}_{page.stem}"
    digest = hashlib.md5(f"{source}|{page.stem}".encode("utf-8")).hexdigest()[:8]
    if len(raw) > limit:
        head = raw[: limit // 2]
        tail = raw[-(limit - len(head)) :]
        raw = f"{head}_{tail}"
    return f"{raw}-{digest}"


def write_outputs(
    args: argparse.Namespace,
    page: Path,
    entries: list,
    elapsed: float,
    sources: dict[Path, str],
) -> tuple[int, int, str]:
    outdir = Path(args.outdir)
    (outdir / "text").mkdir(parents=True, exist_ok=True)
    source = sources.get(page, page.name)
    stem = safe_stem(source, page)
    text = "\n".join(entry[1][0] for entry in entries)
    (outdir / "text" / f"{stem}.txt").write_text(text, encoding="utf-8")

    boxes = [
        {
            "text": entry[1][0],
            "points": [[int(point[0]), int(point[1])] for point in entry[0]],
        }
        for entry in entries
    ]
    empty = sum(1 for box in boxes if not box["text"].strip())
    if not args.no_json:
        (outdir / "json").mkdir(parents=True, exist_ok=True)
        (outdir / "json" / f"{stem}.json").write_text(
            json.dumps(
                {
                    "source": str(page),
                    "engine": args.engine,
                    "layout": args.layout,
                    "lines": bool(args.lines),
                    "reading": args.reading,
                    "elapsed_seconds": round(elapsed, 3),
                    "box_count": len(boxes),
                    "empty_boxes": empty,
                    "boxes": boxes,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    with (outdir / "records.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(
            {
                "source": str(page),
                "stem": stem,
                "elapsed_seconds": round(elapsed, 3),
                "box_count": len(boxes),
                "empty_boxes": empty,
                "text": text,
            },
            ensure_ascii=False,
        ) + "\n")
    if args.label_file and boxes:
        payload = json.dumps(
            [
                {
                    "transcription": box["text"],
                    "points": box["points"],
                    "difficult": False,
                    "history": [],
                }
                for box in boxes
            ],
            ensure_ascii=False,
        )
        with (outdir / "Label.txt").open("a", encoding="utf-8") as handle:
            handle.write(f"{label_path_for(page, args.label_path_prefix)}\t{payload}\n")
    return len(boxes), empty, text


def main() -> None:
    args = parse_args()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    acquire_lock(outdir)
    servers = running_llama_servers()
    print(f"GPU: {gpu_report()}")
    if servers and not args.allow_shared_gpu:
        release_lock()
        raise SystemExit(
            "a llama-server.exe is already running (probably the PPOCRLabel window).\n"
            "Close that recognition task, or pass --allow-shared-gpu."
        )

    pages, pdfs = collect_pages(args.input)
    sources: dict[Path, str] = {page: page.name for page in pages}
    pdf_pages = parse_pages(args.pages)
    for pdf, _ in pdfs:
        render_dir = outdir / "pages" / pdf.stem
        rendered = render_pdf(pdf, render_dir, args.dpi, pdf_pages)
        for image in rendered:
            sources[image] = pdf.name
        pages.extend(rendered)
        print(f"rendered {len(rendered)} page(s) from {pdf.name} at {args.dpi} dpi")
    if not pages:
        release_lock()
        raise SystemExit("no pages to recognise")

    engine, engine_name = build_engine(args.engine)
    print(f"engine={engine_name} layout={args.layout} lines={args.lines} "
          f"ipa={args.ipa} reading={args.reading} pages={len(pages)}")
    started = time.monotonic()
    processed = 0
    try:
        for index, page in enumerate(pages, start=1):
            page_started = time.monotonic()
            try:
                entries = engine.recognize(
                    str(page),
                    layout_mode=args.layout,
                    reading_mode=args.reading,
                    line_mode=args.lines,
                    ipa_mode=args.ipa,
                )
            except Exception as exc:  # noqa: BLE001
                print(f"  [{index}/{len(pages)}] {page.name} FAILED: {exc}")
                continue
            elapsed = time.monotonic() - page_started
            boxes, empty, text = write_outputs(args, page, entries, elapsed, sources)
            processed += 1
            print(f"  [{index}/{len(pages)}] {page.name}: {boxes} boxes, "
                  f"{empty} empty, {elapsed:.1f}s")
            if index == 1:
                with (outdir / "full_text.txt").open("w", encoding="utf-8") as handle:
                    handle.write(f"=== {sources[page]} {page.stem} ===\n{text}\n")
            else:
                with (outdir / "full_text.txt").open("a", encoding="utf-8") as handle:
                    handle.write(f"\n=== {sources[page]} {page.stem} ===\n{text}\n")
    finally:
        engine.stop()
        release_lock()
    print(f"done: {processed}/{len(pages)} pages in {time.monotonic() - started:.1f}s "
          f"-> {outdir}")


if __name__ == "__main__":
    main()
