r"""
Split PPOCRLabel line/word boxes into per-character boxes.

This is a geometry-based helper. It reads Label.txt/Cache.cach style files and
writes a new label file where each multi-character annotation is divided into
one quadrilateral per character.

Typical usage:
    python scripts/split_label_to_char_boxes.py --data-root D:\your_image_folder

Review CharLabel.txt in PPOCRLabel first. Use --in-place only after backup.
"""
from __future__ import annotations

import argparse
import json
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

Point = Tuple[float, float]
Quad = List[Point]


def order_quad(points: Sequence[Sequence[float]]) -> Quad:
    if len(points) != 4:
        raise ValueError("expected exactly 4 points")
    pts = [(float(p[0]), float(p[1])) for p in points]

    sums = [x + y for x, y in pts]
    diffs = [x - y for x, y in pts]
    tl = pts[sums.index(min(sums))]
    br = pts[sums.index(max(sums))]
    tr = pts[diffs.index(max(diffs))]
    bl = pts[diffs.index(min(diffs))]
    return [tl, tr, br, bl]


def lerp(a: Point, b: Point, t: float) -> Point:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def quad_width_height(quad: Quad) -> Tuple[float, float]:
    tl, tr, br, bl = quad
    width = ((tr[0] - tl[0]) ** 2 + (tr[1] - tl[1]) ** 2) ** 0.5
    width += ((br[0] - bl[0]) ** 2 + (br[1] - bl[1]) ** 2) ** 0.5
    height = ((bl[0] - tl[0]) ** 2 + (bl[1] - tl[1]) ** 2) ** 0.5
    height += ((br[0] - tr[0]) ** 2 + (br[1] - tr[1]) ** 2) ** 0.5
    return width / 2.0, height / 2.0


def split_quad(quad: Quad, count: int, direction: str) -> Iterable[Quad]:
    tl, tr, br, bl = quad
    if count <= 1:
        yield quad
        return

    if direction == "vertical":
        for idx in range(count):
            t0 = idx / count
            t1 = (idx + 1) / count
            left_top = lerp(tl, bl, t0)
            right_top = lerp(tr, br, t0)
            right_bottom = lerp(tr, br, t1)
            left_bottom = lerp(tl, bl, t1)
            yield [left_top, right_top, right_bottom, left_bottom]
    else:
        for idx in range(count):
            t0 = idx / count
            t1 = (idx + 1) / count
            left_top = lerp(tl, tr, t0)
            right_top = lerp(tl, tr, t1)
            right_bottom = lerp(bl, br, t1)
            left_bottom = lerp(bl, br, t0)
            yield [left_top, right_top, right_bottom, left_bottom]


def clean_chars(text: str, drop_whitespace: bool) -> List[str]:
    if drop_whitespace:
        return [ch for ch in text if not ch.isspace()]
    return list(text)


def format_points(quad: Quad) -> List[List[int]]:
    return [[int(round(x)), int(round(y))] for x, y in quad]


def split_label(
    label: Dict[str, Any],
    min_chars: int,
    drop_whitespace: bool,
    force_direction: str,
) -> List[Dict[str, Any]]:
    text = str(label.get("transcription", ""))
    chars = clean_chars(text, drop_whitespace)
    points = label.get("points") or []

    if len(chars) < min_chars or len(points) != 4:
        return [label]

    quad = order_quad(points)
    width, height = quad_width_height(quad)
    direction = force_direction
    if direction == "auto":
        direction = "vertical" if height > width * 1.25 else "horizontal"

    out: List[Dict[str, Any]] = []
    for ch, ch_quad in zip(chars, split_quad(quad, len(chars), direction)):
        item = dict(label)
        item["transcription"] = ch
        item["points"] = format_points(ch_quad)
        item["instance_id"] = str(uuid.uuid4())
        history = item.get("history")
        if isinstance(history, list):
            item["history"] = list(history)
        out.append(item)
    return out


def load_ppocr_label(path: Path) -> List[Tuple[str, List[Dict[str, Any]]]]:
    rows: List[Tuple[str, List[Dict[str, Any]]]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, raw in enumerate(f, 1):
            line = raw.rstrip("\r\n")
            if not line:
                continue
            if "\t" not in line:
                raise ValueError(f"{path}:{line_no} has no tab separator")
            image_name, payload = line.split("\t", 1)
            rows.append((image_name, json.loads(payload)))
    return rows


def write_ppocr_label(path: Path, rows: Sequence[Tuple[str, List[Dict[str, Any]]]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for image_name, labels in rows:
            f.write(image_name)
            f.write("\t")
            f.write(json.dumps(labels, ensure_ascii=False))
            f.write("\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Split PPOCRLabel Label.txt boxes into per-character boxes."
    )
    parser.add_argument("--data-root", required=True, help="Folder containing Label.txt.")
    parser.add_argument("--source", default="Label.txt", help="Source label file name.")
    parser.add_argument(
        "--output",
        default="CharLabel.txt",
        help="Output label file name. Ignored when --in-place is used.",
    )
    parser.add_argument(
        "--direction",
        choices=["auto", "horizontal", "vertical"],
        default="auto",
        help="Split direction. Auto treats tall boxes as vertical text.",
    )
    parser.add_argument("--min-chars", type=int, default=2)
    parser.add_argument(
        "--keep-whitespace",
        action="store_true",
        help="Keep whitespace characters as split targets.",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Overwrite source label file after creating a .bak copy.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data_root = Path(args.data_root).expanduser().resolve()
    source = data_root / args.source
    output = source if args.in_place else data_root / args.output

    rows = load_ppocr_label(source)
    converted: List[Tuple[str, List[Dict[str, Any]]]] = []
    old_count = 0
    new_count = 0
    for image_name, labels in rows:
        out_labels: List[Dict[str, Any]] = []
        for label in labels:
            old_count += 1
            pieces = split_label(
                label,
                min_chars=args.min_chars,
                drop_whitespace=not args.keep_whitespace,
                force_direction=args.direction,
            )
            new_count += len(pieces)
            out_labels.extend(pieces)
        converted.append((image_name, out_labels))

    if args.in_place:
        backup = source.with_suffix(source.suffix + ".bak")
        shutil.copy2(source, backup)
        print(f"Backup written: {backup}")

    write_ppocr_label(output, converted)
    print(f"Wrote {new_count} labels from {old_count} source labels to {output}")


if __name__ == "__main__":
    main()
