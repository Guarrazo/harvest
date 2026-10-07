from __future__ import annotations

import copy
import math
from typing import Any

from .reference_nodes import collision_node, quat_yaw

FLOOR_HEIGHT = 3.2
WALL_HEIGHT = 3.0
WALL_THICKNESS = 0.12
FLOOR_THICKNESS = 0.10
DOOR_GAP = 1.25
DOOR_HEIGHT = 2.20


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


def _has_neighbor(room: dict[str, Any], floor_rooms: list[dict[str, Any]], side: str, eps: float = 0.05) -> bool:
    for other in floor_rooms:
        if str(other.get("id")) == str(room.get("id")):
            continue
        overlap_y = min(float(room.get("y", 0.0)) + float(room.get("depth", 0.0)), float(other.get("y", 0.0)) + float(other.get("depth", 0.0))) - max(float(room.get("y", 0.0)), float(other.get("y", 0.0)))
        if side == "west" and abs(float(room.get("x", 0.0)) - (float(other.get("x", 0.0)) + float(other.get("width", 0.0)))) <= eps and overlap_y > eps:
            return True
        if side == "east" and abs((float(room.get("x", 0.0)) + float(room.get("width", 0.0))) - float(other.get("x", 0.0))) <= eps and overlap_y > eps:
            return True
    return False


def _append_header_collision(
    nodes: list[dict[str, Any]],
    template: dict[str, Any] | None,
    *,
    building: dict[str, Any],
    rid: str,
    side: str,
    floor: int,
    gap: float,
    x: float,
    y: float,
) -> None:
    remaining_h = max(0.0, WALL_HEIGHT - DOOR_HEIGHT)
    if remaining_h <= 0.02:
        return
    z = floor * FLOOR_HEIGHT + DOOR_HEIGHT + remaining_h * 0.5
    local = _world(building, x, y, z)
    if side in {"north", "south"}:
        half = (gap * 0.5, WALL_THICKNESS / 2, remaining_h * 0.5)
        yaw = float(building.get("yaw_deg", 0.0))
    else:
        half = (WALL_THICKNESS / 2, gap * 0.5, remaining_h * 0.5)
        yaw = float(building.get("yaw_deg", 0.0)) + 90
    nodes.append(_box(
        template,
        name=f"[NCIG COLLISION] {rid}_{side}_header",
        ref=f"$/#{building.get('id','building')}_{rid}_COLL_{side}_header",
        pos=local,
        half=half,
        yaw=yaw,
    ))


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
        building_width = float(building.get("width_m", 0.0))
        building_depth = float(building.get("depth_m", 0.0))
        if building_width > 0.0 and building_depth > 0.0:
            min_x, max_x = -building_width * 0.5, building_width * 0.5
            min_y, max_y = -building_depth * 0.5, building_depth * 0.5
        else:
            min_y = min(float(r.get("y", 0.0)) for r in floor_rooms)
            max_y = max(float(r.get("y", 0.0)) + float(r.get("depth", 0.0)) for r in floor_rooms)

        # v0.28 reserves a continuous stairwell shaft at the same local XY on
        # every floor. A single full-footprint floor collider would therefore
        # seal that shaft and make the generated stairs physically unusable.
        # Carve the shaft out of the slab on every non-top floor of a
        # multi-storey continuous core, while keeping a cap on the top floor.
        void = None
        floors_total = max(1, int(building.get("floors", 1) or 1))
        vertical_core = building.get("vertical_core") or {}
        core_room = next((r for r in floor_rooms if str(r.get("kind")) == "stairwell"), None)
        if (
            floors_total > 1
            and bool(vertical_core.get("continuous"))
            and floor < floors_total - 1
            and core_room is not None
        ):
            vx0 = max(min_x, float(core_room.get("x", 0.0)))
            vy0 = max(min_y, float(core_room.get("y", 0.0)))
            vx1 = min(max_x, vx0 + float(core_room.get("width", 0.0)))
            vy1 = min(max_y, vy0 + float(core_room.get("depth", 0.0)))
            if vx1 - vx0 > 0.10 and vy1 - vy0 > 0.10:
                void = (vx0, vy0, vx1, vy1)

        segments: list[tuple[float, float, float, float]] = []
        if void is None:
            segments.append((min_x, min_y, max_x, max_y))
        else:
            vx0, vy0, vx1, vy1 = void
            if vx0 - min_x > 0.05:
                segments.append((min_x, min_y, vx0, max_y))
            if max_x - vx1 > 0.05:
                segments.append((vx1, min_y, max_x, max_y))
            if vx1 - vx0 > 0.10 and vy0 - min_y > 0.05:
                segments.append((vx0, min_y, vx1, vy0))
            if vx1 - vx0 > 0.10 and max_y - vy1 > 0.05:
                segments.append((vx0, vy1, vx1, max_y))

        ref_id = str(building.get("id", "building"))
        for seg_index, (sx0, sy0, sx1, sy1) in enumerate(segments, 1):
            w = max(0.1, sx1 - sx0)
            d = max(0.1, sy1 - sy0)
            center = _world(
                building,
                (sx0 + sx1) * 0.5,
                (sy0 + sy1) * 0.5,
                floor * FLOOR_HEIGHT - FLOOR_THICKNESS,
            )
            suffix = f"_seg{seg_index:02d}" if len(segments) > 1 else ""
            floor_ref = f"$/#{ref_id}_F{floor + 1:02d}_COLL_floor{suffix}"
            floor_name = f"[NCIG COLLISION] {ref_id}_F{floor + 1:02d}_floor{suffix}"
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

        gap = min(DOOR_GAP, w * 0.40 if w > 0 else DOOR_GAP)
        opening = (w / 2 - gap / 2, w / 2 + gap / 2)
        # The visual generator puts the room door on the corridor-facing wall:
        # positive-Y rooms use north (lower local-Y edge); negative-Y rooms use south
        # (upper local-Y edge). Exterior entry openings are tracked separately.
        opening_side = "north" if ry >= 0 else "south"
        entry_opening: tuple[float, float] | None = None
        entry_side: str | None = None
        if floor == 0 and building.get("entry_local_x") is not None and building.get("entry_local_y") is not None:
            ex, ey = float(building["entry_local_x"]), float(building["entry_local_y"])
            closest_x = max(rx, min(ex, rx + w))
            closest_y = max(ry, min(ey, ry + d))
            entry_distance = math.hypot(ex - closest_x, ey - closest_y)
            # Only the room touched by the detected entrance owns the external opening.
            if entry_distance <= 1.6:
                distances = {
                    "north": abs(ey - ry),
                    "south": abs(ey - (ry + d)),
                    "west": abs(ex - rx),
                    "east": abs(ex - (rx + w)),
                }
                entry_side = min(distances, key=distances.get)
                if entry_side in {"north", "south"}:
                    c = max(gap * 0.5, min(w - gap * 0.5, ex - rx))
                else:
                    gap = min(DOOR_GAP, d * 0.40 if d > 0 else DOOR_GAP)
                    c = max(gap * 0.5, min(d - gap * 0.5, ey - ry))
                entry_opening = (c - gap * 0.5, c + gap * 0.5)

        for side in ("north", "south", "west", "east"):
            if side == "north":
                active_opening = opening if opening_side == side else (entry_opening if entry_side == side else None)
                parts = _wall_segments(0, w, active_opening)
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
                if active_opening is not None:
                    center_axis = (active_opening[0] + active_opening[1]) * 0.5
                    _append_header_collision(
                        nodes, template, building=building, rid=rid, side=side, floor=floor,
                        gap=active_opening[1] - active_opening[0],
                        x=rx + center_axis, y=ry,
                    )
            elif side == "south":
                active_opening = opening if opening_side == side else (entry_opening if entry_side == side else None)
                parts = _wall_segments(0, w, active_opening)
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
                if active_opening is not None:
                    center_axis = (active_opening[0] + active_opening[1]) * 0.5
                    _append_header_collision(
                        nodes, template, building=building, rid=rid, side=side, floor=floor,
                        gap=active_opening[1] - active_opening[0],
                        x=rx + center_axis, y=ry + d,
                    )
            elif side == "west":
                if _has_neighbor(room, floor_rooms, "west"):
                    continue
                if entry_side == "west":
                    parts = _wall_segments(0, d, entry_opening)
                    for idx, (a, b) in enumerate(parts, 1):
                        local = _world(building, rx, ry + (a + b) / 2, zbase + WALL_HEIGHT / 2)
                        nodes.append(_box(
                            template,
                            name=f"[NCIG COLLISION] {rid}_{side}_{idx}",
                            ref=f"$/#{building.get('id','building')}_{rid}_COLL_{side}_{idx}",
                            pos=local,
                            half=(WALL_THICKNESS / 2, (b - a) / 2, WALL_HEIGHT / 2),
                            yaw=float(building.get("yaw_deg", 0.0)) + 90,
                        ))
                    if entry_opening is not None:
                        center_axis = (entry_opening[0] + entry_opening[1]) * 0.5
                        _append_header_collision(
                            nodes, template, building=building, rid=rid, side=side, floor=floor,
                            gap=entry_opening[1] - entry_opening[0],
                            x=rx, y=ry + center_axis,
                        )
                    continue
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
                if entry_side == "east":
                    parts = _wall_segments(0, d, entry_opening)
                    for idx, (a, b) in enumerate(parts, 1):
                        local = _world(building, rx + w, ry + (a + b) / 2, zbase + WALL_HEIGHT / 2)
                        nodes.append(_box(
                            template,
                            name=f"[NCIG COLLISION] {rid}_{side}_{idx}",
                            ref=f"$/#{building.get('id','building')}_{rid}_COLL_{side}_{idx}",
                            pos=local,
                            half=(WALL_THICKNESS / 2, (b - a) / 2, WALL_HEIGHT / 2),
                            yaw=float(building.get("yaw_deg", 0.0)) + 90,
                        ))
                    if entry_opening is not None:
                        center_axis = (entry_opening[0] + entry_opening[1]) * 0.5
                        _append_header_collision(
                            nodes, template, building=building, rid=rid, side=side, floor=floor,
                            gap=entry_opening[1] - entry_opening[0],
                            x=rx + w, y=ry + center_axis,
                        )
                    continue
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
        "policy": "segmented_floor_per_floor_with_continuous_stairwell_voids_plus_room_shell_walls_with_door_openings_plus_door_headers",
    }
