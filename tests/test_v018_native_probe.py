import json
from pathlib import Path

from ncig.native_probe import build_template_harvest_from_export, summarize_native_probe
from ncig.object_spawner import mesh_node, synthesize_schema_node


def probe_export():
    node = mesh_node(
        name="probe_mesh",
        node_ref="$/#probe_mesh",
        position={"x": 1.0, "y": 2.0, "z": 3.0},
        mesh_path="base\\environment\\architecture\\probe.mesh",
        appearance="default",
        render_profile={
            "castLocalShadows": "Enabled",
            "castRayTracedGlobalShadows": "Disabled",
            "castRayTracedLocalShadows": "Disabled",
            "castShadows": "Enabled",
            "occluderType": "Default",
            "windImpulseEnabled": 0,
        },
    )
    node.pop("ncigSchema", None)
    node.pop("ncigWarnings", None)
    return {
        "xlFormat": 0,
        "sectors": [{
            "min": {"x": 0, "y": 0, "z": 0},
            "max": {"x": 10, "y": 10, "z": 10},
            "variantIndices": [0],
            "nodes": [node],
            "variants": [],
            "category": "Interior",
            "level": 1,
            "prefabRef": "",
            "name": "probe",
        }],
        "variants": [],
        "version": "1.0.4",
        "name": "probe",
        "devices": [],
        "psEntries": [],
    }


def test_v018_native_probe_extracts_real_mesh_template():
    data = probe_export()
    report = summarize_native_probe(data, source="probe.json")
    assert report["node_type_counts"] == {"worldMeshNode": 1}
    assert report["templates"]["worldMeshNode"][0]["data"]["mesh"]["DepotPath"]["$value"].endswith("probe.mesh")


def test_v018_template_harvest_is_compatible_with_existing_bridge():
    harvested = build_template_harvest_from_export(probe_export(), source="probe.json")
    assert harvested["counts"]["worldMeshNode"] == 1
    assert harvested["templates"]["worldMeshNode"][0]["ncigSourceFile"] == "probe.json"


def test_v018_remote_prepare_passes_templates_to_audit():
    text = (Path(__file__).parents[1] / "tools" / "prepare_architecture_remote.cmd").read_text(encoding="utf-8")
    assert '--templates "%CACHE%\\templates.json"' in text


def test_v018_mesh_template_materialization_preserves_native_position_w():
    template = probe_export()["sectors"][0]["nodes"][0]
    spec = {
        "type": "worldMeshNode",
        "name": "generated",
        "position": {"x": 10.0, "y": 20.0, "z": 30.0},
        "data": {"resource": "base\\environment\\architecture\\wall.mesh"},
    }
    node, warning = synthesize_schema_node(spec, "B1", templates={"templates": {"worldMeshNode": [template]}})
    assert warning is None
    assert node["position"] == {"x": 10.0, "y": 20.0, "z": 30.0, "w": 0}
    assert node["streamingRefPoint"] == {"x": 10.0, "y": 20.0, "z": 30.0, "w": 0}
