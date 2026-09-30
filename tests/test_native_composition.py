from ncig.object_spawner import build_schema_backed_object_spawner, clean_native_export
from ncig.reference_nodes import entity_node


def test_composition_strips_ncig_metadata():
    plan = {
        "building_id":"b1",
        "sectors":[{"id":"b1_sector_F01","floor":0,"extents":{"min":{"x":0,"y":0,"z":0},"max":{"x":10,"y":10,"z":3}}}],
        "nodes":[]
    }
    raw = entity_node(name="src", node_ref="$/#src", position={"x":1,"y":2,"z":0}, entity_path="base\\foo.ent")
    raw["ncigSourceFile"] = "favorites/foo.json"
    decoration = {"layouts":[{"building_id":"b1","sector_nodes":{"b1_sector_F01":[raw]}}]}
    out = build_schema_backed_object_spawner(plan, decoration=decoration)
    node = out["sectors"][0]["nodes"][0]
    assert node["type"] == "worldEntityNode"
    assert not any(k.lower().startswith("ncig") for k in node)


def test_clean_native_export_removes_ncig_metadata():
    raw = {
        "xlFormat": 0, "version": "1.0.4", "name": "x", "sectors": [{"nodes": [{"type":"worldEntityNode", "position":{"x":0,"y":0,"z":0}, "ncigSource":"x"}], "ncigSector":"x"}],
        "devices": [], "psEntries": [], "ncig": {"debug": True}
    }
    clean = clean_native_export(raw)
    assert "ncig" not in clean
    assert "ncigSector" not in clean["sectors"][0]
    assert not any(k.lower().startswith("ncig") for k in clean["sectors"][0]["nodes"][0])
