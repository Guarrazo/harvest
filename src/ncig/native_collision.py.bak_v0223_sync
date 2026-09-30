from __future__ import annotations

import copy
import math
from typing import Any

from .reference_nodes import collision_node, quat_yaw

FLOOR_HEIGHT = 3.2
WALL_HEIGHT = 3.0
WALL_THICKNESS = 0.12
FLOOR_THICKNESS = 0.10
DOOR_GAP = 1.0


def _with_template(template: dict[str, Any] | None, generated: dict[str, Any], *, name: str, node_ref: str, position: dict[str, float], rotation: dict[str, float]) -> dict[str, Any]:
    out = copy.deepcopy(template) if isinstance(template, dict) else generated
    if template is None:
        out = generated
    out["name"] = name
    out["nodeRef"] = node_ref
    out["position"] = {"x": float(position["x"]), "y": float(position["y"]), "z": float(position["z"]), "w": 0}
    out["streamingRefPoint"] = {"x": float(position["x"]), "y": float(position["y"]), "z": float(position["z"]), "w": 0}
    out["rotation"] = copy.deepcopy(rotation)
    out["scale"] = {"x": 1.0, "y": 1.0, "z": 1.0}
    out["type"] = "worldCollisionNode"
    if template is not None:
        out["data"] = generated["data"]
    return out


def _box(template: dict[str, Any] | None, *, name: str, ref: str, pos: dict[str, float], half: tuple[float, float, float], yaw: float) -> dict[str, Any]:
    q = quat_yaw(yaw)
    generated = collision_node(
        name=name,
        node_ref=ref,
        position=pos,
        size={"x": half[0], "y": half[1], "z": half[2]},
        rotation=q,
    )
    return _with_template(template, generated, name=name, node_ref=ref, position=pos, rotation=q)


def _world(layout_building: dict[str, Any], x: float, y: float, z: float) -> dict[str, float]:
    a = math.radians(float(layout_building.get("yaw_deg", 0.0)))
    c, s = math.cos(a), math.sin(a)
    p = layout_building.get("position", {})
    return {
        "x": float(p.get("x", 0.0)) + c * x - s * y,
        "y": float(p.get("y", 0.0)) + s * x + c * y,
        "z": float(p.get("z", 0.0)) + z,
    }


def _wall_segments(start: float, length: float, opening: tuple[float, float] | None) -> list[tuple[float, float]]:
    if not opening:
        return [(0.0, length)]
    a, b = opening
    out = []
    if a > 0.05:
        out.append((0.0, a))
    if b < length - 0.05:
        out.append((b, length))
    return out


def build_room_collisions(layout: dict[str, Any], *, template: dict[str, Any] | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    building = layout.get("building", {})
    rooms = [r for r in layout.get("rooms", []) or [] if isinstance(r, dict)]
    nodes: list[dict[str, Any]] = []

    floors = sorted({int(r.get("floor", 0)) for r in rooms})
    floor_node_count = 0
    for floor in floors:
        floor_rooms = [r for r in rooms if int(r.get("floor", 0)) == floor]
        if not floor_rooms:
            continue
        min_x = min(float(r.get("x", 0.0)) for r in floor_rooms)
        max_x = max(float(r.get("x", 0.0)) + float(r.get("width", 0.0)) for r in floor_rooms)
        min_y = min(float(r.get("y", 0.0)) for r in floor_rooms)
        max_y = max(float(r.get("y", 0.0)) + float(r.get("depth", 0.0)) for r in floor_rooms)
        w = max(0.1, max_x - min_x)
        d = max(0.1, max_y - min_y)
        center = _world(
            building,
            (min_x + max_x) * 0.5,
            (min_y + max_y) * 0.5,
            floor * FLOOR_HEIGHT - FLOOR_THICKNESS,
        )
        ref_id = str(building.get("id", "building"))
        floor_ref = f"$/#{ref_id}_F{floor + 1:02d}_COLL_floor"
        floor_name = f"[NCIG COLLISION] {ref_id}_F{floor + 1:02d}_floor"
        nodes.append(_box(
            template,
            name=floor_name,
            ref=floor_ref,
            pos=center,
            half=(w * 0.5, d * 0.5, FLOOR_THICKNESS),
            yaw=float(building.get("yaw_deg", 0.0)),
        ))
        floor_node_count += 1

    for room in rooms:
        rid = str(room.get("id"))
        floor = int(room.get("floor", 0))
        rx, ry = float(room.get("x", 0.0)), float(room.get("y", 0.0))
        w, d = float(room.get("width", 0.0)), float(room.get("depth", 0.0))
        zbase = floor * FLOOR_HEIGHT

        gap = DOOR_GAP
        opening = (w / 2 - gap / 2, w / 2 + gap / 2)
        opening_side = "north" if ry < 0 else "south"

        for side in ("north", "south", "west", "east"):
            if side == "north":
                parts = _wall_segments(0, w, opening if opening_side == side else None)
                for idx, (a, b) in enumerate(parts, 1):
                    local = _world(building, rx + (a + b) / 2, ry, zbase + WALL_HEIGHT / 2)
                    nodes.append(_box(
                        template,
                        name=f"[NCIG COLLISION] {rid}_{side}_{idx}",
                        ref=f"$/#{building.get('id','building')}_{rid}_COLL_{side}_{idx}",
                        pos=local,
                        half=((b - a) / 2, WALL_THICKNESS / 2, WALL_HEIGHT / 2),
                        yaw=float(building.get("yaw_deg", 0.0)),
                    ))
            elif side == "south":
                parts = _wall_segments(0, w, opening if opening_side == side else None)
                for idx, (a, b) in enumerate(parts, 1):
                    local = _world(building, rx + (a + b) / 2, ry + d, zbase + WALL_HEIGHT / 2)
                    nodes.append(_box(
                        template,
                        name=f"[NCIG COLLISION] {rid}_{side}_{idx}",
                        ref=f"$/#{building.get('id','building')}_{rid}_COLL_{side}_{idx}",
                        pos=local,
                        half=((b - a) / 2, WALL_THICKNESS / 2, WALL_HEIGHT / 2),
                        yaw=float(building.get("yaw_deg", 0.0)),
                    ))
            elif side == "west":
                local = _world(building, rx, ry + d / 2, zbase + WALL_HEIGHT / 2)
                nodes.append(_box(
                    template,
                    name=f"[NCIG COLLISION] {rid}_{side}",
                    ref=f"$/#{building.get('id','building')}_{rid}_COLL_{side}",
                    pos=local,
                    half=(d / 2, WALL_THICKNESS / 2, WALL_HEIGHT / 2),
                    yaw=float(building.get("yaw_deg", 0.0)) + 90,
                ))
            else:
                local = _world(building, rx + w, ry + d / 2, zbase + WALL_HEIGHT / 2)
                nodes.append(_box(
                    template,
                    name=f"[NCIG COLLISION] {rid}_{side}",
                    ref=f"$/#{building.get('id','building')}_{rid}_COLL_{side}",
                    pos=local,
                    half=(d / 2, WALL_THICKNESS / 2, WALL_HEIGHT / 2),
                    yaw=float(building.get("yaw_deg", 0.0)) + 90,
                ))

    return nodes, {
        "format": "ncig-native-collision-v1",
        "node_count": len(nodes),
        "room_count": len(rooms),
        "floor_node_count": floor_node_count,
        "policy": "continuous_floor_per_floor_plus_room_shell_walls_with_door_openings",
    }
