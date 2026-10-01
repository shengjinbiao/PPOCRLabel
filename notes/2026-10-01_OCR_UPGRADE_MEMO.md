# 2026-10-01：视觉 OCR 升级备忘录

## 本次目标

1. 改善方言学著作中 IPA、声调、上下标及音系对齐的识别与输出。
2. 保留原有 HunyuanOCR、Qwen OCR 和 PaddleOCR 的可用状态，不就地覆盖旧模型或旧环境。
3. 接入两个优先级最高的新方案：**HunyuanOCR 1.5** 与 **PaddleOCR-VL 1.6**。

## 已完成：文本和排版处理

- IPA 提示词改为“普通汉字正文优先”。只有确实出现 IPA/声调/音系例项的局部才启用严格的音标规则，避免把方言学正文误判为音标或拼音。
- IPA 局部规则包含：`ŋ/g`、`ȵ/n`、`ɕ/c/x`、`ʨ/j`、`ʦ/c`、`ʂ/s`、`ʐ/z` 的区分；上下标、附加符、数字调值和五度调符均要求按原样保留。
- Hunyuan 的兜底输出不再删除行内空格或制表符。页面中确有的音系对齐空档会保留；普通汉字正文不凭空插入空格。

涉及文件：

- `libs/hunyuan_ocr.py`
- `PPOCRLabel.py`
- `libs/autoDialog.py`
- `scripts/vision_ocr.py`

## 已完成：HunyuanOCR 1.5

### 本地安装状态

- 官方原始权重已下载至 `tools/hunyuan15/hf/`。
- 已使用 llama.cpp 转换出 GGUF，并生成 Q4_K_M 量化模型：
  - `tools/hunyuan15/hyocr-q4_k_m.gguf`
  - `tools/hunyuan15/mmproj-hyocr-f16.gguf`
- 已安装独立 llama.cpp CUDA 运行时：`tools/hunyuan15/runtime/`。
- 实测 `HunyuanOCR15.start()` 后服务正常启动，`stop()` 能正常停止。
- 这些模型、运行时和日志已由 `.gitignore` 排除，不会被提交到代码库。

### 程序接入

- 新增 `libs/hunyuan15_ocr.py`，继承旧混元引擎但使用独立的模型目录和服务别名；不影响旧版 `tools/hunyuan/`。
- GUI 自动识别菜单新增“使用 HunyuanOCR 1.5（新版）”。四个视觉模型选项互斥，切换时会释放另一模型的显存。
- 命令行新增：

  ```powershell
  python scripts/vision_ocr.py --engine hunyuan15 --input <图片或PDF> --outdir <输出目录>
  ```

- 新版默认最大输出限制为 4096，并加入 `repeat_penalty=1.08`，用于减少大页音标表出现尾部重复生成的风险。

### 已知情况

- 对一张密集 IPA 表格整页的首次实测，旧的 12288 输出限制下出现过尾部重复生成；该测试已停止，之后将新版上限收紧并加入重复惩罚。
- 新版能够启动不等于该类复杂页面已完成质量验收。后续应以“逐行裁条识别”对 IPA 页进行小样本对比，再决定默认模式。

## 部分完成：PaddleOCR-VL 1.6

### 已完成的程序接入

- 新增 `libs/paddleocr_vl.py`：主程序通过独立 Python 子进程调用 PaddleOCR-VL，返回版面块的文字和坐标，供 PPOCRLabel 编辑。
- 新增 `scripts/paddleocr_vl_worker.py`：在隔离环境内加载 `PaddleOCRVL(pipeline_version="v1.6", device="gpu:0")`。
- GUI 自动识别菜单新增“使用 PaddleOCR-VL 1.6（新版）”。
- 命令行新增：

  ```powershell
  python scripts/vision_ocr.py --engine paddle-vl --input <图片或PDF> --outdir <输出目录>
  ```

- 独立轻量环境已创建：`D:\anaconda3\envs\ppocrlabel-vl-runtime`（Python 3.10）。

### 待人工完成的安装

自动安装 `paddlepaddle-gpu==3.2.1` 时，默认 PyPI 没有该新版 GPU 轮子，NVIDIA 备用索引又出现 DNS 解析失败。因此未把任何新版依赖安装进原 `ppocrlabel` 环境。

在 PowerShell 中，先按本机 CUDA/驱动和 Paddle 官方安装页取得匹配的 Paddle GPU 安装包，然后执行：

```powershell
D:\anaconda3\envs\ppocrlabel-vl-runtime\python.exe -m pip install <匹配的Paddle-GPU安装包或wheel路径>
D:\anaconda3\envs\ppocrlabel-vl-runtime\python.exe -m pip install "paddleocr[doc-parser]==3.7.0"
D:\anaconda3\envs\ppocrlabel-vl-runtime\python.exe -c "import paddle; print(paddle.__version__); from paddleocr import PaddleOCRVL; print('PaddleOCRVL OK')"
```

随后重启 PPOCRLabel，在“自动识别”菜单勾选“使用 PaddleOCR-VL 1.6（新版）”。首次识别会自动下载该模型所需的权重。

安装脚本已更新为独立环境方案：`scripts/setup_paddleocr_vl.ps1`。如果采用手工安装，可不运行该脚本。

### 旧的半成品克隆

- 先前启动的 `D:\anaconda3\envs\ppocrlabel-vl` 是完整克隆旧环境的半成品，复制速度较慢。
- 它不影响原环境和新建的 `ppocrlabel-vl-runtime`；如不再需要，可在确认没有克隆进程后由用户自行结束进程并删除该目录。

## 验证记录

- `python -m py_compile` 已通过：`PPOCRLabel.py`、`libs/autoDialog.py`、`libs/hunyuan_ocr.py`、`libs/hunyuan15_ocr.py`、`libs/paddleocr_vl.py`、两个安装/工作脚本及 `scripts/vision_ocr.py`。
- `git diff --check` 已通过。
- 命令行构造测试已确认 `--engine hunyuan15` 和 `--engine paddle-vl` 能分别创建对应引擎。

## 回退和使用建议

- 原“使用 HunyuanOCR”和“使用 Qwen OCR”选项仍保留；切回即可继续使用旧模型。
- 对普通方言学正文，优先使用默认提示词；“音标页识别”只用于 IPA/音系密集页面。
- 对包含明显横向空档的音系表，先尝试 HunyuanOCR 1.5 的逐行裁条模式，检查空格、调符和上下标后再批量处理。
