from __future__ import annotations

import argparse
import shutil
import tempfile
from pathlib import Path
from typing import Any, Iterable

import numpy as np


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run PP-StructureV3 on a PDF or image folder and export full text."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="PDF file or folder containing page images.",
    )
    parser.add_argument(
        "--output",
        default="full_text.txt",
        help="TXT path to write recognized text.",
    )
    parser.add_argument(
        "--layout_model_dir",
        default=r"C:\Users\sheng\.paddlex\official_models\PP-DocLayout_plus-L",
        help="PP-Structure layout detection model directory.",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=200,
        help="PDF rendering DPI when --input is a PDF.",
    )
    parser.add_argument(
        "--page_separator",
        default="\n\n",
        help="Text inserted between pages.",
    )
    parser.add_argument(
        "--strip_html",
        action="store_true",
        help="Strip HTML tags from recognized table/text blocks.",
    )
    parser.add_argument(
        "--keep_pages_dir",
        default="",
        help="Optional directory to keep rendered PDF page images.",
    )
    parser.add_argument(
        "--two_column_lr",
        action="store_true",
        help="Force left-column then right-column reading order.",
    )
    return parser.parse_args()


def natural_key(path: Path) -> list[Any]:
    import re

    return [
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", path.name)
    ]


def collect_images(input_dir: Path) -> list[Path]:
    images = [p for p in input_dir.iterdir() if p.suffix.lower() in IMAGE_EXTS]
    return sorted(images, key=natural_key)


def render_pdf(pdf_path: Path, dpi: int, output_dir: Path) -> list[Path]:
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError(
            "PDF input requires PyMuPDF. Install it with: pip install pymupdf"
        ) from exc

    output_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(str(pdf_path))
    try:
        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        page_paths = []
        digits = max(4, len(str(doc.page_count)))
        for page_index in range(doc.page_count):
            page = doc.load_page(page_index)
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            out_path = output_dir / f"{pdf_path.stem}_p{page_index + 1:0{digits}d}.png"
            pix.save(str(out_path))
            page_paths.append(out_path)
        return page_paths
    finally:
        doc.close()


def normalize_bbox(bbox: Any) -> list[float] | None:
    if hasattr(bbox, "tolist"):
        bbox = bbox.tolist()
    if not isinstance(bbox, (list, tuple)):
        return None
    if len(bbox) == 4 and all(isinstance(v, (int, float)) for v in bbox):
        return [float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])]
    if len(bbox) >= 4 and all(
        isinstance(v, (list, tuple)) and len(v) >= 2 for v in bbox
    ):
        try:
            xs = [float(pt[0]) for pt in bbox]
            ys = [float(pt[1]) for pt in bbox]
        except Exception:
            return None
        return [min(xs), min(ys), max(xs), max(ys)]
    return None


def sort_blocks(
    blocks: list[tuple[str, list[float] | None]],
    page_width: float | None,
    two_column_lr: bool,
) -> list[tuple[str, list[float] | None]]:
    if not blocks or not page_width:
        return blocks

    rects = []
    for idx, (_, bbox) in enumerate(blocks):
        if not bbox or len(bbox) != 4:
            continue
        x0, y0, x1, y1 = bbox
        rects.append({"idx": idx, "x0": x0, "x1": x1, "y0": y0, "y1": y1})
    if not rects:
        return blocks

    if two_column_lr:
        split = page_width / 2.0
        left = [r for r in rects if ((r["x0"] + r["x1"]) / 2.0) < split]
        right = [r for r in rects if ((r["x0"] + r["x1"]) / 2.0) >= split]
        left.sort(key=lambda r: (r["y0"], r["x0"]))
        right.sort(key=lambda r: (r["y0"], r["x0"]))
        return [blocks[r["idx"]] for r in left + right]

    median_width = float(np.median([r["x1"] - r["x0"] for r in rects]))
    col_gap = max(12.0, median_width * 0.5, page_width * 0.03)
    rects.sort(key=lambda r: (r["x0"], r["y0"]))
    columns = []
    for rect in rects:
        for column in columns:
            if rect["x0"] <= column["max_x"] + col_gap:
                column["items"].append(rect)
                column["max_x"] = max(column["max_x"], rect["x1"])
                break
        else:
            columns.append({"items": [rect], "max_x": rect["x1"]})

    ordered = []
    for column in sorted(columns, key=lambda c: c["items"][0]["x0"]):
        column["items"].sort(key=lambda r: (r["y0"], r["x0"]))
        ordered.extend(blocks[r["idx"]] for r in column["items"])
    return ordered


def strip_html_tags(text: str) -> str:
    import re

    text = re.sub(r"(?is)<(script|style).*?>.*?(</\1>)", "", text)
    return re.sub(r"(?s)<[^>]+>", "", text)


def page_width_from_entry(entry: dict[str, Any]) -> float | None:
    try:
        img_arr = entry.get("doc_preprocessor_res", {}).get("output_img")
        if img_arr is not None:
            return float(img_arr.shape[1])
    except Exception:
        return None
    return None


def extract_page_text(
    entry: dict[str, Any], strip_html: bool, two_column_lr: bool
) -> str:
    blocks: list[tuple[str, list[float] | None]] = []
    parsing_list = entry.get("parsing_res_list") or []
    allowed_labels = {"text", "paragraph_title", "header", "number"}

    for region in parsing_list:
        if isinstance(region, dict):
            label = region.get("label") or ""
            content = region.get("content") or ""
            bbox = region.get("bbox") or region.get("coordinate") or []
        else:
            label = getattr(region, "label", "") or ""
            content = getattr(region, "content", "") or ""
            bbox = getattr(region, "bbox", None) or getattr(region, "coordinate", [])
        if label and label not in allowed_labels:
            continue
        if content:
            if strip_html:
                content = strip_html_tags(content)
            blocks.append((content, normalize_bbox(bbox)))

    if not blocks:
        ocr_res = entry.get("overall_ocr_res") or {}
        texts = ocr_res.get("rec_texts") or []
        polys: Iterable[Any] = ocr_res.get("rec_polys") or ocr_res.get("dt_polys") or []
        for text, poly in zip(texts, polys):
            if text:
                blocks.append((str(text), normalize_bbox(poly)))

    blocks = sort_blocks(blocks, page_width_from_entry(entry), two_column_lr)
    return "\n".join(text for text, _ in blocks if text)


def build_page_list(
    input_path: Path, dpi: int, keep_pages_dir: str
) -> tuple[list[Path], Path | None]:
    if input_path.is_dir():
        return collect_images(input_path), None
    if input_path.suffix.lower() == ".pdf":
        if keep_pages_dir:
            render_dir = Path(keep_pages_dir)
            if render_dir.exists():
                shutil.rmtree(render_dir)
            return render_pdf(input_path, dpi, render_dir), None
        temp_dir = Path(tempfile.mkdtemp(prefix="ppocrlabel_pages_"))
        return render_pdf(input_path, dpi, temp_dir), temp_dir
    if input_path.suffix.lower() in IMAGE_EXTS:
        return [input_path], None
    raise ValueError(f"Unsupported input: {input_path}")


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(input_path)

    pages, temp_dir = build_page_list(input_path, args.dpi, args.keep_pages_dir)
    if not pages:
        raise ValueError(f"No images found in {input_path}")

    try:
        from paddleocr import PPStructureV3
    except ImportError as exc:
        raise RuntimeError(
            "PaddleOCR is required. Run this inside the ppocrlabel conda environment."
        ) from exc

    engine = PPStructureV3(
        layout_detection_model_dir=args.layout_model_dir,
        use_region_detection=True,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
    )

    page_texts = []
    try:
        for page_num, image_path in enumerate(pages, start=1):
            print(f"[{page_num}/{len(pages)}] {image_path.name}")
            result = engine.predict(str(image_path))
            if not result:
                page_texts.append("")
                continue
            entry = result[0] if isinstance(result, (list, tuple)) else result
            page_texts.append(
                extract_page_text(
                    entry,
                    strip_html=args.strip_html,
                    two_column_lr=args.two_column_lr,
                )
            )
    finally:
        if temp_dir is not None:
            shutil.rmtree(temp_dir, ignore_errors=True)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        args.page_separator.join(page_texts).strip() + "\n", encoding="utf-8"
    )
    print(f"Saved full text to {output_path}")


if __name__ == "__main__":
    main()
