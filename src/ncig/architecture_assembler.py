from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from .generator import world_pos
from .architecture_geometry import compatible_family_candidates, dimension_hint_scale, planar_dimensions, rank_family_options, sane_dimensions
from .model import Layout, Room, Vec3
from .runtime_geometry import (
    align_node_local_position,
    linear_fit,
    preferred_surface_rotation,
    scaled_bbox_height,
    surface_scale,
    surface_world_dimensions,
)

FORMAT = "ncig-architecture-assembly-v1"
FLOOR_HEIGHT = 3.2
CEILING_Z = 3.0
DEFAULT_DOOR_WIDTH = 1.30
DEFAULT_DOOR_HEIGHT = 2.20


_STYLE_EXCLUDE = {
    "wall_piece": ("destroyed", "stair", "staircase", "railing", "fence", "cage", "prison", "cell"),
    "door_frame": ("stair", "staircase", "railing", "fence", "cage", "prison", "cell"),
    "door_piece": ("stair", "staircase", "railing", "fence", "cage", "prison", "cell"),
    "window_piece": ("stair", "staircase", "railing", "fence", "cage", "prison", "cell"),
}

def _style_safe_items(items: list[dict[str, Any]], cls: str) -> list[dict[str, Any]]:
    banned = _STYLE_EXCLUDE.get(cls, ())
    safe = [item for item in items if not any(token in (str(item.get("path", "")) + " " + str(item.get("family", ""))).lower() for token in banned)]
    return safe or items

def _items(catalog: dict[str, Any], cls: str, family: str | None = None, building_type: str | None = None) -> list[dict[str, Any]]:
    tokens = _style_tokens(building_type or "mixed")
    return compatible_family_candidates(catalog, cls, family, building_tokens=tokens)


def _style_tokens(building_type: str) -> tuple[str, ...]:
    return {
        "commercial": ("shop", "store", "market", "retail", "mall", "restaurant", "bar", "int"),
        "residential": ("apartment", "res", "housing", "home", "flat", "common\\int"),
        "office": ("office", "corp", "corporate", "business", "int"),
        "industrial": ("industrial", "factory", "warehouse", "workshop", "garage"),
        "mixed": ("shop", "office", "apartment", "common\\int"),
    }.get(building_type, ("int",))


def choose_architecture_family(catalog: dict[str, Any], building_type: str) -> tuple[str | None, dict[str, Any]]:
    """Pick one architectural kit family for a whole building, rather than one unrelated family per piece."""
    items = [x for x in catalog.get("items", []) if isinstance(x, dict) and x.get("class")]
    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        family = str(item.get("family") or "unknown")
        if family != "unknown":
            by_family[family].append(item)

    core = ("floor_piece", "wall_piece", "ceiling_piece")
    secondary = ("door_frame", "door_piece", "window_piece")
    candidates: list[tuple[float, str, dict[str, Any]]] = []
    tokens = _style_tokens(building_type)
    for family, family_items in by_family.items():
        classes = {str(x.get("class")) for x in family_items}
        core_cov = sum(1 for cls in core if cls in classes)
        sec_cov = sum(1 for cls in secondary if cls in classes)
        if core_cov < 2:
            continue
        complete = sum(1 for x in family_items if bool((x.get("dimensions") or {}).get("complete")))
        score_mean = sum(float(x.get("score", 0)) for x in family_items) / max(1, len(family_items))
        style_hits = sum(1 for token in tokens if token in family.lower())
        sane_core = sum(1 for x in family_items if str(x.get("class")) in core and sane_dimensions(x, str(x.get("class"))))
        # Core coverage and sane dimensions dominate. A family that has only a token
        # match but no usable floor/wall/ceiling is not a valid building kit.
        total = core_cov * 850 + sane_core * 180 + sec_cov * 70 + min(20, complete) * 8 + score_mean
        total += style_hits * 80
        info = {
            "family": family,
            "core_coverage": core_cov,
            "sane_core_coverage": sane_core,
            "secondary_coverage": sec_cov,
            "complete_dimension_items": complete,
            "style_hits": style_hits,
            "family_item_count": len(family_items),
            "style_tokens": tokens,
        }
        candidates.append((total, family, info))
    if not candidates:
        return None, {"family": None, "reason": "no_family_with_structural_coverage"}
    candidates.sort(key=lambda row: (-row[0], row[1]))
    _, family, info = candidates[0]
    info["selection_score"] = round(candidates[0][0], 3)
    return family, info



def choose_class_families(catalog: dict[str, Any], primary_family: str | None, building_type: str) -> tuple[dict[str, str], dict[str, Any]]:
    tokens = _style_tokens(building_type)
    classes = (
        "floor_piece", "wall_piece", "ceiling_piece", "door_frame", "door_piece",
        "window_piece", "pillar_piece", "stairs_piece", "rail_piece", "trim_piece",
    )
    families: dict[str, str] = {}
    report: dict[str, Any] = {}
    for cls in classes:
        ranked = rank_family_options(catalog, cls, primary_family, building_tokens=tokens)
        if not ranked:
            continue
        score, family, mode = ranked[0]
        families[cls] = family
        report[cls] = {"family": family, "mode": mode, "selection_score": round(score, 3), "candidates": len(ranked)}
    return families, report

def _dims(item: dict[str, Any]) -> dict[str, float]:
    span, secondary, height = planar_dimensions(item, str(item.get("class") or ""))
    return {
        "l": float(span or 0.0),
        "w": float(secondary or 0.0),
        "h": float(height or 0.0),
    }


def _length_hint(item: dict[str, Any]) -> float | None:
    span, _, _ = planar_dimensions(item, str(item.get("class") or ""))
    return float(span) if isinstance(span, (int, float)) and span > 0 else None


def _floor_dims(item: dict[str, Any]) -> tuple[float | None, float | None]:
    span, secondary, _ = planar_dimensions(item, str(item.get("class") or ""))
    return (
        float(span) if isinstance(span, (int, float)) and span > 0 else None,
        float(secondary) if isinstance(secondary, (int, float)) and secondary > 0 else None,
    )


def _height_hint(item: dict[str, Any]) -> float | None:
    _, _, height = planar_dimensions(item, str(item.get("class") or ""))
    return float(height) if isinstance(height, (int, float)) and height > 0 else None


def _best_item(items: list[dict[str, Any]], *, target_length: float | None = None,
               target_width: float | None = None, target_height: float | None = None) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    if not items:
        return None, {"confidence": "none", "reason": "no_catalog_candidates"}
    ranked: list[tuple[float, int, str, dict[str, Any], dict[str, Any]]] = []
    required = []
    if target_length is not None:
        required.append("length")
    if target_width is not None:
        required.append("width")
    if target_height is not None:
        required.append("height")
    for item in items:
        d = _dims(item)
        score = float(item.get("score", 0))
        errors: list[float] = []
        missing = 0
        coverage = 0
        if target_length is not None:
            length = _length_hint(item)
            if length is not None:
                errors.append(abs(length - target_length))
                coverage += 1
            else:
                missing += 1
        if target_width is not None:
            _, width = _floor_dims(item)
            if width is not None:
                errors.append(abs(width - target_width))
                coverage += 1
            else:
                missing += 1
        if target_height is not None:
            height = _height_hint(item)
            if height is not None:
                errors.append(abs(height - target_height))
                coverage += 1
            else:
                missing += 1
        error = sum(errors) / len(errors) if errors else 0.0
        # Missing required dimensions are penalized heavily so a fully hinted piece
        # beats a higher-scored but dimensionless candidate.
        effective_error = error + missing * 3.0
        # Collisionless variants are poor structural defaults when a collidable variant
        # exists in the same family/class. They remain eligible only as a fallback.
        if item.get("collisionless_variant"):
            effective_error += 0.75
        if not required:
            confidence = "catalog-only"
        elif missing == 0:
            confidence = "hint-fit-complete"
        elif coverage > 0:
            confidence = "hint-fit-partial"
        else:
            confidence = "catalog-only"
        rank = (effective_error * 100.0) - score
        ranked.append((rank, -int(item.get("score", 0)), str(item.get("family", "")), item,
                       {"confidence": confidence,
                        "dimension_error_m": error if errors else None,
                        "missing_dimensions": missing,
                        "dimension_coverage": coverage,
                        "required_dimensions": required,
                        "dimension_source": "runtime_mesh_resource" if isinstance(item.get("bounds"), dict) else "filename_hint"}))
    ranked.sort(key=lambda x: (x[0], x[1], x[2], str(x[3].get("path", ""))))
    _, _, _, chosen, info = ranked[0]
    return chosen, info


def _fit_scale(item: dict[str, Any], proposed: dict[str, float], cls: str | None = None) -> dict[str, float]:
    # Runtime bounds are authoritative. Before bounds are harvested, complete filename
    # dimensions can safely drive a narrow fit (see dimension_hint_scale).
    if not cls:
        return {k: float(v) for k, v in proposed.items()}
    hinted = dimension_hint_scale(item, cls, proposed)
    return hinted or {"x": 1.0, "y": 1.0, "z": 1.0}


def _placement(layout: Layout, room: Room, item: dict[str, Any], *, element_id: str,
               local_x: float, local_y: float, local_z: float, rotation_deg: float,
               semantic: str, target: dict[str, Any], info: dict[str, Any],
               scale: dict[str, float] | None = None,
               target_bbox_center: tuple[float, float, float] | None = None) -> dict[str, Any]:
    final_scale = scale or {"x": 1.0, "y": 1.0, "z": 1.0}
    relative_rotation = float(room.rotation_deg + rotation_deg)
    px, py, pz = float(local_x), float(local_y), float(local_z + room.floor * FLOOR_HEIGHT)
    if target_bbox_center is not None and isinstance(item.get("bounds"), dict):
        px, py, pz = align_node_local_position(item, final_scale, relative_rotation, target_bbox_center)
    world = world_pos(layout.building, px, py, pz)
    return {
        "id": element_id,
        "class": item.get("class"),
        "semantic": semantic,
        "resource": item.get("path"),
        "family": item.get("family"),
        "kit_family": item.get("family"),
        "room_id": room.id,
        "floor": room.floor,
        "position": {"x": world.x, "y": world.y, "z": world.z},
        "rotation_deg": float(layout.building.yaw_deg + relative_rotation),
        "scale": final_scale,
        "target": target,
        "selection": info,
        "requires_bounds_validation": True,
        "dimension_hints": item.get("dimensions"),
    }


def _tile_axis(total: float, piece: float | None) -> list[tuple[float, float, float]]:
    if total <= 0:
        return []
    if not piece or piece <= 0.1:
        return [(total / 2.0, total, 1.0)]
    count = max(1, int(round(total / piece)))
    actual = total / count
    scale = actual / piece
    return [(actual * (i + 0.5), actual, scale) for i in range(count)]


def _floor_bounds(rooms: list[Room], building: Any | None = None) -> tuple[float, float, float, float]:
    if building is not None:
        width = float(getattr(building, "width_m", 0.0))
        depth = float(getattr(building, "depth_m", 0.0))
        if width > 0.0 and depth > 0.0:
            return (-width * 0.5, width * 0.5, -depth * 0.5, depth * 0.5)
    return (
        min(r.x for r in rooms),
        max(r.x + r.width for r in rooms),
        min(r.y for r in rooms),
        max(r.y + r.depth for r in rooms),
    )


def _floor_surface(layout: Layout, floor_rooms: list[Room], catalog: dict[str, Any], placements: list[dict[str, Any]], family: str | None) -> None:
    if not floor_rooms:
        return
    min_x, max_x, min_y, max_y = _floor_bounds(floor_rooms, layout.building)
    width, depth = max_x - min_x, max_y - min_y
    floor = floor_rooms[0].floor
    item, info = _best_item(_items(catalog, "floor_piece", family, layout.building.type),
                            target_length=width, target_width=depth)
    if item is None:
        return
    runtime_mesh = isinstance(item.get("bounds"), dict)
    if runtime_mesh:
        orientation = preferred_surface_rotation(item, width, depth)
        piece_x, piece_y = surface_world_dimensions(item, orientation)
    else:
        orientation, piece_x, piece_y = 0.0, *_floor_dims(item)
    xs, ys = _tile_axis(width, piece_x), _tile_axis(depth, piece_y)
    for ix, (cx, actual_x, _) in enumerate(xs, 1):
        for iy, (cy, actual_y, _) in enumerate(ys, 1):
            if runtime_mesh:
                fit = surface_scale(item, actual_x, actual_y, orientation) or {"x": 1.0, "y": 1.0, "z": 1.0}
                bbox_center = (min_x + cx, min_y + cy, floor * FLOOR_HEIGHT + scaled_bbox_height(item, fit) * 0.5)
            else:
                fit = _fit_scale(item, {"x": actual_x / max(piece_x or actual_x, 1e-6),
                                        "y": actual_y / max(piece_y or actual_y, 1e-6), "z": 1.0}, "floor_piece")
                bbox_center = None
            placements.append(_placement(
                layout, floor_rooms[0], item,
                element_id=f"{floor_rooms[0].id.rsplit('_', 1)[0]}_ARCH_floor_F{floor+1:02d}_{ix:02d}_{iy:02d}",
                local_x=min_x + cx, local_y=min_y + cy, local_z=0.0,
                rotation_deg=orientation, semantic="floor",
                target={"width_m": width, "depth_m": depth, "tile_x": ix, "tile_y": iy,
                        "fit_scale": fit, "surface_orientation_deg": orientation},
                info=info, scale=fit, target_bbox_center=bbox_center,
            ))


def _wall_run(layout: Layout, room: Room, catalog: dict[str, Any], placements: list[dict[str, Any]], *,
              side: str, x0: float, y0: float, length: float, rotation_deg: float,
              opening: tuple[float, float] | None = None, family: str | None = None) -> None:
    candidates = _style_safe_items(_items(catalog, "wall_piece", family, layout.building.type), "wall_piece")
    item, info = _best_item(candidates, target_length=min(length, 3.0), target_height=3.0)
    if item is None:
        return
    piece = _length_hint(item) or min(length, 3.0)
    ranges = [(0.0, length)]
    if opening:
        start, end = opening
        start = max(0.0, min(length, start))
        end = max(start, min(length, end))
        ranges = []
        if start > 0.05:
            ranges.append((0.0, start))
        if end < length - 0.05:
            ranges.append((end, length))
    runtime_mesh = isinstance(item.get("bounds"), dict)
    counter = 0
    for a, b in ranges:
        run = b - a
        count = max(1, int(round(run / piece)))
        actual = run / count
        if runtime_mesh:
            fit_info = linear_fit(item, span=actual, height=3.0, desired_rotation_deg=rotation_deg)
            fit = (fit_info or {}).get("scale") or {"x": 1.0, "y": 1.0, "z": 1.0}
            actual_rotation = float((fit_info or {}).get("rotation_deg", rotation_deg))
        else:
            span_scale = actual / piece
            if not 0.72 <= span_scale <= 1.28 and run > piece * 1.25:
                count = max(1, int(math.ceil(run / piece)))
                actual = run / count
            fit = _fit_scale(item, {"span": actual, "height": 3.0}, "wall_piece")
            actual_rotation = rotation_deg
        cursor = a
        for _ in range(count):
            center = cursor + actual / 2.0
            cursor += actual
            lx, ly = x0, y0
            if side in {"north", "south"}:
                lx += center
            else:
                ly += center
            bbox_center = (lx, ly, room.floor * FLOOR_HEIGHT + 1.5) if runtime_mesh else None
            counter += 1
            placements.append(_placement(
                layout, room, item,
                element_id=f"{room.id}_ARCH_wall_{side}_{counter:02d}",
                local_x=lx, local_y=ly, local_z=0.0,
                rotation_deg=actual_rotation, semantic="wall",
                target={"run_m": length, "segment_m": actual, "side": side, "opening": opening,
                        "fit_scale": fit,
                        "runtime_span_axis": (fit_info or {}).get("span_axis") if runtime_mesh else None},
                info=info, scale=fit, target_bbox_center=bbox_center,
            ))


def _door_and_frame(layout: Layout, room: Room, catalog: dict[str, Any], placements: list[dict[str, Any]], frame_family: str | None, door_family: str | None, wall_family: str | None = None) -> tuple[tuple[float, float], str]:
    gap = min(DEFAULT_DOOR_WIDTH, room.width * 0.40)
    room_center_x = room.x + room.width / 2.0
    if room.y >= 0:
        y, side, rotation = room.y, "south", 0.0
    else:
        y, side, rotation = room.y + room.depth, "north", 180.0
    center = room_center_x - room.x
    opening = (center - gap / 2.0, center + gap / 2.0)
    frame_family = wall_family or frame_family
    door_family = wall_family or door_family
    frame_items = _style_safe_items(_items(catalog, "door_frame", frame_family, layout.building.type), "door_frame")
    door_items = _style_safe_items(_items(catalog, "door_piece", door_family, layout.building.type), "door_piece")
    frame, finfo = _best_item(frame_items, target_length=gap, target_height=DEFAULT_DOOR_HEIGHT)
    door, dinfo = _best_item(door_items, target_length=gap, target_height=DEFAULT_DOOR_HEIGHT)
    for suffix, cls, item, info in (("frame", "door_frame", frame, finfo), ("door", "door_piece", door, dinfo)):
        if item is None:
            continue
        runtime_mesh = isinstance(item.get("bounds"), dict)
        if runtime_mesh:
            fit_info = linear_fit(item, span=gap, height=DEFAULT_DOOR_HEIGHT, desired_rotation_deg=rotation)
            fit = (fit_info or {}).get("scale") or {"x": 1.0, "y": 1.0, "z": 1.0}
            actual_rotation = float((fit_info or {}).get("rotation_deg", rotation))
            bbox_center = (room_center_x, y, room.floor * FLOOR_HEIGHT + DEFAULT_DOOR_HEIGHT * 0.5)
        else:
            fit = _fit_scale(item, {"span": gap, "height": DEFAULT_DOOR_HEIGHT}, cls)
            actual_rotation, bbox_center = rotation, None
        placements.append(_placement(
            layout, room, item,
            element_id=f"{room.id}_ARCH_{suffix}",
            local_x=room_center_x, local_y=y, local_z=0.0,
            rotation_deg=actual_rotation, semantic=cls,
            target={"opening_width_m": gap, "opening_height_m": DEFAULT_DOOR_HEIGHT, "wall_side": side, "fit_scale": fit,
                    "runtime_span_axis": (fit_info or {}).get("span_axis") if runtime_mesh else None},
            info=info, scale=fit, target_bbox_center=bbox_center,
        ))
    return opening, side


def _window(layout: Layout, room: Room, catalog: dict[str, Any], placements: list[dict[str, Any]], family: str | None) -> None:
    windows = _style_safe_items(_items(catalog, "window_piece", family, layout.building.type), "window_piece")
    if not windows or room.width < 2.8:
        return
    item, info = _best_item(windows, target_length=min(room.width, 2.0), target_height=1.4)
    if item is None:
        return
    if room.y >= 0:
        y, rotation = room.y + room.depth, 180.0
    else:
        y, rotation = room.y, 0.0
    target_w = min(room.width, 2.0)
    runtime_mesh = isinstance(item.get("bounds"), dict)
    if runtime_mesh:
        fit_info = linear_fit(item, span=target_w, height=1.4, desired_rotation_deg=rotation)
        fit = (fit_info or {}).get("scale") or {"x": 1.0, "y": 1.0, "z": 1.0}
        actual_rotation = float((fit_info or {}).get("rotation_deg", rotation))
        bbox_center = (room.x + room.width / 2.0, y, room.floor * FLOOR_HEIGHT + 1.6)
    else:
        fit = _fit_scale(item, {"span": target_w, "height": 1.4}, "window_piece")
        actual_rotation, bbox_center = rotation, None
    placements.append(_placement(
        layout, room, item,
        element_id=f"{room.id}_ARCH_window_01",
        local_x=room.x + room.width / 2.0, local_y=y, local_z=0.9,
        rotation_deg=actual_rotation, semantic="window",
        target={"width_m": target_w, "height_m": 1.4, "outer_wall": True, "fit_scale": fit,
                "runtime_span_axis": (fit_info or {}).get("span_axis") if runtime_mesh else None},
        info=info, scale=fit, target_bbox_center=bbox_center,
    ))


def _ceiling_surface(layout: Layout, floor_rooms: list[Room], catalog: dict[str, Any], placements: list[dict[str, Any]], family: str | None) -> None:
    if not floor_rooms:
        return
    min_x, max_x, min_y, max_y = _floor_bounds(floor_rooms, layout.building)
    width, depth = max_x - min_x, max_y - min_y
    floor = floor_rooms[0].floor
    item, info = _best_item(
        _items(catalog, "ceiling_piece", family, layout.building.type),
        target_length=width,
        target_width=depth,
    )
    if item is None:
        return

    runtime_mesh = isinstance(item.get("bounds"), dict)
    if runtime_mesh:
        orientation = preferred_surface_rotation(item, width, depth)
        piece_x, piece_y = surface_world_dimensions(item, orientation)
    else:
        orientation, piece_x, piece_y = 0.0, *_floor_dims(item)

    xs, ys = _tile_axis(width, piece_x), _tile_axis(depth, piece_y)
    top_z = floor * FLOOR_HEIGHT + CEILING_Z
    for ix, (cx, actual_x, _) in enumerate(xs, 1):
        for iy, (cy, actual_y, _) in enumerate(ys, 1):
            if runtime_mesh:
                fit = surface_scale(item, actual_x, actual_y, orientation) or {"x": 1.0, "y": 1.0, "z": 1.0}
                bbox_center = (
                    min_x + cx,
                    min_y + cy,
                    top_z - scaled_bbox_height(item, fit) * 0.5,
                )
            else:
                fit = _fit_scale(
                    item,
                    {
                        "x": actual_x / max(piece_x or actual_x, 1e-6),
                        "y": actual_y / max(piece_y or actual_y, 1e-6),
                        "z": 1.0,
                    },
                    "ceiling_piece",
                )
                bbox_center = None

            placements.append(_placement(
                layout, floor_rooms[0], item,
                element_id=f"{floor_rooms[0].id.rsplit('_', 1)[0]}_ARCH_ceiling_F{floor+1:02d}_{ix:02d}_{iy:02d}",
                local_x=min_x + cx,
                local_y=min_y + cy,
                local_z=CEILING_Z,
                rotation_deg=orientation,
                semantic="ceiling",
                target={
                    "width_m": width,
                    "depth_m": depth,
                    "tile_x": ix,
                    "tile_y": iy,
                    "fit_scale": fit,
                    "surface_orientation_deg": orientation,
                },
                info=info,
                scale=fit,
                target_bbox_center=bbox_center,
            ))


def _has_neighbor(room: Room, floor_rooms: list[Room], side: str, eps: float = 0.05) -> bool:
    for other in floor_rooms:
        if other.id == room.id or other.floor != room.floor:
            continue
        overlap_y = min(room.y + room.depth, other.y + other.depth) - max(room.y, other.y)
        if side == "west" and abs(room.x - (other.x + other.width)) <= eps and overlap_y > eps:
            return True
        if side == "east" and abs((room.x + room.width) - other.x) <= eps and overlap_y > eps:
            return True
    return False


def assemble_room(layout: Layout, room: Room, catalog: dict[str, Any], family: str | None,
                  class_families: dict[str, str] | None = None,\n                  floor_rooms: list[Room] | None = None) -> list[dict[str, Any]]:
    """Assemble room shell/details; floor and ceiling are generated once per floor."""
    placements: list[dict[str, Any]] = []
    fm = class_families or {}
    wall_family = fm.get("wall_piece", family)
    door_gap, _ = _door_and_frame(
        layout, room, catalog, placements,
        fm.get("door_frame", family), fm.get("door_piece", family), wall_family,
    )
    if room.y >= 0:
        _wall_run(layout, room, catalog, placements, side="south", x0=room.x, y0=room.y + room.depth,
                  length=room.width, rotation_deg=0.0, family=wall_family)
        _wall_run(layout, room, catalog, placements, side="north", x0=room.x, y0=room.y,
                  length=room.width, rotation_deg=0.0, opening=door_gap, family=wall_family)
    else:
        _wall_run(layout, room, catalog, placements, side="north", x0=room.x, y0=room.y,
                  length=room.width, rotation_deg=0.0, family=wall_family)
        _wall_run(layout, room, catalog, placements, side="south", x0=room.x, y0=room.y + room.depth,
                  length=room.width, rotation_deg=0.0, opening=door_gap, family=wall_family)
    peers = floor_rooms or [room]
    if not _has_neighbor(room, peers, "west"):
        _wall_run(layout, room, catalog, placements, side="west", x0=room.x, y0=room.y,
                  length=room.depth, rotation_deg=90.0, family=wall_family)
    _wall_run(layout, room, catalog, placements, side="east", x0=room.x + room.width, y0=room.y,
              length=room.depth, rotation_deg=90.0, family=wall_family)
    _window(layout, room, catalog, placements, fm.get("window_piece", family))
    return placements


def build_architecture_assembly(layouts: list[Layout], catalog: dict[str, Any]) -> dict[str, Any]:
    buildings: list[dict[str, Any]] = []
    for layout in layouts:
        all_placements: list[dict[str, Any]] = []
        family, family_info = choose_architecture_family(catalog, str(layout.building.type))
        class_families, class_family_info = choose_class_families(catalog, family, str(layout.building.type))
        floors = sorted({int(r.floor) for r in layout.rooms})
        for floor in floors:
            floor_rooms = [r for r in layout.rooms if int(r.floor) == floor]
            _floor_surface(layout, floor_rooms, catalog, all_placements, class_families.get("floor_piece", family))
            _ceiling_surface(layout, floor_rooms, catalog, all_placements, class_families.get("ceiling_piece", family))
            for room in floor_rooms:
                all_placements.extend(assemble_room(layout, room, catalog, family, class_families, floor_rooms))
        by_class = defaultdict(int)
        unresolved = []
        for p in all_placements:
            by_class[str(p.get("class"))] += 1
            if not p.get("resource"):
                unresolved.append(p["id"])
        buildings.append({
            "id": layout.building.id,
            "floors": layout.building.floors,
            "rooms": len(layout.rooms),
            "placements": all_placements,
            "placement_count": len(all_placements),
            "placement_counts": dict(sorted(by_class.items())),
            "unresolved_count": len(unresolved),
            "unresolved": unresolved,
            "requires_bounds_validation": True,
            "architecture_kit": family_info,
            "selected_family": family,
            "class_families": class_family_info,
            "family_coherence": all((not p.get("resource") or str(p.get("family")) == family or bool(p.get("compatible_family_fallback"))) for p in all_placements),
        })
    return {
        "format": FORMAT,
        "source_catalog_format": catalog.get("format"),
        "source_catalog_selected_count": catalog.get("selected_count"),
        "buildings": buildings,
        "notes": [
            "Resources are selected from the real harvested architecture catalog.",
            "Filename dimensions are hints only; mesh bounds must be verified before final placement.",
            "This assembly emits resource-bound world-plan intent, not a fabricated native World Builder node schema.",
        ],
    }


def _quaternion_yaw(yaw_deg: float) -> dict[str, float]:
    half = math.radians(float(yaw_deg)) / 2.0
    return {"i": 0.0, "j": 0.0, "k": math.sin(half), "r": math.cos(half)}


def apply_architecture_to_world_plan(plan: dict[str, Any], assembly: dict[str, Any]) -> dict[str, Any]:
    building_id = str(plan.get("building_id") or (plan.get("building") or {}).get("id") or "building")
    building = next((b for b in assembly.get("buildings", []) if b.get("id") == building_id), None)
    if building is None:
        raise ValueError(f"assembly contains no building {building_id!r}")
    out = dict(plan)
    out["nodes"] = list(plan.get("nodes") or [])
    existing_refs = {str(n.get("nodeRef")) for n in out["nodes"] if isinstance(n, dict)}
    added = 0
    skipped = 0
    for p in building.get("placements", []):
        resource = p.get("resource")
        if not resource:
            skipped += 1
            continue
        name = str(p["id"])
        ref = f"$/#{building_id}_{name}"
        if ref in existing_refs:
            continue
        existing_refs.add(ref)
        out["nodes"].append({
            "name": name,
            "type": "worldMeshNode",
            "floor": int(p.get("floor", 0)),
            "nodeRef": ref,
            "position": dict(p["position"]),
            "rotation": _quaternion_yaw(float(p.get("rotation_deg", 0.0))),
            "rotation_deg": float(p.get("rotation_deg", 0.0)),
            "scale": dict(p.get("scale") or {"x": 1.0, "y": 1.0, "z": 1.0}),
            "primaryRange": 80.0,
            "secondaryRange": 120.0,
            "uk10": 32,
            "uk11": 512,
            "streamingRefPoint": dict(p["position"]),
            "data": {
                "logicalType": "architecture_piece",
                "architectureClass": p.get("class"),
                "semantic": p.get("semantic"),
                "resource": resource,
                "resourceFamily": p.get("family"),
                "roomId": p.get("room_id"),
                "target": p.get("target"),
                "selection": p.get("selection"),
                "dimensionHints": p.get("dimension_hints"),
                "requiresBoundsValidation": True,
                "scalePolicy": "no_automatic_mesh_scaling",
            },
        })
        added += 1
    out["architecture"] = {
        "format": FORMAT,
        "building_id": building_id,
        "added_node_count": added,
        "skipped_unresolved_count": skipped,
        "note": "Architecture nodes use real harvested resource paths but still require a real worldMeshNode template for native Object Spawner export.",
    }
    return out
