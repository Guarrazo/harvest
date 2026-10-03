import json

from ncig.city_pipeline import SpatialIndex, _records_from_json, detect_city_buildings, build_city_manifest


def _record(x, y, z=0.0):
    return {"x": x, "y": y, "z": z, "type": "worldMeshNode"}


def test_spatial_index_returns_local_records_only():
    records = [_record(0, 0), _record(5, 0), _record(100, 100)]
    index = SpatialIndex(records, 10)
    hits = index.query(0, 0, 10)
    assert set(hits) == {0, 1}


def test_loader_accepts_native_wolvenkit_data_wrapper_and_node_data():
    raw = {
        "FormatVersion": 1,
        "Data": {
            "$type": "worldStreamingSector",
            "category": "Exterior",
            "nodes": [
                {
                    "$type": "worldStaticMeshNode",
                    "debugName": "shop_wall",
                    "mesh": {"DepotPath": {"$value": "base/environment/architecture/shop_wall_l300_w10_h300.mesh"}},
                }
            ],
            "nodeData": {
                "BufferId": "0",
                "Flags": 0,
                "Type": "WolvenKit.worldNodeDataBuffer",
                "Data": [
                    {
                        "Position": {"X": 10, "Y": 20, "Z": 3, "W": 1},
                        "Orientation": {"I": 0, "J": 0, "K": 0, "R": 1},
                        "Scale": {"X": 1, "Y": 1, "Z": 1},
                        "Pivot": {"X": 0, "Y": 0, "Z": 0},
                        "Bounds": {
                            "Min": {"X": 9, "Y": 19, "Z": 0},
                            "Max": {"X": 11, "Y": 21, "Z": 6},
                        },
                        "NodeIndex": 0,
                    }
                ],
            },
        },
    }
    records = _records_from_json(raw, "sector_001.streamingsector.json")
    assert len(records) == 1
    assert records[0]["x"] == 10
    assert records[0]["y"] == 20
    assert records[0]["resource"].endswith("shop_wall_l300_w10_h300.mesh")
    assert records[0]["type"] == "worldStaticMeshNode"


def test_loader_uses_node_data_position_and_preserves_node_index():
    raw = {
        "Data": {
            "$type": "worldStreamingSector",
            "nodes": [{"$type": "worldStaticMeshNode", "mesh": {"DepotPath": {"$value": "base\\environment\\architecture\\wall_l300_w10_h300.mesh"}}}],
            "nodeData": {"Data": [{"Position": {"X": 5, "Y": 6, "Z": 7, "W": 1}, "Orientation": {"I": 0, "J": 0, "K": 0, "R": 1}, "Scale": {"X": 1, "Y": 1, "Z": 1}, "NodeIndex": 0}]},
        }
    }
    records = _records_from_json(raw, "sector.streamingsector.json")
    assert len(records) == 1
    assert (records[0]["x"], records[0]["y"], records[0]["z"]) == (5, 6, 7)
    assert records[0]["node_index"] == 0


def test_city_manifest_tracks_files_and_bounds(tmp_path):
    payload = {
        "sectors": [
            {
                "name": "sector_a",
                "category": "Exterior",
                "nodes": [
                    {"type": "worldMeshNode", "name": "building_wall", "position": {"x": 1, "y": 2, "z": 3}},
                ],
            }
        ]
    }
    path = tmp_path / "sector.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    from ncig.city_pipeline import load_city_records
    records, manifest = load_city_records(tmp_path)
    assert len(records) == 1
    assert manifest["json_file_count"] == 1
    assert manifest["record_count"] == 1
    assert manifest["world_bounds"]["x_min"] == 1
