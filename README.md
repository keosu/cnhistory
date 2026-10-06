# 山河时序 · 中国与周边历史地图数据

从 https://www.toolbay.cc/history-map/index.html 提取原始历史数据，导出独立 JSON、CSV、GeoJSON 和原始 PNG，并提供一个完全读取本地文件的历史地图网页。

**核心成果是数据。** 中国及周边默认范围为东经 60°–150°、北纬 0°–65°；全球文字资料和图块索引也保留。详细规则见 [DATA_FORMAT.md](DATA_FORMAT.md)。

| 数据 | 全球 | 中国及周边筛选 |
| --- | ---: | ---: |
| 来源政权组 | 1,063 | 439 |
| 政权名称／阶段 | 2,881 | 967 |
| 人物任期 | 20,396 | 4,472 |
| 推导变化记录 | 47,073 | 11,978 |
| 中国与日本年号 | 709 | 709 |
| 已归档疆域图块版本 | — | 1,006 |
| 已转换 GeoJSON 文件 | — | 1,006 |

这些文件包含 7,238 个“图块 × 年份 × 颜色”几何记录，并不是 7,238 个独立政权或完整年份地图。首次交付保留了原数据中的 88 条结构／时间异常报告。

展示时间从公元前 2000 年开始。新增 651 个拼合后的疆域版本，相邻同色区域已合并，消除图块之间的横竖接缝；完整原始资料仍保留。时间轴按真实年份比例标注 14 个主要朝代／历史阶段，标签保持单行并横向避让，点击可跳转，无需滚动导航。

## 查看网页

只需要 Python 3.10+；预览不需要安装提取依赖，不需要构建，也不需要联网：

```powershell
python scripts/serve.py --port 8000
```

打开 **http://127.0.0.1:8000**。静态文件也可以放在任意 HTTP 静态服务器上。不要直接双击 HTML 使用 `file://`，浏览器会限制读取 JSON。

网页使用新的 Natural Earth 地理底图和 Leaflet 地图引擎，支持：

- 年份输入、时间滑块、逐年前进／后退和自动播放；
- 0.5×、1×、2×、4×、8× 播放速度，1× 为每秒一年；速度可在播放中调整；
- 左右方向键或屏幕前后按钮逐年切换，长按逐渐加速，松手、窗口失焦或页面隐藏时停止；输入框编辑不拦截方向键；
- 浅色、深色、纸色、琉璃、朱砂、霓虹六套主题，界面、地图背景和疆域配色同步切换，主题和速度保存在本机浏览器；
- 前进、播放、后退、播放速度和年份输入集中在顶部居中；
- 播放、主题、图层和地图工具统一使用 SVG 图标按钮；支持整个应用进入／退出浏览器全屏；
- 近似边界、原始图像与纯底图三种视图；
- 查找政权、人物及年号，查看人物任期；
- 浏览阶段、人物、年号和疆域图块变化，点击跳转年份；
- 下载独立数据或当前年份的 GeoJSON；顶部面板图标可展开／收起历史记录，地图随可用空间调整；桌面和手机分别记住面板状态；
- 页面和导航不显示滚动条，长记录列表仍可在面板内用滚轮或触摸滑动浏览。

## 直接取用数据

- **[完整数据包](dist/cn-history-data.zip)**：包含原始与整理后数据、格式文档及 Schema，解压后保留 `data/` 相对路径即可使用。
- [元数据](data/metadata.json)：统计、空间范围和纪年规则。
- [政权阶段 CSV](data/focus/polity-periods.csv)、[人物任期 CSV](data/focus/rulers.csv)、[变化事件 CSV](data/focus/events.csv)：可用 Excel 打开。
- [政权 JSON](data/focus/entities.json)、[时间变化 JSON](data/focus/events.json)、[修正后疆域时间索引](data/focus/territory-timeline.curated.json)：用于其他程序；[修正规则](data/corrections.json) 记录清朝辖区与名称修正。
- [618 年疆域 GeoJSON](data/derived/snapshots/618.geojson)、[618 年政权标注点](data/derived/snapshots/618.labels.geojson)：直接导入 GIS 或其他地图框架。

## GitHub Pages 发布

正式网址：**https://keosu.github.io/cnhistory/**；仓库：**https://github.com/keosu/cnhistory**。

推送到 `main` 会运行数据与几何检查、时间轴测试和 Chromium 浏览器验收，重新生成独立数据 ZIP，随后将静态网页和数据部署到 Pages。PR 运行同样的检查。工作流位于 `.github/workflows/pages.yml`；Pages 的构建来源设为 **GitHub Actions**。

数据源文件纳入 Git，`dist/` 数据包、`_site/` 发布目录和 `artifacts/` 检查截图由程序生成。需要本地生成发布文件时运行：

```powershell
python scripts/package.py
python scripts/build_site.py
```

所有资源使用相对路径，可部署在 `/cnhistory/` 等子目录。CI 会检查暂存网站的子目录访问。

清朝辖区和中文名称修正记录在 `data/corrections.json`，修正地图索引为 `data/focus/territory-timeline.curated.json`。重新提取或拼合数据后运行 `python scripts/correct.py`，再生成快照和数据包。

## 重跑提取与转换

```powershell
python -m pip install -r requirements.txt
python scripts/extract.py --download-tiles --workers 4
python scripts/vectorize.py
python scripts/stitch.py
python scripts/correct.py
python scripts/snapshot.py --year 618
python scripts/validate.py
python scripts/package.py
```

提取器有缓存、限量并发、失败重试和 SHA-256 归档；下载失败会留下明确清单并以非零状态退出，可重跑续传。读取 JavaScript 时只解析数组字面量，不执行网站代码。首次下载约 1,000 个小文件，耗时主要取决于网络。

只重新整理已经保存的原始数据：

```powershell
python scripts/extract.py --offline
```

调整地理范围：

```powershell
python scripts/extract.py --bbox 70 5 145 60 --download-tiles
python scripts/vectorize.py
python scripts/stitch.py
```

修改范围会重写 `focus` 文件和相关输出；数据目录中可能保留旧范围缓存。使用最新索引和 manifest 选取文件，重建已有年份快照与数据包。全球范围可用 `--bbox -180 -90 180 90`，但会增加下载量。

其他年份单独导出：

```powershell
python scripts/snapshot.py --year -221 --output exports/qin
python scripts/snapshot.py --year 1279 --output exports/yuan
```

生成的一个文件保存疆域色块，另一个文件保存当年的政权标注点，不依赖网页。

## 边界与事件的准确含义

原站的疆域是 PNG，**没有提供政权 GeoJSON，也没有给出颜色与政权的可靠对应表**。本项目逐像素追踪色块，保留岛屿与孔洞，生成近似几何，并明确设置 `polity_id=null`。经纬度配准根据图块布局和海岸线推定，每像素约 0.1°；不是测绘级或经过史学审定的疆域。名称标注点不能当作首都坐标。

原站没有独立的战争、条约、迁都等叙事事件表。本项目的“变化事件”由政权阶段、任期、年号和图片更新时间推导，全部标记 `derived=true`，不推断变化的历史原因。

时间范围前 4000—2017 年，无公元 0 年；区间左闭右开；`9999` 仅表示来源未给出终止时间。来源中的拼写、异常年份和字段缺失保留在原始文件与 [问题清单](data/source-issues.json) 中。

## 检查

```powershell
python -m unittest discover -s tests -v
python scripts/validate.py
node --test tests/playback.test.mjs tests/timeline-layout.test.mjs
```

测试覆盖语言引用及继承、任期角色、异常保留、安全数组解析、图块时间选择、公元零年、岛屿／孔洞、空间裁剪与横竖拼接线消除，并将 618、1279、1644 年拼合后的疆域重新栅格化，逐像素核对原图。全量验证另检查 651 个完整疆域版本的校验值、来源引用与面积保持。

浏览器验收脚本需要额外的 Playwright，可使用本机 Edge，或指定浏览器路径：

```powershell
python -m pip install playwright
python scripts/browser_check.py
```

服务需已在 8000 端口运行。浏览器检查包含单行时间轴刻度比例和标签防重叠、顶部居中播放控件、全屏、面板显隐与地图调整、图标菜单、主题持久化、播放速度切换、方向键和长按、松手／失焦停止、输入框编辑，以及 320／390 像素移动布局。结果和六套主题截图保存在 `artifacts/`。本机默认使用 Edge，Linux 使用 Playwright 安装的 Chromium。数据与代码的转换不会改变上游资料的权利归属；来源说明见 [DATA_FORMAT.md](DATA_FORMAT.md)。
