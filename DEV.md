# HintErase 项目展示页（维护手册）

> 这是给维护者看的开发文档：怎么生成素材、怎么写 `cases.json`、怎么发布。
> 面向访客的项目介绍见 [README.md](README.md)。

纯静态页面（HTML + CSS + 原生 JS，无构建工具），放在 `docs/`，由 GitHub Pages 直接发布。

```
docs/                 ← 网站根目录（GitHub Pages 发布这个目录）
  index.html          页面英文文字（标题、作者、方法简介、局限、BibTeX）直接改这里
  i18n.js             中英切换与中文文字（见“中英双语”）
  style.css / app.js  样式与播放器
  manifest.js         由 build_site.py 生成，不要手改
  media/              由 build_site.py 生成：每个案例一个 mp4 + 封面 + 缩略图
tools/
  build_site.py       把原始结果拼成网页素材
  make_placeholders.py 生成合成占位视频（只用于预览页面）
cases.json            案例清单（自己写，参考 cases.example.json）
```

## 原理：一个案例 = 一个视频

每个案例的所有行（Input、Hint、HintErase、消融行）被裁到同一时间段、统一帧率和尺寸，**上下拼成一个 mp4**。
页面用 canvas 从这个视频里取两行左右拼接显示，中间是可拖动的分割线。因此：

- 对比的两个画面永远逐帧同步（只有一个解码器）；
- 左右两边各自可以切换成任意一行（输入 / 提示 / 我们 / 消融）；
- 时间码显示原片帧号（`src_frame`），方便和推理日志对照。

## 第一步：准备每个案例的原始结果

每个案例一个文件夹，所有视频**必须和 Input 从同一帧开始、帧帧对齐**：

| 行 | 来源 |
|---|---|
| `Input` | 原片片段 |
| `Hint`（可选） | 同一个原片 + 提示 mask（如 `hint_raw.mkv`，FFV1 灰度即可），页面上会以橙色半透明叠加显示 |
| `HintErase` | 我们的输出（`longvideo/run.py` 的结果） |
| `Hole`（提示类案例） | 同一套权重、`--hint_mode hole` 的结果：提示当作洞，展示漏检和宽松框时挖洞方式的问题 |

长视频不需要截出片段：在 `cases.json` 里写 `start`（秒）和 `duration` 即可，脚本会自己截。

## 第二步：写 cases.json

参考 `cases.example.json`。字段：

- `id`：英文短名，也是网页链接锚点（`.../#ktv-demo` 直接打开这个案例）
- `category`：`subtitles` `karaoke` `titles` `logos` `anime` `long` `hints` `failures` 之一（标签名和说明在 `build_site.py` 顶部 `CATEGORIES` 改）
- `title` / `note`：显示在播放器旁边的标题和一句说明
- `title_zh` / `note_zh`（可选）：中文页面显示的标题和说明，不填则中文页面显示英文。只改这两项不会触发视频重新编码
- `start` / `duration`：截取范围（秒），建议 5–10 秒
- `src_frame`：片段第一帧在原片里的帧号（只用于显示时间码）
- `left` / `right`：默认左右显示哪两行（默认 Input / HintErase）
- `max_side`：单行最长边像素（默认 854）；行数多时会自动缩小，保证拼接后高度不超过 4096
- 顶层 `uhd`：“超高清交付”独立板块（落地第 ⑦ 步之后）用哪个案例，该案例应设 `"gallery": false`。不设时板块仍然显示，只是没有播放器（当前就是这个状态：示例素材涉及可识别人物，未公开）。要恢复播放器，除了设这个键，还要把 `index.html` 里 `<div class="uhd-player" id="uhd-player">` 那行加回该板块。
- 顶层 `hero`：首屏播放器用哪个案例；`overview_video`：B 站 BV 号或 YouTube ID（中文浏览器优先显示 B 站）
- 顶层 `placeholder: true` 会在页面顶部显示“占位素材”提示条，正式发布前改为 `false`

## 已经剪好的片段：直接写 cases.json（当前用的是 cases.v2.json）

输入和结果已经剪成同样长度的短片时（如 `D:\workdir\001-Inpainting\测试样例\Hinterase_pub`），不需要 cut_clips，直接写 cases 文件：

```bash
python tools/build_site.py cases.v2.json
```

- 每个案例的 `rows` 写输入和结果两行即可，`start: 0`，不写 `duration` 就用整段。
- 两个文件差一帧时，在提前的那一行加 `"offset": 1`（跳过它的第 1 帧）。现有的后来三段输入都比结果早一帧，已经加了。
- `"gallery": false`：不进中间结果区，只用在首屏播放器（由顶部 `"hero"` 指定）或超高清板块（由顶部 `"uhd"` 指定）。
- 中间结果区按 `category` 分标签页，同一类别的多个案例出现在右侧列表里。

### 没有提示视频时：从输入和结果反推检测框

```bash
python tools/make_hint_boxes.py --input 输入.mp4 --result 擦除结果.mp4 --out 提示.mp4 --roi 0,0.55,1,1 [--offset 1]
```

输入和结果不同的地方就是被擦掉的地方：逐帧求差、按行合并成框、去掉人物运动带来的零碎差异，把橙色框画在输入上，另存一份每帧框坐标的 `.json`。
`--roi` 只在给定区域里找（歌词在下方就写 `0,0.55,1,1`，避免框到走动的人），`--offset` 与 cases 文件里输入行的 offset 相同。生成的提示视频作为 `Hint` 行加入 cases 文件即可（offset 与输入行一致）。

## 从完整结果截取案例：clips.json → cut_clips.py

结果通常是整集 / 整首的完整视频。`clips.v1.json` 按**帧号**描述每个案例（`start_frame` + `frames`），每一行给出完整文件路径：

```bash
python tools/cut_clips.py clips.v1.json     # → raw/<案例>/*.mkv（逐帧对齐）和 cases.json
python tools/build_site.py cases.json       # → docs/media、docs/manifest.js
python tools/make_figures.py ../hinterase_report/figures/figures.json   # → 报告插图
```

- 所有行用同一个帧区间截取，保证逐帧对齐；Hint 行复用 Input 的片段，只额外截取 mask。
- 隔行片源（如 `后来.mpg`）在 Input 行写 `"vf": "yadif=0:0:0"`，与长视频流程的反交错一致，否则输入行会有梳齿纹。
- 路径相对 `hinterase_page/`，`../../测试样例/...` 指向 `D:\workdir\001-Inpainting\测试样例`。
- 想换片段只改 `start_frame` / `frames`，重新跑这三条命令即可；已截过的片段文件不会重复截取（要重截先删掉 `raw/<案例>/`）。

## 中英双语

页面右上角的按钮切换中文 / English。语言选择顺序：链接里的 `?lang=zh` 或 `?lang=en` → 上次的选择（浏览器本地记录）→ 浏览器语言。分享中文页面直接用 `.../?lang=zh`。

| 文字 | 英文写在 | 中文写在 |
|---|---|---|
| 页面固定文字（标题、方法、局限、致谢、页脚…） | `docs/index.html` | `docs/i18n.js` 的 `ZH`，键名与 html 里的 `data-i18n` 相同 |
| 播放器按钮、行名（Input / Hint …） | `docs/i18n.js` 的 `UI.en` | `UI.zh`、`ROWS_ZH`（方法名不翻译） |
| 类别标签和说明 | `tools/build_site.py` 的 `CATEGORIES` | 同一行的后两项 |
| 案例标题和说明 | `cases.json` 的 `title` / `note` | `title_zh` / `note_zh` |

改英文时记得同步改中文；缺少的中文会自动显示英文。BibTeX 不翻译。
修改 `index.html` 里带 `data-i18n` 的文字时不要删掉这个属性，否则切换语言后那一处不会变。

## 第三步：生成素材并本地预览

```bash
python tools/build_site.py cases.json            # 未修改的案例会自动跳过
python tools/build_site.py cases.json --only ktv-demo --force   # 只重做一个
cd docs && python -m http.server 8000            # 浏览器打开 http://localhost:8000
```

需要带 libx264 的 ffmpeg（服务器上用 `/data/miniconda3/envs/ffmpeg-x264/bin` 放到 PATH 前面）。
脚本会打印每个 mp4 的大小，超过 50 MB 会提示。

## 第四步：发布到 GitHub Pages

1. 新建仓库（如 `HintErase`），把整个目录推上去（`raw/` 原始结果不要提交，已在 `.gitignore` 里）。
2. 仓库 Settings → Pages → Source 选 `Deploy from a branch`，Branch 选 `main`，目录选 `/docs`。
3. 一两分钟后访问 `https://<用户名或组织>.github.io/HintErase/`。

## 体积限制（GitHub 的硬约束）

- 单个文件超过 100 MB 无法推送；Pages 站点建议不超过 1 GB，流量软上限每月 100 GB。
- **Git LFS 的文件 Pages 不提供**，视频必须是普通文件。
- 按默认设置（854 宽、CRF 26、8 秒、4–5 行），每个案例约 3–8 MB，30 个案例在 200 MB 左右。
- 合集视频、几分钟的长视频成片放 B 站 / YouTube（`overview_video`）或公司对象存储，不要放进仓库。

## 发布前检查

- [ ] 每个案例都有版权方的书面授权，并在报告附录 Footage 里列出出处
- [ ] 展示的视频都没有参与训练（动漫微调用过同系列剧集时尤其要核对）
- [ ] 只展示 HintErase 及其消融，不放其他方法的结果
- [ ] `index.html` 里的作者、技术报告链接、BibTeX 已填写
- [ ] 方法介绍不涉及训练数据和超参数
- [ ] `cases.json` 里 `placeholder` 已改为 `false`，并删除占位案例
