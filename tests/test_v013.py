from ncig.preflight import build_preflight, merge_harvests


def test_preflight_blocks_mesh_without_template_even_with_resource():
    plan = {"building_id": "b", "nodes": [{"type": "worldMeshNode", "name": "wall", "data": {"resource": "base\\foo\\wall.mesh"}}]}
    assets = {"format": "ncig-harvest-v1", "resources": {"base\\foo\\wall.mesh": {"path": "base\\foo\\wall.mesh", "roles": ["wall", "mesh"]}}}
    report = build_preflight(plan, assets=assets, templates={"format": "ncig-template-harvest-v1", "counts": {}})
    assert not report["ready"]
    assert report["summary"]["blocked_nodes"] == 1
    assert "no harvested template" in report["blockers"][0]["reasons"][0]


def test_preflight_allows_area_with_markers_without_template():
    plan = {"building_id": "b", "nodes": [{"type": "worldAreaShapeNode", "name": "room", "data": {"markers": [[0,0,0],[1,0,0],[1,1,0],[0,1,0]]}}]}
    report = build_preflight(plan)
    assert report["ready"]
    assert report["summary"]["ready_nodes"] == 1


def test_merge_harvests_is_union_and_deterministic():
    a = {"format":"ncig-harvest-v1", "root":"a", "files_scanned":2, "source_files":{"json":2}, "node_type_mentions":{"worldMeshNode":1}, "resources":{"base\\a.mesh":{"path":"base\\a.mesh","roles":["mesh"],"sources":["a.json"],"extensions":[".mesh"]}}}
    b = {"format":"ncig-harvest-v1", "root":"b", "files_scanned":3, "source_files":{"lua":3}, "node_type_mentions":{"worldEntityNode":2}, "resources":{"base\\a.mesh":{"path":"base\\a.mesh","roles":["wall"],"sources":["b.lua"],"extensions":[".mesh"]}, "base\\b.ent":{"path":"base\\b.ent","roles":["entity"],"sources":["b.json"],"extensions":[".ent"]}}}
    out = merge_harvests(b, a)
    assert out["resource_count"] == 2
    assert out["resources"]["base\\a.mesh"]["roles"] == ["mesh", "wall"]
    assert out["node_type_mentions"] == {"worldEntityNode": 2, "worldMeshNode": 1}
