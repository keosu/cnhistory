"""Dissolve equal-color tile seams and build complete temporal map layers."""
from __future__ import annotations

import argparse
from bisect import bisect_right
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
import json

from shapely import box, orient_polygons, union_all
from shapely.geometry import mapping, shape

from extract import ROOT, MAX_YEAR, digest, write_json
from vectorize import rounded


@lru_cache(maxsize=1200)
def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def merge_features(features, start_year, end_year, bbox):
    grouped = defaultdict(list)
    for feature in features:
        grouped[feature["properties"]["source_color"]].append(feature)
    merged, outlines = [], []
    for color, parts in sorted(grouped.items()):
        geometry = orient_polygons(union_all([shape(f["geometry"]) for f in parts], grid_size=0.000001))
        if not geometry.is_valid:
            raise ValueError(f"Invalid stitched geometry: {start_year}/{color}")
        sources = [{"feature_id": f["id"], **{key: f["properties"][key] for key in
                    ("tile_id", "start_year", "end_year", "source_image", "source_url")}} for f in parts]
        merged.append({"type": "Feature", "id": f"merged:{start_year}:{color}",
                       "bbox": rounded(geometry.bounds), "geometry": rounded(mapping(geometry)),
                       "properties": {"start_year": start_year, "end_year": end_year,
                                      "source_color": color, "polity_id": None,
                                      "polity_assignment": "unverified",
                                      "geometry_origin": "raster_color_trace_stitched",
                                      "pixel_size_degrees": 0.1, "sources": sources}})
        outlines.append(geometry.boundary)
    # The focus rectangle is a crop, not a historical border. Never stroke it.
    border = union_all(outlines).difference(box(*bbox).boundary)
    line_features = [] if border.is_empty else [{"type": "Feature", "id": f"boundaries:{start_year}",
                      "geometry": rounded(mapping(border)),
                      "properties": {"start_year": start_year, "end_year": end_year}}]
    return ({"type": "FeatureCollection", "features": merged},
            {"type": "FeatureCollection", "features": line_features})


def build_interval(tiles, start_year, end_year, bbox):
    features, source_snapshots = [], []
    for tile in tiles:
        snapshots = tile["snapshots"]
        index = bisect_right([s["start_year"] for s in snapshots], start_year) - 1
        current = snapshots[index]
        assert current["start_year"] <= start_year < current["end_year"]
        features.extend(read(current["vector_path"])["features"])
        source_snapshots.append({"tile_id": tile["id"], "path": current["vector_path"]})
    merged, boundaries = merge_features(features, start_year, end_year, bbox)
    path = f"data/derived/merged/{start_year}.geojson"
    boundary_path = f"data/derived/boundaries/{start_year}.geojson"
    write_json(ROOT / path, merged)
    write_json(ROOT / boundary_path, boundaries)
    return {"start_year": start_year, "end_year": end_year, "path": path,
            "boundary_path": boundary_path, "features": len(merged["features"]),
            "sha256": digest(ROOT / path), "boundary_sha256": digest(ROOT / boundary_path),
            "source_snapshots": source_snapshots}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.workers <= 8:
        parser.error("workers must be 1..8")
    tiles = read("data/focus/territory-index.json")
    metadata = read("data/metadata.json")
    min_year = read("data/navigation.json")["min_year"]
    years = sorted({min_year, *[s["start_year"] for t in tiles for s in t["snapshots"]
                               if min_year <= s["start_year"] <= MAX_YEAR]})
    intervals = list(zip(years, years[1:] + [MAX_YEAR + 1]))
    entries = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        jobs = [pool.submit(build_interval, tiles, start, end, metadata["focus_bbox"])
                for start, end in intervals]
        for index, job in enumerate(as_completed(jobs), 1):
            entries.append(job.result())
            if index % 100 == 0 or index == len(jobs):
                print(f"Stitched {index}/{len(jobs)}", flush=True)
    entries.sort(key=lambda e: e["start_year"])
    write_json(ROOT / "data/focus/territory-timeline.json", entries)
    write_json(ROOT / "data/derived/stitched-manifest.json", {
        "schema_version": "1.1.0", "min_year": min_year, "max_year": MAX_YEAR,
        "bbox": metadata["focus_bbox"], "method": "Dissolve matching colors across tile edges without buffering or simplification",
        "outlines": "Union of dissolved polygon boundaries, excluding the focus crop rectangle",
        "intervals": len(entries), "features": sum(e["features"] for e in entries),
        "timeline": "data/focus/territory-timeline.json"}, pretty=True)
    print(f"Complete: {len(entries)} seamless map intervals", flush=True)


if __name__ == "__main__":
    main()
