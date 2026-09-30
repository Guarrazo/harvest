from __future__ import annotations

from typing import Any

from .architecture import build_room_shell
from .model import Layout, Room
from .generator import world_pos


def _q_yaw(yaw_deg: float) -> dict[str, float]:
    import math
    h = math.radians(float(yaw_deg)) / 2.0
    return {"i": 0.0, "j": 0.0, "k": math.sin(h), "r": math.cos(h)}


def _room_markers(layout: Layout, room: Room, z: float) -> list[dict[str, float]]:
    pts = [
        (room.x, room.y),
        (room.x + room.width, room.y),
        (room.x + room.width, room.y + room.depth),
        (room.x, room.y + room.depth),
    ]
    out = []
    for x, y in pts:
        p = world_pos(layout.building, x, y, z)
        out.append({"x": p.x, "y": p.y, "z": p.z})
    return out


def _collision_node(name: str, floor: int, position: dict[str, float], size: dict[str, float], rotation: dict[str, float], preset: str, material: str) -> dict[str, Any]:
    return {
        "name": name,
        "type": "worldCollisionNode",
        "floor": floor,
        "nodeRef": f"$/#SHELL_{name}",
        "position": position,
        "rotation": rotation,
        "scale": {"x": 1.0, "y": 1.0, "z": 1.0},
        "primaryRange": 80.0,
        "secondaryRange": 120.0,
        "streamingRefPoint": {**position, "w": 0},
        "data": {"size": size, "preset": preset, "material": material, "logicalType": "shell_collision"},
    }


def build_playable_shell(
    layout: Layout,
    *,
    collision_preset: str | None = None,
    collision_material: str | None = None,
) -> dict[str, Any]:
    """Build the first in-game shell contract around the generated room graph.

    The shell intentionally separates deterministic geometry intent from runtime-sensitive
    node payloads. Collision boxes are emitted only when the caller supplies the exact
    collision preset/material used by their toolchain. Room areas use the known area-shape
    serializer and can be materialized by the native bridge without guessing enum payloads.
    """
    nodes: list[dict[str, Any]] = []
    rooms_out: list[dict[str, Any]] = []
    collision_enabled = bool(collision_preset and collision_material)
    floor_height = 3.2

    for room in layout.rooms:
        z = layout.building.position.z + room.floor * floor_height + 0.02
        markers = _room_markers(layout, room, z)
        door_socket = next((s for s in layout.sockets if s.room_id == room.id and s.kind == "door"), None)
        activity_socket = next((s for s in layout.sockets if s.room_id == room.id and s.kind == "activity"), None)
        center = world_pos(layout.building, room.x + room.width / 2, room.y + room.depth / 2, z)
        area_name = f"{room.id}_area"
        nodes.append({
            "name": area_name,
            "type": "worldAreaShapeNode",
            "floor": room.floor,
            "nodeRef": f"$/#{layout.building.id}_{area_name}",
            "position": {"x": center.x, "y": center.y, "z": center.z},
            "rotation": _q_yaw(layout.building.yaw_deg + room.rotation_deg),
            "scale": {"x": 1.0, "y": 1.0, "z": 1.0},
            "primaryRange": 80.0,
            "secondaryRange": 120.0,
            "streamingRefPoint": {"x": center.x, "y": center.y, "z": center.z, "w": 0},
            "data": {"markers": [[p["x"], p["y"], p["z"]] for p in markers], "height": 2.4, "logicalType": "interior_room_area", "roomId": room.id},
        })

        if collision_enabled:
            for element in build_room_shell(layout.building, room):
                if element.element_type not in {"floor", "wall_segment"} or element.opening:
                    continue
                pos = {"x": element.position.x, "y": element.position.y, "z": element.position.z}
                size = {"x": element.size.x, "y": element.size.y, "z": element.size.z}
                nodes.append(_collision_node(
                    f"{element.id}_collision",
                    room.floor,
                    pos,
                    size,
                    _q_yaw(layout.building.yaw_deg + element.rotation_deg),
                    collision_preset,
                    collision_material,
                ))

        rooms_out.append({
            "id": room.id,
            "floor": room.floor,
            "bounds_local": {"x": room.x, "y": room.y, "width": room.width, "depth": room.depth},
            "area_node": area_name,
            "door_socket": door_socket.id if door_socket else None,
            "activity_socket": activity_socket.id if activity_socket else None,
            "collision": collision_enabled,
        })

    return {
        "format": "ncig-playable-shell-v1",
        "building_id": layout.building.id,
        "collision": {
            "enabled": collision_enabled,
            "preset": collision_preset,
            "material": collision_material,
            "required_for_physical_blocking": True,
        },
        "areas": {"mode": "worldAreaShapeNode", "count": len(layout.rooms)},
        "entrance": next((s.id for s in layout.sockets if s.kind == "entry"), None),
        "vertical_core": [f"{layout.building.id}_F{floor+1:02d}_core" for floor in range(max(1, layout.building.floors))],
        "rooms": rooms_out,
        "nodes": nodes,
        "validation": {
            "room_count": len(rooms_out),
            "area_node_count": sum(1 for n in nodes if n["type"] == "worldAreaShapeNode"),
            "collision_node_count": sum(1 for n in nodes if n["type"] == "worldCollisionNode"),
            "all_rooms_have_doors": all(x["door_socket"] for x in rooms_out) if rooms_out else False,
            "all_rooms_have_areas": sum(1 for x in rooms_out if x["area_node"]) == len(rooms_out),
        },
        "warnings": ([] if collision_enabled else ["Collision nodes were not emitted: supply the exact collision preset and material from a verified World Builder/exporter workflow."]),
    }
