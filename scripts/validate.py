"""Audit references, cached checksums, intervals, and all generated geometries."""
import json
from collections import Counter

from jsonschema import Draft202012Validator

from shapely.geometry import shape

from extract import ROOT, digest, write_json


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def main():
    entities=read("data/normalized/entities.json")
    rulers=read("data/normalized/rulers.json")
    events=read("data/normalized/events.json")
    eras=read("data/normalized/eras.json")
    tiles=read("data/focus/territory-index.json")
    metadata=read("data/metadata.json")
    schema=read("schemas/dataset.schema.json")
    Draft202012Validator.check_schema(schema)
    def validator(name):
        return Draft202012Validator({"$schema":schema["$schema"],"$defs":schema["$defs"],"$ref":"#/$defs/"+name})
    schema_count=0
    for name,records in [("entity",entities),("ruler",rulers),("event",events),("era",eras),
                         ("tile",read("data/normalized/territory-index.json"))]:
        check=validator(name)
        for record in records:
            check.validate(record)
            schema_count+=1
    for records in [entities,rulers,events,eras,[p for e in entities for p in e["periods"]]]:
        assert len(records)==len({r["id"] for r in records}), "Duplicate record IDs"
    entity_ids={e["id"] for e in entities}
    assert all(r["entity_id"] in entity_ids for r in rulers)
    assert all(e["entity_id"] is None or e["entity_id"] in entity_ids for e in events)
    assert all(e["derived"] for e in events)
    for entity in entities:
        for period in entity["periods"]:
            assert not ({"@","$"} & set(period["names"].values())), period["id"]
    manifests=read("data/raw/toolbay/manifest.json")+read("data/raw/toolbay/tile-manifest.json")
    for entry in manifests:
        assert digest(ROOT/entry["path"])==entry["sha256"],entry["path"]
    derived=read("data/derived/manifest.json")
    for entry in derived["files"]:
        assert digest(ROOT/entry["path"])==entry["sha256"],entry["path"]
    total_features=0
    feature_validator=validator("territoryFeature")
    for tile in tiles:
        snapshots=tile["snapshots"]
        assert snapshots[0]["start_year"]==-4000
        assert snapshots[-1]["end_year"]==2018
        for previous,current in zip(snapshots,snapshots[1:]):
            assert previous["end_year"]==current["start_year"]
        for snapshot in snapshots:
            assert (ROOT/snapshot["path"]).is_file(),snapshot["path"]
            features=read(snapshot["vector_path"])["features"]
            total_features+=len(features)
            for feature in features:
                feature_validator.validate(feature)
                schema_count+=1
                geometry=shape(feature["geometry"])
                assert geometry.is_valid and not geometry.is_empty,feature["id"]
                assert geometry.geom_type in ("Polygon","MultiPolygon"),feature["id"]
                w,s,e,n=geometry.bounds
                bw,bs,be,bn=metadata["focus_bbox"]
                assert bw-1e-6<=w<=e<=be+1e-6 and bs-1e-6<=s<=n<=bn+1e-6,feature["id"]
                assert feature["properties"]["polity_id"] is None
                assert feature["properties"]["start_year"]==snapshot["start_year"]
    assert total_features==derived["counts"]["features"]
    timeline=read("data/focus/territory-timeline.json")
    navigation=read("data/navigation.json")
    stitched_manifest=read("data/derived/stitched-manifest.json")
    assert timeline[0]["start_year"]==navigation["min_year"]==-2000
    assert timeline[-1]["end_year"]==navigation["max_year"]+1
    for previous,current in zip(timeline,timeline[1:]):
        assert previous["end_year"]==current["start_year"]
    stitched_features=0
    stitched_validator=validator("stitchedFeature")
    for interval in timeline:
        assert digest(ROOT/interval["path"])==interval["sha256"]
        assert digest(ROOT/interval["boundary_path"])==interval["boundary_sha256"]
        source_features={f["id"]:f for source in interval["source_snapshots"] for f in read(source["path"])["features"]}
        merged=read(interval["path"])["features"]
        colors=set()
        for feature in merged:
            stitched_validator.validate(feature)
            schema_count+=1
            stitched_features+=1
            geometry=shape(feature["geometry"])
            assert geometry.is_valid and not geometry.is_empty,feature["id"]
            properties=feature["properties"]
            assert properties["source_color"] not in colors
            colors.add(properties["source_color"])
            assert properties["start_year"]==interval["start_year"]
            assert properties["end_year"]==interval["end_year"]
            area=0
            for source in properties["sources"]:
                original=source_features[source["feature_id"]]
                assert original["properties"]["source_color"]==properties["source_color"]
                area+=shape(original["geometry"]).area
            assert abs(geometry.area-area)<1e-6,feature["id"]
        for feature in read(interval["boundary_path"])["features"]:
            geometry=shape(feature["geometry"])
            assert geometry.is_valid and geometry.geom_type in ("LineString","MultiLineString")
    assert stitched_features==stitched_manifest["features"]
    report={"status":"passed","source_files_checked":len(manifests),
            "geojson_files_checked":len(derived["files"]),"geometries_checked":total_features,
            "stitched_intervals_checked":len(timeline),"stitched_features_checked":stitched_features,
            "schema_records_checked":schema_count,
            "checks":["JSON Schema","unique IDs","referential integrity","language reference resolution",
                      "source and output SHA-256","complete tile timelines","valid nonempty polygons",
                      "focus bounding box","explicitly unverified polity assignment",
                      "stitched timeline and checksums","cross-tile source references","stitched area preservation"],
            "source_issue_counts":dict(Counter(i["kind"] for i in read("data/source-issues.json")))}
    write_json(ROOT/"artifacts/validation.json",report,pretty=True)
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
