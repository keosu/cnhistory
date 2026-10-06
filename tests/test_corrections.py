"""Check sovereignty corrections, component selection, and export consistency."""
import json
from pathlib import Path
import sys
import unittest
from shapely import union_all
from shapely.geometry import Point, shape

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from correct import corrected_geometry
from snapshot import create_snapshot

def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))

class HistoricalCorrections(unittest.TestCase):
    def test_qing_anchors_preserve_coverage_and_unrelated_colors(self):
        timeline = read("data/focus/territory-timeline.json")
        rules = read("data/corrections.json")
        for year in (1720, 1755, 1756, 1800, 1884, 1911, 1912):
            with self.subTest(year=year):
                entry = next(e for e in timeline if e["start_year"] <= year < e["end_year"])
                original = read(entry["path"])
                corrected, lines, _ = corrected_geometry(original, year, year + 1, [60, 0, 150, 65], rules)
                before = union_all([shape(f["geometry"]) for f in original["features"]])
                after = union_all([shape(f["geometry"]) for f in corrected["features"]])
                self.assertLess(before.symmetric_difference(after).area, 1e-6)
                qing = next((f for f in corrected["features"] if f["properties"].get("polity_id") == rules["qing_entity_id"]), None)
                if year >= 1911:
                    self.assertIsNone(qing)
                    if year == 1911:
                        core = next(shape(f["geometry"]) for f in corrected["features"] if shape(f["geometry"]).covers(Point(114,34.5)))
                        self.assertTrue(core.covers(Point(91,29.6)))
                        self.assertTrue(core.covers(Point(87.6,43.8)))
                    continue
                self.assertIsNotNone(qing)
                geometry = shape(qing["geometry"])
                for anchor in ([114, 34.5], [91, 29.6]):
                    self.assertTrue(geometry.covers(Point(anchor)))
                if year < 1911:
                    self.assertTrue(geometry.covers(Point(105, 47)))
                if year >= 1756:
                    self.assertTrue(geometry.covers(Point(87.6, 43.8)))
                else:
                    self.assertFalse(geometry.covers(Point(87.6, 43.8)))
                unrelated = union_all([shape(f["geometry"]) for f in original["features"]
                                      if f["properties"]["source_color"] == "#ffff00"]).difference(geometry)
                revised_unrelated = union_all([shape(f["geometry"]) for f in corrected["features"]
                                               if f["properties"]["source_color"] == "#ffff00"])
                self.assertLess(unrelated.symmetric_difference(revised_unrelated).area, 1e-6)
                boundary = union_all([shape(f["geometry"]) for f in lines])
                self.assertLess(boundary.intersection(geometry.buffer(-.01)).length, 1e-6)

    def test_names_and_snapshot_exports(self):
        periods = {p["id"]: p for e in read("data/focus/entities.json") for p in e["periods"]}
        self.assertEqual(periods["toolbay-region-0122-period-017"]["names"]["zh"], "日本国")
        for row in (6, 7):
            self.assertEqual(periods[f"toolbay-region-1007-period-00{row}"]["names"]["zh"], "伪满洲国")
        territories, labels = create_snapshot(1800)
        self.assertTrue(any(f["properties"].get("name_zh") == "清" for f in territories["features"]))
        self.assertFalse(any(f["id"] == "toolbay-region-0621-period-007" for f in labels["features"]))

if __name__ == "__main__":
    unittest.main()
