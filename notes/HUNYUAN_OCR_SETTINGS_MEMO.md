# PPOCRLabel HunyuanOCR Settings Memo

This memo records the exact HunyuanOCR settings and processing path currently
used inside PPOCRLabel.

## Model Files

PPOCRLabel loads HunyuanOCR from:

```text
tools/hunyuan/
```

Required files:

```text
tools/hunyuan/HunyuanOCR-Q8_0.gguf
tools/hunyuan/mmproj-HunyuanOCR-bf16.gguf
tools/hunyuan/runtime/**/llama-server.exe
```

The installer script pins the Hugging Face source to:

```text
ggml-org/HunyuanOCR-GGUF
revision 8e070c9ad79e4ca97a9b4daa2f1ce17e8759afb1
```

## Server Launch

`libs/hunyuan_ocr.py` starts a private local `llama-server.exe` on an ephemeral
localhost port. It does not reuse or stop unrelated servers.

Current launch arguments:

```text
-m tools/hunyuan/HunyuanOCR-Q8_0.gguf
--mmproj tools/hunyuan/mmproj-HunyuanOCR-bf16.gguf
--host 127.0.0.1
--port <ephemeral>
--alias hunyuanocr
-ngl 99
-c 16384
--parallel 1
-b 256
-ub 128
--flash-attn on
--temp 0
--jinja
```

The server health check waits up to 120 seconds. Recognition stops the server
when the worker finishes, when the dialog is cancelled, when HunyuanOCR mode is
turned off, and when PPOCRLabel closes.

## Request Format

Recognition calls the local server through the OpenAI-compatible endpoint:

```text
POST /v1/chat/completions
```

The request uses:

```text
model = hunyuanocr
temperature = 0
max_tokens = 12288
```

The message payload sends the image first as a base64 PNG `image_url`, followed
by the OCR prompt.

Current prompt:

```text
识别图片中的文字，按阅读顺序输出。每一行格式为：文字(x1,y1),(x2,y2)。
坐标使用输入图片像素，x1,y1是左上角，x2,y2是右下角。
只输出识别结果，不要解释。
```

## Image Preprocessing

PPOCRLabel opens each image with PIL and converts it to RGB.

Before sending it to HunyuanOCR:

- The long edge is limited to 1536 pixels.
- The resized width and height are rounded down to the model's 32-pixel grid.
- The resized page is encoded as PNG.

The original image size is kept so returned coordinates can be scaled back to
the annotation image.

## Output Parsing

If the model returns entries like:

```text
文字(x1,y1),(x2,y2)
```

PPOCRLabel parses each span into one rectangle:

```text
[[x1,y1], [x2,y1], [x2,y2], [x1,y2]]
```

Coordinates are validated against the resized input image, then scaled back to
the original image size.

If coordinate parsing is incomplete, PPOCRLabel falls back to one full-page box.
In that fallback path, coordinate pairs are stripped from the displayed text
when possible.

Recognition confidence is stored as `0.0` because HunyuanOCR does not return a
calibrated OCR confidence score.

## Length-Limit Retry

If a response ends with `finish_reason == "length"`, PPOCRLabel raises a
Hunyuan-specific length-limit exception and retries the same page.

Retry order:

1. Full page.
2. Two left/right crops.
3. Four quadrant crops.

Crop results are translated back to original image coordinates before saving.
If four crops still hit the output limit, only that page fails. Batch recognition
continues to later pages.

This retry path lives inside `HunyuanOCR.recognize()`, so it applies to both
current-page recognition and batch recognition.

## PPOCRLabel Integration

The UI option is stored as:

```text
use_hunyuan_gguf
```

When HunyuanOCR is enabled:

- PP-Structure is turned off.
- PaddleOCR models are unloaded.
- Automatic recognition passes `ocr=None` into `AutoDialog`.
- Current-page and batch recognition both call the same HunyuanOCR engine.

PaddleOCR remains available for ordinary box re-recognition when HunyuanOCR mode
is not the active automatic recognition mode.

## Saving And UI

HunyuanOCR worker results are saved on the GUI thread through the `pageReady`
signal. The worker waits until the GUI save completes before continuing.

After auto recognition finishes, PPOCRLabel writes both:

```text
Cache.cach
Label.txt
```

Auto-saved images are marked as checked so `Label.txt` is not left empty.

Long text in the recognition result list and auto-recognition dialog is shown
with word wrap enabled. Each list item also keeps the full text in its tooltip.

## Logs

Server logs are appended to:

```text
tools/hunyuan/logs/server.log
```

Each page or crop writes a response log:

```text
tools/hunyuan/logs/<image-stem>-result.json
tools/hunyuan/logs/<image-stem>-crop2-1-result.json
tools/hunyuan/logs/<image-stem>-crop4-1-result.json
```

The JSON log records the source path, resized input size, original size,
elapsed seconds, and raw model response.
