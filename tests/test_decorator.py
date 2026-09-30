import json
from pathlib import Path

from ncig.decorator import decorate_layout
from ncig.generator import generate_layout
from ncig.model import BuildingAnchor, Vec3
from ncig.module_library import build_module_library


def test_decorator_places_harvested_nodes():
    b = BuildingAnchor(id="b1", district="watson", type="residential", position=Vec3(0,0,0), yaw_deg=15, width_m=12, depth_m=12, floors=1, seed=123)
    layout = generate_layout(b)
    harvest = {"templates": {"worldEntityNode": [
        {"ncigSourceFile":"favorites/bedroom.json", "type":"worldEntityNode", "name":"bed", "position":{"x":0,"y":0,"z":0}, "rotation":{"i":0,"j":0,"k":0,"r":1}, "scale":{"x":1,"y":1,"z":1}}
    ]}}
    library = build_module_library(harvest)
    out = decorate_layout(layout, library, density=1.0)
    assert out["placement_count"] > 0
    assert out["node_count"] > 0
    assert all(n["type"] == "worldEntityNode" for n in out["nodes"])
