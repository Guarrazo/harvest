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
    assert manifest["format"] == "ncig-city-index-v3"
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

def _native_cr2w_sector_payload():
    return {
        "Header": {"WKitJsonVersion": "0.0.9", "DataType": "CR2W"},
        "Data": {
            "Version": 195,
            "BuildVersion": 0,
            "RootChunk": {
                "$type": "worldStreamingSector",
                "category": "Exterior",
                "nodes": [
                    {
                        "HandleId": "0",
                        "Data": {
                            "$type": "worldEntityNode",
                            "debugName": {"$type": "CName", "$storage": "string", "$value": "shop_door"},
                            "entityTemplate": {
                                "DepotPath": {
                                    "$type": "ResourcePath",
                                    "$storage": "string",
                                    "$value": "base\\env\\shop\\door.ent",
                                }
                            },
                        },
                    },
                    {
                        "HandleId": "1",
                        "Data": {
                            "$type": "worldStaticMeshNode",
                            "debugName": {"$type": "CName", "$storage": "string", "$value": "shop_wall"},
                            "mesh": {
                                "DepotPath": {
                                    "$type": "ResourcePath",
                                    "$storage": "string",
                                    "$value": "base\\environment\\architecture\\shop_wall_l300_w10_h300.mesh",
                                }
                            },
                        },
                    },
                ],
                "nodeData": {
                    "BufferId": "0",
                    "Flags": 0,
                    "Type": "WolvenKit.RED4.Archive.Buffer.worldNodeDataBuffer",
                    "Data": [
                        {
                            "Id": "0",
                            "Position": {"$type": "Vector4", "W": 0, "X": 10, "Y": 20, "Z": 3},
                            "Orientation": {"$type": "Quaternion", "i": 0, "j": 0, "k": 0, "r": 1},
                            "Scale": {"$type": "Vector3", "X": 1, "Y": 1, "Z": 1},
                            "NodeIndex": 0,
                        },
                        {
                            "Id": "0",
                            "Position": {"$type": "Vector4", "W": 0, "X": 11, "Y": 20, "Z": 3},
                            "Orientation": {"$type": "Quaternion", "i": 0, "j": 0, "k": 0, "r": 1},
                            "Scale": {"$type": "Vector3", "X": 1, "Y": 1, "Z": 1},
                            "NodeIndex": 1,
                        },
                    ],
                },
            },
            "EmbeddedFiles": [],
        },
    }


def test_city_index_parses_native_cr2w_rootchunk_and_wrapped_nodes(tmp_path):
    src = tmp_path / "sectors"
    src.mkdir()
    path = src / "sector_01.streamingsector.json"
    path.write_text(json.dumps(_native_cr2w_sector_payload()), encoding="utf-8")

    report = inspect_city_json(path)
    assert report["data_type"] == "worldStreamingSector"
    assert report["root_chunk_present"] is True
    assert report["node_count"] == 2
    assert report["nodeData_Data_count"] == 2
    assert report["parsed_record_count"] == 2

    db = tmp_path / "city.sqlite"
    manifest = build_city_index(src, db)
    assert manifest["indexed_records"] == 2

    conn = sqlite3.connect(db)
    try:
        rows = conn.execute("SELECT type,name,resource FROM records ORDER BY id").fetchall()
    finally:
        conn.close()

    assert rows[0][0] == "worldEntityNode"
    assert rows[0][1] == "shop_door"
    assert rows[0][2].endswith(r"base\env\shop\door.ent")
    assert rows[1][0] == "worldStaticMeshNode"
    assert rows[1][1] == "shop_wall"
    assert rows[1][2].endswith(r"shop_wall_l300_w10_h300.mesh")
