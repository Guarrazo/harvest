import json
from pathlib import Path

from ncig.asset_harvest import harvest, harvest_templates
from ncig.reference_nodes import entity_node, mesh_node, light_node, collision_node, area_shape_node, fnv1a64


def test_reference_serializers_shapes():
    pos = {"x": 1.0, "y": 2.0, "z": 3.0}
    e = entity_node(name="e", node_ref="$/#e", position=pos, entity_path="base\\foo.ent")
    m = mesh_node(name="m", node_ref="$/#m", position=pos, mesh_path="base\\foo.mesh")
    l = light_node(name="l", node_ref="$/#l", position=pos)
    c = collision_node(name="c", node_ref="$/#c", position=pos, size={"x":2,"y":3,"z":4})
    a = area_shape_node(name="a", node_ref="$/#a", markers=[(0,0,0),(2,0,0),(2,2,0),(0,2,0)])
    assert e["type"] == "worldEntityNode" and e["data"]["entityTemplate"]["DepotPath"]["$value"].endswith(".ent")
    assert m["type"] == "worldMeshNode" and m["data"]["mesh"]["DepotPath"]["$value"].endswith(".mesh")
    assert l["type"] == "worldStaticLightNode" and "intensity" in l["data"]
    assert c["type"] == "worldCollisionNode" and c["data"]["compiledData"]["Data"]["Actors"]
    assert a["type"] == "worldAreaShapeNode" and a["data"]["outline"]["Data"]["buffer"]
    assert fnv1a64("abc") == "16654208175385433931"


def test_automatic_harvest_and_templates(tmp_path: Path):
    root = tmp_path / "entSpawner"
    (root / "data" / "favorite").mkdir(parents=True)
    probe = {
        "xlFormat": 0,
        "version": "1.0.4",
        "name": "favorite_test",
        "sectors": [{"nodes": [{
            "type": "worldMeshNode", "name": "mesh", "position": {"x": 0, "y": 0, "z": 0},
            "data": {"mesh": {"DepotPath": {"$type":"ResourcePath","$value":"base\\test\\wall.mesh"}}, "meshAppearance":{"$type":"CName","$value":"default","$storage":"string"}}
        }]}]
    }
    (root / "data" / "favorite" / "test.json").write_text(json.dumps(probe), encoding="utf-8")
    (root / "data" / "favorite" / "test.lua").write_text('local p = "base\\test\\chair.ent"', encoding="utf-8")
    assets = harvest(root)
    assert "base\\test\\wall.mesh" in assets["resources"]
    assert "base\\test\\chair.ent" in assets["resources"]
    templates = harvest_templates(root)
    assert templates["counts"]["worldMeshNode"] == 1
