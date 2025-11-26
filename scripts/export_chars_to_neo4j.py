"""
Split PP-OCRLabel recognition crops into per-character images and optionally
push the mapping into Neo4j.

Typical usage (from repo root):
    python scripts/export_chars_to_neo4j.py --data-root test \\
        --rec-gt rec_gt.txt --char-dir-name char_img \\
        --neo4j-uri bolt://localhost:7687 --neo4j-user neo4j \\
        --neo4j-password <password> --source-tag oracle_bones
"""
from __future__ import annotations

import argparse
import csv
import os
from dataclasses import dataclass
import sys
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

import numpy as np
from PIL import Image


try:
    from neo4j import GraphDatabase

    _NEO4J_AVAILABLE = True
except Exception:
    _NEO4J_AVAILABLE = False


@dataclass
class CharRecord:
    char: str
    img_path: Path
    line_file: str
    order: int


def load_rec_gt(rec_gt_path: Path) -> Iterable[Tuple[str, str]]:
    with rec_gt_path.open("r", encoding="utf-8") as f:
        for idx, raw in enumerate(f, 1):
            line = raw.rstrip("\n\r")
            if not line.strip():
                continue
            if "\t" not in line:
                # Allow path-only line; treat label as empty but warn.
                print(
                    f"[warn] missing tab/text in {rec_gt_path}:{idx}, treating as empty label",
                    file=sys.stderr,
                )
                rel_path, text = line.strip(), ""
            else:
                rel_path, text = line.split("\t", 1)
            yield rel_path, text


def resolve_image_path(
    rel_path: str, data_root: Path, crop_dir_name: str
) -> Path:
    raw = Path(rel_path)
    if raw.is_absolute():
        return raw
    candidate = data_root / raw
    if candidate.exists():
        return candidate
    candidate = data_root / crop_dir_name / raw.name
    return candidate


def find_split_positions(mask: np.ndarray, expected: int) -> Sequence[int]:
    """
    Return split column indices (including 0 and width) for roughly balanced
    character slices. Uses a vertical projection search and falls back to
    uniform spacing.
    """
    height, width = mask.shape
    if expected <= 1 or width <= expected:
        return [0, width]

    projection = mask.sum(axis=0).astype(np.float32)
    smoothed = np.convolve(projection, np.ones(5, dtype=np.float32) / 5, mode="same")
    candidates = np.argsort(smoothed)
    splits = {0, width}
    min_gap = max(2, width // max(expected * 3, 1))

    for idx in candidates:
        if idx <= 1 or idx >= width - 1:
            continue
        if all(abs(int(idx) - s) >= min_gap for s in splits):
            splits.add(int(idx))
            if len(splits) == expected + 1:
                break

    if len(splits) != expected + 1:
        step = width / expected
        splits = {0, width}
        for i in range(1, expected):
            splits.add(int(round(i * step)))

    return sorted(splits)


def slice_line_to_chars(
    img_path: Path, text: str, char_dir: Path
) -> List[CharRecord]:
    image = Image.open(img_path).convert("RGB")
    gray = np.array(image.convert("L"))
    # Foreground mask: values near black are foreground.
    mask = gray < 200

    splits = find_split_positions(mask, len(text))
    records: List[CharRecord] = []
    for idx, (left, right) in enumerate(zip(splits[:-1], splits[1:])):
        left = max(0, left)
        right = min(image.width, right)
        if right <= left:
            continue
        char_img = image.crop((left, 0, right, image.height))
        out_name = f"{img_path.stem}_{idx:03d}.png"
        out_path = char_dir / out_name
        char_img.save(out_path)
        records.append(
            CharRecord(
                char=text[idx] if idx < len(text) else "",
                img_path=out_path,
                line_file=img_path.name,
                order=idx,
            )
        )
    return records


def write_csv(records: Sequence[CharRecord], out_path: Path) -> None:
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["img_path", "char", "line_file", "order"]
        )
        writer.writeheader()
        for rec in records:
            writer.writerow(
                {
                    "img_path": str(rec.img_path),
                    "char": rec.char,
                    "line_file": rec.line_file,
                    "order": rec.order,
                }
            )


def push_to_neo4j(
    records: Sequence[CharRecord],
    uri: str,
    user: str,
    password: str,
    source_tag: str,
) -> None:
    if not _NEO4J_AVAILABLE:
        raise ImportError(
            "neo4j driver not installed. Install with `pip install neo4j`."
        )

    driver = GraphDatabase.driver(uri, auth=(user, password))

    def _merge(tx, rec: CharRecord) -> None:
        tx.run(
            """
            MERGE (c:Character {text: $text, source: $source})
            MERGE (i:GlyphImage {path: $path})
            SET i.line = $line, i.char_order = $order
            MERGE (c)-[:RENDERED_AS]->(i)
            """,
            text=rec.char,
            source=source_tag,
            path=str(rec.img_path),
            line=rec.line_file,
            order=rec.order,
        )

    with driver.session() as session:
        for rec in records:
            session.execute_write(_merge, rec)

    driver.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Split PP-OCRLabel rec_gt lines into per-character crops."
    )
    parser.add_argument(
        "--data-root",
        type=str,
        required=True,
        help="Folder containing rec_gt.txt and crop_img (e.g., ./test).",
    )
    parser.add_argument(
        "--rec-gt",
        type=str,
        default="rec_gt.txt",
        help="Recognition ground-truth file name.",
    )
    parser.add_argument(
        "--crop-dir-name",
        type=str,
        default="crop_img",
        help="Folder name that stores line crops.",
    )
    parser.add_argument(
        "--char-dir-name",
        type=str,
        default="char_img",
        help="Output folder name for character crops.",
    )
    parser.add_argument(
        "--csv-out",
        type=str,
        default="char_gt.csv",
        help="Output CSV mapping char images to text.",
    )
    parser.add_argument(
        "--neo4j-uri",
        type=str,
        default="",
        help="Neo4j bolt URI, e.g. bolt://localhost:7687. Leave empty to skip upload.",
    )
    parser.add_argument("--neo4j-user", type=str, default="neo4j")
    parser.add_argument("--neo4j-password", type=str, default="")
    parser.add_argument(
        "--source-tag",
        type=str,
        default="ppocrlabel",
        help="Source tag stored on Neo4j nodes.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data_root = Path(args.data_root).expanduser().resolve()
    rec_gt_path = data_root / args.rec_gt
    char_dir = data_root / args.char_dir_name
    char_dir.mkdir(parents=True, exist_ok=True)

    all_records: List[CharRecord] = []
    for rel_path, text in load_rec_gt(rec_gt_path):
        img_path = resolve_image_path(rel_path, data_root, args.crop_dir_name)
        if not img_path.exists():
            print(f"[warn] missing image: {img_path}")
            continue
        all_records.extend(slice_line_to_chars(img_path, text, char_dir))

    csv_out_path = data_root / args.csv_out
    write_csv(all_records, csv_out_path)
    print(f"Wrote {len(all_records)} character rows to {csv_out_path}")

    if args.neo4j_uri:
        push_to_neo4j(
            all_records,
            args.neo4j_uri,
            args.neo4j_user,
            args.neo4j_password,
            args.source_tag,
        )
        print(f"Pushed {len(all_records)} records to Neo4j at {args.neo4j_uri}")


if __name__ == "__main__":
    main()
