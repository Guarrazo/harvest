import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from ncig.structural_layout_upgrade import upgrade_layout_bundle
from ncig.structural_assembly_upgrade import upgrade_assembly


def sample_bundle(floors=3):
    building = {
        "id": "v028_demo",
        "district": "watson",
        "type": "commercial",
        "position": {"x": 100.0, "y": 200.0, "z": 0.0},
        "yaw_deg": 15.0,
        "width_m": 16.0,
        "depth_m": 14.0,
        "floors": floors,
        "entry_local_x": 0.0,
        "entry_local_y": 6.5,
        "entry_yaw_deg": 15.0,
    }
    rooms = []
    sectors = []
    for floor in range(floors):
        rooms.extend([
            {"id": f"v028_demo_F{floor+1}_R01", "kind": "shopfloor", "floor": floor, "x": -8.0, "y": 0.9, "width": 6.0, "depth": 5.0, "rotation_deg": 0.0, "is_start": floor == 0, "is_exit": False},
            {"id": f"v028_demo_F{floor+1}_R02", "kind": "stockroom", "floor": floor, "x": -2.0, "y": 0.9, "width": 4.0, "depth": 5.0, "rotation_deg": 0.0, "is_start": False, "is_exit": False},
            {"id": f"v028_demo_F{floor+1}_R03", "kind": "office", "floor": floor, "x": 2.0, "y": 0.9, "width": 6.0, "depth": 5.0, "rotation_deg": 0.0, "is_start": False, "is_exit": floor == floors - 1},
            {"id": f"v028_demo_F{floor+1}_R04", "kind": "shopfloor", "floor": floor, "x": -8.0, "y": -5.9, "width": 8.0, "depth": 5.0, "rotation_deg": 0.0, "is_start": False, "is_exit": False},
            {"id": f"v028_demo_F{floor+1}_R05", "kind": "stockroom", "floor": floor, "x": 0.0, "y": -5.9, "width": 8.0, "depth": 5.0, "rotation_deg": 0.0, "is_start": False, "is_exit": False},
        ])
        sectors.append({"id": f"v028_demo_sector_F{floor+1:02d}", "building_id": building["id"], "floor": floor, "category": "interior", "min_xyz": {"x": 91, "y": 191, "z": floor*3.2-0.2}, "max_xyz": {"x": 109, "y": 209, "z": floor*3.2+4.0}, "rooms": []})
    return {"format": "ncig-layout-refined-v1", "layouts": [{"building": building, "rooms": rooms, "sockets": [], "sectors": sectors, "warnings": []}]}


def test_structural_layout_creates_continuous_core_and_vertical_links():
    out = upgrade_layout_bundle(sample_bundle())
    layout = out["layouts"][0]
    cores = [r for r in layout["rooms"] if r.get("kind") == "stairwell"]
    links = [s for s in layout["sockets"] if s.get("kind") == "vertical_link"]
    assert len(cores) == 3
    assert len(links) == 4
    assert layout["building"]["vertical_core"]["continuous"] is True
    assert layout["building"]["vertical_core"]["same_xy_across_floors"] is True
    assert len(layout["zones"]) >= 6


def test_structural_layout_rebuilds_sockets_after_room_split():
    out = upgrade_layout_bundle(sample_bundle())
    layout = out["layouts"][0]
    room_ids = {str(r["id"]) for r in layout["rooms"]}
    for socket in layout["sockets"]:
        assert socket.get("room_id") in room_ids
    stair_ids = {r["id"] for r in layout["rooms"] if r["kind"] == "stairwell"}
    assert all(v in stair_ids for v in layout["building"]["vertical_core"]["room_ids_by_floor"].values())


def test_assembly_adds_stairs_and_removes_surface_overlap():
    bundle = sample_bundle(floors=2)
    layouts = upgrade_layout_bundle(bundle)
    tmp = Path("/tmp/ncig_v028_test")
    tmp.mkdir(exist_ok=True)
    lp = tmp / "layouts.json"; ap = tmp / "assembly.json"; cp = tmp / "catalog.json"; op = tmp / "out.json"
    lp.write_text(json.dumps(layouts), encoding="utf-8")
    assembly = {"format": "ncig-architecture-assembly-style-aware-v1", "buildings": [{
        "id": "v028_demo", "floors": 2, "rooms": 10,
        "placements": [
            {"id":"floor_a", "class":"floor_piece", "resource":"base\\environment\\architecture\\common\\int\\floor_l300_w300_h010.mesh", "floor":0, "position":{"x":100,"y":202,"z":0}, "rotation_deg":15,"scale":{"x":1,"y":1,"z":1}},
            {"id":"ceil_a", "class":"ceiling_piece", "resource":"base\\environment\\architecture\\common\\int\\ceiling_l300_w300_h010.mesh", "floor":0, "position":{"x":100,"y":202,"z":3}, "rotation_deg":15,"scale":{"x":1,"y":1,"z":1}},
        ],
        "placement_count":2,"placement_counts":{"floor_piece":1,"ceiling_piece":1},"class_families":{"stairs_piece":"common/int"},"unresolved":[],"unresolved_count":0,"family_coherence":True
    }]}
    ap.write_text(json.dumps(assembly), encoding="utf-8")
    catalog = {"format":"ncig-architecture-catalog-clean-v1","items":[{
        "path":"base\\environment\\architecture\\common\\stairs\\stairs_l300_w200_h320_a.mesh","class":"stairs_piece","family":"common/int","dimensions":{"metres":{"l":3.0,"w":2.0,"h":3.2},"complete":True},"score":100
    }]}
    cp.write_text(json.dumps(catalog), encoding="utf-8")
    out = upgrade_assembly(lp, ap, cp, op)
    b = out["buildings"][0]
    assert sum(1 for p in b["placements"] if p.get("class") == "stairs_piece") == 2
    assert out["structural_upgrade"]["stairs_placements"] == 2


def test_structural_connectivity_reports_all_rooms_reachable():
    from ncig.structural_connectivity import build_connectivity
    bundle = upgrade_layout_bundle(sample_bundle(floors=3))
    report = build_connectivity(bundle["layouts"][0])
    assert report["all_rooms_reachable"] is True
    assert report["vertical_link_count"] == 4
    assert report["unreachable_rooms"] == []
