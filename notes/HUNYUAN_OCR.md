# HunyuanOCR GGUF in PPOCRLabel

This integration runs HunyuanOCR through a local `llama-server.exe` that is
started on demand by PPOCRLabel. LM Studio is not required.

## Files

The runtime and model files live under:

```text
tools/hunyuan/
```

This directory is ignored by git because it contains large downloaded binaries,
model weights, and inference logs.

To install or repair the local files, run:

```powershell
D:\anaconda3\envs\ppocrlabel\python.exe scripts\setup_hunyuan_gguf.py
```

The script downloads the pinned GGUF model, multimodal projector, and Windows
CUDA llama.cpp runtime, then verifies their SHA-256 hashes.

## Use

In PPOCRLabel, open the auto recognition menu and choose:

```text
Use HunyuanOCR (GGUF, full-page text)
```

Then run automatic recognition for the current page or for the pending pages.
PPOCRLabel starts the local llama.cpp server only while recognition is running
and stops it afterwards.

Current-page recognition and batch recognition use the same HunyuanOCR path. If
a page reaches the model output limit, PPOCRLabel retries that page as two
left/right crops. If either half still reaches the limit, it retries as four
quadrants. Successful crop results are merged back into original image
coordinates before saving. If four crops still reach the limit, that page is
reported as failed and batch recognition continues with the next page.

## Current behavior

When the model returns text in the form `text(x1,y1),(x2,y2)`, PPOCRLabel parses
the coordinates and saves one annotation box per returned text span. If the
model does not return complete coordinates, PPOCRLabel falls back to one editable
full-page text box and removes coordinate pairs from the displayed text where it
can. The confidence score is stored as `0` because the model does not provide
calibrated OCR confidence.

The image sent to the model is resized to a maximum long edge of 1536 pixels to
keep memory use stable on 8 GB GPUs.

PaddleOCR remains available for ordinary box re-recognition and line-level OCR.
Switching HunyuanOCR off returns automatic recognition to PaddleOCR or
PP-Structure, depending on the selected options.
