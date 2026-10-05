from ncig.architecture_assembler import _wall_run, build_architecture_assembly
from ncig.model import BuildingAnchor, Layout, Room, Sector, Vec3
from ncig.native_collision import build_room_collisions


def _single_layout(*, entry=None):
    building_data = {
        "id": "B1",
        "district": "test",
        "type": "commercial",
        "position": {"x": 0, "y": 0, "z": 0},
        "yaw_deg": 0,
        "width_m": 8,
        "depth_m": 8,
        "floors": 1,
    }
    if entry:
        building_data.update(entry)
    room = {
        "id": "B1_F1_R01",
        "floor": 0,
        "x": -4,
        "y": 0.8,
        "width": 8,
        "depth": 3.2,
    }
    return {
        "building": building_data,
        "rooms": [room],
        "sectors": [],
    }


def test_collision_door_gap_is_on_corridor_wall_not_exterior_wall():
    nodes, _ = build_room_collisions(_single_layout())
    north = [n for n in nodes if "_B1_F1_R01_COLL_north_" in n["nodeRef"]]
    south = [n for n in nodes if "_B1_F1_R01_COLL_south_" in n["nodeRef"]]
    assert len(north) >= 2
    assert len(south) == 1
    assert any(n["nodeRef"].endswith("COLL_north_header") for n in nodes)


def test_detected_entry_opens_the_external_wall():
    building = BuildingAnchor(
        "B1", "test", "commercial", Vec3(0, 0, 0), 0, 8, 8, 1,
        entry_local_x=0.0, entry_local_y=3.7, entry_yaw_deg=90.0,
    )
    room = Room("B1_F1_R01", "shopfloor", 0, -4, 0.6, 8, 3.2)
    sector = Sector("B1_sector_F01", "B1", 0, "interior", Vec3(-4, -4, -1), Vec3(4, 4, 4), [room.id])
    layout = Layout(building, [room], [], [sector], [])
    dims = lambda l, w, h: {"source": "filename_hint", "metres": {"l": l, "w": w, "h": h}, "complete": True}
    items = []
    for cls, suffix, l, w, h in [
        ("floor_piece", "floor", 3.0, 3.0, 0.1),
        ("wall_piece", "wall", 3.0, 0.1, 3.0),
        ("ceiling_piece", "ceiling", 3.0, 3.0, 0.1),
        ("door_frame", "doorframe", 1.2, 0.1, 2.1),
        ("door_piece", "door", 1.2, 0.05, 2.1),
        ("window_piece", "window", 2.0, 0.1, 1.4),
    ]:
        items.append({
            "path": f"base\\environment\\architecture\\common\\int\\shopkit_{suffix}_l{int(l*100)}_w{int(w*100)}_h{int(h*100)}.mesh",
            "class": cls,
            "family": "common/int/shopkit",
            "score": 100,
            "dimensions": dims(l, w, h),
        })
    catalog = {"format": "ncig-architecture-catalog-v1", "items": items, "selected_count": len(items)}
    out = build_architecture_assembly([layout], catalog)
    placements = out["buildings"][0]["placements"]
    entry_doors = [p for p in placements if p["id"].endswith("_ARCH_entry_door")]
    assert len(entry_doors) == 1
    assert not any(p["id"].endswith("_ARCH_door") for p in placements)
    external_north = [
        p for p in placements
        if p["class"] == "wall_piece"
        and p["target"].get("side") == "south"
        and p["target"].get("opening") is not None
    ]
    assert external_north


def test_thin_runtime_wall_receives_mirrored_visual_face():
    building = BuildingAnchor("B1", "test", "commercial", Vec3(0, 0, 0), 0, 6, 6, 1)
    room = Room("B1_F1_R01", "shopfloor", 0, -3, 0, 6, 3)
    sector = Sector("B1_sector_F01", "B1", 0, "interior", Vec3(-3, -1, 0), Vec3(3, 4, 4), [room.id])
    layout = Layout(building, [room], [], [sector], [])
    wall = {
        "path": "base\\environment\\architecture\\common\\int\\shopkit_wall.mesh",
        "class": "wall_piece",
        "family": "common/int/shopkit",
        "score": 100,
        "dimensions": {"source": "runtime_mesh", "complete": True},
        "bounds": {
            "min": {"x": -1.5, "y": -0.02, "z": 0.0},
            "max": {"x": 1.5, "y": 0.02, "z": 3.0},
            "dimensions_m": {"x": 3.0, "y": 0.04, "z": 3.0},
        },
    }
    placements = []
    _wall_run(
        layout, room, {
            "items": [
                wall,
                {"path": "base\\environment\\architecture\\common\\int\\shopkit_wall2.mesh",
                 "class": "wall_piece", "family": "common/int/shopkit", "score": 90,
                 "dimensions": {"source": "runtime_mesh", "complete": True},
                 "bounds": wall["bounds"]},
            ]
        },
        placements, side="north", x0=room.x, y0=room.y, length=6.0,
        rotation_deg=0.0, family="common/int/shopkit",
    )
    assert len(placements) == 4
    assert sum(1 for p in placements if p["semantic"] == "wall_backface") == 2


def test_detected_exterior_entry_collision_gap_is_on_facade_wall():
    layout = _single_layout(entry={"entry_local_x": 0.0, "entry_local_y": 3.7})
    nodes, _ = build_room_collisions(layout)
    south = [n for n in nodes if "_B1_F1_R01_COLL_south_" in n["nodeRef"]]
    north = [n for n in nodes if "_B1_F1_R01_COLL_north_" in n["nodeRef"]]
    assert len(south) >= 2
    assert len(north) == 1
    assert any(n["nodeRef"].endswith("COLL_south_header") for n in nodes)
