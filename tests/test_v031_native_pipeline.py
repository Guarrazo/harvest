from ncig.native_collision import build_room_collisions


def _layout(entry_x: float, entry_y: float, *, floors: int = 2) -> dict:
    bid = "test_building"
    building = {
        "id": bid,
        "position": {"x": 0.0, "y": 0.0, "z": 0.0},
        "width_m": 12.0,
        "depth_m": 10.0,
        "floors": floors,
        "yaw_deg": 0.0,
        "entry_local_x": entry_x,
        "entry_local_y": entry_y,
        "entry_yaw_deg": 0.0,
        "vertical_core": {"continuous": floors > 1},
    }
    rooms = [
        {"id": f"{bid}_F{f+1}_stair", "kind": "stairwell", "floor": f, "x": -1.3, "y": 1.0, "width": 2.6, "depth": 3.2}
        for f in range(floors)
    ]
    rooms += [
        {"id": f"{bid}_F1_room", "kind": "office", "floor": 0, "x": -5.5, "y": -3.5, "width": 3.0, "depth": 2.5},
        {"id": f"{bid}_F2_room", "kind": "office", "floor": 1, "x": 2.0, "y": -3.5, "width": 3.0, "depth": 2.5},
    ]
    return {"building": building, "rooms": rooms}


def test_lateral_entry_header_calls_do_not_raise():
    for entry in [(-6.0, 0.0), (6.0, 0.0)]:
        nodes, meta = build_room_collisions(_layout(*entry))
        assert nodes
        assert meta["node_count"] == len(nodes)


def test_stairwell_void_splits_floor_collision():
    nodes, _ = build_room_collisions(_layout(-6.0, 0.0))
    floor_nodes = [n for n in nodes if "_COLL_floor" in str(n.get("nodeRef", ""))]
    assert len(floor_nodes) > 2
    assert any("_seg" in str(n.get("nodeRef", "")) for n in floor_nodes)


def test_single_storey_does_not_create_floor_hole():
    nodes, _ = build_room_collisions(_layout(-6.0, 0.0, floors=1))
    floor_nodes = [n for n in nodes if "_COLL_floor" in str(n.get("nodeRef", ""))]
    assert len(floor_nodes) == 1
    assert "_seg" not in str(floor_nodes[0].get("nodeRef", ""))
