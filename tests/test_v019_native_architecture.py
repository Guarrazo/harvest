import json
from pathlib import Path

from ncig.native_architecture import build_native_architecture_export, write_native_architecture_export
from ncig.reference_nodes import mesh_node


def real_like_mesh_template():
    node = mesh_node(
        name="[Static Mesh] h0_001_mm_c__adam_smasher",
        node_ref="",
        position={"x": -1163.4287109375, "y": 1555.0905761719, "z": 31.378211975098},
        mesh_path="base\\characters\\boss\\adam_smasher\\h0_001_mm_c__adam_smasher\\h0_001_mm_c__adam_smasher.mesh",
        appearance="default",
        render_profile={
            "castRayTracedLocalShadows": "Default",
            "castRayTracedGlobalShadows": "Default",
            "castShadows": "Default",
            "occluderType": "Default",
            "windImpulseEnabled": 1,
        },
    )
    node["uk10"] = 1040
    node.pop("ncigSchema", None)
    node.pop("ncigWarnings", None)
    return node


def datasets():
    layout = {
        "format": "ncig-layout-v1",
        "layouts": [{
            "building": {"id": "B1"},
            "rooms": [], "sockets": [],
            "sectors": [{
                "id": "B1_sector_F01", "building_id": "B1", "floor": 0,
                "category": "interior",
                "min_xyz": {"x": -5, "y": -5, "z": 0},
                "max_xyz": {"x": 5, "y": 5, "z": 3.2}, "rooms": []
            }],
        }],
    }
    assembly = {
        "format": "ncig-architecture-assembly-v1",
        "buildings": [{
            "id": "B1", "floors": 1, "rooms": 1,
            "placements": [{
                "id": "B1_floor_01",
                "class": "floor_piece",
                "resource": "base\\environment\\architecture\\floor_probe.mesh",
                "floor": 0,
                "position": {"x": 1.0, "y": 2.0, "z": 0.0},
                "rotation_deg": 90.0,
                "scale": {"x": 1.0, "y": 1.0, "z": 1.0},
            }],
            "placement_count": 1,
            "unresolved_count": 0,
        }],
    }
    templates = {
        "format": "ncig-template-harvest-v1",
        "templates": {"worldMeshNode": [real_like_mesh_template()]},
        "counts": {"worldMeshNode": 1},
    }
    base = {
        "xlFormat": 0,
        "sectors": [{
            "name": "mesh_probe", "prefabRef": "", "min": {"x": 0, "y": 0, "z": 0},
            "max": {"x": 10, "y": 10, "z": 10}, "variants": [], "variantIndices": [0],
            "category": "Exterior", "nodes": [], "level": 1,
        }],
        "variants": [], "name": "mesh_probe", "version": "1.0.4",
        "devices": [], "psEntries": [],
    }
    return layout, assembly, templates, base


def test_v019_native_export_clones_real_mesh_shape_and_patches_known_fields():
    layout, assembly, templates, base = datasets()
    out, report = build_native_architecture_export(layout, assembly, templates, base)
    node = out["sectors"][0]["nodes"][0]
    assert node["type"] == "worldMeshNode"
    assert node["uk10"] == 1040
    assert node["uk11"] == 512
    assert node["data"]["castShadows"] == "Default"
    assert "ncigSourceFile" not in node
    assert node["data"]["windImpulseEnabled"] == 1
    assert node["data"]["mesh"]["DepotPath"]["$value"] == "base\\environment\\architecture\\floor_probe.mesh"
    assert node["position"] == {"x": 1.0, "y": 2.0, "z": 0.0, "w": 0.0}
    assert node["streamingRefPoint"] == {"x": 1.0, "y": 2.0, "z": 0.0, "w": 0}
    assert abs(node["rotation"]["k"] - 0.70710678) < 1e-6
    assert abs(node["rotation"]["r"] - 0.70710678) < 1e-6
    assert report["emitted_node_count"] == 1
    assert report["bounds_validation_required"] is True


def test_v019_writer_supports_single_building(tmp_path: Path):
    layout, assembly, templates, base = datasets()
    def w(name, data):
        p = tmp_path / name
        p.write_text(json.dumps(data), encoding="utf-8")
        return p
    out = tmp_path / "native.json"
    report = tmp_path / "report.json"
    meta = write_native_architecture_export(w("layouts.json", layout), w("assembly.json", assembly), w("templates.json", templates), w("base.json", base), out, report, building_id="B1")
    assert meta["building_ids"] == ["B1"]
    exported = json.loads(out.read_text(encoding="utf-8"))
    assert len(exported["sectors"][0]["nodes"]) == 1
