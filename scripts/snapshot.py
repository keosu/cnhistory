"""Export a single year's combined territories and active polity labels."""
import argparse
from bisect import bisect_right
import json
from pathlib import Path

from extract import ROOT, MIN_YEAR, MAX_YEAR, write_json
from stitch import merge_features


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def snapshot_for_year(tile, year):
    snapshots = tile["snapshots"]
    index = bisect_right([s["start_year"] for s in snapshots], year) - 1
    return snapshots[index] if index >= 0 and year < snapshots[index]["end_year"] else None


def create_snapshot(year):
    if not MIN_YEAR <= year <= MAX_YEAR or year == 0:
        raise ValueError(f"year must be {MIN_YEAR}..{MAX_YEAR}, excluding 0")
    features = []
    for tile in read("data/focus/territory-index.json"):
        current = snapshot_for_year(tile, year)
        if current:
            features.extend(read(current["vector_path"])["features"])
    territories, _ = merge_features(features, year, 1 if year == -1 else year + 1,
                                    read("data/metadata.json")["focus_bbox"])
    labels = []
    for entity in read("data/focus/entities.json"):
        if not entity["start_year"] <= year < entity["end_year"]:
            continue
        for period in entity["periods"]:
            if period["start_year"] <= year < period["end_year"] and period["label_position"]:
                labels.append({"type": "Feature", "id": period["id"],
                               "geometry": {"type": "Point", "coordinates": period["label_position"]},
                               "properties": {**period, "position_kind": "source_label_anchor_not_capital"}})
    return ({**territories, "year": year},
            {"type": "FeatureCollection", "year": year, "features": labels})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--output", type=Path, help="Output directory, default data/derived/snapshots")
    args = parser.parse_args()
    try:
        territories, labels = create_snapshot(args.year)
    except ValueError as exc:
        parser.error(str(exc))
    destination = args.output or ROOT / "data/derived/snapshots"
    write_json(destination / f"{args.year}.geojson", territories)
    write_json(destination / f"{args.year}.labels.geojson", labels)
    print(f"{args.year}: {len(territories['features'])} color features, {len(labels['features'])} polity labels -> {destination}")


if __name__ == "__main__":
    main()
