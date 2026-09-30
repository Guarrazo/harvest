from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from .generator import world_pos
from .architecture_geometry import compatible_family_candidates, dimension_hint_scale, planar_dimensions, rank_family_options, sane_dimensions
from .model import Layout, Room, Vec3

FORMAT = "ncig-architecture-assembly-v1"
FLOOR_HEIGHT = 3.2
CEILING_Z = 3.0
DEFAULT_DOOR_WIDTH = 1.0


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
               scale: dict[str, float] | None = None) -> dict[str, Any]:
    world = world_pos(layout.building, local_x, local_y, local_z + room.floor * FLOOR_HEIGHT)
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
        "rotation_deg": float(layout.building.yaw_deg + room.rotation_deg + rotation_deg),
        "scale": scale or {"x": 1.0, "y": 1.0, "z": 1.0},
        "target": target,
        "selection": info,
        "dimension_hints": item.get("dimensions", {}),
        "requires_bounds_validation": True,
        "native_node_type": "worldMeshNode",
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


def _room_floor(layout: Layout, room: Room, catalog: dict[str, Any], placements: list[dict[str, Any]], family: str | None) -> None:
    item, info = _best_item(_items(catalog, "floor_piece", family, layout.building.type), target_length=room.width, target_width=room.depth)
    if item is None:
        placements.append({"id": f"{room.id}_ARCH_floor_missing", "class": "floor_piece", "room_id": room.id,
                           "floor": room.floor, "resource": None, "selection": info,
                           "requires_bounds_validation": True, "status": "unresolved"})
        return
    plen, pwidth = _floor_dims(item)
    xs = _tile_axis(room.width, plen)
    ys = _tile_axis(room.depth, pwidth)
    for ix, (cx, _, sx) in enumerate(xs, 1):
        for iy, (cy, _, sy) in enumerate(ys, 1):
            placements.append(_placement(
                layout, room, item,
                element_id=f"{room.id}_ARCH_floor_{ix:02d}_{iy:02d}",
                local_x=room.x + cx, local_y=room.y + cy, local_z=0.0,
                rotation_deg=0.0, semantic="floor",
                target={"width_m": room.width, "depth_m": room.depth, "tile_x": ix, "tile_y": iy, "fit_scale": _fit_scale(item, {"x": sx, "y": sy, "z": 1.0}, "floor_piece")},
                info=info,
                scale=_fit_scale(item, {"x": sx, "y": sy, "z": 1.0}, "floor_piece"),
            ))


def _wall_run(layout: Layout, room: Room, catalog: dict[str, Any], placements: list[dict[str, Any]], *,
              side: str, x0: float, y0: float, length: float, rotation_deg: float,
              opening: tuple[float, float] | None = None, family: str | None = None) -> None:
    candidates = _items(catalog, "wall_piece", family, layout.building.type)
    item, info = _best_item(candidates, target_length=min(length, 3.0), target_height=3.0)
    if item is None:
        placements.append({"id": f"{room.id}_ARCH_{side}_wall_missing", "class": "wall_piece", "room_id": room.id,
                           "floor": room.floor, "resource": None, "selection": info,
                           "requires_bounds_validation": True, "status": "unresolved"})
        return
    piece = _length_hint(item) or min(length, 3.0)
    height = _height_hint(item) or 3.0
    if piece <= 0.1:
        piece = min(length, 3.0)
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
    counter = 0
    for a, b in ranges:
        run = b - a
        # Use whole pieces where possible, then fit the remainder. The remainder is
        # scaled along the long axis only; it is capped so we do not stretch a mesh wildly.
        count = max(1, int(round(run / piece)))
        actual = run / count
        span_scale = actual / piece
        if not 0.72 <= span_scale <= 1.28 and run > piece * 1.25:
            count = max(1, int(math.ceil(run / piece)))
            actual = run / count
            span_scale = actual / piece
        cursor = a
        for n in range(count):
            seg = actual
            center = cursor + seg / 2.0
            cursor += seg
            counter += 1
            lx, ly = x0, y0
            if side in {"north", "south"}:
                lx += center
                scale = {"x": span_scale, "y": 1.0, "z": (3.0 / height) if height > 0.1 else 1.0}
            else:
                ly += center
                scale = {"x": span_scale, "y": 1.0, "z": (3.0 / height) if height > 0.1 else 1.0}
            placements.append(_placement(
                layout, room, item,
                element_id=f"{room.id}_ARCH_wall_{side}_{counter:02d}",
                local_x=lx, local_y=ly, local_z=0.0,
                rotation_deg=rotation_deg, semantic="wall",
                target={"run_m": length, "segment_m": seg, "side": side, "opening": opening, "fit_scale": _fit_scale(item, {"span": actual, "height": 3.0}, "wall_piece")},
                info=info, scale=_fit_scale(item, {"span": actual, "height": 3.0}, "wall_piece"),
            ))


def _door_and_frame(layout: Layout, room: Room, catalog: dict[str, Any], placements: list[dict[str, Any]], frame_family: str | None, door_family: str | None) -> tuple[tuple[float, float], str]:
    gap = min(DEFAULT_DOOR_WIDTH, room.width * 0.32)
    room_center_x = room.x + room.width / 2.0
    # Room y-sign matches the generator's corridor-facing side.
    if room.y >= 0:
        y = room.y
        side = "south"
        rotation = 0.0
    else:
        y = room.y + room.depth
        side = "north"
        rotation = 180.0
    center = room_center_x - room.x
    opening = (center - gap / 2.0, center + gap / 2.0)
    frame, finfo = _best_item(_items(catalog, "door_frame", frame_family, layout.building.type), target_length=gap, target_height=2.1)
    door, dinfo = _best_item(_items(catalog, "door_piece", door_family, layout.building.type), target_length=gap, target_height=2.1)
    for suffix, cls, item, info in (("frame", "door_frame", frame, finfo), ("door", "door_piece", door, dinfo)):
        if item is None:
            placements.append({"id": f"{room.id}_ARCH_{suffix}_missing", "class": cls, "room_id": room.id,
                               "floor": room.floor, "resource": None, "selection": info,
                               "requires_bounds_validation": True, "status": "unresolved"})
            continue
        span = _length_hint(item) or gap
        height = _height_hint(item) or 2.1
        sx = max(0.72, min(1.28, gap / span)) if span > 0 else 1.0
        sz = max(0.80, min(1.20, 2.1 / height)) if height > 0 else 1.0
        placements.append(_placement(
            layout, room, item,
            element_id=f"{room.id}_ARCH_{suffix}",
            local_x=room_center_x, local_y=y, local_z=0.0,
            rotation_deg=rotation, semantic=cls,
            target={"opening_width_m": gap, "wall_side": side, "fit_scale": _fit_scale(item, {"span": gap, "height": 2.1}, cls)},
            info=info, scale=_fit_scale(item, {"span": gap, "height": 2.1}, cls),
        ))
    return opening, side


def _window(layout: Layout, room: Room, catalog: dict[str, Any], placements: list[dict[str, Any]], family: str | None) -> None:
    windows = _items(catalog, "window_piece", family, layout.building.type)
    if not windows or room.width < 2.8:
        return
    item, info = _best_item(windows, target_length=min(room.width, 2.0), target_height=1.4)
    if item is None:
        return
    # The outer wall is opposite the corridor-facing wall.
    if room.y >= 0:
        y = room.y + room.depth
        rotation = 180.0
    else:
        y = room.y
        rotation = 0.0
    span = _length_hint(item) or min(room.width, 2.0)
    height = _height_hint(item) or 1.4
    target_w = min(room.width, 2.0)
    sx = max(0.75, min(1.25, target_w / span)) if span > 0 else 1.0
    sz = max(0.80, min(1.20, 1.4 / height)) if height > 0 else 1.0
    placements.append(_placement(
        layout, room, item,
        element_id=f"{room.id}_ARCH_window_01",
        local_x=room.x + room.width / 2.0, local_y=y, local_z=0.9,
        rotation_deg=rotation, semantic="window",
        target={"width_m": target_w, "height_m": 1.4, "outer_wall": True, "fit_scale": _fit_scale(item, {"span": target_w, "height": 1.4}, "window_piece")},
        info=info, scale=_fit_scale(item, {"span": target_w, "height": 1.4}, "window_piece"),
    ))


def _ceiling(layout: Layout, room: Room, catalog: dict[str, Any], placements: list[dict[str, Any]], family: str | None) -> None:
    item, info = _best_item(_items(catalog, "ceiling_piece", family, layout.building.type), target_length=room.width, target_width=room.depth)
    if item is None:
        return
    plen, pwidth = _floor_dims(item)
    xs = _tile_axis(room.width, plen)
    ys = _tile_axis(room.depth, pwidth)
    for ix, (cx, _, sx) in enumerate(xs, 1):
        for iy, (cy, _, sy) in enumerate(ys, 1):
            placements.append(_placement(
                layout, room, item,
                element_id=f"{room.id}_ARCH_ceiling_{ix:02d}_{iy:02d}",
                local_x=room.x + cx, local_y=room.y + cy, local_z=CEILING_Z,
                rotation_deg=0.0, semantic="ceiling",
                target={"width_m": room.width, "depth_m": room.depth, "tile_x": ix, "tile_y": iy, "fit_scale": _fit_scale(item, {"x": sx, "y": sy, "z": 1.0}, "ceiling_piece")},
                info=info,
                scale=_fit_scale(item, {"x": sx, "y": sy, "z": 1.0}, "ceiling_piece"),
            ))


def assemble_room(layout: Layout, room: Room, catalog: dict[str, Any], family: str | None, class_families: dict[str, str] | None = None) -> list[dict[str, Any]]:
    placements: list[dict[str, Any]] = []
    fm = class_families or {}
    _room_floor(layout, room, catalog, placements, fm.get("floor_piece", family))
    door_gap, _ = _door_and_frame(layout, room, catalog, placements, fm.get("door_frame", family), fm.get("door_piece", family))
    if room.y >= 0:
        _wall_run(layout, room, catalog, placements, side="south", x0=room.x, y0=room.y + room.depth,
                  length=room.width, rotation_deg=0.0, family=fm.get("wall_piece", family))
        _wall_run(layout, room, catalog, placements, side="north", x0=room.x, y0=room.y,
                  length=room.width, rotation_deg=0.0, opening=door_gap, family=family)
    else:
        _wall_run(layout, room, catalog, placements, side="north", x0=room.x, y0=room.y,
                  length=room.width, rotation_deg=0.0, family=fm.get("wall_piece", family))
        _wall_run(layout, room, catalog, placements, side="south", x0=room.x, y0=room.y + room.depth,
                  length=room.width, rotation_deg=0.0, opening=door_gap, family=family)
    _wall_run(layout, room, catalog, placements, side="west", x0=room.x, y0=room.y,
              length=room.depth, rotation_deg=90.0, family=fm.get("wall_piece", family))
    _wall_run(layout, room, catalog, placements, side="east", x0=room.x + room.width, y0=room.y,
              length=room.depth, rotation_deg=90.0, family=fm.get("wall_piece", family))
    _window(layout, room, catalog, placements, fm.get("window_piece", family))
    _ceiling(layout, room, catalog, placements, fm.get("ceiling_piece", family))
    return placements

def build_architecture_assembly(layouts: list[Layout], catalog: dict[str, Any]) -> dict[str, Any]:
    buildings: list[dict[str, Any]] = []
    for layout in layouts:
        all_placements: list[dict[str, Any]] = []
        family, family_info = choose_architecture_family(catalog, str(layout.building.type))
        class_families, class_family_info = choose_class_families(catalog, family, str(layout.building.type))
        for room in layout.rooms:
            all_placements.extend(assemble_room(layout, room, catalog, family, class_families))
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
