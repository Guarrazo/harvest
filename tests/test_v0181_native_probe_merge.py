import json
from pathlib import Path

from ncig.native_probe import merge_template_harvests


def test_v0181_merge_preserves_both_types_and_deduplicates():
    a = {
        "format": "ncig-template-harvest-v1",
        "templates": {"worldEntityNode": [{"type": "worldEntityNode", "position": {"x": 0}, "ncigSourceFile": "a.json"}]},
        "source_files": ["a.json"],
    }
    b = {
        "format": "ncig-template-harvest-v1",
        "templates": {
            "worldMeshNode": [{"type": "worldMeshNode", "position": {"x": 1}, "ncigSourceFile": "b.json"}],
            "worldEntityNode": [{"type": "worldEntityNode", "position": {"x": 0}, "ncigSourceFile": "b.json"}],
        },
        "source_files": ["b.json"],
    }
    out = merge_template_harvests(a, b)
    assert out["counts"] == {"worldEntityNode": 1, "worldMeshNode": 1}
    assert out["source_files"] == ["a.json", "b.json"]
