# 后续开发状态

更新日期：2026-10-06。继续开发前先读本文件和 DATA_FORMAT.md。

## 项目位置与发布

- 工作区：`C:\Users\jianlong\sources\cngeojson`，Windows / PowerShell。
- 仓库：<https://github.com/keosu/cnhistory>，`origin` 为 `git@github.com:keosu/cnhistory.git`，主分支 `main`。
- 正式网站：<https://keosu.github.io/cnhistory/>。
- GitHub Pages 使用 GitHub Actions；`.github/workflows/pages.yml` 在 main 推送后检查、打包并部署。
- 当前内容提交：`44ed038`，修正清朝辖区、中文名称与修正时间索引。本状态文件另行提交。
- 对应部署：<https://github.com/keosu/cnhistory/actions/runs/37449338659>。记录时数据检查通过、正在打包；后续以 Actions 实际状态为准。
- 本地预览：`python scripts/serve.py --port 8000`，<http://127.0.0.1:8000/>。

## 用户目标与已完成行为

核心目标是从 Toolbay 提取中国及周边历史资料，生成独立可复用数据，并用新地图展示疆域、政权随年份变化。

- 展示范围前 2000—2017 年，无公元 0 年。
- 14 个主要朝代标签在单行时间轴上横向避让，刻度保持年份比例；手机隐藏标签下方年份但保留 title。
- 前进、播放、后退、倍速、年份输入在顶部居中；左右键逐年切换，长按加速，松手／失焦停止。
- SVG 图标按钮、全屏、可隐藏右侧面板，桌面／手机分别保存面板状态。
- 六套主题：light/dark/paper/vivid/vermilion/neon；界面、底图和疆域配色同步更新。
- 去除了页内来源署名、原图颜色提示、操作说明文字。不要再次添加冗余说明。

## 数据格式与入口

文件以 UTF-8 JSON、CSV、标准 GeoJSON 和 PNG 为主，不依赖后端、数据库或外部地图服务。

| 数据 | 入口 |
| --- | --- |
| 政权与阶段 | `data/focus/entities.json`（439 组、967 阶段） |
| 人物任期 | `data/focus/rulers.json` / `rulers.csv`（4472 条） |
| 推导变化 | `data/focus/events.json` / `events.csv`（11978 条） |
| 年号 | `data/focus/eras.json` |
| 修正地图索引（网页默认） | `data/focus/territory-timeline.curated.json`（653 区间） |
| 未修正拼合索引 | `data/focus/territory-timeline.json`（651 区间） |
| 修正地图与轮廓 | `data/derived/curated/{year}.geojson`、`curated-boundaries/{year}.geojson` |
| 未改动拼合地图 | `data/derived/merged/{year}.geojson`、`boundaries/{year}.geojson` |
| 原始 PNG | `data/raw/toolbay/t/{tile}/{year}.png`（1006 图块版本） |
| 项目修正规则 | `data/corrections.json`、`data/corrections/qing-southern-xinjiang.geojson` |
| 元数据／Schema | `data/metadata.json`、`schemas/dataset.schema.json` |
| 独立数据包 | `dist/cn-history-data.zip`，约 35 MiB，CI 重新生成 |

时间索引的 `start_year <= year < end_year`，`path` 指向该区间 GeoJSON，`boundary_path` 指向描边文件。-221 是前 221 年；9999 是原站结束时间未知的哨兵。坐标为 `[经度,纬度]`，EPSG:4326，焦点框 `[60,0,150,65]`，约 0.1° 像素。

GeoJSON 为 FeatureCollection，疆域 Polygon/MultiPolygon，名称锚点 Point，边界 LineString/MultiLineString。普通色块的 `polity_id=null`：原站没有可靠颜色与政权对应表。清朝人工修正 Feature 明确写入 polity_id、correction_ids、source_features。事件是阶段／任期／年号／图块更新推导，非战争叙事事件库。部分最早区间有政权标签但没有疆域色块。

## 清朝与名称修正（最近工作）

- 用户明确授权忽略原图中的错误，修正清朝实际辖区。
- 清辖蒙古从 1691 年起、西藏从 1720 年起、北疆从现有 1756 年变化节点起，与清朝主体统一填色和几何；蒙古止于 1911 年，其余止于 1912 年。
- 1756 是现有北疆地图节点；征服过程跨 1755—1757 年，南疆平定为 1759 年，不将其描述为全部新疆在 1756 年已平定。
- 南疆 1759—1864 年另行修正：使用后期 1884 年清疆轮廓与南疆窗口的交集，截取误归浩罕色块的喀什一带。没有合并费尔干纳浩罕主体；1864 年后起事／割据色块保持独立。
- 选取覆盖地理锚点的连通组件；不能简单将某颜色所有多边形一起并入清朝。
- 修正前后总体覆盖面积保持一致，统一清朝内部不再描政权边界。
- “満洲国／满洲国”→“伪满洲国”；“大日本帝国”→“日本国”。JSON、CSV、事件和标注位置数据同步修改，source_names/source_title 保存旧值。
- 清辖西藏阶段含 sovereign_entity_id，在网页／当前年标注导出中不作为独立政权显示。
- `scripts/correct.py` 可重跑；原始 PNG、source-arrays、未修正拼合层保留。

## 代码与复现

- `index.html`、`web/app.js`、`web/styles.css`：网页。
- `web/playback.js`：播放和长按控制；`web/icons.js`：SVG 图标；`web/timeline-layout.js`：单行标签避让。
- Leaflet 本地 vendored，EPSG:4326；禁止把原 PNG 当作 Web Mercator 瓦片。
- `scripts/extract.py`：原数据提取；`vectorize.py`：PNG 色块转换；`stitch.py`：同色跨图块合并并去裁剪框边线。
- `scripts/correct.py`：修正文字与输出 curated 时间索引；重提取／拼合之后必须运行。
- `scripts/snapshot.py --year 1800`：输出修正疆域与名称锚点。
- `scripts/package.py`：数据 ZIP；`scripts/build_site.py`：输出 _site，要求空目录。
- 忽略 artifacts/、dist/、_site/、缓存；data/** 在 Git 中禁用换行转换，保持原始数据校验值。

完整重建顺序：extract → vectorize → stitch → correct → snapshot → validate → package → build_site。只改文字／修正规则：correct → 测试 → validate → package。UI 修改无需重跑提取。

## 验证与工具

- Python：`C:\Python3\Python310\python.exe`，Node 24。
- Edge：`C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`，Playwright 已安装。
- `python -m unittest discover -s tests -v`：13 项通过，包含清朝锚点、非清同色区域、覆盖面积、边线、名称及快照一致性。
- `node --test tests/*.test.mjs`：10 项通过。
- `python scripts/validate.py`：来源校验、Schema、651 未修正区间与 curated 校验；最近完整验证通过，随后南疆增补有独立测试，CI 正在复核最新版本。
- `python scripts/browser_check.py`：桌面／手机／全屏／主题／导出／键盘回归通过；新增清朝导出与名称检查。
- CI 在 Linux 安装 Chromium，检查 `_site` 子目录，再部署 Pages；需要等部署完成并线上检查后才称已上线。

## 后续建议

1. 优先继续维护 data/corrections.json，而非直接涂改原始图片或在前端硬编码归属。
2. 若增加历史边界，提供独立 GeoJSON 及明确有效区间、来源或修正说明；避免以颜色推断所有政权。
3. Schema 当前区分原始拼合层的结构，人工修正额外属性见 DATA_FORMAT.md；可后续补充 curated 专用 Schema。
4. 当前没有待处理用户界面需求；用户最新要求为保存开发状态并解释数据格式。
