"""Trace source color masks to approximate, temporally indexed GeoJSON.

The result is geometry of image colors, NOT verified polity boundaries.
White/unassigned and ocean blue are omitted. No color-to-polity inference.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path

import numpy as np
from PIL import Image
from rasterio.features import shapes
from rasterio.transform import Affine
from shapely import box, make_valid, orient_polygons, union_all
from shapely.geometry import mapping, shape

from extract import ROOT, digest, write_json

BACKGROUND_COLORS = {0xFFFFFF, 0x39C1FF}


def rounded(value):
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, (list, tuple)):
        return [rounded(v) for v in value]
    if isinstance(value, dict):
        return {k: rounded(v) for k, v in value.items()}
    return value


def polygons(geometry):
    if geometry.is_empty:
        return []
    if geometry.geom_type == "Polygon":
        return [geometry]
    if hasattr(geometry, "geoms"):
        return [p for child in geometry.geoms for p in polygons(child)]
    return []


def vectorize_image(path, bounds, clip_bbox, properties, tolerance=0):
    with Image.open(path) as image:
        rgba = np.array(image.convert("RGBA"), dtype=np.int32)
    h, w = rgba.shape[:2]
    colors = (rgba[:, :, 0] << 16) + (rgba[:, :, 1] << 8) + rgba[:, :, 2]
    mask = (rgba[:, :, 3] > 0) & ~np.isin(colors, list(BACKGROUND_COLORS))
    transform = Affine((bounds[2] - bounds[0]) / w, 0, bounds[0],
                       0, -(bounds[3] - bounds[1]) / h, bounds[3])
    clip = box(*clip_bbox)
    grouped = defaultdict(list)
    for geometry, color in shapes(colors, mask=mask, transform=transform, connectivity=4):
        polygon = shape(geometry)
        if not polygon.is_valid:
            polygon = make_valid(polygon)
        grouped[int(color)].extend(polygons(polygon.intersection(clip)))
    features = []
    for color, parts in sorted(grouped.items()):
        if not parts:
            continue
        geometry = union_all(parts)
        if tolerance:
            geometry = geometry.simplify(tolerance, preserve_topology=True)
        geometry = orient_polygons(geometry)
        if not geometry.is_valid:
            raise ValueError(f"Invalid polygon after conversion: {path}, color={color}")
        color_hex = f"#{color:06x}"
        feature_id = f"{properties['tile_id']}:{properties['start_year']}:{color_hex}"
        features.append({"type": "Feature", "id": feature_id, "bbox": rounded(geometry.bounds),
                         "geometry": rounded(mapping(geometry)), "properties": {
                             **properties, "source_color": color_hex, "polity_id": None,
                             "polity_assignment": "unverified", "geometry_origin": "raster_color_trace",
                             "pixel_size_degrees": 0.1,
                             "source_color_pixels": int(np.count_nonzero(colors == color)),
                             "simplification_degrees": tolerance}})
    return {"type": "FeatureCollection", "features": features}


def convert(tile, snapshot, bbox, tolerance):
    path = ROOT / snapshot["path"]
    output = ROOT / snapshot["vector_path"]
    collection = vectorize_image(path, tile["bbox"], bbox,
                                 {"tile_id": tile["id"], "start_year": snapshot["start_year"],
                                  "end_year": snapshot["end_year"], "source_image": snapshot["path"],
                                  "source_url": snapshot["source_url"]}, tolerance)
    write_json(output, collection)
    # A standard PNG world file references pixel CENTERS, unlike image edge bounds.
    worldfile = path.with_suffix(".pgw")
    west, south, east, north = tile["bbox"]
    worldfile.write_text(f"0.1\n0\n0\n-0.1\n{west + 0.05:.2f}\n{north - 0.05:.2f}\n", encoding="ascii")
    path.with_suffix(".prj").write_text(
        'GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563]],'
        'PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433],AUTHORITY["EPSG","4326"]]', encoding="ascii")
    return {"path": output.relative_to(ROOT).as_posix(), "sha256": digest(output),
            "bytes": output.stat().st_size, "features": len(collection["features"]),
            "source_sha256": digest(path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--simplify", type=float, default=0, help="Optional tolerance in degrees; default preserves pixel edges")
    args = parser.parse_args()
    if args.simplify < 0 or not 1 <= args.workers <= 8:
        parser.error("simplify must be nonnegative; workers must be 1..8")
    metadata = json.loads((ROOT / "data/metadata.json").read_text(encoding="utf-8"))
    tiles = json.loads((ROOT / "data/focus/territory-index.json").read_text(encoding="utf-8"))
    jobs = [(tile, snapshot) for tile in tiles for snapshot in tile["snapshots"]]
    missing = [s["path"] for _, s in jobs if not (ROOT / s["path"]).is_file()]
    if missing:
        raise SystemExit(f"Missing {len(missing)} source images; run extract.py --download-tiles first")
    entries = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(convert, tile, snapshot, metadata["focus_bbox"], args.simplify)
                   for tile, snapshot in jobs]
        for index, future in enumerate(as_completed(futures), 1):
            entries.append(future.result())
            if index % 100 == 0 or index == len(jobs):
                print(f"Vectorized {index}/{len(jobs)}", flush=True)
    write_json(ROOT / "data/derived/manifest.json", {
        "schema_version": "1.0.0", "bbox": metadata["focus_bbox"], "crs": "EPSG:4326",
        "excluded_colors": [f"#{c:06x}" for c in sorted(BACKGROUND_COLORS)],
        "method": "Exact pixel-edge polygonization; clip to focus bbox; group per source tile and color",
        "polity_assignment": "None. A color can represent multiple unrelated polities.",
        "simplification_degrees": args.simplify,
        "counts": {"files": len(entries), "features": sum(e["features"] for e in entries),
                   "bytes": sum(e["bytes"] for e in entries)},
        "files": sorted(entries, key=lambda e: e["path"])}, pretty=True)
    print(f"Complete: {len(entries)} independent GeoJSON files", flush=True)


if __name__ == "__main__":
    main()
