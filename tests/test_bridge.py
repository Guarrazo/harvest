import json
from pathlib import Path
from ncig.bridge import fingerprint_export, build_template_export
from ncig.object_spawner import fingerprint_exact_export, build_exact_object_spawner


def test_fingerprint_and_bridge(tmp_path: Path):
    template = {"objects": [{"type": "worldMeshNode", "name": "old", "position": {"x": 0, "y": 0, "z": 0}, "rotation": {"i":0,"j":0,"k":0,"r":1}, "scale": {"x":1,"y":1,"z":1}}, {"type": "worldEntityNode", "name": "door", "position": {"x":0,"y":0,"z":0}}]}
    tp=tmp_path/'template.json'; tp.write_text(json.dumps(template))
    fp=fingerprint_export(tp)
    assert fp['node_lists'] == ['$.objects']
    plan={"nodes":[{"name":"floor01","type":"worldMeshNode","nodeRef":"$/#floor01","position":{"x":1,"y":2,"z":3},"rotation":{"i":0,"j":0,"k":0,"r":1},"scale":{"x":1,"y":1,"z":1}}]}
    out=build_template_export(plan,tp)
    assert len(out['objects'])==1
    assert out['objects'][0]['name']=='floor01'
    assert out['objects'][0]['position']['z']==3


def test_exact_export_shape_and_bridge():
    import json
    from pathlib import Path
    root = Path(__file__).parents[1]
    template = json.loads((root / "examples" / "ncig_probe_exported.json").read_text(encoding="utf-8"))
    plan = json.loads((root / "build" / "v011_demo" / "wb_plans" / "demo_shop_001_world_plan_v2.json").read_text(encoding="utf-8"))
    fp = fingerprint_exact_export(template)
    assert fp["version"] == "1.0.4"
    assert fp["node_counts"] == {"worldEntityNode": 1}
    result = build_exact_object_spawner(plan, template)
    assert result["name"] == "ncig_demo_shop_001"
    assert result["sectors"][0]["min"] == plan["sectors"][0]["min"]
    assert result["sectors"][0]["max"] == plan["sectors"][0]["max"]
    assert result["ncig"]["emitted_node_count"] == 3
    assert result["ncig"]["skipped_node_count"] > 0
