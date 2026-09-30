import json
from pathlib import Path

from ncig.object_spawner import build_schema_backed_object_spawner
from ncig.reference_nodes import mesh_node, light_node


def test_schema_bridge_uses_harvested_templates(tmp_path: Path):
    plan = {
        "building_id": "b1",
        "sectors": [{"id":"b1_F01","floor":0,"extents":{"min":{"x":0,"y":0,"z":0},"max":{"x":10,"y":10,"z":3}}}],
        "nodes": [
            {"name":"wall","type":"worldMeshNode","floor":0,"position":{"x":1,"y":2,"z":0}},
            {"name":"light","type":"worldStaticLightNode","floor":0,"position":{"x":2,"y":2,"z":2}},
        ],
    }
    templates = {
        "format": "ncig-template-harvest-v1",
        "templates": {
            "worldMeshNode": [mesh_node(name="source", node_ref="$/#source", position={"x":0,"y":0,"z":0}, mesh_path="base\\test\\wall.mesh", appearance="default", render_profile={
                "castLocalShadows":"Enabled", "castRayTracedGlobalShadows":"Enabled", "castRayTracedLocalShadows":"Disabled", "castShadows":"Enabled", "occluderType":"Default", "windImpulseEnabled":0
            })],
            "worldStaticLightNode": [light_node(name="source_light", node_ref="$/#source_light", position={"x":0,"y":0,"z":0}, profile={"type":"Point","contactShadows":"Disabled","attenuation":"Default"})]
        }
    }
    out = build_schema_backed_object_spawner(plan, None, templates=templates)
    nodes = out["sectors"][0]["nodes"]
    assert {x["type"] for x in nodes} == {"worldMeshNode","worldStaticLightNode"}
    assert all(not any(k.lower().startswith("ncig") for k in x) for x in nodes)
