"""HunyuanOCR-1.5 local GGUF engine, kept separate from HunyuanOCR-1.0."""
from pathlib import Path

from libs.hunyuan_ocr import HunyuanOCR, IPA_PROMPT, PROMPT_PREFIX


ROOT15 = Path(__file__).resolve().parents[1] / "tools" / "hunyuan15"
HUNYUAN15_PROMPT = (
    "请提取文档图片中正文的全部信息，按原阅读顺序逐行输出。"
    "只输出原图文字，不解释、不补写、不重复；普通汉字、标点、数字优先按原样转写。"
)
HUNYUAN15_IPA_PROMPT = HUNYUAN15_PROMPT + IPA_PROMPT


class HunyuanOCR15(HunyuanOCR):
    """Run the official HunyuanOCR-1.5 GGUF without replacing v1.0 files."""

    server_alias = "hunyuanocr15"
    # HunyuanOCR-1.5's own client uses a smaller generation budget and a mild
    # repetition penalty; the old 12k-token setting can run on noisy IPA rows.
    max_tokens = 4096
    repeat_penalty = 1.08

    def __init__(self, root=ROOT15, line_mode=False, ipa_mode=False):
        super().__init__(root=root, line_mode=line_mode, ipa_mode=ipa_mode)

    def check_files(self):
        servers = list((self.root / "runtime").rglob("llama-server.exe"))
        if not servers:
            raise FileNotFoundError(
                "缺少 HunyuanOCR-1.5 运行时；请运行 scripts/setup_hunyuan15_gguf.py。"
            )
        model = self.root / "hyocr-q4_k_m.gguf"
        projector = self.root / "mmproj-hyocr-f16.gguf"
        for path in (model, projector):
            if not path.is_file():
                raise FileNotFoundError(
                    f"缺少 HunyuanOCR-1.5 文件：{path.name}；"
                    "请运行 scripts/setup_hunyuan15_gguf.py。"
                )
        return servers[0], model, projector

    def _layout_prompt(self, layout_hint):
        base = HUNYUAN15_IPA_PROMPT if self.ipa_mode else HUNYUAN15_PROMPT
        inherited = super()._layout_prompt(layout_hint)
        old_base = IPA_PROMPT if self.ipa_mode else PROMPT_PREFIX
        return base + inherited[len(old_base):]
