"""Apply project name/sovereignty corrections and export a reusable map timeline."""
from copy import deepcopy
from bisect import bisect_right
import json
import re

from shapely import box, orient_polygons, union_all
from shapely.geometry import Point, mapping, shape

from extract import ROOT, digest, write_json, export_csv
from vectorize import rounded


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def corrected_geometry(collection, year, end_year, bbox, rules):
    """Merge anchored Qing components, never every polygon of the same color."""
    active = [rule for rule in rules["qing_regions"] if rule["start_year"] <= year < rule["end_year"]]
    result = deepcopy(collection)
    if not active:
        return result, [], []
    parts = [(feature, part) for feature in collection["features"]
             for part in (list(shape(feature["geometry"]).geoms)
                          if feature["geometry"]["type"] == "MultiPolygon"
                          else [shape(feature["geometry"])])]
    qing = next(((feature, part) for feature, part in parts
                 if part.covers(Point(rules["qing_anchor"]))), None)
    if qing is None:
        raise ValueError(f"Qing anchor missing at {year}")
    selected = [(qing[0], qing[1], "qing-core")]
    for rule in active:
        target = next(((feature, part) for feature, part in parts
                       if feature["properties"]["source_color"] == rule["source_color"]
                       and part.covers(Point(rule["anchor"]))), None)
        if target and not any(part.equals(target[1]) for _, part, _ in selected):
            selected.append((*target, rule["id"]))
    if len(selected) == 1:
        return result, [], []
    corrected, source_refs = [], []
    claimed = union_all([part for _, part, _ in selected], grid_size=0.000001)
    for feature in collection["features"]:
        geometry = shape(feature["geometry"])
        selected_here = [part for source, part, _ in selected if source["id"] == feature["id"]]
        if selected_here:
            geometry = geometry.difference(union_all(selected_here))
            source_refs.append({"feature_id": feature["id"], "source_color": feature["properties"]["source_color"]})
        if not geometry.is_empty:
            item = deepcopy(feature)
            item["geometry"] = rounded(mapping(orient_polygons(geometry)))
            item["bbox"] = rounded(geometry.bounds)
            item["properties"].update(start_year=year, end_year=end_year)
            corrected.append(item)
    corrected.append({"type": "Feature", "id": f"curated:qing:{year}",
                      "bbox": rounded(claimed.bounds), "geometry": rounded(mapping(orient_polygons(claimed))),
                      "properties": {"start_year": year, "end_year": end_year,
                                     "source_color": qing[0]["properties"]["source_color"],
                                     "polity_id": rules["qing_entity_id"], "name_zh": "清",
                                     "polity_assignment": "project_editorial_correction",
                                     "geometry_origin": "curated_component_union",
                                     "correction_ids": [rule["id"] for rule in active],
                                     "source_features": source_refs}})
    border = union_all([shape(f["geometry"]).boundary for f in corrected]).difference(box(*bbox).boundary)
    lines = [] if border.is_empty else [{"type": "Feature", "id": f"curated-boundaries:{year}",
             "geometry": rounded(mapping(border)), "properties": {"start_year": year, "end_year": end_year}}]
    return {"type": "FeatureCollection", "features": corrected}, lines, source_refs


def correct_names(rules):
    replacements = rules["name_replacements_zh"]
    pattern = re.compile(r"(?<!伪)(?:" + "|".join(map(re.escape, replacements)) + ")")
    def rename(value):
        return pattern.sub(lambda match: replacements[match.group()], value) if value is not None else value
    subordinate = {rule["period_id"]: rule for rule in rules["subordinate_periods"]}
    for scope in ("normalized", "focus"):
        entities = read(f"data/{scope}/entities.json")
        for entity in entities:
            for period in entity["periods"]:
                for field in ("names", "abbreviations"):
                    if period.get(field):
                        current = period[field]["zh"]
                        revised = rename(current)
                        if revised != current:
                            period.setdefault("source_" + field, deepcopy(period[field]))
                            period[field]["zh"] = revised
                if period["id"] in subordinate:
                    rule = subordinate[period["id"]]
                    period.setdefault("source_names", deepcopy(period["names"]))
                    period["names"]["zh"] = rule["name_zh"]
                    period["sovereign_entity_id"] = rule["sovereign_entity_id"]
        write_json(ROOT / f"data/{scope}/entities.json", entities)
        events = read(f"data/{scope}/events.json")
        for event in events:
            previous = event["title"]
            event["title"] = rename(previous)
            if event["record_id"] in subordinate:
                event["title"] = event["title"].replace("(西藏)", subordinate[event["record_id"]]["name_zh"])
            if previous != event["title"]:
                event.setdefault("source_title", previous)
        write_json(ROOT / f"data/{scope}/events.json", events)
        if scope == "focus":
            event_fields = ["id", "kind", "year", "title", "entity_id", "record_id", "derived"]
            export_csv(ROOT / "data/focus/events.csv", [{key: event[key] for key in event_fields} for event in events], event_fields)
            periods = [p for e in entities for p in e["periods"]]
            export_csv(ROOT / "data/focus/polity-periods.csv", [
                {"id": p["id"], "entity_id": p["entity_id"], "name_zh": p["names"]["zh"],
                 "name_en": p["names"]["en"], "start_year": p["start_year"], "end_year": p["end_year"],
                 "longitude": (p["label_position"] or [None, None])[0],
                 "latitude": (p["label_position"] or [None, None])[1]} for p in periods],
                ["id", "entity_id", "name_zh", "name_en", "start_year", "end_year", "longitude", "latitude"])
            points = read("data/focus/polity-labels.geojson")
            by_id = {p["id"]: p for p in periods}
            for feature in points["features"]:
                period = by_id[feature["id"]]
                feature["properties"].update({k: v for k, v in period.items() if k != "label_position"})
            write_json(ROOT / "data/focus/polity-labels.geojson", points)


def main():
    rules = read("data/corrections.json")
    correct_names(rules)
    source_timeline = read("data/focus/territory-timeline.json")
    source_starts = [entry["start_year"] for entry in source_timeline]
    min_year, max_end = source_starts[0], source_timeline[-1]["end_year"]
    years = sorted({*source_starts, *[rule[field] for rule in rules["qing_regions"]
                    for field in ("start_year", "end_year") if min_year <= rule[field] < max_end]})
    bbox = read("data/metadata.json")["focus_bbox"]
    entries = []
    for year, end_year in zip(years, years[1:] + [max_end]):
        source = source_timeline[bisect_right(source_starts, year) - 1]
        collection, lines, refs = corrected_geometry(read(source["path"]), year, end_year, bbox, rules)
        entry = {**source, "start_year": year, "end_year": end_year, "source_path": source["path"]}
        if refs:
            entry.update(path=f"data/derived/curated/{year}.geojson",
                         boundary_path=f"data/derived/curated-boundaries/{year}.geojson", correction_manifest="data/corrections.json")
            write_json(ROOT / entry["path"], collection)
            write_json(ROOT / entry["boundary_path"], {"type": "FeatureCollection", "features": lines})
            entry.update(sha256=digest(ROOT / entry["path"]), boundary_sha256=digest(ROOT / entry["boundary_path"]),
                         features=len(collection["features"]))
            original = union_all([shape(f["geometry"]) for f in read(source["path"])["features"]])
            revised = union_all([shape(f["geometry"]) for f in collection["features"]])
            assert original.symmetric_difference(revised).area < 1e-6, year
            assert all(shape(f["geometry"]).is_valid for f in collection["features"]), year
        entries.append(entry)
    write_json(ROOT / "data/focus/territory-timeline.curated.json", entries)
    print(f"Corrections applied: {sum('correction_manifest' in e for e in entries)} intervals; {len(entries)} total")


if __name__ == "__main__":
    main()
