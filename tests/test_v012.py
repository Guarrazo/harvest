from ncig.resource_resolver import bind_resources, infer_semantics, resolve_resource
from ncig.object_spawner import build_schema_backed_object_spawner


def _assets():
    return {
        "format": "ncig-harvest-v1",
        "resources": {
            "base\\foo\\office_wall.mesh": {"path": "base\\foo\\office_wall.mesh", "roles": ["wall", "mesh"], "sources": ["a.json"]},
            "base\\foo\\concrete_panel.mesh": {"path": "base\\foo\\concrete_panel.mesh", "roles": ["wall", "mesh"], "sources": ["b.json"]},
            "base\\foo\\office_floor.mesh": {"path": "base\\foo\\office_floor.mesh", "roles": ["floor", "mesh"], "sources": ["a.json"]},
            "base\\foo\\office_door.ent": {"path": "base\\foo\\office_door.ent", "roles": ["door", "entity"], "sources": ["c.json"]},
        },
        "by_role": {
            "wall": ["base\\foo\\office_wall.mesh", "base\\foo\\concrete_panel.mesh"],
            "floor": ["base\\foo\\office_floor.mesh"],
            "door": ["base\\foo\\office_door.ent"],
            "entity": ["base\\foo\\office_door.ent"],
        },
    }


def test_infer_semantics_from_generated_wall_name():
    spec = {"type": "worldMeshNode", "name": "b_F01_wall_n", "data": {"logicalType": "wall_segment", "materialRole": "wall"}}
    assert infer_semantics(spec)[0] == "wall"


def test_resolver_prefers_matching_role_and_filename_over_first_candidate():
    spec = {"type": "worldMeshNode", "name": "office_floor", "data": {"resourceRole": "floor"}}
    result = resolve_resource(spec, _assets())
    assert result["resource"] == "base\\foo\\office_floor.mesh"
    assert result["confidence"] == "high"


def test_entity_resolution_enforces_ent_extension():
    spec = {"type": "worldEntityNode", "name": "office_door", "data": {"semantic": "door"}}
    result = resolve_resource(spec, _assets())
    assert result["resource"].endswith(".ent")


def test_bind_resources_is_deterministic_and_preserves_explicit_assignment():
    plan = {"building_id": "b", "nodes": [
        {"type": "worldMeshNode", "name": "b_wall", "data": {"materialRole": "wall"}},
        {"type": "worldMeshNode", "name": "b_floor", "data": {"resource": "base\\explicit\\floor.mesh", "resourceRole": "floor"}},
    ]}
    bound, report = bind_resources(plan, _assets())
    assert bound["nodes"][0]["data"]["resource"] == "base\\foo\\office_wall.mesh"
    assert bound["nodes"][1]["data"]["resource"] == "base\\explicit\\floor.mesh"
    assert report["bound_count"] == 1
    assert report["skipped_count"] == 1


def test_schema_bridge_uses_resolved_asset_not_first_by_role():
    plan = {"building_id": "b", "sectors": [{"id":"b_F01","floor":0,"extents":{"min":{"x":0,"y":0,"z":0},"max":{"x":5,"y":5,"z":3}}}], "nodes": [
        {"type":"worldEntityNode", "name":"b_door", "floor":0, "position":{"x":1,"y":1,"z":0}, "data":{"semantic":"door"}}
    ]}
    out = build_schema_backed_object_spawner(plan, assets=_assets())
    node = out["sectors"][0]["nodes"][0]
    assert node["data"]["entityTemplate"]["DepotPath"]["$value"] == "base\\foo\\office_door.ent"


def test_opening_semantic_outranks_generic_wall_logical_type():
    assets = _assets()
    assets["resources"]["base\\foo\\office_doorframe.mesh"] = {"path":"base\\foo\\office_doorframe.mesh","roles":["door","mesh"],"sources":["d.json"]}
    assets["by_role"].setdefault("door", []).append("base\\foo\\office_doorframe.mesh")
    spec = {"type":"worldMeshNode", "name":"room_door_opening", "data":{"materialRole":"opening", "logicalType":"wall_segment"}}
    result = resolve_resource(spec, assets)
    assert result["resource"] == "base\\foo\\office_doorframe.mesh"


def test_no_semantic_intent_does_not_bind_arbitrary_mesh():
    spec = {"type":"worldMeshNode", "name":"room_prop_03", "data":{}}
    result = resolve_resource(spec, _assets())
    assert result["resource"] is None
    assert result["reason"] == "no-semantic-intent"
