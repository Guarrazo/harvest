from __future__ import annotations

import json
from pathlib import Path

from ncig.collision_probe import load_manifest, probe_target, run_probe


def _sector(path: Path) -> None:
    raw = {
        "Header": {"filepath": "base\\worlds\\03_night_city\\exterior_test.streamingsector.json"},
        "Data": {
            "nodes": [
                {"Data": {"type": "worldCollisionNode", "name": "FacadeBlock", "position": {"x": 0, "y": 0, "z": 1}}},
                {"Data": {"type": "worldMeshNode", "name": "DoorFacade", "resource": "base\\door.mesh", "position": {"x": 0, "y": 2, "z": 1}}},
                {"Data": {"type": "worldBuildingProxyMeshNode", "name": "Proxy", "position": {"x": 1, "y": 2, "z": 2}}},
                {"Data": {"type": "worldCollisionNode", "name": "OtherCollision", "position": {"x": 20, "y": 20, "z": 0}}},
            ],
            "nodeData": [
                {"NodeIndex": 0, "position": {"x": 0, "y": 0, "z": 1}, "scale": {"x": 1, "y": 1, "z": 1}},
                {"NodeIndex": 1, "position": {"x": 0, "y": 2, "z": 1}},
                {"NodeIndex": 2, "position": {"x": 1, "y": 2, "z": 2}},
                {"NodeIndex": 3, "position": {"x": 20, "y": 20, "z": 0}},
            ],
        }
    }
    path.write_text(json.dumps(raw), encoding="utf-8")


def _manifest(path: Path, source: Path) -> None:
    data = {
        "format": "ncig-collision-removal-manifest-v1",
        "version": "0.24.0",
        "targets": [{
            "building_id": "auto_test",
            "source_file": str(source),
            "sector": source.stem,
            "node_type": "worldCollisionNode",
            "node_index": 0,
            "expectedNodes": 4,
            "reason": "explicit_collision_overlaps_detected_exterior_door",
            "safe_to_auto_remove": True,
        }],
    }
    path.write_text(json.dumps(data), encoding="utf-8")


def test_probe_exact_target_and_neighbor_types(tmp_path: Path) -> None:
    sector = tmp_path / "exterior_test.streamingsector.json"
    _sector(sector)
    manifest = {
        "building_id": "auto_test",
        "source_file": str(sector),
        "sector": sector.stem,
        "node_type": "worldCollisionNode",
        "node_index": 0,
        "expectedNodes": 4,
        "reason": "explicit_collision_overlaps_detected_exterior_door",
        "safe_to_auto_remove": True,
    }
    report = probe_target(manifest, sector, nearby_radius_m=5.0, nearby_limit=8)
    assert report["node_index_in_range"] is True
    assert report["expectedNodes_matches_export"] is True
    assert report["target_type_matches_manifest"] is True
    assert "worldMeshNode" in report["nearby_node_type_counts"]
    assert "worldBuildingProxyMeshNode" in report["nearby_node_type_counts"]
    assert report["diagnostic"]["classification"] == "explicit_collision_target"
    assert report["archive_xl_path_recovered"] is True
    assert "expectedNodes: 4" in report["archive_xl_fragment"]
    assert "index: 0" in report["archive_xl_fragment"]


def test_run_probe_resolves_moved_export_root(tmp_path: Path) -> None:
    sectors = tmp_path / "sectors"
    sectors.mkdir()
    source = sectors / "exterior_test.streamingsector.json"
    _sector(source)
    manifest = tmp_path / "manifest.json"
    _manifest(manifest, Path(r"C:\CyberpunkExports\sectors\exterior_test.streamingsector.json"))
    out = run_probe(manifest, sectors, limit=1)
    assert out["probe_count"] == 1
    assert out["error_count"] == 0
    assert out["probes"][0]["node_index"] == 0


def test_manifest_format_is_checked(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"format": "wrong", "targets": []}), encoding="utf-8")
    try:
        load_manifest(bad)
    except ValueError as exc:
        assert "unsupported manifest format" in str(exc)
    else:
        raise AssertionError("invalid manifest format was accepted")
