from __future__ import annotations

import json
import sqlite3
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ncig.world_audit import _candidate_audit, _style_profile


def _candidate():
    return {
        "id": "b1",
        "position": {"x": 0.0, "y": 0.0, "z": 0.0},
        "yaw_deg": 0.0,
        "width_m": 10.0,
        "depth_m": 8.0,
        "height_m": 3.2,
        "floors": 1,
        "entry_side": "north",
        "entry_world": {"x": 0.0, "y": -4.0, "z": 0.0},
        "entry_local_x": 0.0,
        "entry_local_y": -4.0,
        "entry_width_m": 1.2,
        "entry_height_m": 2.1,
    }


def test_proxy_is_not_collision_and_requires_probe() -> None:
    rows = [{
        "proxy": 1, "collision": 0, "door": 0, "mesh": 1,
        "x": 0.0, "y": 0.0, "z": 1.5, "yaw_deg": 0.0,
        "l": 10.0, "w": 8.0, "h": 3.0, "sx": 1.0, "sy": 1.0, "sz": 1.0,
        "shape_x": 0.0, "shape_y": 0.0, "shape_z": 0.0,
        "source_file": "x", "sector": "s", "type": "worldBuildingProxyMeshNode", "name": "proxy", "resource": "proxy.mesh"
    }]
    audit = _candidate_audit(_candidate(), rows)
    assert audit["collision_status"] == "proxy_only_no_explicit_collision"
    assert audit["proxy_status"] == "proxy_only"
    assert audit["recommended_access_action"] == "runtime_probe_proxy_only"


def test_small_collision_over_door_is_removal_candidate() -> None:
    rows = [
        {"proxy": 0, "collision": 1, "door": 0, "mesh": 0,
         "x": 0.0, "y": -4.05, "z": 1.0, "yaw_deg": 0.0,
         "l": 1.2, "w": 0.4, "h": 2.2, "sx": 1.0, "sy": 1.0, "sz": 1.0,
         "shape_x": 1.2, "shape_y": 0.4, "shape_z": 2.2,
         "shape_kind": "shape_or_mesh", "node_index": 17, "source_node_count": 900,
         "source_file": "sector.json", "sector": "sector_a", "type": "worldCollisionNode", "name": "door blocker", "resource": ""},
        {"proxy": 0, "collision": 0, "door": 1, "mesh": 1,
         "x": 0.0, "y": -4.0, "z": 0.0, "yaw_deg": 0.0,
         "l": 1.2, "w": 0.2, "h": 2.1, "sx": 1.0, "sy": 1.0, "sz": 1.0,
         "shape_x": 0.0, "shape_y": 0.0, "shape_z": 0.0,
         "source_file": "sector.json", "sector": "sector_a", "type": "worldMeshNode", "name": "main entrance door", "resource": "base\\environment\\architecture\\common\\int\\int_ent_industrial_a\\door.mesh"},
    ]
    audit = _candidate_audit(_candidate(), rows)
    assert audit["door_status"] == "confident_exterior_door"
    assert audit["recommended_access_action"] == "candidate_for_archive_xl_collision_node_removal"
    assert audit["removal_candidates"][0]["node_index"] == 17
    assert audit["removal_candidates"][0]["safe_to_auto_remove"] is True


def test_style_profile_prefers_real_exterior_family_tokens() -> None:
    rows = [
        {"mesh": 1, "proxy": 0, "resource": r"base\environment\architecture\common\int\int_nkt_apartment_a\wall.mesh"},
        {"mesh": 1, "proxy": 0, "resource": r"base\environment\architecture\common\int\int_nkt_apartment_a\window.mesh"},
        {"mesh": 1, "proxy": 0, "resource": r"base\environment\architecture\common\int\int_nkt_apartment_a\wall2.mesh"},
    ]
    profile = _style_profile(rows)
    assert "nkt" in profile["style_tokens"]
    assert any("nkt" in x for x in profile["dominant_resource_families"])
