from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ncig.refine_pipeline import clean_catalog, refine_candidates, refine_layouts


def test_candidate_rejects_existing_interior() -> None:
    report = {
        "format": "old",
        "candidates": [{
            "id": "a",
            "score": 90,
            "type": "commercial",
            "width_m": 10,
            "depth_m": 10,
            "height_m": 6,
            "position": {"x": 0, "y": 0, "z": 0},
            "evidence": {
                "architecture_nodes": 30,
                "entrance_nodes": 2,
                "wall_nodes": 12,
                "wall_sides": ["north", "south", "east", "west"],
                "geometry_ready": True,
                "interior_nodes": 14,
            },
        }],
    }
    out = refine_candidates(report)
    assert out["output_candidate_count"] == 0
    assert out["strong_rejections"] == 1


def test_candidate_dedupes_two_entries_same_shell() -> None:
    base = {
        "score": 85,
        "type": "commercial",
        "width_m": 10,
        "depth_m": 10,
        "height_m": 8,
        "evidence": {"architecture_nodes": 20, "entrance_nodes": 1, "wall_nodes": 8, "wall_sides": ["north", "south", "east"], "geometry_ready": True, "interior_nodes": 0},
    }
    report = {"format": "old", "candidates": [
        {**base, "id": "a", "position": {"x": 0, "y": 0, "z": 0}},
        {**base, "id": "b", "position": {"x": 3, "y": 2, "z": 0}, "score": 80},
    ]}
    out = refine_candidates(report)
    assert out["output_candidate_count"] == 1
    assert out["duplicate_suppressed"] == 1


def test_catalog_removes_triangles_and_frames() -> None:
    catalog = {"format": "x", "items": [
        {"class": "floor_piece", "family": "a", "path": "int_floor_triangle_l300_w300.mesh", "score": 10, "dimensions": {"complete": True, "metres": {"l": 3, "w": 3, "h": 0.1}}},
        {"class": "floor_piece", "family": "a", "path": "int_floor_tile_l300_w300.mesh", "score": 9, "dimensions": {"complete": True, "metres": {"l": 3, "w": 3, "h": 0.1}}},
        {"class": "wall_piece", "family": "a", "path": "int_wall_frame_w300_h300.mesh", "score": 10, "dimensions": {"complete": True, "metres": {"l": 0.2, "w": 3, "h": 3}}},
        {"class": "wall_piece", "family": "a", "path": "int_wall_solid_w300_h300.mesh", "score": 9, "dimensions": {"complete": True, "metres": {"l": 0.2, "w": 3, "h": 3}}},
    ]}
    out = clean_catalog(catalog)
    paths = {x["path"] for x in out["items"]}
    assert "int_floor_triangle_l300_w300.mesh" not in paths
    assert "int_wall_frame_w300_h300.mesh" not in paths
    assert "int_floor_tile_l300_w300.mesh" in paths
    assert "int_wall_solid_w300_h300.mesh" in paths


def test_layout_refinement_changes_topology_and_keeps_closed_two_sided_envelope() -> None:
    bundle = {"format": "old", "layouts": [{
        "building": {"id": "b1", "district": "watson", "type": "commercial", "position": {"x": 10, "y": 20, "z": 0}, "yaw_deg": 15, "width_m": 14, "depth_m": 12, "floors": 1, "entry_local_x": 0, "entry_local_y": -5},
        "rooms": [], "sockets": [], "sectors": [], "warnings": []
    }]}
    out = refine_layouts(bundle)
    rooms = out["layouts"][0]["rooms"]
    assert len(rooms) >= 4
    for room in rooms:
        assert room["width"] >= 1.8
        assert room["depth"] > 0
    # Front and back strips together cover the two exterior bands; no room can protrude outside the envelope.
    assert min(r["x"] for r in rooms) >= -7.00001
    assert max(r["x"] + r["width"] for r in rooms) <= 7.00001
    assert min(r["y"] for r in rooms) >= -6.00001
    assert max(r["y"] + r["depth"] for r in rooms) <= 6.00001


if __name__ == "__main__":
    test_candidate_rejects_existing_interior()
    test_candidate_dedupes_two_entries_same_shell()
    test_catalog_removes_triangles_and_frames()
    test_layout_refinement_changes_topology_and_keeps_closed_two_sided_envelope()
    print("NCIG v0.23.0 refinement tests: OK")
