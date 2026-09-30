import json

from ncig.city_pipeline import SpatialIndex, _records_from_json, detect_city_buildings, build_city_manifest


def _record(x, y, z=0.0):
    return {"x": x, "y": y, "z": z, "type": "worldMeshNode"}


def test_spatial_index_returns_local_records_only():
    records = [_record(0, 0), _record(5, 0), _record(100, 100)]
    index = SpatialIndex(records, 10)
    hits = index.query(0, 0, 10)
    assert set(hits) == {0, 1}


def test_loader_accepts_direct_single_sector_with_node_data():
    raw = {
        "name": "sector_001",
        "nodes": [
            {
                "type": "worldMeshNode",
                "name": "shop_wall",
                "data": {"mesh": {"DepotPath": {"$value": "base/environment/architecture/shop_wall_l300_w10_h300.mesh"}}},
            }
        ],
        "nodeData": [
            {
                "NodeIndex": 0,
                "Position": {"x": 10, "y": 20, "z": 3},
                "Rotation": {"i": 0, "j": 0, "k": 0, "r": 1},
            }
        ],
    }
    records = _records_from_json(raw, "sector_001.json")
    assert len(records) == 1
    assert records[0]["x"] == 10
    assert records[0]["y"] == 20
    assert records[0]["resource"].endswith("shop_wall_l300_w10_h300.mesh")


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
