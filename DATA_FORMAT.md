# 历史地图数据格式 v1.0

本数据集将 [Toolbay 历史时间线](https://www.toolbay.cc/history-map/index.html) 的公开静态资源转换成独立文件。抓取日期见 `data/raw/toolbay/*manifest.json`。原站声明的显示范围为公元前 4000 年至公元 2017 年。文件使用 UTF-8；CSV 带 UTF-8 BOM，方便 Excel 打开。

## 文件与关系

| 文件 | 内容 | 如何使用 |
| --- | --- | --- |
| `data/metadata.json` | 范围、坐标、时间规则、数量和局限 | 应首先读取 |
| `data/source-arrays.json` | 原始 JavaScript 数组的无损 JSON 表达 | 保留行次序、占位符、异常值；不执行脚本 |
| `data/normalized/entities.json` | 全球来源政权组及阶段 | 组内 `periods` 给出各阶段名称、标注位置 |
| `data/normalized/rulers.json` | 全球人物及任期 | `entity_id` 关联政权组，不代表独立人物数据库 |
| `data/normalized/eras.json` | 中国和日本年号 | `lane` 区分原站并行年号序列 |
| `data/normalized/events.json` | 从各类记录生成的变化节点 | `derived=true`，不是战争或条约事件库 |
| `data/normalized/territory-index.json` | 全球 32 个图块的版本索引 | 全球仅保存索引；本次只下载焦点范围的图像 |
| `data/focus/` | 中国及周边的上述文件子集、CSV | 新地图默认读取此目录 |
| `data/navigation.json` | 前 2000 年起的展示范围、14 个主要阶段及详细分界 | `primary_periods` 用于网页；`periods` 保留更详细的 31 个阶段，不修改原站政权记录 |
| `data/focus/territory-timeline.json` | 拼合后的 651 个完整疆域版本时间索引 | 推荐用于地图，每个区间直接加载一个文件 |
| `data/focus/polity-labels.geojson` | 每个政权阶段的名称标注点 | 点是原图标签锚点，不能当作首都坐标 |
| `data/raw/toolbay/t/{tile}/{year}.png` | 原始疆域图块 | 不同图块有不同的更新时间 |
| 同目录 `.pgw`、`.prj` | PNG 地理定位与坐标参考文件 | 可尝试在 QGIS 等 GIS 中加载；配准为推定 |
| `data/derived/territories/{tile}/{year}.geojson` | 按颜色追踪的疆域近似多边形 | 与图像逐一对应，图块外裁剪到焦点范围 |
| `data/derived/merged/{year}.geojson` | 同年相邻同色区域合并后的完整疆域 | 消除内部图块拼接线，保留每个来源图块引用 |
| `data/derived/boundaries/{year}.geojson` | 对应疆域的展示边界线 | 剔除裁剪框边线，避免把展示范围描成国界 |
| `data/derived/manifest.json` | 转换方法、排除颜色、文件校验值 | 核对输出和对应原图 SHA-256 |
| `data/derived/snapshots/{year}.geojson` | 合并图块后的指定年疆域 | 由 `scripts/snapshot.py` 生成 |
| `data/source-issues.json` | 原始数据异常 | 保留原值，并列出异常记录编号 |

`data/focus/entities.json` 不是“中国政权白名单”。默认选取任一阶段标注点落在 `[60, 0, 150, 65]` 内的来源分组，并保留该组完整历史。这一空间范围涵盖中国、朝鲜半岛、日本、蒙古、中亚部分地区、印度及东南亚大陆等。它按标签位置筛选，不是用疆域相交筛选，不能保证覆盖所有曾控制这一范围的政权。

原图块是 45° × 45°；下载 `50/51/60/61/70/71` 六个相交图块的全部 1,006 个版本，实际原图范围因此大于焦点框。GeoJSON 已裁剪到焦点框；原始图像视图展示完整图块。

## 时间规则

网页和当前年份导出采用 `data/focus/territory-timeline.curated.json`，引用修正后的 `curated/`、`curated-boundaries/` 文件及未改动年份的拼合层。`data/corrections.json` 记录清辖蒙古从 1691 年起、西藏从 1720 年起、北疆从现有 1756 年变化节点起与清朝主体合并；蒙古规则止于 1911 年，其他规则止于 1912 年。1756 是本项目采用的北疆地图节点，准噶尔征服过程跨 1755—1757 年，南疆平定完成于 1759 年。地理标注点只选中连通组件，其他同色政权和后期不同颜色表示的割据区域保持独立；没有将整个中亚或浩罕汗国并入清朝。

修正 Feature 的 `polity_id` 为 `toolbay-region-0728`，`polity_assignment` 为 `project_editorial_correction`，`geometry_origin` 为 `curated_component_union`，附有 `correction_ids` 和 `source_features`。中文名称将“満洲国／满洲国”改为“伪满洲国”、“大日本帝国”改为“日本国”；JSON、CSV、标注点和事件标题一致更新，`source_names`、`source_abbreviations`、`source_title` 保留改名前值。清辖西藏阶段另含 `sovereign_entity_id`，不作为独立政权标签显示。`scripts/correct.py` 可重复运行；原始 PNG 与未经修正的拼合层仍可独立取用。

网页和拼合时间索引从 **公元前 2000 年**开始；原始文件、规范化文字数据和原图块索引保留原站更早记录。`data/navigation.json` 的 `primary_periods` 给出网页使用的 14 个主要阶段：夏、商、周、秦、汉、魏晋、南北朝、隋、唐、宋、元、明、清、近现代；这是粗粒度导航分组，不是连续政权认定。`periods` 另保留 31 个详细朝代／阶段，使用通行分期，夏商早期年代标为近似。夏的起始年代早于展示范围，因此导航跳到前 2000 年。宋辽夏金等时期可以重叠；导航年份不改写原站政权时间和疆域，例如原站商的阶段从前 1500 年起，而导航采用约前 1600 年。

- 使用历史纪年整数：`-221` 表示公元前 221 年，`1` 表示公元 1 年，不采用天文学年编号，没有公元 0 年。原始数据中的值原样保存。
- 时间区间统一为左闭右开：`start_year <= year < end_year`。
- `end_year=9999` 是原站“尚未结束”的哨兵，同时保留 `open_ended=true`。这不是延续至未来的历史断言。资料的可用上限仍为 **2017 年**。
- 年粒度会损失同一年内的更替顺序。零长度、倒置、间断、重叠等异常不静默纠正。
- 原站的 `Region.js` 对有异常的阶段序列仅按结束年份寻找阶段，可能越过明确的开始年份。新页面使用明确的区间，重叠时采用来源顺序中第一条匹配记录，所以少数异常年份可能与原站显示不同。
- `9999` 不生成结束事件。图块索引的最后版本结束值为 `2018`，使 `2017` 可以正常查询。

取某年疆域时，每块独立选择“不晚于目标年”的最后一个版本，不能要求所有图块的文件名年份相同。例如 618 年，某图块可能沿用 602 年或更早的文件。

## 政权、阶段与人物

来源 `region_list[i]` 是一个区域／政权演变分组，并不一定是同一政权实体。例如第一组包含“黄河文明”和“商”。因此 `entities.json` 用 `periods` 保留这种分组，不把整组错误命名为一个朝代。

```json
{
  "id": "toolbay-region-0000",
  "start_year": -4000,
  "end_year": -1046,
  "open_ended": false,
  "in_focus": true,
  "periods": [
    {
      "id": "toolbay-region-0000-period-004",
      "entity_id": "toolbay-region-0000",
      "start_year": -1500,
      "end_year": -1046,
      "open_ended": false,
      "names": {"ja": "商(殷)", "en": "Shang(Yin)", "zh": "商(殷)"},
      "abbreviations": {"ja": "商", "en": "Shang", "zh": "商"},
      "symbol_key": null,
      "label_position": [114, 34.5],
      "source_pixel": [2940, 555],
      "display_level": 0,
      "source": {"file": "js/regions.js", "region_index": 0, "row_index": 4}
    }
  ],
  "source": {"file": "js/regions.js", "region_index": 0}
}
```

上例省略了本组更早的阶段。`names` 和 `abbreviations` 分别是全称与简称，语言键为 `ja/en/zh`。原数组用 `@` 引用日文、`$` 引用英文；导出时按 `Region.js` 的次序解析，并继承前一阶段未重设的名字、简称和位置。名称内容保留来源文本，包括未翻译名称、错字、日文汉字与空格。

`rulers.json` 每条记录是一段任期，不是经过去重的人物。字段有 `id/entity_id/start_year/end_year/open_ended/names/role/portrait_key/source`。`role` 也是 `ja/en/zh` 三语对象；一个分组可以同时存在君主、首相等不同角色。仅提取了人物、符号的资源键，**未下载头像与旗帜**。

ID 使用来源数组与行索引，同一份源快照内确定、可追溯。若原站插入或删除行，后续 ID 可能改变；跨版本合并不能假设它是永恒的政权／人物编号。

## 年号与变化事件

年号字段为 `id/country/lane/name/start_year/end_year/open_ended/source`。`country` 为 `cn` 或 `jp`；并行年号允许同时有效。原始的 `null` 条目表示前一年号结束，保存在 `source-arrays.json` 中；规范化文件只保留有名称的条目。

事件字段：

| 字段 | 说明 |
| --- | --- |
| `id` | 事件类型与记录编号组合 |
| `kind` | `polity_start`、`polity_change`、`polity_end`、`ruler_start`、`ruler_end`、`era_start`、`territory_change` |
| `year` | 发生变化的来源年份 |
| `title` | 从名称和变化类型生成的展示文字 |
| `entity_id` | 所属来源政权组；年号和图块变化为 `null` |
| `record_id` | 所关联的阶段、任期、年号或图块版本编号 |
| `derived` | 固定 `true`，明确标识推导记录 |
| `source` | 原始文件与数组索引；图块事件另含图片路径 |

政权阶段变化也可能只是名称、国旗或标签位置的变更；图块更新也不能直接断言发生了战争。源资料不提供疆域变化的原因，不能据此建立“某场事件导致某条边界”的可靠因果关系。

## 坐标与多边形

从 `Map.js` 的 8 × 4 个 450 像素图块以及海岸线对齐推定原图采用等距圆柱布局，总尺寸 3600 × 1800 像素：

```text
longitude = x / 10 - 180
latitude  = 90 - y / 10
```

经纬度顺序为 `[longitude, latitude]`，输出采用 GeoJSON 的 WGS84 经纬度约定。**原站没有提供 CRS 元数据或测量控制点**，所以这里是推定配准，不是测绘级坐标转换。0.1° 是像素分辨率，不是历史边界误差的上界。

图像边界用于多边形追踪；`.pgw` 的原点使用左上像素中心，因此存在合理的 0.05° 半像素偏移。没有把 Web Mercator 直接套在 PNG 上；网页使用 Leaflet 的 EPSG:4326 坐标系统，使两种展示方式同位。

转换使用原始 RGB 色块：排除海洋 `#39c1ff`、白色无分配区域 `#ffffff` 和透明像素，保留小岛、孔洞和断开的部分。默认不简化，逐像素边缘追踪；然后按图块、年份、颜色组合为 Polygon 或 MultiPolygon，并裁剪到焦点框。这个中间层保留原图块分块。

`scripts/stitch.py` 再按每个变化年份取出六个有效图块，联合相同颜色的几何，消除经线／纬线方向的图块内部接缝，不使用缓冲或平滑，不改变覆盖面积。结果在 `merged/`，每个 Feature 的 `sources` 数组保留参与联合的原图块 Feature 编号、时间、图片路径和 URL；`geometry_origin` 为 `raster_color_trace_stitched`，外层时间是完整快照的有效区间。同色联合仍不代表政权归属核定，`polity_id` 保持 `null`。展示使用独立 `boundaries/` 线层，其边界已去掉焦点裁剪框，填色层不描边。网页颜色经过柔化；GeoJSON 的 `source_color` 保留原 RGB。

每个 Feature 的属性：

```json
{
  "tile_id": "61",
  "start_year": 618,
  "end_year": 619,
  "source_image": "data/raw/toolbay/t/61/618.png",
  "source_url": "https://www.toolbay.cc/history-map/t/61/618.png",
  "source_color": "#009900",
  "polity_id": null,
  "polity_assignment": "unverified",
  "geometry_origin": "raster_color_trace",
  "pixel_size_degrees": 0.1,
  "source_color_pixels": 13260,
  "simplification_degrees": 0
}
```

`source_color_pixels` 是原始整张图内该颜色的像素数，**不是裁剪后的面积**。同一颜色可能对应多个无关政权；一个政权也可能跨多个图块或色块。所有 `polity_id` 明确为 `null`，名称标注点独立存放。后续若要建立真正的政权边界库，应另建人工核定的关联表，注明核定来源与依据，保留当前色块数据作为证据。

## 在其他项目中使用

无需本项目网页，任何 GeoJSON 库都可直接读取文件。以下 Python 代码仅依赖标准库，读取已去除图块接缝的 618 年完整疆域：

```python
import json
from pathlib import Path

root = Path(".")  # 解压后包含 data/ 的目录
year = 618
index = json.loads((root / "data/focus/territory-timeline.json").read_text(encoding="utf-8"))
snapshot = next(s for s in index if s["start_year"] <= year < s["end_year"])
collection = json.loads((root / snapshot["path"]).read_text(encoding="utf-8"))
Path("618.geojson").write_text(json.dumps(collection), encoding="utf-8")
```

`schemas/dataset.schema.json` 提供主要记录的 JSON Schema 定义，分别引用 `#/$defs/entity`、`period`、`ruler`、`era`、`event`、`tile`、`territoryFeature`、`stitchedFeature`。完整审计结果见 `artifacts/validation.json`。异常值保留不等于已修订；验证通过只说明结构、引用、归档完整性及几何有效性通过检查。

来源页面与下载的代码没有发现明确的历史数据再利用许可声明；转换不会改变原始资料的权利归属。Natural Earth 底图为公有领域，Leaflet 的许可另存于 `web/vendor/leaflet/LICENSE`。
