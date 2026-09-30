import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / 'src'))

from ncig.generator import generate_layout, validate_layout
from ncig.model import BuildingAnchor, Vec3
from ncig.worldplan import build_world_plan
from ncig.scanner import parse_observation, find_entry_nodes


def building():
    return BuildingAnchor(
        id="v02_001", district="watson", type="residential",
        position=Vec3(10, 20, 0), yaw_deg=30, width_m=16, depth_m=14,
        floors=3, seed=123
    )


def test_entry_and_world_plan():
    layout = generate_layout(building())
    assert validate_layout(layout) == []
    assert any(s.kind == "entry" for s in layout.sockets)
    plan = build_world_plan(layout)
    assert plan["format"] == "ncig-world-plan-v3"
    assert len(plan["sectors"]) == 3
    assert any(n["type"] == "worldMeshNode" for n in plan["nodes"])
    assert any(n["type"] == "worldStaticMarkerNode" for n in plan["nodes"])


def test_scanner_flexible_fields():
    obs = [parse_observation({
        "Name": "door_123",
        "NodeType": "worldEntityNode",
        "NodeInstance": "door_small",
        "SectorPath": "base/worlds/sector.streamingsector",
        "NodeRef": "$/#door123",
        "Position": {"X": 1, "Y": 2, "Z": 3},
        "Yaw": 45,
    })]
    obs = [x for x in obs if x]
    assert len(find_entry_nodes(obs)) == 1
