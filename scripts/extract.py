"""Archive Toolbay's public historical atlas and export independent datasets.

No downloaded JavaScript is executed. JSON5 parses only array literals.
Run from any directory; all paths resolve relative to this repository.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.request import Request, urlopen

import json5
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/toolbay"
OUT = ROOT / "data/normalized"
BASE = "https://www.toolbay.cc/history-map/"
MIN_YEAR, MAX_YEAR = -4000, 2017
DEFAULT_BBOX = [60, 0, 150, 65]
TEXT_PATHS = ["index.html", "js/era.js?v=2", "js/territory.js?v=2",
              "js/regions.js?v=2", "js/Region.js?v=2", "js/Map.js?v=2",
              "js/twha.js?v=2", "js/YearBar.js?v=2", "style.css"]


def write_json(path, value, pretty=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False,
                              indent=2 if pretty else None,
                              separators=None if pretty else (",", ":")) + "\n", encoding="utf-8")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fetch(path, refresh=False):
    target = RAW / path.split("?")[0]
    if refresh or not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        for attempt in range(4):
            try:
                request = Request(BASE + path, headers={"User-Agent": "HistoricalDataResearch/1.0"})
                with urlopen(request, timeout=35) as response:
                    content = response.read()
                if path.endswith(".png"):
                    from io import BytesIO
                    with Image.open(BytesIO(content)) as im:
                        im.verify()
                partial = target.with_suffix(target.suffix + ".part")
                partial.write_bytes(content)
                partial.replace(target)
                break
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(1 + attempt * 2)
    return {"path": target.relative_to(ROOT).as_posix(), "url": BASE + path,
            "bytes": target.stat().st_size, "sha256": digest(target),
            "retrieved_at": datetime.fromtimestamp(target.stat().st_mtime, timezone.utc).isoformat()}


def parse_arrays(path):
    source = path.read_text(encoding="utf-8-sig")
    declarations = list(re.finditer(r"(?m)^\s*var\s+(\w+)\s*=\s*", source))
    result = {}
    for index, match in enumerate(declarations):
        end = declarations[index + 1].start() if index + 1 < len(declarations) else len(source)
        literal = source[match.end():end].strip().removesuffix(";")
        value = json5.loads(literal)
        if not isinstance(value, list):
            raise ValueError(f"Expected an array: {path}:{match[1]}")
        result[match[1]] = value
    if not result:
        raise ValueError(f"No array declarations found: {path}")
    return result


def names(values):
    ja, en, zh = (list(values) + [None, None, None])[:3]
    if ja == "$":
        ja = en
    if en == "@":
        en = ja
    if zh == "$":
        zh = en
    if zh == "@":
        zh = ja
    return {"ja": ja, "en": en, "zh": zh}


def lonlat(x, y):
    return [round(x / 10 - 180, 6), round(90 - y / 10, 6)]


def in_bbox(point, bbox):
    return bool(point and bbox[0] <= point[0] <= bbox[2] and bbox[1] <= point[1] <= bbox[3])


def overlaps(a, b):
    return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]


def tile_bbox(x, y):
    return [x * 45 - 180, 90 - (y + 1) * 45, (x + 1) * 45 - 180, 90 - y * 45]


def source_ref(file, **indices):
    return {"file": file, **indices}


def normalize(regions, era_arrays, territory, bbox):
    entities, rulers, eras, events, tiles, issues = [], [], [], [], [], []

    def issue(kind, record_id, **extra):
        issues.append({"kind": kind, "record_id": record_id, **extra})

    def event(kind, year, record_id, title, reference, entity_id=None):
        if MIN_YEAR <= year <= MAX_YEAR:
            events.append({"id": f"{kind}:{record_id}", "kind": kind, "year": year,
                           "title": title, "entity_id": entity_id, "record_id": record_id,
                           "derived": True, "source": reference})

    for index, row in enumerate(regions):
        eid = f"toolbay-region-{index:04d}"
        entity = {"id": eid, "start_year": row[1], "end_year": row[2],
                  "open_ended": row[2] == 9999, "periods": [],
                  "source": source_ref("js/regions.js", region_index=index)}
        name = abbr = position = pixel = level = None
        role, in_people = None, False
        for ri, item in enumerate(row[3:], start=3):
            ref = source_ref("js/regions.js", region_index=index, row_index=ri)
            if len(item) == 3:
                role, in_people = names(item), True
                continue
            if len(item) < 4:
                raise ValueError(f"Unexpected region row {index}/{ri}: {item}")
            if len(item) not in (6, 9, 12):
                issue("unexpected_row_length", f"{eid}-row-{ri}", length=len(item), raw=item)
            if not in_people:
                if item[3]:
                    name = names(item[3:6])
                if len(item) >= 9 and item[6]:
                    abbr = names(item[6:9])
                if len(item) >= 12:
                    pixel = item[9:11]
                    position = lonlat(*pixel)
                    level = item[11]
                pid = f"{eid}-period-{ri:03d}"
                period = {"id": pid, "entity_id": eid, "start_year": item[0],
                          "end_year": item[1], "open_ended": item[1] == 9999,
                          "names": name, "abbreviations": abbr, "symbol_key": item[2],
                          "label_position": position, "source_pixel": pixel,
                          "display_level": level, "source": ref}
                entity["periods"].append(period)
                if item[0] >= item[1]:
                    issue("non_positive_period", pid, start_year=item[0], end_year=item[1])
                event("polity_start" if ri == 3 else "polity_change", item[0], pid,
                      f"{name['zh'] or name['en']} · {'记录开始' if ri == 3 else '阶段变化'}", ref, eid)
            else:
                rid = f"{eid}-ruler-{ri:04d}"
                ruler = {"id": rid, "entity_id": eid, "start_year": item[0],
                         "end_year": item[1], "open_ended": item[1] == 9999,
                         "names": names(item[3:6]), "role": role, "portrait_key": item[2], "source": ref}
                rulers.append(ruler)
                if item[0] >= item[1]:
                    issue("non_positive_reign", rid, start_year=item[0], end_year=item[1])
                event("ruler_start", item[0], rid, f"{ruler['names']['zh']} · 任期开始", ref, eid)
                event("ruler_end", item[1], rid, f"{ruler['names']['zh']} · 任期结束", ref, eid)
        if not entity["periods"]:
            issue("entity_without_periods", eid)
        else:
            last = entity["periods"][-1]
            event("polity_end", row[2], eid, f"{last['names']['zh']} · 记录结束", entity["source"], eid)
            for previous, current in zip(entity["periods"], entity["periods"][1:]):
                if previous["end_year"] != current["start_year"]:
                    issue("non_contiguous_periods", current["id"], previous_end=previous["end_year"],
                          current_start=current["start_year"])
        entity["in_focus"] = any(in_bbox(p["label_position"], bbox) for p in entity["periods"])
        entities.append(entity)

    for key, lanes in era_arrays.items():
        for lane_index, lane in enumerate(lanes):
            for ri, (year, label) in enumerate(lane):
                end = lane[ri + 1][0] if ri + 1 < len(lane) else 9999
                era_id = f"toolbay-{key}-{lane_index}-{ri:03d}"
                ref = source_ref("js/era.js", variable=key, lane_index=lane_index, row_index=ri)
                # Null markers explicitly terminate an era; retained in the original arrays.
                if label is None:
                    continue
                record = {"id": era_id, "country": "cn" if key == "era_cn" else "jp",
                          "lane": lane_index, "name": label, "start_year": year,
                          "end_year": end, "open_ended": end == 9999, "source": ref}
                eras.append(record)
                if year >= end:
                    issue("non_positive_era", era_id, start_year=year, end_year=end)
                event("era_start", year, era_id, f"{label} · 年号开始", ref)

    for x, columns in enumerate(territory):
        for y, original_years in enumerate(columns):
            tile_id = f"{x}{y}"
            years = sorted({MIN_YEAR, *original_years})
            if len(original_years) != len(set(original_years)):
                issue("duplicate_tile_year", tile_id)
            bounds = tile_bbox(x, y)
            records = []
            for yi, year in enumerate(years):
                path = f"t/{tile_id}/{year}.png"
                records.append({"start_year": year,
                                "end_year": years[yi + 1] if yi + 1 < len(years) else MAX_YEAR + 1,
                                "path": "data/raw/toolbay/" + path, "source_url": BASE + path,
                                "vector_path": f"data/derived/territories/{tile_id}/{year}.geojson"})
                event("territory_change", year, f"tile-{tile_id}-{year}", f"疆域图块 {tile_id} 更新",
                      source_ref("js/territory.js", x=x, y=y, image=path))
            tiles.append({"id": tile_id, "x": x, "y": y, "bbox": bounds,
                          "in_focus": overlaps(bounds, bbox), "snapshots": records})
    events.sort(key=lambda e: (e["year"], e["kind"], e["id"]))
    return entities, rulers, eras, events, tiles, issues


def export_csv(path, rows, fields):
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def export(bbox):
    regions = parse_arrays(RAW / "js/regions.js")["region_list"]
    era_arrays = parse_arrays(RAW / "js/era.js")
    territory = parse_arrays(RAW / "js/territory.js")["territory"]
    write_json(ROOT / "data/source-arrays.json", {"region_list": regions, "territory": territory, **era_arrays})
    entities, rulers, eras, events, tiles, issues = normalize(regions, era_arrays, territory, bbox)
    focus_ids = {e["id"] for e in entities if e["in_focus"]}
    focus_tiles = [t for t in tiles if t["in_focus"]]
    tile_ids = {t["id"] for t in focus_tiles}
    focus_events = [e for e in events if e["entity_id"] in focus_ids or e["kind"] == "era_start"
                    or (e["kind"] == "territory_change" and f"{e['source']['x']}{e['source']['y']}" in tile_ids)]
    for name, value in [("entities", entities), ("rulers", rulers), ("eras", eras), ("events", events),
                        ("territory-index", tiles)]:
        write_json(OUT / f"{name}.json", value)
    focus = {"entities": [e for e in entities if e["in_focus"]],
             "rulers": [r for r in rulers if r["entity_id"] in focus_ids], "eras": eras,
             "events": focus_events, "territory-index": focus_tiles}
    for name, value in focus.items():
        write_json(ROOT / "data/focus" / f"{name}.json", value)
    points = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "id": p["id"],
         "geometry": {"type": "Point", "coordinates": p["label_position"]},
         "properties": {**{k: v for k, v in p.items() if k != "label_position"},
                        "position_kind": "source_label_anchor_not_capital"}}
        for e in focus["entities"] for p in e["periods"] if p["label_position"]]}
    write_json(ROOT / "data/focus/polity-labels.geojson", points)
    OUT.mkdir(parents=True, exist_ok=True)
    export_csv(ROOT / "data/focus/polity-periods.csv", [
        {"id": p["id"], "entity_id": e["id"], "name_zh": p["names"]["zh"],
         "name_en": p["names"]["en"], "start_year": p["start_year"], "end_year": p["end_year"],
         "longitude": (p["label_position"] or [None, None])[0],
         "latitude": (p["label_position"] or [None, None])[1]}
        for e in focus["entities"] for p in e["periods"]],
        ["id", "entity_id", "name_zh", "name_en", "start_year", "end_year", "longitude", "latitude"])
    export_csv(ROOT / "data/focus/events.csv", [
        {k: e[k] for k in ["id", "kind", "year", "title", "entity_id", "record_id", "derived"]}
        for e in focus_events], ["id", "kind", "year", "title", "entity_id", "record_id", "derived"])
    export_csv(ROOT / "data/focus/rulers.csv", [
        {"id": r["id"], "entity_id": r["entity_id"], "name_zh": r["names"]["zh"],
         "name_en": r["names"]["en"], "role_zh": (r["role"] or {}).get("zh"),
         "start_year": r["start_year"], "end_year": r["end_year"]}
        for r in focus["rulers"]], ["id", "entity_id", "name_zh", "name_en", "role_zh", "start_year", "end_year"])
    metadata = {
        "schema_version": "1.0.0", "source": BASE + "index.html", "source_max_year": MAX_YEAR,
        "min_year": MIN_YEAR, "focus_bbox": bbox, "bbox_order": "west,south,east,north",
        "year_convention": "Historical signed years: -1=1 BCE, 1=1 CE; no year zero. Source values preserved.",
        "interval_convention": "start_year <= year < end_year; 9999 is the source open-ended sentinel, not a future claim",
        "entity_semantics": "A source region groups consecutive polity/name phases; it is not necessarily one continuous polity.",
        "focus_selection": "Any source label anchor inside bbox; retain the entity's complete history. Not a territory intersection test.",
        "georeferencing": {"crs": "EPSG:4326", "image_size": [3600, 1800], "tile_size": [450, 450],
                           "pixel_size_degrees": 0.1, "longitude": "x / 10 - 180", "latitude": "90 - y / 10",
                           "status": "inferred_equirectangular", "basis": "8x4 tile layout in Map.js and visual coastline alignment",
                           "accuracy": "Approximate raster map; source label anchors are not geocoded capitals."},
        "events": "Derived from record boundaries and image updates; source has no separate narrative event dataset.",
        "territories": "Raster color masks; no source polygon geometry or verified color-to-polity table.",
        "license": "No explicit reuse license identified in downloaded source files. Source rights remain with their owners.",
        "counts": {"global_entities": len(entities), "global_periods": sum(len(e["periods"]) for e in entities),
                   "global_rulers": len(rulers), "global_events": len(events), "eras": len(eras),
                   "focus_entities": len(focus["entities"]), "focus_periods": len(points["features"]),
                   "focus_rulers": len(focus["rulers"]), "focus_events": len(focus_events),
                   "focus_tiles": len(focus_tiles), "focus_snapshots": sum(len(t["snapshots"]) for t in focus_tiles),
                   "source_issues": len(issues)}}
    write_json(ROOT / "data/metadata.json", metadata, pretty=True)
    write_json(ROOT / "data/source-issues.json", issues, pretty=True)
    print(json.dumps(metadata["counts"], ensure_ascii=False, indent=2), flush=True)
    return focus_tiles


def archive_tiles(tiles, workers):
    paths = [f"sf/{t['id']}.png" for t in tiles]
    paths += [s["path"].removeprefix("data/raw/toolbay/") for t in tiles for s in t["snapshots"]]
    entries, errors = [], []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fetch, path): path for path in paths}
        for index, future in enumerate(as_completed(futures), start=1):
            try:
                entries.append(future.result())
            except Exception as exc:
                errors.append({"path": futures[future], "error": str(exc)})
            if index % 50 == 0 or index == len(paths):
                print(f"Archived {index}/{len(paths)}; errors={len(errors)}", flush=True)
    write_json(RAW / "tile-manifest.json", sorted(entries, key=lambda e: e["path"]), pretty=True)
    write_json(RAW / "download-errors.json", errors, pretty=True)
    if errors:
        raise RuntimeError(f"{len(errors)} downloads failed; rerun to resume. See download-errors.json")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bbox", type=float, nargs=4, default=DEFAULT_BBOX, metavar=("WEST", "SOUTH", "EAST", "NORTH"))
    parser.add_argument("--download-tiles", action="store_true", help="Archive every change snapshot intersecting the focus bbox")
    parser.add_argument("--offline", action="store_true", help="Normalize existing local source files only")
    parser.add_argument("--refresh", action="store_true", help="Refetch source JS/HTML (tiles remain cached)")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    w, s, e, n = args.bbox
    if not (-180 <= w < e <= 180 and -90 <= s < n <= 90):
        parser.error("bbox must be a non-wrapping longitude/latitude rectangle")
    if args.offline and (args.download_tiles or args.refresh):
        parser.error("--offline cannot be combined with network options")
    if not 1 <= args.workers <= 8:
        parser.error("workers must be between 1 and 8")
    if not args.offline:
        entries = [fetch(path, args.refresh) for path in TEXT_PATHS]
        write_json(RAW / "manifest.json", entries, pretty=True)
    tiles = export(args.bbox)
    if args.download_tiles:
        archive_tiles(tiles, args.workers)


if __name__ == "__main__":
    main()
