"""Local, on-demand HunyuanOCR GGUF server; no LM Studio dependency."""
import atexit
import base64
import io
import json
import logging
from pathlib import Path
import re
import socket
import subprocess
import time

import requests
import numpy as np
from PIL import Image

logger = logging.getLogger("PPOCRLabel")
ROOT = Path(__file__).resolve().parents[1] / "tools" / "hunyuan"
PROMPT_PREFIX = (
    "识别图片中的文字，按阅读顺序输出。每一行格式为：文字(x1,y1),(x2,y2)。"
    "坐标使用输入图片像素，x1,y1是左上角，x2,y2是右下角。"
    "不要合并相邻栏、不要解释，只输出识别结果。"
)
COORD_PATTERN = re.compile(
    r"\(?\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*\)?"
    r"\s*,\s*\(?\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*\)?"
)


class HunyuanCancelled(RuntimeError):
    pass


class HunyuanLengthLimit(RuntimeError):
    pass


def strip_coordinate_pairs(text):
    return COORD_PATTERN.sub("", text).strip()


def parse_coordinate_output(text, input_size, original_size):
    """Parse HunyuanOCR text followed by (x1,y1),(x2,y2) boxes."""
    entries = []
    cursor = 0
    matches = list(COORD_PATTERN.finditer(text))
    if not matches:
        return entries

    # HunyuanOCR occasionally uses its 1024px coordinate canvas even when the
    # submitted image was smaller.  Treat the largest plausible coordinate as
    # the returned canvas rather than discarding the whole page because one
    # x2 is outside input_size (the former cause of a single full-page box).
    raw_values = [float(value) for match in matches for value in match.groups()]
    max_x = max(raw_values[0::4] + raw_values[2::4])
    max_y = max(raw_values[1::4] + raw_values[3::4])
    coord_width = max(float(input_size[0]), min(max_x, 1024.0))
    coord_height = max(float(input_size[1]), min(max_y, 1024.0))
    sx = original_size[0] / coord_width
    sy = original_size[1] / coord_height
    for match in COORD_PATTERN.finditer(text):
        label = text[cursor:match.start()].strip()
        label = label.strip("` \t\r\n:：;；")
        cursor = match.end()
        if not label:
            continue
        x1, y1, x2, y2 = map(float, match.groups())
        if not (0 <= x1 < x2 <= 1024 and 0 <= y1 < y2 <= 1024):
            logger.warning("Ignoring implausible HunyuanOCR coordinate: %s", match.group(0))
            continue
        x1 = max(0, min(original_size[0], x1 * sx))
        x2 = max(0, min(original_size[0], x2 * sx))
        y1 = max(0, min(original_size[1], y1 * sy))
        y2 = max(0, min(original_size[1], y2 * sy))
        entries.append([[[x1, y1], [x2, y1], [x2, y2], [x1, y2]], (label, 0.0)])

    tail = text[cursor:].strip().strip("` \t\r\n:：;；")
    if tail:
        raise ValueError("trailing text without coordinates")
    return entries


class HunyuanOCR:
    def __init__(self, root=ROOT):
        self.root = Path(root)
        self.process = None
        self.log_file = None
        self.url = None
        self.cancelled = False
        atexit.register(self.stop)

    def check_files(self):
        servers = list((self.root / "runtime").rglob("llama-server.exe"))
        if not servers:
            raise FileNotFoundError("缺少 HunyuanOCR llama-server，请按 notes/HUNYUAN_OCR.md 配置。")
        model = self.root / "HunyuanOCR-Q8_0.gguf"
        projector = self.root / "mmproj-HunyuanOCR-bf16.gguf"
        for path in (model, projector):
            if not path.is_file():
                raise FileNotFoundError(str(path))
        return servers[0], model, projector

    def stop(self):
        self.cancelled = True
        proc, self.process = self.process, None
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)
        if self.log_file is not None:
            self.log_file.close()
            self.log_file = None

    def _check_cancel(self, cancelled):
        if self.cancelled or cancelled():
            raise HunyuanCancelled("HunyuanOCR 已取消")

    def start(self, cancelled=lambda: False):
        if self.process is not None and self.process.poll() is None:
            self._check_cancel(cancelled)
            return
        self.stop()
        self.cancelled = False
        self._check_cancel(cancelled)
        server, model, projector = self.check_files()
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        self.url = f"http://127.0.0.1:{port}"
        log_dir = self.root / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = (log_dir / "server.log").open("ab")
        command = [str(server), "-m", str(model), "--mmproj", str(projector),
                   "--host", "127.0.0.1", "--port", str(port),
                   "--alias", "hunyuanocr", "-ngl", "99", "-c", "16384",
                   "--parallel", "1", "-b", "256", "-ub", "128",
                   "--flash-attn", "on", "--temp", "0", "--jinja"]
        self.process = subprocess.Popen(
            command, stdout=self.log_file, stderr=subprocess.STDOUT,
            cwd=str(server.parent), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        deadline = time.monotonic() + 120
        try:
            while time.monotonic() < deadline:
                self._check_cancel(cancelled)
                if self.process is None or self.process.poll() is not None:
                    raise RuntimeError("HunyuanOCR 启动失败，请查看 tools/hunyuan/logs/server.log")
                try:
                    if requests.get(self.url + "/health", timeout=1).status_code == 200:
                        return
                except requests.RequestException:
                    pass
                time.sleep(0.15)
            raise TimeoutError("HunyuanOCR 启动超时")
        except Exception:
            self.stop()
            raise

    def _crop_boxes(self, width, height, parts):
        if parts == 2:
            mid_x = width // 2
            return [(0, 0, mid_x, height), (mid_x, 0, width, height)]
        mid_x = width // 2
        mid_y = height // 2
        return [
            (0, 0, mid_x, mid_y),
            (mid_x, 0, width, mid_y),
            (0, mid_y, mid_x, height),
            (mid_x, mid_y, width, height),
        ]

    @staticmethod
    def _find_vertical_gutter(page):
        """Find a likely two-column gutter; return None for a single column."""
        gray = np.asarray(page.convert("L"))
        height, width = gray.shape[:2]
        if width < 80 or height < 80:
            return None
        y0, y1 = int(height * 0.08), int(height * 0.96)
        x0, x1 = int(width * 0.25), int(width * 0.75)
        ink = (gray[y0:y1, x0:x1] < 210).mean(axis=0)
        radius = max(2, width // 350)
        smooth = np.convolve(ink, np.ones(radius * 2 + 1) / (radius * 2 + 1), mode="same")
        offset = int(np.argmin(smooth))
        gutter = x0 + offset
        # A true gutter needs to be visibly quieter than the body around it.
        baseline = float(np.median(smooth))
        if baseline <= 0 or smooth[offset] > baseline * 0.55:
            return None
        return gutter

    @staticmethod
    def _layout_prompt(layout_hint):
        hints = {
            "horizontal-single": "本图是横排单栏。请自上而下识别。",
            "horizontal-left": "本图是横排双栏的左栏。请只识别此栏，并自上而下输出。",
            "horizontal-right": "本图是横排双栏的右栏。请只识别此栏，并自上而下输出。",
            "horizontal-two-full": "本图是横排双栏。请先完整识别左栏，再完整识别右栏；每一行都必须带坐标。",
            "vertical-single": "本图是竖排单栏。请按从右到左、每列从上到下的顺序识别。",
            "vertical-right": "本图是竖排双栏的右栏。请只识别此栏，按从右到左、每列从上到下的顺序输出。",
            "vertical-left": "本图是竖排双栏的左栏。请只识别此栏，按从右到左、每列从上到下的顺序输出。",
        }
        return PROMPT_PREFIX + hints.get(layout_hint, hints["horizontal-single"])

    @staticmethod
    def _has_header_ink(page, header_height):
        gray = np.asarray(page.convert("L"))[:header_height]
        return bool(gray.size and (gray < 210).mean() > 0.008)

    @staticmethod
    def _ink_bands(values, threshold=0.012):
        """Return contiguous ink bands from a one-dimensional projection."""
        active = values > threshold
        bands = []
        start = None
        for index, value in enumerate(active):
            if value and start is None:
                start = index
            elif not value and start is not None:
                if index - start >= 2:
                    bands.append([start, index])
                start = None
        if start is not None and len(active) - start >= 2:
            bands.append([start, len(active)])
        # Small descenders and scan gaps should belong to the same text line.
        merged = []
        for band in bands:
            if merged and band[0] - merged[-1][1] <= 3:
                merged[-1][1] = band[1]
            else:
                merged.append(band)
        return merged

    @staticmethod
    def _wrap_fallback_text(text, count):
        """Break an unsegmented model response into reviewable text rows."""
        compact = "".join((text or "").split())
        if not compact or count <= 1:
            return [compact] if compact else []
        target = max(8, int(np.ceil(len(compact) / count)))
        punctuation = set("，。；：！？、）】》」』\"”")
        lines, start = [], 0
        while start < len(compact) and len(lines) < count - 1:
            ideal = min(len(compact) - 1, start + target)
            limit = min(len(compact) - 1, start + int(target * 1.35))
            cut = next((index + 1 for index in range(ideal, limit + 1) if compact[index] in punctuation), ideal)
            lines.append(compact[start:cut])
            start = cut
        if start < len(compact):
            lines.append(compact[start:])
        return lines

    def _fallback_line_entries(self, page, text, vertical=False):
        """Turn coordinate-less model text into separately editable line boxes.

        The text model's newlines are retained as the editable units.  Their
        approximate positions come from the image's horizontal (or vertical)
        ink projection, which is markedly more useful than one full-page box.
        """
        width, height = page.size
        gray = np.asarray(page.convert("L"))
        ink = gray < 210
        projection = ink.mean(axis=0 if vertical else 1)
        bands = self._ink_bands(projection)
        if not bands:
            bands = [[0, width if vertical else height]]
        if vertical:
            bands = list(reversed(bands))
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if len(lines) <= 1 and len(text.strip()) > 20 and len(bands) > 1:
            estimated_lines = max(1, int(np.ceil(len("".join(text.split())) / 18)))
            lines = self._wrap_fallback_text(text, min(len(bands), estimated_lines))
        if len(lines) <= 1:
            return [[[[0, 0], [width, 0], [width, height], [0, height]], (text, 0.0)]]

        entries = []
        for index, line in enumerate(lines):
            band_index = round(index * (len(bands) - 1) / max(1, len(lines) - 1))
            start, end = bands[band_index]
            if vertical:
                region = ink[:, max(0, start - 2):min(width, end + 2)]
                ys, xs = np.where(region)
                x0, x1 = max(0, start - 2), min(width, end + 2)
                y0, y1 = (max(0, int(ys.min()) - 2), min(height, int(ys.max()) + 3)) if len(ys) else (0, height)
            else:
                region = ink[max(0, start - 2):min(height, end + 2), :]
                ys, xs = np.where(region)
                y0, y1 = max(0, start - 2), min(height, end + 2)
                x0, x1 = (max(0, int(xs.min()) - 2), min(width, int(xs.max()) + 3)) if len(xs) else (0, width)
            entries.append(
                [[[x0, y0], [x1, y0], [x1, y1], [x0, y1]], (line, 0.0)]
            )
        return entries

    def _translate_results(self, results, offset):
        ox, oy = offset
        translated = []
        for box, text_score in results:
            points = [[point[0] + ox, point[1] + oy] for point in box]
            translated.append([points, text_score])
        return translated

    def _recognize_page(self, page, source_name, log_suffix, layout_hint="horizontal-single", cancelled=lambda: False):
        # Bound image workspace on 8GB cards; round to the model's 32px grid.
        scale = min(1.0, 1536 / max(page.size))
        size = tuple(max(32, int(n * scale / 32) * 32) for n in page.size)
        model_page = page.resize(size, Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        model_page.save(buffer, format="PNG")
        payload = {
            "model": "hunyuanocr", "temperature": 0, "max_tokens": 12288,
            "messages": [{"role": "system", "content": ""}, {"role": "user", "content": [
                {"type": "image_url", "image_url": {
                    "url": "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")}},
                {"type": "text", "text": self._layout_prompt(layout_hint)},
            ]}],
        }
        started = time.monotonic()
        try:
            response = requests.post(self.url + "/v1/chat/completions", json=payload,
                                     timeout=(5, 300))
            response.raise_for_status()
            choice = response.json()["choices"][0]
        except Exception:
            self._check_cancel(cancelled)
            raise
        self._check_cancel(cancelled)
        text = choice["message"]["content"]
        log_stem = Path(source_name).stem[:60] + log_suffix
        log_path = self.root / "logs" / (log_stem + "-result.json")
        log_path.write_text(json.dumps({"source": str(source_name), "input_size": size,
                                      "original_size": page.size,
                                      "layout_hint": layout_hint,
                                      "elapsed_seconds": time.monotonic() - started,
                                      "response": choice}, ensure_ascii=False, indent=2), encoding="utf-8")
        if choice.get("finish_reason") == "length":
            raise HunyuanLengthLimit("HunyuanOCR 输出达到长度限制")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("HunyuanOCR 未返回文字，未保存本页。")
        try:
            parsed = parse_coordinate_output(text, size, page.size)
            if parsed:
                return parsed
        except Exception as exc:
            logger.warning("HunyuanOCR coordinate parsing failed; using full page box: %s", exc)

        plain_text = strip_coordinate_pairs(text) or text.strip()
        return self._fallback_line_entries(
            page, plain_text, vertical=layout_hint.startswith("vertical")
        )

    def _recognize_crops(self, page, source_name, parts, cancelled=lambda: False):
        results = []
        for index, box in enumerate(self._crop_boxes(*page.size, parts), start=1):
            self._check_cancel(cancelled)
            crop = page.crop(box)
            crop_results = self._recognize_page(
                crop,
                source_name,
                f"-crop{parts}-{index}",
                "horizontal-single",
                cancelled=cancelled,
            )
            results.extend(self._translate_results(crop_results, box[:2]))
        return results

    def _recognize_columns(self, page, source_name, vertical, cancelled=lambda: False):
        width, height = page.size
        gutter = self._find_vertical_gutter(page)
        split = gutter if gutter is not None else width // 2
        gap = max(2, width // 300)
        # Dictionary pages often have a running head across both columns.  It
        # must be recognised as one strip, not cut in half with the body.
        header_height = min(96, max(48, int(height * 0.06)))
        header_results = []
        if self._has_header_ink(page, header_height):
            self._check_cancel(cancelled)
            header_results = self._recognize_page(
                page.crop((0, 0, width, header_height)),
                source_name,
                "-header",
                "horizontal-single",
                cancelled=cancelled,
            )
        left = (0, header_height, max(1, split - gap), height)
        right = (min(width - 1, split + gap), header_height, width, height)
        # Horizontal Chinese dictionaries read the left column first; vertical
        # pages read the right column first.  This order is retained on merge.
        regions = ((right, "vertical-right"), (left, "vertical-left")) if vertical else (
            (left, "horizontal-left"), (right, "horizontal-right")
        )
        results = self._translate_results(header_results, (0, 0))
        crop_fallbacks = []
        for index, (box, hint) in enumerate(regions, start=1):
            self._check_cancel(cancelled)
            crop_results = self._recognize_page(
                page.crop(box), source_name, f"-column-{index}", hint, cancelled=cancelled
            )
            crop_width, crop_height = page.crop(box).size
            crop_fallbacks.append(
                len(crop_results) == 1
                and self._is_full_page_box(crop_results[0][0], crop_width, crop_height)
            )
            results.extend(self._translate_results(crop_results, box[:2]))
        # Some model versions omit coordinates for narrow column crops.  A
        # full-page retry often returns line coordinates; retain the requested
        # double-column instruction and restore the reading order geometrically.
        if all(crop_fallbacks):
            full_hint = "vertical-single" if vertical else "horizontal-two-full"
            full_results = self._recognize_page(
                page, source_name, "-full-layout-fallback", full_hint, cancelled=cancelled
            )
            if len(full_results) >= 3 and not (
                len(full_results) == 1
                and self._is_full_page_box(full_results[0][0], width, height)
            ):
                return self._sort_results_by_columns(full_results, vertical)
        return results

    @staticmethod
    def _is_full_page_box(box, width, height):
        try:
            xs = [point[0] for point in box]
            ys = [point[1] for point in box]
            return min(xs) <= 1 and min(ys) <= 1 and max(xs) >= width - 1 and max(ys) >= height - 1
        except (TypeError, ValueError, IndexError):
            return False

    @staticmethod
    def _sort_results_by_columns(results, vertical):
        if len(results) < 2:
            return results
        centers = []
        for index, (box, _) in enumerate(results):
            xs = [point[0] for point in box]
            ys = [point[1] for point in box]
            centers.append((index, sum(xs) / len(xs), sum(ys) / len(ys)))
        split = (min(item[1] for item in centers) + max(item[1] for item in centers)) / 2.0
        left = [item for item in centers if item[1] < split]
        right = [item for item in centers if item[1] >= split]
        left.sort(key=lambda item: (item[2], item[1]))
        right.sort(key=lambda item: (item[2], item[1]))
        ordered = (right + left) if vertical else (left + right)
        return [results[item[0]] for item in ordered]

    def recognize(self, image_path, layout_mode="auto", reading_mode="horizontal", cancelled=lambda: False):
        self.start(cancelled)
        self._check_cancel(cancelled)
        with Image.open(image_path) as source:
            page = source.convert("RGB")
        valid_modes = {
            "auto", "horizontal-single", "horizontal-two",
            "vertical-single", "vertical-two",
        }
        if layout_mode not in valid_modes:
            layout_mode = "auto"
        vertical = layout_mode.startswith("vertical") or (
            layout_mode == "auto" and reading_mode == "vertical"
        )
        if layout_mode == "auto":
            layout_mode = ("vertical-two" if vertical else "horizontal-two") if self._find_vertical_gutter(page) else (
                "vertical-single" if vertical else "horizontal-single"
            )
        try:
            if layout_mode.endswith("-two"):
                return self._recognize_columns(page, image_path, vertical, cancelled=cancelled)
            hint = "vertical-single" if vertical else "horizontal-single"
            return self._recognize_page(page, image_path, "", hint, cancelled=cancelled)
        except HunyuanLengthLimit:
            logger.warning("HunyuanOCR full page reached token limit; retrying with 2 crops: %s", image_path)
            try:
                return self._recognize_crops(page, image_path, 2, cancelled=cancelled)
            except HunyuanLengthLimit:
                logger.warning("HunyuanOCR 2-crop retry reached token limit; retrying with 4 crops: %s", image_path)
                try:
                    return self._recognize_crops(page, image_path, 4, cancelled=cancelled)
                except HunyuanLengthLimit as exc:
                    raise ValueError(
                        "HunyuanOCR 自动裁剪为 4 块后仍达到长度限制，已跳过本页。"
                    ) from exc
