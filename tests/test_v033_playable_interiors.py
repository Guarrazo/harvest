import json

from ncig.object_spawner import synthesize_schema_node
from ncig.reference_nodes import interior_trigger_node, mesh_node


def test_mesh_serializer_matches_entspawner_shape():
    node = mesh_node(
        name="[NCIG] test_mesh",
        node_ref="$/#test_mesh",
        position={"x": 1.0, "y": 2.0, "z": 3.0},
        mesh_path="base\\environment\\architecture\\common\\int\\sample.mesh",
    )
    assert node["type"] == "worldMeshNode"
    assert node["uk10"] == 1040
    assert node["data"]["mesh"]["DepotPath"]["$value"].endswith(".mesh")
    assert "$type" not in node["data"]["mesh"]["DepotPath"]
    assert node["data"]["castLocalShadows"] == "Default"
    assert node["data"]["castRayTracedGlobalShadows"] == "Default"
    assert node["data"]["castRayTracedLocalShadows"] == "Default"
    assert node["data"]["castShadows"] == "Default"
    assert node["data"]["occluderType"] == "Default"
    assert node["data"]["windImpulseEnabled"] == 1


def test_world_mesh_can_be_synthesized_without_template():
    spec = {
        "type": "worldMeshNode",
        "name": "floor",
        "position": {"x": 1.0, "y": 2.0, "z": 3.0},
        "rotation": {"i": 0, "j": 0, "k": 0, "r": 1},
        "scale": {"x": 1.0, "y": 1.0, "z": 1.0},
        "data": {"resource": "base\\environment\\architecture\\common\\int\\sample.mesh"},
    }
    node, warning = synthesize_schema_node(spec, "demo", assets=None, templates=None)
    assert warning is None
    assert node["type"] == "worldMeshNode"
    assert node["data"]["mesh"]["DepotPath"]["$value"].endswith("sample.mesh")


def test_interior_trigger_contains_interior_notifier_and_outline():
    node = interior_trigger_node(
        name="[NCIG INTERIOR] demo",
        node_ref="$/#demo_INTERIOR",
        markers=[(0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0)],
        height=3.0,
    )
    assert node["type"] == "worldTriggerAreaNode"
    notifiers = node["data"]["notifiers"]
    assert notifiers[0]["Data"]["$type"] == "worldInteriorAreaNotifier"
    assert notifiers[0]["Data"]["treatAsInterior"] == 1
    assert notifiers[0]["Data"]["setTier2"] == 0
    assert "outline" in node["data"]
