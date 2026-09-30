import json
from pathlib import Path
from ncig.architecture_assembler import apply_architecture_to_world_plan
from ncig.architecture_catalog import build_architecture_catalog
from ncig.generator import generate_layout
from ncig.model import BuildingAnchor, Vec3
from ncig.cli import _cmd_probe_plan


def fixture():
    return json.loads(Path(Path(__file__).parents[1] / "examples" / "architecture_harvest_fixture.json").read_text(encoding="utf-8"))


def test_v016_apply_writes_quaternion_rotation():
    b = BuildingAnchor("B16", "Watson", "commercial", Vec3(0,0,0), 30, 8, 8, 1)
    layout = generate_layout(b)
    cat = build_architecture_catalog(fixture(), max_per_class=20, interior_only=True)
    from ncig.architecture_assembler import build_architecture_assembly
    assembly = build_architecture_assembly([layout], cat)
    plan = {"building_id":"B16","nodes":[],"sectors":[{"id":"B16_F01","floor":0}]}
    out = apply_architecture_to_world_plan(plan, assembly)
    node = next(x for x in out["nodes"] if x.get("type")=="worldMeshNode")
    q = node["rotation"]
    assert set(q) == {"i","j","k","r"}
    assert node["rotation_deg"] != 0.0


def test_v016_partial_dimensions_are_explicit():
    b = BuildingAnchor("B17", "Watson", "commercial", Vec3(0,0,0), 0, 8, 8, 1)
    layout = generate_layout(b)
    cat = build_architecture_catalog(fixture(), max_per_class=20, interior_only=True)
    from ncig.architecture_assembler import build_architecture_assembly
    assembly = build_architecture_assembly([layout], cat)
    infos = [p["selection"] for p in assembly["buildings"][0]["placements"] if p.get("resource")]
    assert infos
    assert all("dimension_coverage" in x for x in infos)


def test_v016_probe_plan_detects_mesh_gap(tmp_path):
    plan = {"nodes":[{"type":"worldMeshNode"},{"type":"worldEntityNode"}],"building_id":"B"}
    templates = {"templates":{"worldEntityNode":[{"type":"worldEntityNode"}]}}
    pp = tmp_path/"plan.json"; tp=tmp_path/"templates.json"; out=tmp_path/"out.json"
    pp.write_text(json.dumps(plan),encoding="utf-8"); tp.write_text(json.dumps(templates),encoding="utf-8")
    class A: pass
    a=A(); a.plan=str(pp); a.templates=str(tp); a.out=str(out)
    assert _cmd_probe_plan(a)==0
    data=json.loads(out.read_text(encoding="utf-8"))
    assert "worldMeshNode" in data["missing_node_types"]
