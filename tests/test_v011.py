from ncig.generator import generate_layout
from ncig.model import BuildingAnchor, Vec3
from ncig.worldplan import build_world_plan
from ncig.object_spawner import build_schema_backed_object_spawner
from ncig.reference_nodes import mesh_node, collision_node
from ncig.shell import build_playable_shell


def _building():
    return BuildingAnchor(
        id="v011_001", district="watson", type="residential",
        position=Vec3(100, 200, 5), yaw_deg=37, width_m=12, depth_m=10,
        floors=2, seed=42,
    )


def test_architecture_rotation_includes_building_yaw():
    plan = build_world_plan(generate_layout(_building()))
    wall = next(n for n in plan["nodes"] if n["data"].get("logicalType") == "wall_segment")
    assert abs(wall["rotation"]["k"]) > 0.1


def test_playable_shell_has_one_area_per_room_and_no_collision_without_verified_values():
    layout = generate_layout(_building())
    shell = build_playable_shell(layout)
    assert shell["validation"]["room_count"] == shell["validation"]["area_node_count"]
    assert shell["validation"]["collision_node_count"] == 0
    assert shell["collision"]["enabled"] is False


def test_playable_shell_can_emit_floor_and_wall_collisions_with_explicit_values():
    layout = generate_layout(_building())
    shell = build_playable_shell(layout, collision_preset="TestPreset", collision_material="TestMaterial")
    assert shell["validation"]["collision_node_count"] > 0
    assert shell["collision"]["enabled"] is True


def test_harvested_mesh_and_collision_templates_receive_plan_overrides():
    plan = {
        "building_id": "b1",
        "sectors": [{"id": "b1_F01", "floor": 0, "extents": {"min": {"x": 0, "y": 0, "z": 0}, "max": {"x": 5, "y": 5, "z": 3}}}],
        "nodes": [
            {"name": "wall", "type": "worldMeshNode", "floor": 0, "position": {"x": 1, "y": 2, "z": 0}, "data": {"resource": "base\\real\\wall.mesh", "appearance": "variant"}},
            {"name": "col", "type": "worldCollisionNode", "floor": 0, "position": {"x": 2, "y": 2, "z": 0}, "data": {"size": {"x": 4, "y": 0.2, "z": 3}, "preset": "P", "material": "M"}},
        ],
    }
    templates = {
        "format": "ncig-template-harvest-v1",
        "templates": {
            "worldMeshNode": [mesh_node(name="src", node_ref="$/#src", position={"x": 0, "y": 0, "z": 0}, mesh_path="base\\old\\wall.mesh", appearance="default", render_profile={"castLocalShadows": "Enabled", "castRayTracedGlobalShadows": "Enabled", "castRayTracedLocalShadows": "Disabled", "castShadows": "Enabled", "occluderType": "Default", "windImpulseEnabled": 0})],
            "worldCollisionNode": [collision_node(name="src_col", node_ref="$/#src_col", position={"x": 0, "y": 0, "z": 0}, size={"x": 1, "y": 1, "z": 1}, preset="OldP", material="OldM")],
        },
    }
    out = build_schema_backed_object_spawner(plan, templates=templates)
    mesh, col = out["sectors"][0]["nodes"]
    assert mesh["data"]["mesh"]["DepotPath"]["$value"] == "base\\real\\wall.mesh"
    assert mesh["data"]["meshAppearance"]["$value"] == "variant"
    shape = col["data"]["compiledData"]["Data"]["Actors"][0]["Shapes"][0]
    assert shape["Size"]["X"] == 4.0
    assert shape["Size"]["Y"] == 0.2
    assert shape["Size"]["Z"] == 3.0
    assert shape["Preset"]["$value"] == "P"
    assert shape["Materials"][0]["$value"] == "M"


def test_area_template_is_rebuilt_from_room_markers():
    layout = generate_layout(_building())
    plan = build_world_plan(layout, playable_shell=True)
    area = next(n for n in plan["nodes"] if n["type"] == "worldAreaShapeNode")
    out = build_schema_backed_object_spawner(plan)
    area_out = next(n for n in out["sectors"][0]["nodes"] if n["name"].endswith("_area"))
    assert area_out["data"]["outline"]["Data"]["buffer"]
