## PP-Structure Web UI (scripts/ppstructure_webui.py)

用途：本地 Web 校对界面，包含两个流程：
- 版面/整页：预览图片，查看/编辑识别文本，保存为同名 `.txt`。
- 逐字切片（可选）：加载 `char_gt.csv` 的单字切片，左右对照图像与文本，人工确认后再保存，可同步产出“已确认”子集。

依赖：
- `paddleocr`（ppocrlabel 环境已带）
- `gradio`（如缺失：`pip install gradio`）

整页校对示例（PowerShell）：
```powershell
python scripts\ppstructure_webui.py `
  --input_dir "D:\甲骨文字典\test" `
  --output_dir ".\pp_edits" `
  --layout_model_dir "C:\Users\sheng\.paddlex\official_models\PP-DocLayout_plus-L"
```

逐字切片 + 整页一起跑（假设 `char_gt.csv` 和切片图在同一目录）：
```powershell
python scripts\ppstructure_webui.py `
  --input_dir "D:\甲骨文字典\目录" `
  --output_dir "D:\甲骨文字典\目录\pp_edits" `
  --char_csv "D:\甲骨文字典\目录\char_gt.csv" `
  --char_img_root "D:\甲骨文字典\目录" `
  --approved_dir "D:\甲骨文字典\目录\curated_chars"
```
- `char_csv`：需含 `img_path`, `char` 列。
- `char_img_root`：`img_path` 为相对路径时指定基目录，留空则按 CSV 原样。
- `approved_dir`：在逐字 Tab 点击“保存该字”且文本非空时，将切片复制到此目录并追加一行到 `approved.csv`（仅保存过的人工确认数据）。`approved_csv` 可自定义输出文件路径。

界面行为：
- 整页 Tab：选择图片即调用 `PPStructureV3.predict`（同图缓存），优先用 `parsing_res_list`，为空回退 `overall_ocr_res`；列→行重排避免双栏交错。点击“保存”写入 `output_dir/同名.txt` 并更新缓存。
- 逐字 Tab：滑条切换切片；编辑文本后点“保存该字”，会覆盖 `char_csv` 中该行的 `char`。若配置了 `approved_dir/approved_csv` 且文本非空，会复制切片并在 `approved.csv` 追加一行；文本为空则跳过收集。默认显示行号、来源行文件名与顺序。

访问：启动后浏览器打开 http://127.0.0.1:7860（仅本机）。`allowed_paths` 允许读取 `input_dir`。
