# Local Change Notes

## 2026-09-21

- 第六轮：**音标页模式（IPA）** 固化为引擎参数 + GUI 勾选项 + 命令行开关。
  - 引擎：新增 `IPA_PROMPT`（五度调符 ˥˦˧˨˩ + 国际音标字符表 + 禁止注音符号/拼音代替 + 繁体保持 + 页眉页码也输出）；
    `HunyuanOCR(ipa_mode=…)` 与 `recognize(..., ipa_mode=…)`；`_layout_prompt` 改为实例方法，按 `self.ipa_mode` 选基础提示词，
    指定版式的附加语照旧拼接（六种版式不受影响）。
  - GUI：混元/Qwen 菜单新增可勾选项「音标页识别（国际音标）」，存设置 `hunyuan_ipa_mode`，与「逐行裁条识别」并列；
    识别对话框会提示当前模式。
  - CLI：`scripts/vision_ocr.py --ipa`（建议与 `--lines` 同用）。
  - 实测依据（方言大词典 p016）：默认提示词 → 注音符号 / `[1][4]` / `ar·yr·uar`；加 IPA 提示词 → 0 注音、95 个调符、`ər/iər/uər/ār`。
    但**调值取值仍不可靠**（`[˦˦]`→`[˧]`、`[˨˦]`→`[˥]`，例词一律 `˥˥`），需要后处理约束；
    另：密集页整页读会撞 token 上限并触发 2 块重试，逐行模式未触发。
  - 单元检查 `tmp/ipa_switch_check.py`：提示词切换、版式附加语、参数存在性全过；`py_compile` 五个文件 OK。

## 2026-09-21

- 第五轮：新增无界面命令行入口 `scripts/vision_ocr.py`。
  - 一条命令跑完「PDF/页图 → 渲染 → 出框 → 整页或逐行识别 → 文本 + 带框 JSON」；
    调用的是同一套引擎代码（`libs/hunyuan_ocr.py` / `libs/qwen_ocr.py`），
    所以以后修的 bug 两边同时生效。
  - 参数：`--input`（PDF 或多个页图/目录）、`--outdir`、`--engine hunyuan|qwen`、
    `--layout`（复用 `HunyuanLayout` 的六种）、`--lines`、`--reading`、`--pages`、`--dpi`、
    `--label-file`（另写 PPOCRLabel 格式的 Label.txt）。
  - 产出：`text/<页>.txt`、`json/<页>.json`（框+文字+元数据）、`records.jsonl`、`full_text.txt`、
    PDF 趟另存 `pages/<书名>/page-NNN.png`。
  - 安全：先查 GPU 占用与已在跑的 `llama-server.exe`（默认拒绝共用显卡，`--allow-shared-gpu` 可覆盖），
    并用 `tools/hunyuan/logs/.vision_ocr.lock` 防两个命令行任务相撞。
  - 坑（已修）：输出名不能用原图全名（这书的文件名 180 字符，拼两遍超 Windows 路径长度）→
    改为「保头保尾 + 8 位哈希」；`-X utf8` 下 `tasklist`/`nvidia-smi` 的 GBK 输出会炸 UTF-8 解码 →
    统一 `errors="replace"`。
  - 冒烟实测：页图 p015 逐行 28 框/0 空/11.2s；汉文典 PDF 第 1 页 150dpi 渲染 + 整页识别 6 框/3.2s。

## 2026-09-21

- 第四轮（老盛报「两行并成一行的长文本在文本框里被遮住」「有一行回显了 prompt 的坐标格式」）：
  - **显示**：结果列表行高不再固定——新增 `_fit_label_item_height()`，按当前宽度算换行后的文本高度设 sizeHint，
    并在 `addLabel` / `labelItemChanged` 里刷新；列表设 `ElideNone` 并关闭 uniformItemSizes。
    自动识别对话框的日志列表同样处理。长文本（合并行）现在换行显示、不再被遮尾。
  - **坐标模板回显**：新增 `strip_coord_template()`（`COORD_TEMPLATE_PATTERN`）。日志里实测两种形态：
    纯回显 `文字(x1,y1),(x2,y2)` → 整条丢弃；正文被追加占位符 `临渊羡鱼,(x1,y1),(x2,y2)` →
    **只剥占位符、正文全留**（并收拢剥后留下的重复标点）。`_clean_line_text` 同时把条内换行折掉。
    整页路径（混元/千问）同样接上，附单元检查 `tmp/wzj_template_check.py`。

## 2026-09-21

- 第三轮（老盛报「逐行模式漏字/漏行，漏掉的常在标点附近」后定位并修）：
  - **根因**：第二轮那套「墨迹段质量 ≥ 主段 20% 或落在正文范围内」太脆——「正文范围」是用每条带最重的一段估的，而本页字间空隙大于合并阈值，一行碎成多段、最重段落在中间，估出的范围变成 427..824（真值约 187..1010），两侧正文被判越界删掉。
    实测 p015：第 3 行框只盖 x=252..828，模型读不到行首「撰。”」与行尾「书无涉，其」；第 21 行行首「故国。」（占该行墨迹 10.5%）被删；第 0 行行尾 4px 的标点被「最小宽 17px」滤掉。
  - **新算法**（`_text_bands`）：页级列覆盖 → 高覆盖列组成「正文块」；低覆盖连续区（≥12px）作为「空白屏障」；每条带按屏障切成若干墨迹组，**只有整体落在正文块之外的组才丢**，其余一律保留（行的左右端取保留列的极值）。判据只与位置有关、与行内墨迹质量无关，所以行首/行尾的字与标点不会再被质量阈值切掉。
  - 带高门槛 10→8px；新增「通栏细线」过滤（高度 <14px 且宽 ≥80% 正文宽 → 版框横线/扫描黑边，不建框）。
  - 逐行模式：某条读不出文字时**垫更高的白边重试一次**（避免空文本在存盘时被跳过成漏行）。
  - **交叉验证**（新增 `tmp/wzj_verify_bands.py`）：用 PP-OCRv5 det 的行框当独立基准逐行比对。p015：28 带 vs det 29 框，21/28 条左右端差 ≤3px；残留差异分别是 det 把页边竖排书名并进正文框（我正确地排除了）、扫描斑点被计入、页脚两端的点被正文块判据排除。带数核对确认**没有真行被丢**（丢的都是 5-6px 噪声带；p016 det 多出的 2 框是页底斑点）。
  - 真机复测 p015 逐行模式：28 框 vs 28 带（一一对应），总字数 650→673，第 3 行恢复「撰。”…书无涉，其」、第 9 行恢复行首「存。」、第 21 行恢复「故国。」。
  - 残留：扫描斑点会被计入（抹宽条图，无碍）；页脚两端的点会被正文块判据排除（数字保留）；页边竖排书名的处理见上。

## 2026-09-21

- 同日第二轮（老盛报「页码缺失 / 左边到顶 / 行错开一行」后定位并修）：
  - **框几何**：新增 `_text_bands()`——墨迹带按「位置 + 质量」双判据取左右范围
    （带内墨迹段：质量 ≥ 主段 20% **或** 落在正文范围内），滤掉扫描黑边、版框线、
    页边竖排书名（书耳），同时保留宽空格后合法的行尾短段；带高 < 10px 的噪点带丢弃。
    原实现用整行 min/max，导致每行 x0≈0（左边到顶）与右侧越界。
  - **文本配行**：新增 `_allocate_lines()`——模型常把整页读成几个「段落块」（实测 p010
    只有 3 个换行、414/79/289 字），改按**每带容量**（墨迹宽度）切片、切点就近取标点；
    Σ容量 = 总字数，因此每条印刷行都分到文本、不再跳带（旧实现按比例均摊会整段顺移一行）。
  - **新增「逐行裁条识别」开关**（`hunyuan_line_mode`，菜单可勾）：按印刷行逐条裁图单独送
    模型，框与文严格 1:1，页脚/页码也能读到；薄条先垫白到可读高度（`_line_strip`）。
    实测 p010（1191x1730）：整页 6.4s/29 框，逐行 10.2s/29 框，页码 `·630·` 读出为 `630`。
  - `_clean_line_text()` + `_strip_meta_prefix()`：清掉模型对短行加的 LaTeX 外壳
    （`$$ \therefore 630 \cdot $$` → `·630·`）和「图片中的文本内容是：」之类的前缀。
  - 逐行模式不写每行日志（只写一份 `-lines-result.json` 汇总），避免每页几十个日志文件。

## 2026-09-21

- 混元 / Qwen 版式与阅读顺序修复（老盛报“第一段跑到第二段后面”后定位）：
  - 新增默认版式「整页识别（默认，不切栏）」：整页一次送入，只发默认 OCR 指令，
    不裁栏、不合并、不做任何几何重排。旧的「自动判断」（程序按墨迹中缝硬切页面）
    退役，旧设置值 `auto` 归一化为 `page`；另加「模型自判版式」（model-auto）。
  - 混元 / Qwen 结果保存前不再走 `sort_ocr_result_entries` 几何重排
    （由 `result_order_from_model` 标记控制）；该重排只保留给 PaddleOCR 的二栏模式。
    这是“段落顺序错乱”的主因：`~/.autoOCRSettings.pkl` 的 `two_column_left_to_right=True`
    会把单栏页按 center_x 硬切成两个假栏再重排。
  - `_fallback_line_entries`：无坐标回退改成“文本行 ↔ 墨迹带按序对位”
    （原来按比例均摊，5 行撒到 30 条带上）；行数少于带数时先按带数重切；
    过滤极窄扫描噪点带；带数 < 2 或无法对齐时退回整页一框（兜底）。
  - 拒绝语 / 提示词回显（“图片中的文字过于模糊…”“每一行格式为…”）不再被当正文建框。
  - `_find_vertical_gutter` 收紧到页宽 35%–65% 并要求两侧有墨、中缝足够安静；
    指定双栏但找不到真中缝时整页一次读（不再按页宽中点硬切）。
  - 版式选项单一事实来源：`libs/hunyuan_ocr.HunyuanLayout`（PPOCRLabel 菜单、
    autoDialog 提示、引擎白名单共用一份表）。
  - 日志名保留页号并按页去重（原来 `stem[:60]` 把页号截掉，整本书互相覆盖）。
  - 验证脚本：`tmp/diag_fallback_order.py`（复现旧错序）、`tmp/verify_layout.py`（离线 30 项检查）、
    `tmp/e2e_page_mode.py`（真机整页模式，p012 得 27 框、文字与模型输出完全一致）。

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
