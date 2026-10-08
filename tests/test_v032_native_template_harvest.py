import json

from ncig.native_template_harvest import harvest_native_templates


def test_harvests_worldmesh_from_streamingsector_tree(tmp_path):
    root = tmp_path / "sectors"
    root.mkdir()
    sector = {
        "Data": {
            "nodes": [{
                "type": "worldMeshNode",
                "position": {"x": 1, "y": 2, "z": 3},
                "rotation": {"i": 0, "j": 0, "k": 0, "r": 1},
                "scale": {"x": 1, "y": 1, "z": 1},
                "streamingRefPoint": {"x": 1, "y": 2, "z": 3},
                "data": {
                    "mesh": {
                        "DepotPath": {
                            "$value": "base\\\\environment\\\\architecture\\\\common\\\\int\\\\sample.mesh"
                        }
                    }
                }
            }]
        }
    }
    (root / "always_loaded_0.streamingsector.json").write_text(json.dumps(sector), encoding="utf-8")

    out = harvest_native_templates(root, max_files=8)
    assert out["harvest"]["mesh_fallback"] is False
    assert len(out["templates"]["worldMeshNode"]) == 1
    assert out["templates"]["worldMeshNode"][0]["data"]["mesh"]["DepotPath"]["$value"].endswith(".mesh")


def test_mesh_fallback_is_explicit(tmp_path):
    root = tmp_path / "sectors"
    root.mkdir()
    (root / "empty.json").write_text("{}", encoding="utf-8")
    out = harvest_native_templates(root, max_files=8)
    assert out["harvest"]["mesh_fallback"] is True
    assert out["templates"]["worldMeshNode"][0]["ncigTemplateMode"] == "reference_serializer_fallback"

def test_base_templates_merge_preserves_harvest_metadata(tmp_path):
    root = tmp_path / "sectors"
    root.mkdir()
    (root / "empty.json").write_text("{}", encoding="utf-8")
    base = {
        "format": "ncig-template-harvest-v1",
        "templates": {
            "worldEntityNode": [{
                "type": "worldEntityNode",
                "position": {"x": 0, "y": 0, "z": 0},
                "rotation": {"i": 0, "j": 0, "k": 0, "r": 1},
                "scale": {"x": 1, "y": 1, "z": 1},
                "streamingRefPoint": {"x": 0, "y": 0, "z": 0},
                "data": {"entityTemplate": {"DepotPath": {"$value": "base\\\\entities\\\\sample.ent"}}}
            }]
        }
    }
    out = harvest_native_templates(root, base_templates=base, max_files=8)
    assert out["harvest"]["base_templates_merged"] is True
    assert out["harvest"]["mesh_fallback"] is True
    assert out["counts"]["worldEntityNode"] == 1
