import json
from pathlib import Path

from ncig.cli import _cmd_architecture_audit
from ncig.object_spawner import mesh_node


def test_v018_architecture_audit_becomes_mesh_ready_with_real_template(tmp_path: Path):
    catalog = {
        "format": "ncig-architecture-catalog-v1",
        "selected_count": 1,
        "items": [{"class": "wall_piece", "dimensions": {"complete": True}}],
    }
    assembly = {
        "format": "ncig-architecture-assembly-v1",
        "buildings": [{"id": "B1", "placement_count": 4, "unresolved_count": 0}],
    }
    cat_path = tmp_path / "catalog.json"; cat_path.write_text(json.dumps(catalog), encoding="utf-8")
    asm_path = tmp_path / "assembly.json"; asm_path.write_text(json.dumps(assembly), encoding="utf-8")
    template = mesh_node(name="probe", node_ref="$/#probe", position={"x":0,"y":0,"z":0}, mesh_path="base\\probe.mesh", render_profile={
        "castLocalShadows":"Enabled", "castRayTracedGlobalShadows":"Disabled", "castRayTracedLocalShadows":"Disabled",
        "castShadows":"Enabled", "occluderType":"Default", "windImpulseEnabled":0})
    templates = {"format":"ncig-template-harvest-v1", "counts":{"worldMeshNode":1}, "templates":{"worldMeshNode":[template]}}
    tpl_path = tmp_path / "templates.json"; tpl_path.write_text(json.dumps(templates), encoding="utf-8")
    out = tmp_path / "audit.json"

    class A: pass
    a=A(); a.catalog=str(cat_path); a.assembly=str(asm_path); a.templates=str(tpl_path); a.out=str(out)
    assert _cmd_architecture_audit(a) == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["native_worldMesh_template_count"] == 1
    assert report["ready_for_native_mesh_export"] is True
    assert report["assembly_unresolved"] == 0
