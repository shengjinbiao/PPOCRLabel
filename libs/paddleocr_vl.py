"""Bridge PPOCRLabel to PaddleOCR-VL in its isolated conda environment."""
import json
import os
from pathlib import Path
import subprocess
import threading


ROOT = Path(__file__).resolve().parents[1]
# Kept separate from both the application's environment and a possible interrupted
# clone named ``ppocrlabel-vl``.
DEFAULT_PYTHON = Path(r"D:\anaconda3\envs\ppocrlabel-vl-runtime\python.exe")
WORKER = ROOT / "scripts" / "paddleocr_vl_worker.py"
RESULT_PREFIX = "__PPOCRLABEL_RESULT__"


class PaddleOCRVL:
    """Persistent PaddleOCR-VL-1.6 process returning editable layout blocks."""

    def __init__(self, python_path=DEFAULT_PYTHON, worker=WORKER):
        self.python_path = Path(python_path)
        self.worker = Path(worker)
        self.process = None
        self._lock = threading.Lock()

    def check_files(self):
        if not self.python_path.is_file():
            raise FileNotFoundError(
                "缺少独立 PaddleOCR-VL 环境；请先运行 scripts/setup_paddleocr_vl.ps1。"
            )
        if not self.worker.is_file():
            raise FileNotFoundError(str(self.worker))

    def start(self):
        if self.process is not None and self.process.poll() is None:
            return
        self.check_files()
        self.stop()
        # Paddle/PaddleX and their native dependencies can write Chinese diagnostics
        # using the active Windows code page.  The JSON protocol itself is UTF-8;
        # force that for Python output and make third-party diagnostics non-fatal.
        child_env = os.environ.copy()
        child_env["PYTHONIOENCODING"] = "utf-8"
        child_env["PYTHONUTF8"] = "1"
        self.process = subprocess.Popen(
            [str(self.python_path), "-X", "utf8", "-u", str(self.worker)],
            cwd=str(ROOT),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=child_env,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    def stop(self):
        process, self.process = self.process, None
        if process is None:
            return
        if process.stdin:
            try:
                process.stdin.close()
            except OSError:
                pass
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

    @staticmethod
    def _entry(item):
        x1, y1, x2, y2 = (float(value) for value in item["box"])
        return [
            [[x1, y1], [x2, y1], [x2, y2], [x1, y2]],
            (item["text"], float(item.get("score", 0.0))),
        ]

    def recognize(self, image_path, cancelled=lambda: False, **_unused):
        with self._lock:
            self.start()
            if cancelled():
                raise RuntimeError("PaddleOCR-VL 已取消")
            request = json.dumps({"image_path": str(image_path)}, ensure_ascii=False)
            assert self.process is not None and self.process.stdin and self.process.stdout
            self.process.stdin.write(request + "\n")
            self.process.stdin.flush()
            diagnostics = []
            while True:
                if cancelled():
                    self.stop()
                    raise RuntimeError("PaddleOCR-VL 已取消")
                line = self.process.stdout.readline()
                if not line:
                    raise RuntimeError("PaddleOCR-VL 工作进程意外停止：" + "".join(diagnostics[-8:]))
                line = line.rstrip("\r\n")
                if line.startswith(RESULT_PREFIX):
                    payload = json.loads(line[len(RESULT_PREFIX):])
                    if "error" in payload:
                        raise RuntimeError(payload["error"])
                    return [self._entry(item) for item in payload.get("entries", []) if item.get("text")]
                diagnostics.append(line)
