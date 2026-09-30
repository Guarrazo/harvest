from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from .model import BuildingAnchor, Layout, Room, Socket, Vec3
from .generator import world_pos


@dataclass(frozen=True)
class ArchElement:
    id: str
    element_type: str
    room_id: str | None
    floor: int
    position: Vec3
    size: Vec3
    rotation_deg: float = 0.0
    material_role: str = "generic"
    opening: bool = False
    properties: dict[str, Any] | None = None


def _wall_segment(anchor: BuildingAnchor, room: Room, floor: int, suffix: str, x: float, y: float, sx: float, sy: float, rotation: float, role: str, opening: bool = False) -> ArchElement:
    p = world_pos(anchor, x, y, floor * 3.2)
    return ArchElement(
        id=f"{room.id}_{suffix}",
        element_type="wall_segment",
        room_id=room.id,
        floor=floor,
        position=p,
        size=Vec3(sx, sy, 3.0),
        rotation_deg=rotation,
        material_role=role,
        opening=opening,
        properties={"generator": "ncig-v0.2", "collision": True},
    )


def build_room_shell(anchor: BuildingAnchor, room: Room) -> list[ArchElement]:
    z = room.floor * 3.2
    cx, cy = room.x + room.width / 2, room.y + room.depth / 2
    elements = [
        ArchElement(
            id=f"{room.id}_floor",
            element_type="floor",
            room_id=room.id,
            floor=room.floor,
            position=world_pos(anchor, cx, cy, z),
            size=Vec3(room.width, room.depth, 0.10),
            material_role="floor",
            properties={"generator": "ncig-v0.2"},
        ),
        ArchElement(
            id=f"{room.id}_ceiling",
            element_type="ceiling",
            room_id=room.id,
            floor=room.floor,
            position=world_pos(anchor, cx, cy, z + 3.0),
            size=Vec3(room.width, room.depth, 0.10),
            material_role="ceiling",
            properties={"generator": "ncig-v0.2"},
        ),
    ]
    # Corridor-facing opening. One side remains a doorway while all other sides are solid.
    if room.y >= 0:
        door_y = room.y
        elements += [
            _wall_segment(anchor, room, room.floor, "wall_s", cx, room.y + room.depth, room.width, 0.12, 0, "wall"),
            _wall_segment(anchor, room, room.floor, "wall_w", room.x, cy, 0.12, room.depth, 0, "wall"),
            _wall_segment(anchor, room, room.floor, "wall_e", room.x + room.width, cy, 0.12, room.depth, 0, "wall"),
        ]
        # The north/south naming follows the local room orientation, not world orientation.
        gap = min(1.0, max(0.8, room.width * 0.3))
        side = max(0.15, (room.width - gap) / 2)
        elements.append(_wall_segment(anchor, room, room.floor, "wall_n_a", room.x + side / 2, door_y, side, 0.12, 0, "wall"))
        elements.append(_wall_segment(anchor, room, room.floor, "wall_n_b", room.x + room.width - side / 2, door_y, side, 0.12, 0, "wall"))
        elements.append(_wall_segment(anchor, room, room.floor, "door_opening", room.x + room.width / 2, door_y, gap, 0.14, 0, "opening", True))
    else:
        door_y = room.y + room.depth
        elements += [
            _wall_segment(anchor, room, room.floor, "wall_n", cx, room.y, room.width, 0.12, 0, "wall"),
            _wall_segment(anchor, room, room.floor, "wall_w", room.x, cy, 0.12, room.depth, 0, "wall"),
            _wall_segment(anchor, room, room.floor, "wall_e", room.x + room.width, cy, 0.12, room.depth, 0, "wall"),
        ]
        gap = min(1.0, max(0.8, room.width * 0.3))
        side = max(0.15, (room.width - gap) / 2)
        elements.append(_wall_segment(anchor, room, room.floor, "wall_s_a", room.x + side / 2, door_y, side, 0.12, 0, "wall"))
        elements.append(_wall_segment(anchor, room, room.floor, "wall_s_b", room.x + room.width - side / 2, door_y, side, 0.12, 0, "wall"))
        elements.append(_wall_segment(anchor, room, room.floor, "door_opening", room.x + room.width / 2, door_y, gap, 0.14, 0, "opening", True))
    return elements


def build_architecture(layout: Layout) -> list[ArchElement]:
    elements: list[ArchElement] = []
    for room in layout.rooms:
        elements.extend(build_room_shell(layout.building, room))
    return elements


def architecture_to_dict(elements: list[ArchElement]) -> list[dict[str, Any]]:
    return [asdict(e) for e in elements]
