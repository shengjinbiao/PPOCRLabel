# PPOCRLabel Local OCR Development Memo

This memo records the local OCR and ancient-character annotation work in
PPOCRLabel, including HunyuanOCR and Qwen visual-model integration, layout
handling, usability changes, and model trade-offs.

## Goal

PPOCRLabel is being used to transcribe scanned pages and connect ancient
character image forms with their printed numbers and source explanations. The
recognition result is an editable starting point for page-by-page review. Many
ancient glyphs cannot be represented by ordinary OCR text, so preserving the
association between each image, its number, and nearby explanation is central.

## Local Runtime

HunyuanOCR runtime files are installed under:

```text
tools/hunyuan/
```

That directory is ignored by git because it contains large model/runtime files
and inference logs. The helper script is:

```text
scripts/setup_hunyuan_gguf.py
```

It downloads and verifies the pinned HunyuanOCR GGUF model, multimodal projector,
and llama.cpp Windows CUDA runtime.

## PPOCRLabel Integration

The new mode is exposed as a checkable automatic recognition option:

```text
Use HunyuanOCR (GGUF, full-page text)
```

The option is mutually exclusive with PP-Structure. When selected, automatic
recognition uses `libs/hunyuan_ocr.py`; PaddleOCR is still used for the existing
box re-recognition tools.

Qwen OCR is a second optional visual recognition engine. It uses the local
`Qwen-2-VL-7B-OCR` GGUF and multimodal projector. PPOCRLabel starts its bundled
`llama-server.exe` directly; LM Studio does not participate in recognition.
The files may remain in the LM Studio model folder because PPOCRLabel reads
them by path. Qwen shares the layout choices, worker, GUI-thread saving, and
page/crop handling used by HunyuanOCR.

The Qwen server runs as a hidden process on an ephemeral localhost port. It
starts when recognition begins and stops when the current-page or batch task
ends or is cancelled. A single-page run releases GPU memory after that page;
a batch keeps the model loaded across pages and releases it at the end.

## Layout And Review

The layout selector supports automatic detection, horizontal single-column,
horizontal two-column left-to-right, vertical single-column, and vertical
two-column right-to-left modes. The selection informs the visual-model prompt
and crop order. Horizontal two-column processing can recognize a page header
separately from the body columns.

Both visual engines use returned line coordinates when available. If a model
returns text without usable coordinates, the fallback splits it into editable
lines, but those boxes are approximate and may not align exactly with printed
lines. Review and adjustment are expected. The result pane and recognition
dialog wrap long lines to make proofreading easier.

## Traditional OCR And Visual Models

Traditional OCR (PaddleOCR / PP-Structure) detects text regions and recognizes
their characters. It is generally faster and lighter, returns useful boxes and
confidence scores, works well on clean modern print, and suits large-scale
processing. It can struggle with unusual historical layouts, small or damaged
type, rare characters, mixed scripts, and understanding relationships between
an illustration, its number, and surrounding prose.

Visual models (HunyuanOCR and Qwen2-VL OCR here) inspect a page or crop as an
image and use broader visual context. They can be more capable with rare forms
and contextual text, and can follow instructions about columns and reading
order. They require more GPU memory and usually run more slowly. Their output
can still contain errors or omissions; confidence is not calibrated, and boxes
may be missing or approximate. Current comparisons on this book are close,
with a slight user-reported preference for HunyuanOCR; Qwen has recognized some
characters such as “儘” in a comparison. No model is a universal winner, so
compare on representative pages and proofread the result.

For the ancient-character image workflow, OCR should assist with ordinary
printed text and locating related material, not be expected to identify most
oracle-bone or bronze-script glyphs. The practical target is to keep a glyph
crop associated with its printed number and source note, then verify that link
manually. Mapping numbers such as “127 殷甲文（A1：48，4）” to a specific corpus or
collection is a later data-linking task.

PaddleOCR model loading was made lazy so HunyuanOCR can be selected immediately
after startup without requiring `self.ocr` to exist. This fixed an early crash
where current-page auto recognition accessed the Paddle OCR object even when the
HunyuanOCR mode was active.

## GUI Thread And Saving Fixes

HunyuanOCR recognition runs through the existing `AutoDialog` worker thread, but
Qt-backed save operations are routed back to the GUI thread with a `pageReady`
signal. The worker waits for the GUI save to finish before moving to the next
page.

Automatic saves now mark the image as checked before writing `Label.txt`.
Previously, HunyuanOCR results could appear on screen and in cache while
`Label.txt` remained empty because `savePPlabel()` writes only checked files.

Window close now calls `saveLabelFile(mode="Auto")` in the close path so it does
not show a manual-save information dialog while Qt is shutting down.

## Result Handling

HunyuanOCR output is parsed in two modes:

- If the model returns `text(x1,y1),(x2,y2)` spans, PPOCRLabel creates one box per
  coordinate span and maps coordinates back to the original image size.
- If coordinate parsing is incomplete, PPOCRLabel falls back to one full-page box
  and strips coordinate pairs from the displayed text where possible.

The right-side result list and the auto-recognition dialog list now enable word
wrap, so long HunyuanOCR text does not display as one horizontal line.

Scores are stored as `0.0` because the GGUF model does not provide calibrated OCR
confidence.

## Length Limit Handling

The llama.cpp server currently starts with:

```text
-c 16384
```

Recognition requests use:

```text
max_tokens = 12288
```

If a full-page HunyuanOCR response reaches the model output limit, recognition
does not immediately fail the page. The retry path is:

1. Try the full page.
2. If output reaches the length limit, retry as two left/right crops.
3. If either half still reaches the limit, retry as four quadrants.
4. Translate crop coordinates back to original image coordinates and merge the
   successful results.
5. If four crops still hit the limit, fail only that page.

This logic is implemented inside `HunyuanOCR.recognize()`, so both current-page
recognition and batch recognition use it. Batch recognition catches per-page
HunyuanOCR exceptions, records the failed page, advances the progress bar, and
continues with later pages.

## Validation Performed

The manual smoke script is:

```text
test/hunyuan_gui_smoke.py
```

Validation covered:

- Cold startup with HunyuanOCR selected before PaddleOCR models are loaded.
- Current-page HunyuanOCR recognition with a mocked result.
- Batch behavior where one page fails and the next page still saves.
- Simulated length-limit retry where full-page recognition fails and two crops
  save successfully.
- Real GGUF/llama.cpp recognition on a scanned `说文解字六书疏证` page.

Observed real-model behavior on the tested page: the model often returns useful
full-page text but may not return complete coordinates. The fallback full-page
box path is therefore still necessary.

## Operational Notes

Existing PPOCRLabel windows keep their already-started `llama-server` process and
parameters. After changing context or token limits, close and reopen PPOCRLabel
to use the new values.

If a `llama-server.exe` remains running, inspect its parent process before
stopping it. During development, one running instance belonged to an active
`pythonw.exe` PPOCRLabel window rather than the smoke test.
