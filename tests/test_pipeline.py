"""Regression checks for source semantics and raster geometry fidelity."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image
from rasterio.features import rasterize
from rasterio.transform import Affine
from shapely.geometry import shape, box, mapping, LineString

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from extract import names, normalize, parse_arrays, tile_bbox
from snapshot import snapshot_for_year, create_snapshot
from vectorize import vectorize_image
from stitch import merge_features


class SourceSemantics(unittest.TestCase):
    def test_language_references_and_missing_field(self):
        self.assertEqual(names(["甲", "Alpha", "@"]), {"ja":"甲", "en":"Alpha", "zh":"甲"})
        self.assertEqual(names(["$", "Alpha", "$"]), {"ja":"Alpha", "en":"Alpha", "zh":"Alpha"})
        self.assertIsNone(names(["甲", "Alpha"])["zh"])

    def test_inherited_names_positions_and_role_switch(self):
        source = [[None, -10, 30,
                   [-10, 10, None, "甲", "A", "@", "甲", "A", "@", 2940, 555, 0],
                   [10, 30, None, "乙", "B", "@"],
                   ["王", "King", "@"], [12, 20, None, "丙", "C", "@"]]]
        entities,rulers,_,events,_,issues = normalize(source,{},[],[60,0,150,65])
        self.assertEqual(len(entities[0]["periods"]),2)
        self.assertEqual(entities[0]["periods"][1]["label_position"],[114,34.5])
        self.assertEqual(entities[0]["periods"][1]["abbreviations"]["en"],"A")
        self.assertEqual(rulers[0]["role"]["zh"],"王")
        self.assertTrue(all(e["derived"] for e in events))
        self.assertEqual(issues,[])

    def test_anomalies_are_preserved_and_reported(self):
        source=[[None,1,9999,[1,9999,None,"甲","A","@","甲","A","@",2940,555,0],
                 ["王","King","@"],[20,10,None,"丙","C"]]]
        entities,rulers,_,events,_,issues=normalize(source,{},[],[60,0,150,65])
        self.assertEqual(rulers[0]["end_year"],10)
        self.assertIsNone(rulers[0]["names"]["zh"])
        self.assertTrue(entities[0]["open_ended"])
        self.assertTrue(any(i["kind"]=="non_positive_reign" for i in issues))
        self.assertFalse(any(e["year"]==9999 for e in events))

    def test_json5_does_not_execute_code(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"source.js"
            path.write_text("var data = [1, /* comment */ 'two', null,];",encoding="utf-8")
            self.assertEqual(parse_arrays(path)["data"],[1,"two",None])
            path.write_text("var data = process.exit();",encoding="utf-8")
            with self.assertRaises(ValueError):
                parse_arrays(path)

    def test_tile_intervals_use_previous_change(self):
        tile={"snapshots":[{"start_year":-4000,"end_year":618},
                           {"start_year":618,"end_year":907},
                           {"start_year":907,"end_year":2018}]}
        self.assertEqual(snapshot_for_year(tile,617)["start_year"],-4000)
        self.assertEqual(snapshot_for_year(tile,618)["start_year"],618)
        self.assertEqual(snapshot_for_year(tile,906)["start_year"],618)
        self.assertEqual(snapshot_for_year(tile,907)["start_year"],907)
        self.assertIsNone(snapshot_for_year(tile,2018))
        self.assertEqual(tile_bbox(6,1),[90,0,135,45])

    def test_year_zero_is_rejected(self):
        with self.assertRaises(ValueError):
            create_snapshot(0)


class RasterFidelity(unittest.TestCase):
    def test_trace_preserves_holes_islands_and_excludes_background(self):
        rgba=np.full((10,10,4),255,dtype=np.uint8)
        rgba[1:8,1:8,:3]=[255,0,0]
        rgba[3:5,3:5,:3]=[255,255,255]  # A white hole must survive.
        rgba[8,8,:3]=[255,0,0]  # A disconnected one-pixel island must survive.
        rgba[0,0,:3]=[57,193,255]  # Source ocean is background.
        rgba[9,9]=[0,255,0,0]  # Transparent pixels are background too.
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"raster.png"
            Image.fromarray(rgba).save(path)
            result=vectorize_image(path,[90,0,91,1],[90,0,91,1],{"tile_id":"test","start_year":1})
        self.assertEqual(len(result["features"]),1)
        feature=result["features"][0]
        self.assertIsNone(feature["properties"]["polity_id"])
        self.assertTrue(shape(feature["geometry"]).is_valid)
        restored=rasterize([(feature["geometry"],1)],out_shape=(10,10),transform=Affine(.1,0,90,0,-.1,1))
        np.testing.assert_array_equal(restored,(rgba[:,:,0]==255)&(rgba[:,:,1]==0))

    def test_focus_clipping(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"raster.png"
            Image.new("RGB",(10,10),(0,255,0)).save(path)
            result=vectorize_image(path,[90,0,91,1],[90.3,.2,90.7,.8],{"tile_id":"test","start_year":1})
        geometry=shape(result["features"][0]["geometry"])
        self.assertAlmostEqual(geometry.area,.24)
        self.assertEqual(geometry.bounds,(90.3,.2,90.7,.8))


class TileSeams(unittest.TestCase):
    @staticmethod
    def feature(bounds, color, tile_id):
        return {"type":"Feature","id":tile_id,"geometry":mapping(box(*bounds)),
                "properties":{"source_color":color,"tile_id":tile_id,"start_year":600,
                              "end_year":700,"source_image":f"{tile_id}.png","source_url":"https://example.com"}}

    def test_matching_colors_remove_horizontal_and_vertical_seams(self):
        parts=[self.feature(bounds,"#ff0000",str(i)) for i,bounds in enumerate([
            [89,44,90,45],[90,44,91,45],[89,45,90,46],[90,45,91,46]])]
        collection,lines=merge_features(parts,618,619,[88,43,92,47])
        self.assertEqual(len(collection["features"]),1)
        geometry=shape(collection["features"][0]["geometry"])
        self.assertTrue(geometry.equals(box(89,44,91,46)))
        boundary=shape(lines["features"][0]["geometry"])
        self.assertEqual(boundary.intersection(LineString([(90,44.1),(90,45.9)])).length,0)
        self.assertEqual(boundary.intersection(LineString([(89.1,45),(90.9,45)])).length,0)
        self.assertEqual(len(collection["features"][0]["properties"]["sources"]),4)

    def test_different_colors_keep_true_border_and_hide_crop_frame(self):
        parts=[self.feature([89,44,90,46],"#ff0000","left"),
               self.feature([90,44,91,46],"#00ff00","right")]
        collection,lines=merge_features(parts,618,619,[89,44,91,46])
        self.assertEqual(len(collection["features"]),2)
        boundary=shape(lines["features"][0]["geometry"])
        self.assertTrue(boundary.equals(LineString([(90,44),(90,46)])))

    def test_real_snapshots_preserve_every_source_pixel(self):
        root=Path(__file__).resolve().parents[1]
        index=json.loads((root/"data/focus/territory-index.json").read_text(encoding="utf-8"))
        timeline=json.loads((root/"data/focus/territory-timeline.json").read_text(encoding="utf-8"))
        for year in (618,1279,1644):
            with self.subTest(year=year):
                mosaic=np.zeros((900,1350),dtype=np.int32)
                for tile in index:
                    current=snapshot_for_year(tile,year)
                    rgba=np.array(Image.open(root/current["path"]).convert("RGBA"),dtype=np.int32)
                    colors=(rgba[:,:,0]<<16)+(rgba[:,:,1]<<8)+rgba[:,:,2]
                    colors[np.isin(colors,[0xffffff,0x39c1ff])|(rgba[:,:,3]==0)]=0
                    x,y=(tile["x"]-5)*450,tile["y"]*450
                    mosaic[y:y+450,x:x+450]=colors
                expected=mosaic[250:900,150:1050]
                current=next(s for s in timeline if s["start_year"]<=year<s["end_year"])
                features=json.loads((root/current["path"]).read_text(encoding="utf-8"))["features"]
                restored=rasterize([(f["geometry"],int(f["properties"]["source_color"][1:],16)) for f in features],
                                   out_shape=expected.shape,transform=Affine(.1,0,60,0,-.1,65),dtype="int32")
                np.testing.assert_array_equal(restored,expected)


if __name__ == "__main__":
    unittest.main()
