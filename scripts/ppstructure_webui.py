"""
Simple Gradio web UI for two workflows:
1) Page/layout: preview an image, view/edit recognized text, save to .txt
2) Char-level proofing (optional): step through single-character slices from
   a CSV (e.g., char_gt.csv) and edit the corresponding text.

Usage:
  python scripts/ppstructure_webui.py --input_dir D:\\path\\to\\images \\
      --output_dir ./ppstructure_edits \\
      --layout_model_dir C:\\Users\\you\\.paddlex\\official_models\\PP-DocLayout_plus-L

Enable char-level tab (CSV must have img_path, char columns):
  python scripts/ppstructure_webui.py --input_dir D:\\test --char_csv test\\char_gt.csv
"""
from __future__ import annotations

import argparse
import csv
import shutil
from pathlib import Path
from typing import Dict, List, Tuple

import gradio as gr
import numpy as np
from paddleocr import PPStructureV3


def parse_args():
    parser = argparse.ArgumentParser(description="PP-Structure web UI for batch edit.")
    parser.add_argument("--input_dir", required=True, help="Folder with images.")
    parser.add_argument(
        "--layout_model_dir",
        default=r"C:\Users\sheng\.paddlex\official_models\PP-DocLayout_plus-L",
        help="PP-Structure layout detection model directory.",
    )
    parser.add_argument(
        "--output_dir",
        default="ppstructure_edits",
        help="Directory to save edited text files.",
    )
    parser.add_argument(
        "--char_csv",
        type=str,
        default="",
        help="Optional: char-level CSV (e.g., char_gt.csv) for per-character proofing; must have img_path/char columns.",
    )
    parser.add_argument(
        "--char_img_root",
        type=str,
        default="",
        help="Optional: base dir for char images if CSV img_path is relative; leave empty to use CSV as-is.",
    )
    parser.add_argument(
        "--approved_dir",
        type=str,
        default="",
        help="Optional: copy saved char slices into this directory (curated set).",
    )
    parser.add_argument(
        "--approved_csv",
        type=str,
        default="",
        help="Optional: append saved char-text pairs into this CSV; default is approved_dir/approved.csv if approved_dir set.",
    )
    return parser.parse_args()


def build_engine(layout_model_dir: str) -> PPStructureV3:
    return PPStructureV3(
        layout_detection_model_dir=layout_model_dir,
        use_region_detection=True,
    )


def collect_images(input_dir: Path) -> List[Path]:
    exts = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
    return sorted([p for p in input_dir.iterdir() if p.suffix.lower() in exts])


def _reorder_blocks_by_layout(blocks: List[Tuple[str, List[float]]], width: float):
    if not blocks or width is None or width <= 0:
        return blocks
    rects = []
    for idx, (_, bbox) in enumerate(blocks):
        if not bbox or len(bbox) != 4:
            continue
        x0, y0, x1, y1 = bbox
        rects.append({"idx": idx, "x0": x0, "x1": x1, "y0": y0, "y1": y1})
    if not rects:
        return blocks
    widths = [r["x1"] - r["x0"] for r in rects]
    median_width = float(np.median(widths)) if widths else 0.0
    col_gap = max(width * 0.02, median_width * 0.3, 12.0)
    rects.sort(key=lambda r: (r["x0"], r["y0"]))
    columns = []
    for r in rects:
        placed = False
        for col in columns:
            if r["x0"] <= col["max_x"] + col_gap:
                col["items"].append(r)
                col["max_x"] = max(col["max_x"], r["x1"])
                placed = True
                break
        if not placed:
            columns.append({"items": [r], "max_x": r["x1"]})
    columns.sort(key=lambda c: c["items"][0]["x0"])
    ordered_indices = []
    for col in columns:
        col["items"].sort(key=lambda r: (r["y0"], r["x0"]))
        ordered_indices.extend(r["idx"] for r in col["items"])
    return [blocks[i] for i in ordered_indices]


def extract_text_blocks(entry: Dict) -> Tuple[str, List[List[float]]]:
    parsing_list = entry.get("parsing_res_list") or []
    blocks = []
    for reg in parsing_list:
        if isinstance(reg, dict):
            content = reg.get("content") or ""
            bbox = reg.get("bbox") or reg.get("coordinate") or []
        else:
            content = getattr(reg, "content", "") or ""
            bbox = getattr(reg, "bbox", None) or getattr(reg, "coordinate", [])
        if content:
            blocks.append((content, bbox))
    if not blocks:
        ocr = entry.get("overall_ocr_res") or {}
        texts = ocr.get("rec_texts") or []
        polys = ocr.get("rec_polys") or []
        for t, poly in zip(texts, polys):
            blocks.append((t, poly.tolist() if hasattr(poly, "tolist") else poly))

    width = None
    try:
        img_arr = entry.get("doc_preprocessor_res", {}).get("output_img")
        if img_arr is not None:
            width = float(img_arr.shape[1])
    except Exception:
        width = None

    normalized = []
    for text, bbox in blocks:
        if hasattr(bbox, "tolist"):
            bbox = bbox.tolist()
        norm = None
        if isinstance(bbox, (list, tuple)):
            if len(bbox) == 4 and all(isinstance(v, (int, float)) for v in bbox):
                norm = [float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])]
            elif len(bbox) >= 4 and all(isinstance(v, (list, tuple)) and len(v) >= 2 for v in bbox):
                try:
                    xs = [float(pt[0]) for pt in bbox]
                    ys = [float(pt[1]) for pt in bbox]
                    norm = [min(xs), min(ys), max(xs), max(ys)]
                except Exception:
                    norm = None
        if norm is None:
            norm = bbox
        normalized.append((text, norm))

    normalized = _reorder_blocks_by_layout(normalized, width)
    joined_text = "\n".join(t for t, _ in normalized)
    bboxes = [b for _, b in normalized]
    return joined_text, bboxes


class AppState:
    def __init__(self, engine: PPStructureV3, images: List[Path], output_dir: Path):
        self.engine = engine
        self.images = images
        self.output_dir = output_dir
        self.cache: Dict[str, str] = {}  # image_name -> text
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def load_image(self, image_name: str):
        img_path = next((p for p in self.images if p.name == image_name), None)
        if img_path is None:
            return None, ""
        if image_name in self.cache:
            return str(img_path), self.cache[image_name]
        res = self.engine.predict(str(img_path))
        if not res:
            text = ""
        else:
            entry = res[0] if isinstance(res, (list, tuple)) else res
            text, _ = extract_text_blocks(entry)
        self.cache[image_name] = text
        return str(img_path), text

    def save_text(self, image_name: str, text: str):
        if not image_name:
            return "No image selected."
        self.cache[image_name] = text or ""
        out_path = self.output_dir / f"{Path(image_name).stem}.txt"
        out_path.write_text(self.cache[image_name], encoding="utf-8")
        return f"Saved to {out_path}"


class CharState:
    def __init__(
        self,
        csv_path: Path,
        img_root: Path | None,
        approved_dir: Path | None = None,
        approved_csv: Path | None = None,
    ):
        self.csv_path = csv_path
        self.img_root = img_root
        self.approved_dir = approved_dir
        self.approved_csv = approved_csv
        self.records: List[Dict[str, str]] = []
        self._load()
        if self.approved_dir:
            self.approved_dir.mkdir(parents=True, exist_ok=True)
            if self.approved_csv is None:
                self.approved_csv = self.approved_dir / "approved.csv"

    def _resolve_img(self, p: str) -> str:
        path = Path(p)
        if self.img_root and not path.is_absolute():
            path = self.img_root / path
        return str(path.resolve())

    def _load(self):
        with self.csv_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                img_path = row.get("img_path") or row.get("path") or ""
                char = row.get("char") or row.get("text") or ""
                line_file = row.get("line_file") or ""
                order = row.get("order") or ""
                if not img_path:
                    continue
                self.records.append(
                    {
                        "img_path": self._resolve_img(img_path),
                        "char": char,
                        "line_file": line_file,
                        "order": order,
                    }
                )
        if not self.records:
            raise ValueError(f"No records found in {self.csv_path}")

    def get(self, idx: int) -> Dict[str, str]:
        if idx < 0 or idx >= len(self.records):
            return {}
        return self.records[idx]

    def save_char(self, idx: int, text: str) -> str:
        if idx < 0 or idx >= len(self.records):
            return "Index out of range."
        self.records[idx]["char"] = text or ""
        fieldnames = ["img_path", "char", "line_file", "order"]
        with self.csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for rec in self.records:
                writer.writerow(
                    {
                        "img_path": rec.get("img_path", ""),
                        "char": rec.get("char", ""),
                        "line_file": rec.get("line_file", ""),
                        "order": rec.get("order", ""),
                    }
                )

        msg = f"Saved char to {self.csv_path} (row {idx + 1}/{len(self.records)})"

        # Optional curated export: copy image + append row only when user saves
        if self.approved_dir or self.approved_csv:
            if text:
                src = Path(self.records[idx]["img_path"])
                dst = src
                if self.approved_dir:
                    self.approved_dir.mkdir(parents=True, exist_ok=True)
                    dst = self.approved_dir / src.name
                    shutil.copyfile(src, dst)

                out_csv = self.approved_csv or (self.approved_dir / "approved.csv")
                need_header = not out_csv.exists()
                with out_csv.open("a", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    if need_header:
                        writer.writeheader()
                    writer.writerow(
                        {
                            "img_path": str(dst),
                            "char": text,
                            "line_file": self.records[idx].get("line_file", ""),
                            "order": self.records[idx].get("order", ""),
                        }
                    )
                msg += f"; appended curated row to {out_csv}"
            else:
                msg += "; skipped curated export (empty text)"

        return msg


def main():
    args = parse_args()
    input_dir = Path(args.input_dir)
    if not input_dir.is_dir():
        raise ValueError(f"Input dir not found: {input_dir}")
    images = collect_images(input_dir)
    if not images:
        raise ValueError(f"No images found in {input_dir}")
    engine = build_engine(args.layout_model_dir)
    state = AppState(engine, images, Path(args.output_dir))
    char_state = None
    if args.char_csv:
        csv_path = Path(args.char_csv)
        img_root = Path(args.char_img_root) if args.char_img_root else None
        approved_dir = Path(args.approved_dir) if args.approved_dir else None
        approved_csv = Path(args.approved_csv) if args.approved_csv else None
        char_state = CharState(csv_path, img_root, approved_dir, approved_csv)
        print(f"[char] loaded {len(char_state.records)} records from {csv_path}")

    img_choices = [p.name for p in images]

    with gr.Blocks() as demo:
        gr.Markdown("## PP-Structure 校对 / 甲骨文字形逐字校对")

        with gr.Tab("版面/整页"):
            with gr.Row():
                with gr.Column(scale=1, min_width=240):
                    image_dropdown = gr.Dropdown(
                        choices=img_choices, value=img_choices[0], label="图片"
                    )
                    status = gr.Markdown("")
                with gr.Column(scale=3):
                    image_view = gr.Image(label="预览", type="filepath")
                with gr.Column(scale=3):
                    text_box = gr.Textbox(
                        label="识别文本（可编辑）", lines=20, interactive=True
                    )
                    save_btn = gr.Button("保存")

            def on_select(img_name):
                path, text = state.load_image(img_name)
                return path, text, f"Loaded {img_name}"

            def on_save(img_name, text):
                msg = state.save_text(img_name, text)
                return msg

            image_dropdown.change(
                on_select, inputs=image_dropdown, outputs=[image_view, text_box, status]
            )
            save_btn.click(on_save, inputs=[image_dropdown, text_box], outputs=status)

            init_path, init_text = state.load_image(img_choices[0])
            image_view.value = init_path
            text_box.value = init_text

        if char_state:
            with gr.Tab("逐字切片校对"):
                total = len(char_state.records)
                with gr.Row():
                    with gr.Column(scale=1, min_width=220):
                        idx_slider = gr.Slider(
                            minimum=0,
                            maximum=total - 1,
                            step=1,
                            value=0,
                            label=f"索引 (0 - {total-1})",
                        )
                        char_status = gr.Markdown("")
                    with gr.Column(scale=3):
                        char_img = gr.Image(label="字形切片", type="filepath")
                    with gr.Column(scale=2):
                        char_text = gr.Textbox(
                            label="对应现代文字（可编辑）", lines=4, interactive=True
                        )
                        char_save_btn = gr.Button("保存该字")

                def on_char_change(idx):
                    rec = char_state.get(int(idx))
                    if not rec:
                        return None, "", "Index out of range"
                    return (
                        rec["img_path"],
                        rec.get("char", ""),
                        f"第 {int(idx)+1}/{total} 行 | {rec.get('line_file','')} #{rec.get('order','')}",
                    )

                def on_char_save(idx, text):
                    msg = char_state.save_char(int(idx), text)
                    return msg

                idx_slider.change(
                    on_char_change,
                    inputs=idx_slider,
                    outputs=[char_img, char_text, char_status],
                )
                char_save_btn.click(
                    on_char_save, inputs=[idx_slider, char_text], outputs=char_status
                )

                init_img, init_char, init_status = on_char_change(0)
                char_img.value = init_img
                char_text.value = init_char
                char_status.value = init_status

    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False,
        allowed_paths=[str(input_dir.resolve())],
    )


if __name__ == "__main__":
    main()
