import json
import sqlite3

from ncig.city_index import build_city_index, inspect_city_json


def _native_sector_payload():
    return {
        "FormatVersion": 1,
        "Data": {
            "$type": "worldStreamingSector",
            "category": "Exterior",
            "nodes": [
                {
                    "$type": "worldEntityNode",
                    "debugName": "shop_door",
                    "entityTemplate": {"DepotPath": {"$value": "base\\env\\shop\\door.ent"}},
                },
                {
                    "$type": "worldStaticMeshNode",
                    "debugName": "shop_wall",
                    "mesh": {"DepotPath": {"$value": "base\\environment\\architecture\\shop_wall_l300_w10_h300.mesh"}},
                },
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
                        "NodeIndex": 0,
                    },
                    {
                        "Position": {"X": 11, "Y": 20, "Z": 3, "W": 1},
                        "Orientation": {"I": 0, "J": 0, "K": 0, "R": 1},
                        "Scale": {"X": 1, "Y": 1, "Z": 1},
                        "NodeIndex": 1,
                    },
                ],
            },
        },
    }


def test_city_index_persists_detection_evidence(tmp_path):
    src = tmp_path / "sectors"
    src.mkdir()
    (src / "sector_01.streamingsector.json").write_text(
        json.dumps(_native_sector_payload()), encoding="utf-8"
    )
    db = tmp_path / "city.sqlite"
    manifest = build_city_index(src, db)
    assert manifest["indexed_records"] == 2
    conn = sqlite3.connect(db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM records").fetchone()[0] == 2
    finally:
        conn.close()


def test_inspector_reports_wolvenkit_data_wrapper(tmp_path):
    path = tmp_path / "sector.streamingsector.json"
    path.write_text(json.dumps(_native_sector_payload()), encoding="utf-8")
    report = inspect_city_json(path)
    assert report["data_type"] == "worldStreamingSector"
    assert report["node_count"] == 2
    assert report["nodeData_type"] == "dict"
    assert report["nodeData_Data_count"] == 2
    assert report["parsed_record_count"] == 2
