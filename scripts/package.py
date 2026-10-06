"""Build a portable data-only zip, with all paths kept intact."""
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    output = ROOT / "dist/cn-history-data.zip"
    output.parent.mkdir(exist_ok=True)
    files = [p for folder in ("data", "schemas") for p in (ROOT / folder).rglob("*") if p.is_file()]
    files += [ROOT / "DATA_FORMAT.md"]
    with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(files):
            archive.write(path, path.relative_to(ROOT).as_posix())
        archive.writestr("README.md", "# 中国与周边历史地图 · 独立数据包\n\n"
                         "先阅读 DATA_FORMAT.md 和 data/metadata.json。\n\n"
                         "data/focus/ 是中国与周边的数据；data/normalized/ 保留全球文字和图块索引；"
                         "data/raw/ 保留来源脚本及本次下载的原图；data/derived/ 是近似疆域 GeoJSON。"
                         "本包仅包含数据、格式说明和 schemas，不含网站或提取程序。\n\n"
                         "保留 data/ 相对路径即可使用，格式说明末尾的示例只需要 Python 标准库。"
                         "data/derived/snapshots/618.geojson 是可直接加载的 618 年疆域示例。\n\n"
                         "注意：边界由 PNG 色块推算，polity_id 为 null；事件为来源记录边界的推导，"
                         "不是战争事件库；资料显示上限为 2017 年，原始异常未擅自修正。\n")
    report = {"path": output.relative_to(ROOT).as_posix(), "files": len(files)+1,
              "bytes": output.stat().st_size, "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}
    output.with_suffix(".manifest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
