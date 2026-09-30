from ncig.generator import generate_layout
from ncig.model import BuildingAnchor, Vec3
from ncig.worldplan import build_world_plan
from ncig.object_spawner import build_schema_backed_object_spawner
from ncig.reference_nodes import entity_node, mesh_node, light_node
from ncig.plan_lint import lint_report


def _building():
    return BuildingAnchor(
        id="v010_001", district="watson", type="residential",
        position=Vec3(10, 20, 0), yaw_deg=15, width_m=18, depth_m=14,
        floors=3, seed=123,
    )


def test_world_plan_assigns_every_node_to_a_floor_and_has_vertical_links():
    plan = build_world_plan(generate_layout(_building()))
    assert all("floor" in node for node in plan["nodes"])
    assert len(plan["connectivity"]["validation"]) >= 2
    assert plan["connectivity"]["validation"]["vertical_link_count"] == 4
    assert sum(e["type"] == "vertical_transition" for e in plan["connectivity"]["edges"]) == 4
    assert lint_report(plan)["valid"]


def test_native_bridge_keeps_nodes_in_their_floor_sector():
    plan = build_world_plan(generate_layout(_building()))
    templates = {
        "format": "ncig-template-harvest-v1",
        "templates": {
            "worldMeshNode": [mesh_node(name="mesh", node_ref="$/#mesh", position={"x":0,"y":0,"z":0}, mesh_path="base\\test\\wall.mesh", appearance="default")],
            "worldStaticMarkerNode": [entity_node(name="marker", node_ref="$/#marker", position={"x":0,"y":0,"z":0}, entity_path="base\\test\\marker.ent")],
        }
    }
    out = build_schema_backed_object_spawner(plan, templates=templates)
    floor_counts = {}
    for sector in out["sectors"]:
        floor_counts[sector["name"]] = len(sector["nodes"])
    assert len(floor_counts) == 3
    assert all(v > 0 for v in floor_counts.values())
    assert out["ncig"]["emitted_node_count"] == sum(floor_counts.values())


def test_plan_lint_catches_missing_floor():
    plan = build_world_plan(generate_layout(_building()))
    plan["nodes"][0].pop("floor")
    report = lint_report(plan)
    assert not report["valid"]
    assert any(f["code"] == "MISSING_FLOOR" for f in report["findings"])
