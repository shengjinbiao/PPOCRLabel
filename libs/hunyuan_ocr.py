"""Local, on-demand HunyuanOCR GGUF server; no LM Studio dependency."""
import atexit
import base64
import hashlib
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
META_MARKERS = (
    "无法准确识别",
    "无法识别",
    "重新拍摄",
    "重新上传",
    "过于模糊",
    "模糊，无法",
    "每一行格式为",
    "坐标使用输入图片像素",
    "不要合并相邻栏",
    "本图是横排",
    "本图是竖排",
    "请只识别此栏",
    "请自上而下",
    "按从右到左",
)

IPA_PROMPT = (
    "识别图片中的文字，按阅读顺序逐行输出，不要合并行、不要解释。"
    "本页是汉语方言学著作，含国际音标与声调符号，请严格按下述要求转写："
    "1）声调一律用五度调符 ˥ ˦ ˧ ˨ ˩ 表示，例如 [˦˦]、[˨˦]、[˨˩˧]、[˥˧]；"
    "绝对不要用注音符号（ㄧㄨㄩㄚㄛㄜㄝ…）或拼音字母代替调符。"
    "2）音标字母用标准国际音标字符逐字转写：ŋ ɕ ʑ ʨ ʨʰ ʦ ʦʰ ʂ ʐ ɿ ʅ ɚ ɛ ɔ ɤ ɐ ɑ æ ə ʰ ʷ ʲ ̃；"
    "不要用近似拉丁字母代替（不要把 ɕ 写成 x、不要把 ʨ 写成 j、不要省略 ʰ）。"
    "3）汉字照原样（繁体）转写，不要转成简体；页眉、页码、书耳等孤立小字也要输出。"
)

# 印刷行/墨迹带的尺度门槛
BAND_MIN_HEIGHT = 8
LINE_MIN_CHARS = 5
MARGIN_TRIM_FRAC = 0.01
# 页级列覆盖判据：正文块 = 高覆盖列；稀疏区 = 空白/页边，用来分隔正文与页边杂物
BODY_COVERAGE_FRAC = 0.35
SPARSE_COVERAGE_FRAC = 0.12
BARRIER_MIN_WIDTH = 12
BODY_TOLERANCE_FRAC = 0.015
RULE_MAX_HEIGHT = 14
RULE_WIDTH_FRAC = 0.8
META_PREFIX = re.compile(
    r"^\s*(?:"
    r"图片中的?(?:文本|文字)(?:内容)?(?:是|为)?[:：]?"
    r"|图中的?文字[:：]?"
    r"|图片中文字内容[:：]?"
    r"|识别(?:出来|结果|内容|到的文字)?(?:是|为)?[:：]?"
    r"|本图中的?(?:文本|文字)(?:内容)?(?:是|为)?[:：]?"
    r"|内容(?:是|为)[:：]?"
    r")\s*"
)
LATEX_TOKENS = {
    "\\therefore": "·",
    "\\cdot": "·",
    "\\times": "×",
    "\\ldots": "…",
    "\\dots": "…",
    "\\cdots": "…",
    "\\sim": "~",
}
COORD_PATTERN = re.compile(
    r"\(?\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*\)?"
    r"\s*,\s*\(?\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*\)?"
)
# 提示词里的字面占位符，模型偶尔会把它当地页文字回显，例如
# “文字(x1,y1),(x2,y2)”或“临渊羡鱼,(x1,y1),(x2,y2)”。
COORD_TEMPLATE_PATTERN = re.compile(
    r"[（(]\s*[xXｘ]\s*[1１]\s*[,，]\s*[yYｙ]\s*[1１]\s*[)）]"
    r"|[（(]\s*[xXｘ]\s*[2２]\s*[,，]\s*[yYｙ]\s*[2２]\s*[)）]"
)
TEMPLATE_WORDS = "文字坐标识别结果图片内容行每输出"


class HunyuanCancelled(RuntimeError):
    pass


class HunyuanLengthLimit(RuntimeError):
    pass


def strip_coordinate_pairs(text):
    return COORD_PATTERN.sub("", text).strip()


def strip_coord_template(text):
    """Remove the prompt's literal coordinate placeholders from a reply.

    Real page text is kept: the model sometimes appends its output template to a
    genuine line (“临渊羡鱼,(x1,y1),(x2,y2)”).  Only when nothing but template
    vocabulary is left (“文字(x1,y1),(x2,y2)”) is the text dropped as a pure echo.
    """
    if not text:
        return text
    had_template = bool(COORD_TEMPLATE_PATTERN.search(text))
    if not had_template:
        return text
    cleaned = COORD_TEMPLATE_PATTERN.sub("", text)
    remainder = re.sub(r"[\s，,。；;：:、]+", "", cleaned)
    if not remainder or all(char in TEMPLATE_WORDS for char in remainder):
        return ""
    # 剥掉占位符后常留下重复标点（“临渊羡鱼,,不见”），仅在此处收拢。
    return re.sub(r"([,，。；;])\1+", r"\1", cleaned)


def looks_like_model_meta(text):
    """True when a reply is a refusal or an echo of our own prompt, not page text.

    The vision models sometimes answer a bad crop with "图片中的文字过于模糊…"
    or repeat the prompt back.  Such replies must never become annotation text.
    """
    compact = "".join((text or "").split())
    if not compact:
        return True
    hits = sum(1 for marker in META_MARKERS if marker in compact)
    if hits >= 2:
        return True
    return hits == 1 and len(compact) <= 60


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
    coord_width = float(input_size[0])
    coord_height = float(input_size[1])
    if max_x > coord_width * 1.02 or max_y > coord_height * 1.02:
        # Coordinates past the submitted size: the model used a larger canvas.
        coord_width = max(coord_width, min(max_x, 1024.0))
        coord_height = max(coord_height, min(max_y, 1024.0))
        logger.warning(
            "HunyuanOCR coordinates exceed the submitted size %sx%s (max %sx%s); "
            "assuming a %sx%s canvas",
            input_size[0],
            input_size[1],
            max_x,
            max_y,
            coord_width,
            coord_height,
        )
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


class HunyuanLayout:
    """混元 / Qwen 版式选项的单一事实来源（键、菜单标签、提示）。

    “page”是默认：整页一次送入，只用默认 OCR 指令，不裁栏、不合并，
    也不做任何几何重排，直接按模型给的阅读顺序保存。
    旧的“auto”会自己算中缝硬切页面，容易错切，已退役。
    """

    DEFAULT = "page"
    ORDER = (
        "page",
        "model-auto",
        "horizontal-single",
        "horizontal-two",
        "vertical-single",
        "vertical-two",
    )
    LABELS = {
        "page": "整页识别（默认，不切栏）",
        "model-auto": "模型自判版式",
        "horizontal-single": "横排单栏",
        "horizontal-two": "横排双栏（左→右）",
        "vertical-single": "竖排单栏",
        "vertical-two": "竖排双栏（右→左）",
    }
    DETAILS = {
        "page": "整页一次送入模型，只用默认 OCR 指令；不裁栏、不合并、不重排，按模型给的阅读顺序保存。适合批量不校对。",
        "model-auto": "整页一次送入，请模型自行判断横排/竖排、单栏/双栏，并按正确阅读顺序输出；不裁栏、不重排。",
        "horizontal-single": "整栏送入，加“横排单栏、自上而下”提示；不裁栏、不重排。",
        "horizontal-two": "先按中缝定位左右栏分别送入，再按左栏、右栏合并；找不到真中缝时整页一次读。",
        "vertical-single": "整栏送入，加“竖排、从右到左每列自上而下”提示；不裁栏、不重排。",
        "vertical-two": "先按中缝定位左右栏分别送入，再按右栏、左栏合并；找不到真中缝时整页一次读。",
    }

    @classmethod
    def is_valid(cls, mode):
        return mode in cls.LABELS

    @classmethod
    def normalize(cls, mode):
        """把旧设置（含已退役的 auto/default）映射到当前模式。"""
        if mode in (None, "", "auto", "default"):
            return cls.DEFAULT
        return mode if mode in cls.LABELS else cls.DEFAULT

    @classmethod
    def label(cls, mode):
        return cls.LABELS.get(mode, mode)

    @classmethod
    def detail(cls, mode):
        return cls.DETAILS.get(mode, cls.DETAILS[cls.DEFAULT])

    @classmethod
    def options(cls):
        return [(mode, cls.LABELS[mode], cls.DETAILS[mode]) for mode in cls.ORDER]


class HunyuanOCR:
    def __init__(self, root=ROOT, line_mode=False, ipa_mode=False):
        self.root = Path(root)
        self.process = None
        self.log_file = None
        self.url = None
        self.cancelled = False
        self.line_mode = bool(line_mode)
        # 音标页模式：用 IPA 专用提示词（五度调符 + 国际音标字符表，禁止注音/拼音代替）。
        self.ipa_mode = bool(ipa_mode)
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
        """Find a likely two-column gutter; return None for a single column.

        The search band is kept near the page centre (35%-65%) and a gutter must
        be markedly quieter than the body **and** be flanked by ink on both
        sides.  The old 25%-75% band accepted the page's own blank margin as a
        "gutter", which cut single-column pages into a whole-page crop plus an
        empty sliver and scrambled the reading order.
        """
        gray = np.asarray(page.convert("L"))
        height, width = gray.shape[:2]
        if width < 160 or height < 160:
            return None
        y0, y1 = int(height * 0.10), int(height * 0.94)
        x0, x1 = int(width * 0.35), int(width * 0.65)
        if x1 - x0 < 8:
            return None
        ink = (gray[y0:y1, x0:x1] < 210).mean(axis=0)
        radius = max(2, width // 350)
        smooth = np.convolve(ink, np.ones(radius * 2 + 1) / (radius * 2 + 1), mode="same")
        baseline = float(np.median(smooth))
        if baseline <= 0:
            return None
        offset = int(np.argmin(smooth))
        # A true gutter needs to be visibly quieter than the body around it.
        if smooth[offset] > baseline * 0.45:
            return None
        left = ink[: max(1, offset - radius)]
        right = ink[min(len(ink) - 1, offset + radius):]
        if len(left) < radius or len(right) < radius:
            return None
        if float(left.mean()) < baseline * 0.35 or float(right.mean()) < baseline * 0.35:
            return None
        return x0 + offset

    def _layout_prompt(self, layout_hint):
        base = IPA_PROMPT if self.ipa_mode else PROMPT_PREFIX
        if layout_hint in ("page", "", None):
            # 整页默认模式：只给默认 OCR 指令（或 IPA 指令），不加版式附加语。
            return base
        hints = {
            "model-auto": (
                "请自行判断本图是横排还是竖排、单栏还是双栏，并按该版式正确的阅读顺序输出。"
            ),
            "horizontal-single": "本图是横排单栏。请自上而下识别。",
            "horizontal-left": "本图是横排双栏的左栏。请只识别此栏，并自上而下输出。",
            "horizontal-right": "本图是横排双栏的右栏。请只识别此栏，并自上而下输出。",
            "horizontal-two-full": "本图是横排双栏。请先完整识别左栏，再完整识别右栏；每一行都必须带坐标。",
            "vertical-single": "本图是竖排单栏。请按从右到左、每列从上到下的顺序识别。",
            "vertical-right": "本图是竖排双栏的右栏。请只识别此栏，按从右到左、每列从上到下的顺序输出。",
            "vertical-left": "本图是竖排双栏的左栏。请只识别此栏，按从右到左、每列从上到下的顺序输出。",
            "vertical-two-full": "本图是竖排双栏。请先完整识别右栏，再完整识别左栏；每一行都必须带坐标。",
        }
        return base + hints.get(layout_hint, "")

    @staticmethod
    def _log_stem(source_name, suffix):
        """Keep the page suffix (files end with the page number) plus a short hash."""
        stem = Path(source_name).stem
        digest = hashlib.md5(stem.encode("utf-8")).hexdigest()[:8]
        if len(stem) > 64:
            stem = stem[:24] + "_" + stem[-36:]
        return stem + "-" + digest + suffix

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

        The geometry comes from the image (ink bands = printed lines); the text
        comes from the model.  The model often answers with paragraph-sized
        blocks instead of one line per printed line, so the text is cut to the
        **capacity** of each band (its measured ink width), never spread evenly:
        every band then receives text and no band is skipped, which removes the
        "off by one line" drift.  If the page cannot be aligned with any
        confidence, one full-page box is returned instead, so a guessed box
        layout can never silently reorder the text.
        """
        width, height = page.size
        compact = "".join((text or "").split())
        full_page_box = [
            [[[0, 0], [width, 0], [width, height], [0, height]], (text.strip(), 0.0)]
        ]
        if not compact:
            return []
        bands = self._text_bands(page, vertical=vertical)
        if len(bands) < 2:
            # 无法对齐：宁可用一个整页框，也不猜位置。
            return full_page_box
        if len(compact) < LINE_MIN_CHARS * len(bands):
            # 字数远少于印刷行容量：模型明显没读全，不匀摊。
            logger.warning(
                "Fallback text is %d chars for %d printed lines; using one full-page box",
                len(compact),
                len(bands),
            )
            return full_page_box
        model_lines = [line.strip() for line in text.splitlines() if line.strip()]
        if len(model_lines) == len(bands):
            # 模型正好一行对一行：直接采用它的行界。
            pieces = model_lines
        else:
            pieces = self._allocate_lines(compact, [band["span"] for band in bands])
        entries = []
        for piece, band in zip(pieces, bands):
            x0, x1 = band["x0"], band["x1"]
            y0, y1 = band["y0"], band["y1"]
            entries.append([[[x0, y0], [x1, y0], [x1, y1], [x0, y1]], (piece, 0.0)])
        return entries

    @staticmethod
    def _sparse_barriers(coverage, min_width=BARRIER_MIN_WIDTH, threshold=SPARSE_COVERAGE_FRAC):
        """Blank column ranges wide enough to separate a line from marginal matter."""
        sparse = coverage < threshold
        barriers = []
        start = None
        for index, value in enumerate(sparse):
            if value and start is None:
                start = index
            elif not value and start is not None:
                if index - start >= min_width:
                    barriers.append((start, index))
                start = None
        if start is not None and len(sparse) - start >= min_width:
            barriers.append((start, len(sparse)))
        return barriers

    @staticmethod
    def _body_block(coverage, fallback, tolerance, min_width=BARRIER_MIN_WIDTH):
        """Column range where the body text lives (runs of high-coverage columns)."""
        strong = coverage >= BODY_COVERAGE_FRAC
        runs = []
        start = None
        for index, value in enumerate(strong):
            if value and start is None:
                start = index
            elif not value and start is not None:
                runs.append((start, index))
                start = None
        if start is not None:
            runs.append((start, len(strong)))
        runs = [run for run in runs if run[1] - run[0] >= min_width]
        if not runs:
            return float(fallback[0]), float(fallback[1])
        return (
            float(min(run[0] for run in runs)) - tolerance,
            float(max(run[1] for run in runs)) + tolerance,
        )

    def _text_bands(self, page, vertical=False):
        """Printed text lines: ink bands with complete, noise-free extents.

        A band's span runs from its first to its last ink column, so the first
        and last characters of a printed line — punctuation included — are never
        trimmed by a mass threshold.  Only an ink group lying **entirely**
        outside the body block is dropped; that removes the scan border, a
        printed frame line and a vertical running title in the margin, while a
        short tail after a wide gap still overlaps the body block and stays.
        """
        width, height = page.size
        ink = np.asarray(page.convert("L")) < 210
        if vertical:
            ink = ink.T
        extent, cross = ink.shape[0], ink.shape[1]
        margin = max(2, int(cross * MARGIN_TRIM_FRAC))
        bands = self._ink_bands(ink.mean(axis=1))
        bands = [[max(0, s - 2), min(extent, e + 2)] for s, e in bands]
        coverage = np.zeros(cross, dtype=float)
        tracks = []
        for start, end in bands:
            columns = np.where(ink[start:end, :].any(axis=0))[0]
            if end - start < BAND_MIN_HEIGHT or len(columns) == 0:
                continue
            span_px = int(columns.max() - columns.min())
            if (
                end - start < RULE_MAX_HEIGHT
                and span_px >= RULE_WIDTH_FRAC * max(1, cross - 2 * margin)
            ):
                # 通栏细线（版框横线 / 扫描黑边）不是文本行。
                continue
            tracks.append([start, end, columns])
            coverage[columns] += 1.0
        if not tracks:
            return []
        coverage /= float(len(tracks))
        barriers = self._sparse_barriers(coverage)
        body_lo, body_hi = self._body_block(
            coverage,
            (margin, cross - margin),
            max(8, int(cross * BODY_TOLERANCE_FRAC)),
        )
        result = []
        for start, end, columns in tracks:
            band_profile = ink[start:end, :].sum(axis=0)
            groups = []
            current = []
            previous = None
            for column in columns:
                column = int(column)
                if previous is not None and any(
                    previous < barrier_hi and column > barrier_lo
                    for barrier_lo, barrier_hi in barriers
                ):
                    # 这两段之间跨过了空白/页边区，不能算同一组。
                    groups.append(current)
                    current = []
                current.append(column)
                previous = column
            if current:
                groups.append(current)
            keep = []
            for group in groups:
                group_lo, group_hi = group[0], group[-1]
                overlaps_body = not (group_hi < body_lo or group_lo > body_hi)
                if overlaps_body or float(band_profile[group].sum()) <= 0:
                    keep.extend(group)
            if not keep:
                keep = [int(column) for column in columns]
            lo, hi = min(keep), max(keep)
            if vertical:
                result.append(
                    {"x0": start, "x1": end, "y0": lo, "y1": hi, "span": hi - lo}
                )
            else:
                result.append(
                    {"x0": lo, "x1": hi, "y0": start, "y1": end, "span": hi - lo}
                )
        if vertical:
            result.reverse()
        return result

    @staticmethod
    def _allocate_lines(text, capacities):
        """Cut a run-on model reply into one piece per printed line.

        Each printed line receives text proportional to its measured width and
        the cut prefers a punctuation mark near the target.  The total equals the
        character count, so every line gets text and no line is skipped.
        """
        total = len(text)
        count = len(capacities)
        weights = [max(1.0, float(capacity)) for capacity in capacities]
        weight_sum = sum(weights) or float(count)
        punctuation = set("，。；：！？、）】》」』\"”.,;:!?)]}")
        pieces = []
        cursor = 0
        for index in range(count - 1):
            remaining = total - cursor
            left = count - index - 1
            target = weights[index] * total / weight_sum
            want = int(round(target))
            want = max(1, min(want, remaining - left))
            low = max(1, int(want * 0.6))
            high = min(remaining - left, max(want, int(want * 1.4)))
            cut = None
            for offset in range(want, high + 1):
                if text[cursor + offset - 1] in punctuation:
                    cut = cursor + offset
                    break
            if cut is None:
                for offset in range(want - 1, low - 1, -1):
                    if text[cursor + offset - 1] in punctuation:
                        cut = cursor + offset
                        break
            if cut is None:
                cut = cursor + want
            pieces.append(text[cursor:cut])
            cursor = cut
        pieces.append(text[cursor:])
        return pieces

    def _translate_results(self, results, offset):
        ox, oy = offset
        translated = []
        for box, text_score in results:
            points = [[point[0] + ox, point[1] + oy] for point in box]
            translated.append([points, text_score])
        return translated

    def _recognize_page(self, page, source_name, log_suffix, layout_hint="page", cancelled=lambda: False, write_log=True):
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
        log_stem = self._log_stem(source_name, log_suffix)
        log_path = self.root / "logs" / (log_stem + "-result.json")
        if write_log:
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

        plain_text = strip_coord_template(
            self._strip_meta_prefix(strip_coordinate_pairs(text) or text.strip())
        )
        if looks_like_model_meta(plain_text):
            logger.warning(
                "%s replied with a refusal or a prompt echo for %s; skipping: %s",
                type(self).__name__,
                source_name,
                plain_text[:80],
            )
            return []
        return self._fallback_line_entries(
            page, plain_text, vertical=layout_hint.startswith("vertical")
        )

    @staticmethod
    def _line_strip(page, band, vertical=False, min_side=56, pad=4):
        """Crop one printed line and centre it on white.

        A bare 20-30px strip is often refused as "too blurry"; padding it to a
        readable height keeps single-line recognition reliable.
        """
        width, height = page.size
        box = (
            max(0, band["x0"] - pad),
            max(0, band["y0"] - pad),
            min(width, band["x1"] + pad),
            min(height, band["y1"] + pad),
        )
        crop = page.crop(box)
        crop_width, crop_height = crop.size
        if vertical:
            target = (max(min_side, crop_width + 24), crop_height + 24)
        else:
            target = (crop_width + 24, max(min_side, crop_height + 24))
        canvas = Image.new("RGB", target, (255, 255, 255))
        canvas.paste(
            crop, ((target[0] - crop_width) // 2, (target[1] - crop_height) // 2)
        )
        return canvas

    @staticmethod
    def _strip_meta_prefix(text):
        """Drop a leading "图片中的文本内容是：" style preamble."""
        cleaned = (text or "").lstrip()
        while True:
            match = META_PREFIX.match(cleaned)
            if not match:
                break
            cleaned = cleaned[match.end():].lstrip()
        return cleaned

    @classmethod
    def _clean_line_text(cls, text):
        """Strip meta preambles and LaTeX-ish wrappers around short lines.

        A printed page number "·630·" came back as "$$ \\therefore 630 \\cdot $$"
        and a short line came back prefixed with "图片中的文本内容是：".
        """
        cleaned = strip_coord_template(cls._strip_meta_prefix(text))
        cleaned = re.sub(r"\s*\n\s*", "", cleaned)
        if not cleaned.strip():
            return ""
        if "$" not in cleaned and "\\" not in cleaned:
            return cleaned.strip()
        for token, replacement in LATEX_TOKENS.items():
            cleaned = cleaned.replace(token, replacement)
        cleaned = re.sub(r"\\[a-zA-Z]+|\\[,;:!]|[{}$]", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if re.fullmatch(r"[\s\d·．.．\-—–()（）\[\]{}]+", cleaned):
            cleaned = re.sub(r"\s+", "", cleaned)
        return cleaned

    def _recognize_page_by_lines(self, page, source_name, vertical=False, cancelled=lambda: False):
        """OCR every printed line on its own: box and text match by construction.

        Slower (one call per line) but immune to the model merging or skipping
        lines, and it reads footers such as the page number that a whole-page
        read tends to drop.
        """
        bands = self._text_bands(page, vertical=vertical)
        if not bands:
            logger.warning(
                "No text bands found in %s; using a whole-page read", source_name
            )
            return self._recognize_page(page, source_name, "", "page", cancelled=cancelled)
        results = []
        empty = 0
        for index, band in enumerate(bands, start=1):
            self._check_cancel(cancelled)
            strip = self._line_strip(page, band, vertical=vertical)
            entries = self._recognize_page(
                strip,
                source_name,
                f"-line-{index}",
                "page",
                cancelled=cancelled,
                write_log=False,
            )
            text = self._clean_line_text(
                " ".join(t for _, (t, _) in entries if t).strip()
            )
            if not text:
                # 这条没读出来（条太薄/太小最常见）：垫更高的白边再试一次，
                # 免得因为空文本在 PPOCRLabel 存盘时被跳过而成漏行。
                strip = self._line_strip(page, band, vertical=vertical, min_side=140)
                entries = self._recognize_page(
                    strip,
                    source_name,
                    f"-line-{index}-retry",
                    "page",
                    cancelled=cancelled,
                    write_log=False,
                )
                text = self._clean_line_text(
                    " ".join(t for _, (t, _) in entries if t).strip()
                )
            if not text:
                empty += 1
            results.append(
                [
                    [
                        [band["x0"], band["y0"]],
                        [band["x1"], band["y0"]],
                        [band["x1"], band["y1"]],
                        [band["x0"], band["y1"]],
                    ],
                    (text, 0.0),
                ]
            )
        logger.info(
            "Line-mode OCR %s: %d lines, %d without text", source_name, len(results), empty
        )
        try:
            log_path = self.root / "logs" / (
                self._log_stem(source_name, "-lines") + "-result.json"
            )
            log_path.write_text(
                json.dumps(
                    {
                        "source": str(source_name),
                        "mode": "line",
                        "vertical": vertical,
                        "empty_lines": empty,
                        "lines": [{"box": box, "text": text} for box, (text, _) in results],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.warning("Unable to write line-mode log for %s: %s", source_name, exc)
        return results

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
        if gutter is None:
            # 指定双栏但没找到真正的中缝：整页一次读，仍用双栏提示，
            # 顺序由模型负责，不再按几何位置重排（错切会把整页顺序打乱）。
            logger.warning(
                "No two-column gutter found in %s; reading the whole page with a two-column prompt",
                source_name,
            )
            return self._recognize_page(
                page,
                source_name,
                "-no-gutter-full",
                "vertical-two-full" if vertical else "horizontal-two-full",
                cancelled=cancelled,
            )
        split = gutter
        gap = max(2, width // 300)
        # Dictionary pages often have a running head across both columns.  It
        # must be recognised as one strip, not cut in half with the body.
        header_height = min(160, max(64, int(height * 0.08)))
        top = header_height
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
            if not header_results:
                # 页眉没读出（拒绝语/空白）：正文从页顶开始，避免丢内容。
                top = 0
        left = (0, top, max(1, split - gap), height)
        right = (min(width - 1, split + gap), top, width, height)
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
        # full-page retry often returns line coordinates.  The prompt already
        # asks for left column first (right column first when vertical), so the
        # model order is kept unless it clearly contradicts that instruction.
        if all(crop_fallbacks):
            full_hint = "vertical-two-full" if vertical else "horizontal-two-full"
            full_results = self._recognize_page(
                page, source_name, "-full-layout-fallback", full_hint, cancelled=cancelled
            )
            if len(full_results) >= 3 and not (
                len(full_results) == 1
                and self._is_full_page_box(full_results[0][0], width, height)
            ):
                if self._sequence_follows_columns(full_results, vertical):
                    return full_results
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
    def _sequence_follows_columns(results, vertical):
        """True when the model already emitted the requested column order."""
        if len(results) < 3:
            return True
        centers = []
        for box, _ in results:
            xs = [point[0] for point in box]
            ys = [point[1] for point in box]
            centers.append(((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0))
        xs_all = [center[0] for center in centers]
        split = (min(xs_all) + max(xs_all)) / 2.0
        keys = []
        for center_x, center_y in centers:
            side = 0 if center_x < split else 1
            keys.append(((1 - side) if vertical else side, center_y))
        return keys == sorted(keys)

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

    PAGE_MODE = HunyuanLayout.DEFAULT
    MODEL_AUTO_MODE = "model-auto"
    COLUMN_MODES = ("horizontal-two", "vertical-two")
    VALID_LAYOUT_MODES = tuple(HunyuanLayout.ORDER)

    def recognize(self, image_path, layout_mode="page", reading_mode="horizontal",
                  cancelled=lambda: False, line_mode=None, ipa_mode=None):
        if line_mode is not None:
            self.line_mode = bool(line_mode)
        if ipa_mode is not None:
            self.ipa_mode = bool(ipa_mode)
        self.start(cancelled)
        self._check_cancel(cancelled)
        with Image.open(image_path) as source:
            page = source.convert("RGB")
        requested = layout_mode
        layout_mode = HunyuanLayout.normalize(layout_mode)
        if layout_mode != requested:
            # 旧的“自动判断”会自己算中缝硬切页面（容易错切），已退役，
            # 改为整页默认指令；要模型自判请选 model-auto。
            logger.warning(
                "Layout mode %r is retired or unknown; using %r", requested, layout_mode
            )
        if layout_mode in (self.PAGE_MODE, self.MODEL_AUTO_MODE):
            vertical = reading_mode == "vertical"
            hint = layout_mode
        else:
            vertical = layout_mode.startswith("vertical")
            hint = "vertical-single" if vertical else "horizontal-single"
        try:
            if layout_mode in self.COLUMN_MODES:
                if self.line_mode:
                    logger.warning(
                        "Line mode is ignored for two-column layout modes: %s", image_path
                    )
                return self._recognize_columns(page, image_path, vertical, cancelled=cancelled)
            if self.line_mode:
                return self._recognize_page_by_lines(
                    page, image_path, vertical=vertical, cancelled=cancelled
                )
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
