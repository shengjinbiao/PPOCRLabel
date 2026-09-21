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

The layout selector offers, in order: whole-page default (`page`), model-decides
(`model-auto`), horizontal single-column, horizontal two-column left-to-right,
vertical single-column, and vertical two-column right-to-left. `page` is the
default: one request for the whole page with the plain OCR prompt only.
`model-auto` is also one whole-page request, but the prompt asks the model to
judge the layout itself. Only the two explicit two-column modes crop the page,
and they do so behind a strict gutter test (35%-65% of the width, ink on both
sides); when no real gutter is found they read the whole page once instead.
The retired `auto` mode used to cut the page at a raw ink minimum, which could
pick a blank margin and scramble the order.

Neither visual engine's result is re-sorted geometrically before saving. This is
intentional: the model's own reading order (or the requested column merge order)
is authoritative, and `PPOCRLabel.sort_ocr_result_entries` remains available to
the PaddleOCR two-column mode only.

Both visual engines use returned line coordinates when available. If a model
returns text without usable coordinates, the fallback splits it into editable
lines whose geometry comes from the page's ink bands and whose text is cut to
**each band's capacity** (its measured ink width), so every printed line gets
text and none is skipped. Those boxes are approximate and may not align exactly
with printed lines. When the page cannot be aligned with confidence the fallback
returns a single full-page box instead, so a guessed box layout can never
reorder the text. Replies that are refusals or echoes of the prompt are
discarded rather than saved as page text.

For exact line-by-line alignment there is a separate **line mode**
(`hunyuan_line_mode`, a checkable menu entry): every printed line is cropped on
its own and sent to the model, so box and text correspond by construction. It
costs about twice the whole-page time (p010: 6.4s vs 10.2s) and it reads
footers such as the page number that a whole-page read tends to drop. Thin
strips are padded onto a white canvas first, because a bare 20-30px strip is
often refused as "too blurry". Line mode writes one `-lines-result.json`
summary per page instead of one log per line.

The result pane and recognition dialog wrap long lines to make proofreading
easier.

### Dialect dictionaries and IPA

A second prompt switch, **IPA mode** (`hunyuan_ipa_mode`, menu entry "音标页识别",
CLI `--ipa`), replaces the base prompt with `IPA_PROMPT`: tone values must be
written with the five-level letters ˥ ˦ ˧ ˨ ˩ (never Zhuyin or pinyin), IPA
letters must use the proper characters (ŋ ɕ ʑ ʨ ʦ ʰ ʂ ʐ ɿ ʅ ɚ ɛ ɔ …), Chinese
characters stay traditional, and isolated small print such as page numbers is
kept.

Measured on 《现代汉语方言大词典》第1卷 p016 (tone table plus IPA examples):

| | default prompt | IPA prompt |
|---|---|---|
| Zhuyin substitutes (ㄧㄟㄢ…) | printed, or `[1]`/`[4]` | **0** |
| five-level tone letters | **0** | **95** |
| rime suffixes | `ar / yr / uar` | **`ər / iər / uər / ār / iār`** |
| 陰平 bracket | `[1]` | `[˧]` (should be `[˦˦]`) |
| example tone | `fən.ʃv pi.ʃ` | `fən˥˥ pi˥˥` (should be `˨˩˧`) |

The character *inventory* is fixed by the prompt; the tone **values** are not
yet reliable — the model produces well-formed but wrong contours. Constraining
them (finite legal contour shapes, plus consistency inside one dialect point) is
the next step before this can be trusted for dialect data.

Dense dictionary pages also hit the `max_tokens` limit in whole-page mode (p016 did,
twice, triggering the 2-crop retry); line mode did not. Prefer `--lines` here.

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
- If coordinates are missing or incomplete (the usual case: both engines returned
  **zero** coordinate pairs on all five 温州经籍志 test pages), the fallback builds
  editable line boxes whose geometry comes from the image and whose text is cut
  to each band's capacity. See "Box Geometry From The Image" below.

Text cleanup before saving:

- `_strip_meta_prefix()` removes a leading "图片中的文本内容是：" style preamble.
- `_clean_line_text()` removes LaTeX-ish wrappers the model puts around short
  lines; a printed page number `·630·` came back as `$$ \therefore 630 \cdot $$`.
- `strip_coord_template()` removes the prompt's literal coordinate placeholders.
  The model answers with them in two shapes: a pure echo ("文字(x1,y1),(x2,y2)"),
  which is dropped entirely, and a real line with the template appended
  ("临渊羡鱼,(x1,y1),(x2,y2)"), where only the placeholders are stripped so no
  page text is lost. Repeated punctuation left behind is collapsed.
- `looks_like_model_meta()` drops refusals ("图片中的文字过于模糊…") and echoes of
  our own prompt instead of saving them as page text.

The right-side result list and the auto-recognition dialog list enable word wrap.
Both also size each row from the wrapped text height (`_fit_label_item_height()`)
and use `ElideNone`, because a merged two-line recognition result is one long box
text that used to be clipped at the row height.

Scores are stored as `0.0` because the GGUF model does not provide calibrated OCR
confidence.

## Box Geometry From The Image

When the model returns no coordinates, boxes are derived from the page image:

- `_ink_bands()` projects ink onto the reading axis and groups contiguous ink
  into bands; one band is one printed line (small gaps up to 3 px are merged).
  Bands shorter than `BAND_MIN_HEIGHT` (8 px) are scan noise or binding shadow,
  and a band thinner than `RULE_MAX_HEIGHT` (14 px) that spans most of the body
  width is a printed rule or the scan border — neither becomes an annotation box.
- `_text_bands()` then decides each band's extent from ink **position only**:
  page-level column coverage defines the *body block* (runs of columns present in
  >= `BODY_COVERAGE_FRAC`, 35%, of bands) and the *barriers* (blank column ranges
  at least `BARRIER_MIN_WIDTH`, 12 px, wide, i.e. margins and gutters). A band's
  ink is split at the barriers into groups, and a group is dropped **only when it
  lies entirely outside the body block** (expanded by `BODY_TOLERANCE_FRAC`, 1.5%).
  Everything else is kept, so a line's span runs from its first to its last ink
  column.
- Text is then assigned to bands by `_allocate_lines()`, i.e. by capacity
  (measured band width), never by even spreading.

Why position-only matters: an earlier version kept an ink run when it was heavy
enough (with or without the body range). On this book a line fragments into many
runs (inter-character gaps exceed the 6 px merge tolerance), the heaviest run
lands mid-line, so the estimated body range came out 427..824 instead of
187..1010 and both edges of every line were deleted — measured on p015: the box
covered x=252..828 of a line whose text runs 186..1004, so the model lost
"撰。”" at the head and "书无涉，其" at the tail, and a 4 px line-final comma
was dropped by a minimum-width rule. A partial line is worse than a slightly wide
one: err on the inclusive side.

An even earlier version took the outermost ink pixel of each band, which
stretched every box to x0 = 0 on pages with a black scan edge (measured: column 0
at 100% ink over the full page height) and to the right frame line on the other
side.

The cross-check for all of this is `tmp/wzj_verify_bands.py`: it compares the
band extents with PP-OCRv5 det boxes on the same page (det is an independent
source), so a clipped head or tail shows up as a negative delta.

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

Caveat: the retry path merges its 2 or 4 crops in raster order (left/right, then
quadrants), so a two-column page that has to be retried this way can come out
interleaved. It only triggers when a page exceeds `max_tokens`.

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

Second round (2026-09-21), five pages of 温州经籍志, HunyuanOCR and Qwen OCR:

- Root cause of the reported "off by one line" (user's own diagnosis, confirmed):
  on p010 HunyuanOCR's raw reply had only **3 newlines** (414/79/289 chars) while
  the page has 30 printed lines. The reply's character count (782) matched the
  summed band capacity (782), so no content was lost — only the line breaks were
  wrong, and the old proportional mapping skipped a band, shifting every later
  line by one.
- p010 page mode, before → after: 27 boxes for 30 bands with x0 = 0 on many boxes
  → 29 boxes, one per printed line, min x0 = 213, max x1 = 1055.
- p010 line mode: 29 boxes, box and text strictly 1:1, page number read as `630`,
  no marginal running title leaking into the text.
- Single-line strip test: an uncovered band (y=535..566, 31 px) read correctly on
  its own; a bare 6 px band was refused as "too blurry" (correct behaviour, and
  the reason such bands are filtered instead of annotated).
- Timings on a 1191x1730 page, RTX 4060 Ti 8 GB: whole page 6.4 s; line mode
  10.2 s for 29 calls.
- Engine difference seen on these pages: HunyuanOCR handles punctuation more
  conventionally (full-width marks) while Qwen OCR read the footers (page number,
  running title) that HunyuanOCR dropped.

Verification scripts (inside the PPOCRLabel tree, not part of the product):

```text
tmp/verify_layout.py      layout modes, prompts, filters, band filtering
tmp/wzj_check.py          per-page box/band audit against Label.txt
tmp/wzj_raw.py            raw replies + page-edge ink profile
tmp/wzj_merge.py          merge mechanism + single-line strip test
tmp/wzj_runs.py           per-band ink runs with mass ratios
tmp/wzj_verify_fix.py     capacity allocation, geometry, page/line mode runs
```

## Known Limitations

- Box geometry is inferred from the image whenever the model omits coordinates
  (which is the normal case here), so a box can still cover about 1.5 printed
  lines where the model merged lines; the line count and the reading order are
  what the capacity pass guarantees.
- Whole-page reads tend to drop footers (page number, running title). Use line
  mode, or Qwen OCR, when the printed page number matters for citation.
- Very short lines (a few characters) are sometimes misread, because the
  fragment carries no context on its own (p010 line 14).
- Lines the model merged into one paragraph are re-cut by capacity, so the cut
  position is approximate; punctuation is preferred but not guaranteed.

## Operational Notes

Code changes in `libs/hunyuan_ocr.py`, `libs/qwen_ocr.py`, `libs/autoDialog.py`
or `PPOCRLabel.py` only take effect after PPOCRLabel is closed and reopened.

GPU memory on the 8 GB card: HunyuanOCR weights are about 1.5 GB (551 MB model +
951 MB projector) and Qwen2-VL-7B-OCR about 5.5 GB (4.25 GB + 1.29 GB). Serialise
runs: do not start a Qwen job while another recognition batch is running.

Recognition logs are named `<image-stem tail>-<md5[:8]><suffix>-result.json`,
which keeps the page number visible and prevents pages of the same book from
overwriting one another. Line mode writes a single `-lines-result.json` per page
instead of one file per line.

Existing PPOCRLabel windows keep their already-started `llama-server` process and
parameters. After changing context or token limits, close and reopen PPOCRLabel
to use the new values.

If a `llama-server.exe` remains running, inspect its parent process before
stopping it. During development, one running instance belonged to an active
`pythonw.exe` PPOCRLabel window rather than the smoke test.
