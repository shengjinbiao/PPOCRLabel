## PP-Structure Web UI (scripts/ppstructure_webui.py)

目的：提供一个简易本地 Web 界面，调用 `PPStructureV3` 对目录下图片做版面识别，左侧预览图片，右侧显示识别文本，可手动编辑并保存为同名 `.txt`。

依赖：
- 已装 `paddleocr`（你的 `ppocrlabel` 环境中有）
- `gradio`（如缺失：`pip install gradio`）

启动示例：
```powershell
D:\anaconda3\envs\ppocrlabel\python.exe scripts\ppstructure_webui.py ^
  --input_dir "D:\简帛\test" ^
  --output_dir ".\ppstructure_edits" ^
  --layout_model_dir "C:\Users\sheng\.paddlex\official_models\PP-DocLayout_plus-L"
```
打开 http://127.0.0.1:7860。

行为：
- 选择图片时调用 `PPStructureV3.predict`，结果缓存在内存（同图不重跑）。
- 文本来源：优先 `parsing_res_list`，为空回退 `overall_ocr_res.rec_texts/rec_polys`。
- 块排序：按列→行重排（基于 bbox 和页面宽度估计列间距）避免双栏交错。
- 保存：点击“保存”写入 `output_dir` 下同名 `.txt`，更新缓存。
- `allowed_paths` 允许 `input_dir`，服务监听 127.0.0.1:7860。

可改进：
- 增加“重新识别/刷新缓存”按钮。
- 支持加载已有 `.txt` 覆盖识别结果或批量预跑。
- 暴露列间距阈值或关闭重排用于特殊版式。
