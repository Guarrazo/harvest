import json
from pathlib import Path

from ncig.architecture_assembler import apply_architecture_to_world_plan, build_architecture_assembly
from ncig.generator import generate_layout
from ncig.model import BuildingAnchor, Vec3
from ncig.architecture_catalog import build_architecture_catalog


def fixture():
    return json.loads(Path(Path(__file__).parents[1] / "examples" / "architecture_harvest_fixture.json").read_text(encoding="utf-8"))


def test_v015_assembly_uses_real_catalog_paths():
    b = BuildingAnchor("B1", "Watson", "commercial", Vec3(100, 200, 5), 30, 8.0, 8.0, 1)
    layout = generate_layout(b)
    cat = build_architecture_catalog(fixture(), max_per_class=20, interior_only=True)
    assembly = build_architecture_assembly([layout], cat)
    items = assembly["buildings"][0]["placements"]
    resolved = [x for x in items if x.get("resource")]
    assert resolved
    assert all(x["resource"].startswith("base\\environment\\architecture\\") for x in resolved)
    assert all(x["requires_bounds_validation"] for x in resolved)


def test_v015_no_automatic_mesh_scaling():
    b = BuildingAnchor("B2", "Watson", "commercial", Vec3(0, 0, 0), 15, 8.0, 8.0, 1)
    layout = generate_layout(b)
    cat = build_architecture_catalog(fixture(), max_per_class=20, interior_only=True)
    assembly = build_architecture_assembly([layout], cat)
    for p in assembly["buildings"][0]["placements"]:
        if p.get("resource"):
            assert p["scale"] == {"x": 1.0, "y": 1.0, "z": 1.0}


def test_v015_apply_adds_unique_mesh_nodes():
    b = BuildingAnchor("B3", "Watson", "commercial", Vec3(0, 0, 0), 0, 8.0, 8.0, 1)
    layout = generate_layout(b)
    cat = build_architecture_catalog(fixture(), max_per_class=20, interior_only=True)
    assembly = build_architecture_assembly([layout], cat)
    plan = {"building_id": "B3", "nodes": [], "sectors": [{"id": "B3_F01", "floor": 0}]}
    out = apply_architecture_to_world_plan(plan, assembly)
    refs = [x["nodeRef"] for x in out["nodes"]]
    assert len(refs) == len(set(refs))
    assert out["architecture"]["added_node_count"] > 0
    assert all(x["type"] == "worldMeshNode" for x in out["nodes"])
