"""Direct local Qwen OCR server, independent of LM Studio."""
import base64
import io
import json
import logging
from pathlib import Path
import socket
import subprocess
import time

import requests
from PIL import Image

from libs.hunyuan_ocr import (
    HunyuanOCR,
    HunyuanLengthLimit,
    ROOT as HUNYUAN_ROOT,
    parse_coordinate_output,
    strip_coordinate_pairs,
)

logger = logging.getLogger("PPOCRLabel")
DEFAULT_QWEN_DIR = Path.home() / ".lmstudio" / "models" / "mradermacher" / "Qwen-2-VL-7B-OCR-GGUF"


class QwenOCR(HunyuanOCR):
    """Run the Qwen 2 VL OCR GGUF through PPOCRLabel's local llama server."""

    model_id = "qwenocr"

    def __init__(self, model_dir=DEFAULT_QWEN_DIR, root=HUNYUAN_ROOT):
        super().__init__(root)
        self.model_dir = Path(model_dir)

    def check_files(self):
        servers = list((self.root / "runtime").rglob("llama-server.exe"))
        if not servers:
            raise FileNotFoundError("缺少本地 llama-server 运行时。")
        model = self.model_dir / "Qwen-2-VL-7B-OCR.Q4_K_S.gguf"
        projector = self.model_dir / "Qwen-2-VL-7B-OCR.mmproj-fp16.gguf"
        for path in (model, projector):
            if not path.is_file():
                raise FileNotFoundError(f"找不到 Qwen OCR 文件：{path}")
        return servers[0], model, projector

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
        self.log_file = (log_dir / "qwen-server.log").open("ab")
        command = [
            str(server), "-m", str(model), "--mmproj", str(projector),
            "--host", "127.0.0.1", "--port", str(port),
            "--alias", self.model_id, "-ngl", "99", "-c", "8192",
            "--parallel", "1", "-b", "256", "-ub", "128",
            "--flash-attn", "on", "--temp", "0", "--jinja",
        ]
        self.process = subprocess.Popen(
            command,
            stdout=self.log_file,
            stderr=subprocess.STDOUT,
            cwd=str(server.parent),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        deadline = time.monotonic() + 120
        try:
            while time.monotonic() < deadline:
                self._check_cancel(cancelled)
                if self.process is None or self.process.poll() is not None:
                    raise RuntimeError("Qwen OCR 启动失败，请查看 tools/hunyuan/logs/qwen-server.log")
                try:
                    if requests.get(self.url + "/health", timeout=1).status_code == 200:
                        return
                except requests.RequestException:
                    pass
                time.sleep(0.15)
            raise TimeoutError("Qwen OCR 启动超时")
        except Exception:
            self.stop()
            raise

    def _recognize_page(self, page, source_name, log_suffix, layout_hint="horizontal-single", cancelled=lambda: False):
        scale = min(1.0, 1536 / max(page.size))
        size = tuple(max(32, int(value * scale / 32) * 32) for value in page.size)
        model_page = page.resize(size, Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        model_page.save(buffer, format="PNG")
        payload = {
            "model": self.model_id,
            "temperature": 0,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": [
                {"type": "image_url", "image_url": {
                    "url": "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")}},
                {"type": "text", "text": self._layout_prompt(layout_hint)},
            ]}],
        }
        started = time.monotonic()
        response = requests.post(self.url + "/v1/chat/completions", json=payload, timeout=(10, 300))
        response.raise_for_status()
        self._check_cancel(cancelled)
        choice = response.json()["choices"][0]
        text = choice["message"]["content"]
        log_dir = self.root / "logs"
        log_stem = Path(source_name).stem[:60] + "-qwen" + log_suffix
        (log_dir / (log_stem + "-result.json")).write_text(
            json.dumps({"source": str(source_name), "input_size": size,
                        "original_size": page.size, "layout_hint": layout_hint,
                        "elapsed_seconds": time.monotonic() - started,
                        "response": choice}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if choice.get("finish_reason") == "length":
            raise HunyuanLengthLimit("Qwen OCR 输出达到长度限制")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Qwen OCR 未返回文字，未保存本页。")
        try:
            parsed = parse_coordinate_output(text, size, page.size)
            if parsed:
                return parsed
        except Exception as exc:
            logger.warning("Qwen OCR coordinate parsing failed; using visual line split: %s", exc)
        plain_text = strip_coordinate_pairs(text) or text.strip()
        return self._fallback_line_entries(page, plain_text, vertical=layout_hint.startswith("vertical"))
