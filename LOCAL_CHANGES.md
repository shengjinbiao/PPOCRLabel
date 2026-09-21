# Local Change Notes

## 2026-05-30

- Updated `PPOCRLabel.py` full-text export:
  - `PaddleOCR -> 导出整本文本` now allows export when recognition results exist only in `Cache.cach`.
  - Full-text export no longer skips labels marked `difficult: true`, so auto-recognized or unconfirmed pages can still be exported.
  - Existing page order and blank-line page separator behavior are unchanged.

- Added `scripts/batch_full_text.py`:
  - Command-line PP-Structure full-text export for a PDF, a single image, or an image directory.
  - Supports PDF page rendering, optional kept page images, HTML stripping, and forced left-column then right-column ordering.

- Generated one ad-hoc full-text export outside the repo source tree:
  - `D:\古汉语文化百科词典\full_text_from_cache.txt`
  - Source: `D:\古汉语文化百科词典\Cache.cach`

- Generated a second full-text export with explicit page headers:
  - `D:\古汉语文化百科词典\full_text_from_cache_with_pages.txt`
  - Page count: 1257

## 2026-08-28

- Improved `PaddleOCR -> 二栏从左到右` auto recognition:
  - When this mode is enabled, auto recognition now finds the central gutter,
    runs PaddleOCR on the left and right column crops separately, then maps
    detected boxes back to full-page coordinates.
  - The column-crop results are post-processed as nested dictionary rows: a
    narrow CJK box that was mistaken for vertical text is split by character,
    then same-row headword/reading/definition fragments inside each main
    column are merged into one horizontal annotation.
  - If crop-based OCR fails, it falls back to the original full-page OCR path.
  - This is intended for mixed dictionary pages where vertical Chinese headword
    columns and horizontal Latin text were being merged into one OCR line.
