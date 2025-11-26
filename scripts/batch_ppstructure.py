import argparse
import os
from pathlib import Path

from paddleocr import PPStructureV3


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run PP-StructureV3 on all images in a directory and dump blocks."
    )
    parser.add_argument(
        "--input_dir",
        type=str,
        required=True,
        help="Folder containing images to process.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="ppstructure_blocks.txt",
        help="Path to save the extracted blocks.",
    )
    parser.add_argument(
        "--layout_model_dir",
        type=str,
        default=r"C:\Users\sheng\.paddlex\official_models\PP-DocLayout_plus-L",
        help="PP-Structure layout detection model directory.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    input_dir = Path(args.input_dir)
    if not input_dir.is_dir():
        raise ValueError(f"Input dir does not exist: {input_dir}")

    engine = PPStructureV3(
        layout_detection_model_dir=args.layout_model_dir,
        use_region_detection=True,
    )

    image_exts = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
    images = sorted(
        [p for p in input_dir.iterdir() if p.suffix.lower() in image_exts]
    )
    if not images:
        raise ValueError(f"No images found in {input_dir}")

    lines = []
    stats = []
    for img_path in images:
        res = engine.predict(str(img_path))
        if not res:
            stats.append(f"{img_path.name}: 0 blocks (no result)")
            continue
        entry = res[0] if isinstance(res, (list, tuple)) else res
        parsing_list = entry.get("parsing_res_list") or []
        lines.append(f"{img_path.name}")
        stats.append(f"{img_path.name}: {len(parsing_list)} blocks")
        if parsing_list:
            for idx, reg in enumerate(parsing_list):
                if isinstance(reg, dict):
                    label = reg.get("label") or ""
                    region_label = reg.get("region_label") or reg.get("region") or ""
                    bbox = reg.get("bbox") or reg.get("coordinate") or []
                    content = reg.get("content") or ""
                else:
                    label = getattr(reg, "label", "") or ""
                    region_label = (
                        getattr(reg, "region_label", "")
                        or getattr(reg, "region", "")
                        or ""
                    )
                    bbox = getattr(reg, "bbox", None) or getattr(reg, "coordinate", [])
                    content = getattr(reg, "content", "") or ""
                lines.append("#################")
                lines.append(f"index:  {idx}")
                lines.append(f"label:  {label}")
                lines.append(f"region_label:   {region_label}")
                lines.append(f"bbox:   {bbox}")
                lines.append(f"content:        {content}")
                lines.append("#################,")
                lines.append("")  # blank line between blocks
        else:
            # fallback to overall_ocr_res if parsing list is empty
            ocr = entry.get("overall_ocr_res") or {}
            rec_texts = ocr.get("rec_texts") or []
            rec_polys = ocr.get("rec_polys") or []
            for idx, (text, poly) in enumerate(zip(rec_texts, rec_polys)):
                lines.append("#################")
                lines.append(f"index:  {idx}")
                lines.append("label:  text")
                lines.append("region_label:   ocr")
                lines.append(f"bbox:   {poly.tolist() if hasattr(poly, 'tolist') else poly}")
                lines.append(f"content:        {text}")
                lines.append("#################,")
                lines.append("")
            if not rec_texts:
                lines.append("(no parsing_res_list returned)")
        lines.append("")  # blank line between images

    output_path = Path(args.output)
    output_path.write_text("\n".join(lines), encoding="utf-8-sig")
    print(f"Saved blocks to {output_path}")
    print("Summary:")
    print("\n".join(stats))


if __name__ == "__main__":
    main()
