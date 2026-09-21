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

If coordinates are missing or incomplete, PPOCRLabel falls back to editable line
boxes aligned to the image's ink bands in order; when the page cannot be aligned
reliably it returns one full-page box. Coordinate pairs are stripped from the
displayed text when possible.

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

The layout option is stored as `hunyuan_layout_mode` and validated against
`libs/hunyuan_ocr.HunyuanLayout` (single source of truth for the menu, the
dialog hints and the engine's accepted modes):

```text
page              整页识别（默认，不切栏）   默认值；整页一次，只用默认指令
model-auto        模型自判版式               整页一次，请模型自判单/双栏
horizontal-single 横排单栏
horizontal-two    横排双栏（左→右）          唯一会裁栏合并的横排模式
vertical-single   竖排单栏
vertical-two      竖排双栏（右→左）          唯一会裁栏合并的竖排模式
```

A stored value of `auto` (the retired “program finds the gutter” behaviour) is
normalized to `page` on startup. Recognised results are saved in the order the
model returned them; no geometric re-sorting is applied to HunyuanOCR or Qwen
output (`result_order_from_model`), only to PaddleOCR's two-column mode.

The line-by-line mode is stored as `hunyuan_line_mode`. When enabled, every
printed line is cropped and recognised on its own, so box and text match by
construction and footers such as the page number are read too. It costs about
twice the whole-page time (p010: 6.4s vs 10.2s) and is ignored for the two
columns layout modes.

The IPA mode is stored as `hunyuan_ipa_mode` (menu entry "音标页识别（国际音标）").
It swaps the base prompt for `IPA_PROMPT`: tone values must use the five-level
letters ˥ ˦ ˧ ˨ ˩ (never Zhuyin or pinyin), IPA letters must use the proper
characters, Chinese stays traditional, and isolated small print is kept. It is
independent of the layout mode and is recommended together with `--lines` for
dense dictionary pages.

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
