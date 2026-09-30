import json
from pathlib import Path

from ncig.target_detector import load_world_records, detect_building_candidates


def test_detect_decorative_building_from_sector_fixture(tmp_path: Path):
    payload = {
        "sectors": [{
            "name": "exterior_test",
            "category": "Exterior",
            "nodes": [
                {"type": "worldMeshNode", "name": "building_wall_a", "position": {"x": 0, "y": 0, "z": 0},
                 "data": {"mesh": {"DepotPath": {"$value": "base\\environment\\architecture\\building\\shop_wall.mesh"}}}},
                {"type": "worldMeshNode", "name": "building_wall_b", "position": {"x": 6, "y": 0, "z": 0},
                 "data": {"mesh": {"DepotPath": {"$value": "base\\environment\\architecture\\building\\shop_wall.mesh"}}}},
                {"type": "worldMeshNode", "name": "building_wall_c", "position": {"x": 0, "y": 5, "z": 0},
                 "data": {"mesh": {"DepotPath": {"$value": "base\\environment\\architecture\\building\\shop_wall.mesh"}}}},
                {"type": "worldMeshNode", "name": "shop_door_entry", "position": {"x": 3, "y": 0, "z": 0},
                 "data": {"mesh": {"DepotPath": {"$value": "base\\environment\\architecture\\building\\shop_door.mesh"}}}},
            ],
        }]
    }
    src = tmp_path / "sector.json"
    src.write_text(json.dumps(payload), encoding="utf-8")
    records = load_world_records(src)
    report = detect_building_candidates(records)
    assert report["candidate_count"] == 1
    candidate = report["candidates"][0]
    assert candidate["type"] == "commercial"
    assert candidate["evidence"]["entrance_nodes"] >= 1

from ncig.target_detector import candidates_to_buildings


def test_candidates_convert_to_building_anchor():
    report = {"format": "ncig-building-candidates-v1", "candidates": [{
        "id": "auto_0001_commercial", "score": 90, "confidence": "high", "type": "commercial",
        "position": {"x": 10, "y": 20, "z": 3}, "yaw_deg": 30,
        "width_m": 12, "depth_m": 8, "floors": 2,
        "suggested_action": "fill", "evidence": {"architecture_nodes": 10}
    }]}
    result = candidates_to_buildings(report)
    assert result["selected_count"] == 1
    b = result["buildings"][0]
    assert b["yaw_deg"] == 30
    assert b["width_m"] == 12
    assert b["seed"] > 0
