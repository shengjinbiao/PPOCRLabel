"""Run baidu/Unlimited-OCR on rendered PDF page images.

This script intentionally sets Hugging Face cache variables before importing
transformers so model files stay on D:.
"""
import argparse
import os
import time
from pathlib import Path

os.environ.setdefault("HF_HOME", r"D:\hf_cache")
os.environ.setdefault("HUGGINGFACE_HUB_CACHE", r"D:\hf_cache\hub")

import torch
from transformers import AutoModel, AutoTokenizer


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--images",
        nargs="+",
        required=True,
        help="Rendered page images to OCR.",
    )
    parser.add_argument(
        "--out",
        default=r"D:\PPOCRLabel\tmp\unlimited_ocr_output",
        help="Output directory.",
    )
    parser.add_argument("--model", default="baidu/Unlimited-OCR")
    parser.add_argument("--base-size", type=int, default=1024)
    parser.add_argument("--image-size", type=int, default=640)
    parser.add_argument("--max-length", type=int, default=32768)
    parser.add_argument("--crop-mode", action="store_true")
    parser.add_argument(
        "--prompt",
        default=(
            "<image>OCR this page exactly. Preserve the original Chinese character forms. "
            "Do not convert simplified/traditional characters. Do not normalize variants. "
            "Do not guess missing or uncertain characters; use □ for each uncertain character. "
            "Keep the original vertical text reading order."
        ),
    )
    return parser.parse_args()


def main():
    args = parse_args()
    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)

    print(f"HF_HOME={os.environ.get('HF_HOME')}", flush=True)
    print(f"HUGGINGFACE_HUB_CACHE={os.environ.get('HUGGINGFACE_HUB_CACHE')}", flush=True)
    print(f"torch={torch.__version__}, cuda={torch.cuda.is_available()}", flush=True)
    if torch.cuda.is_available():
        print(f"gpu={torch.cuda.get_device_name(0)}", flush=True)

    print(f"Loading tokenizer: {args.model}", flush=True)
    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)

    print(f"Loading model: {args.model}", flush=True)
    started = time.time()
    model = AutoModel.from_pretrained(
        args.model,
        trust_remote_code=True,
        use_safetensors=True,
        torch_dtype=torch.bfloat16,
    )
    model = model.eval().cuda()
    print(f"Model loaded in {time.time() - started:.1f}s", flush=True)

    for image in args.images:
        image_path = Path(image)
        page_out = out_root / image_path.stem
        page_out.mkdir(parents=True, exist_ok=True)
        print(f"\n=== OCR {image_path} ===", flush=True)
        started = time.time()
        model.infer(
            tokenizer,
            prompt=args.prompt,
            image_file=str(image_path),
            output_path=str(page_out),
            base_size=args.base_size,
            image_size=args.image_size,
            crop_mode=args.crop_mode,
            max_length=args.max_length,
            no_repeat_ngram_size=35,
            ngram_window=128,
            save_results=True,
        )
        print(f"Page done in {time.time() - started:.1f}s", flush=True)

        result_files = sorted(
            [p for p in page_out.rglob("*") if p.suffix.lower() in {".txt", ".json", ".md"}]
        )
        if not result_files:
            print("No text/json/md result files produced.", flush=True)
        for result in result_files:
            text = result.read_text("utf-8", errors="replace")
            print(f"\n--- {result.name} ({len(text)} chars) ---", flush=True)
            print(text[:2000], flush=True)

    print("\nDONE", flush=True)


if __name__ == "__main__":
    main()
