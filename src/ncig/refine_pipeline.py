from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

VERSION = "0.23.0"
CANDIDATE_FORMAT = "ncig-city-building-candidates-v2"
CATALOG_FORMAT = "ncig-architecture-catalog-clean-v1"
LAYOUT_FORMAT = "ncig-layout-refined-v1"
FLOOR_HEIGHT = 3.2
CORRIDOR_CHOICES = (1.55, 1.8, 2.05, 2.25)

QUALITY_BANS: dict[str, tuple[str, ...]] = {
    "floor_piece": (
        "triangle", "triangular", "corner", "convex", "concave", "wedge", "diag", "diagonal",
        "stair", "staircase", "railing", "rail", "pillar", "column", "beam", "frame", "grate",
        "grid", "wall", "ceiling", "roof", "trim", "molding", "door", "window",
    ),
    "ceiling_piece": (
        "triangle", "triangular", "corner", "convex", "concave", "wedge", "diag", "diagonal",
        "stair", "staircase", "railing", "rail", "pillar", "column", "beam", "support", "grate",
        "grid", "wall", "floor", "ground", "trim", "molding", "door", "window",
    ),
    "wall_piece": (
        "triangle", "triangular", "corner", "convex", "concave", "wedge", "diag", "diagonal",
        "stair", "staircase", "railing", "rail", "pillar", "column", "beam", "ceiling", "floor",
        "roof", "frame", "grate", "grid", "bars", "window", "door", "trim", "molding", "top", "end",
        "destroyed", "fence", "cage", "prison", "cell",
    ),
    "door_frame": ("stair", "railing", "fence", "cage", "prison", "cell", "grate", "grid", "bars", "security"),
    "door_piece": ("stair", "railing", "fence", "cage", "prison", "cell", "grate", "grid", "bars"),
    "window_piece": ("stair", "railing", "fence", "cage", "prison", "cell"),
}

QUALITY_GOOD: dict[str, tuple[str, ...]] = {
    "floor_piece": ("floor", "tile", "tiles", "plank", "deck", "concrete", "platform", "ground"),
    "ceiling_piece": ("ceiling", "roof", "panel", "plaster"),
    "wall_piece": ("wall", "solid", "partition", "bulkhead", "panel"),
}


def _hash_int(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16)


def _score01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _candidate_quality(candidate: dict[str, Any]) -> tuple[str, int, list[str]]:
    evidence = candidate.get("evidence") or {}
    arch = max(0, int(evidence.get("architecture_nodes", 0)))
    walls = max(0, int(evidence.get("wall_nodes", 0)))
    wall_sides = len(evidence.get("wall_sides") or [])
    entrances = max(0, int(evidence.get("entrance_nodes", 0)))
    interiors = max(0, int(evidence.get("interior_nodes", 0)))
    geom = bool(evidence.get("geometry_ready"))
    width = float(candidate.get("width_m", 0.0) or 0.0)
    depth = float(candidate.get("depth_m", 0.0) or 0.0)
    height = float(candidate.get("height_m", 0.0) or 0.0)

    reasons: list[str] = []
    score = 0.0
    score += min(24.0, walls * 4.5)
    score += min(18.0, wall_sides * 6.0)
    score += min(14.0, entrances * 7.0)
    score += min(8.0, max(0, arch - 3) * 0.9)
    if geom:
        score += 16.0
    else:
        score -= 22.0
        reasons.append("geometry_not_ready")

    if 5.0 <= width <= 28.0 and 5.0 <= depth <= 28.0:
        score += 8.0
    else:
        score -= 18.0
        reasons.append("footprint_out_of_range")
    if 3.2 <= height <= 48.0:
        score += 5.0
    else:
        score -= 10.0
        reasons.append("height_out_of_range")

    if walls < 3:
        score -= 14.0
        reasons.append("too_few_facade_walls")
    if wall_sides < 2:
        score -= 18.0
        reasons.append("insufficient_facade_sides")
    if entrances < 1:
        score -= 20.0
        reasons.append("no_entrance_evidence")

    negative = max(0, int(evidence.get("negative_exterior_signals", 0)))
    if negative:
        score -= min(15.0, negative * 3.0)
        reasons.append("negative_exterior_signals")

    interior_ratio = interiors / max(1, arch)
    strong_existing_interior = interiors >= 10 or (interiors >= 5 and interior_ratio >= 0.18)
    weak_existing_interior = interiors >= 2
    if strong_existing_interior:
        score -= 60.0
        reasons.append("existing_interior_strong")
        action = "reject"
    elif weak_existing_interior:
        score -= min(18.0, interiors * 2.5)
        reasons.append("existing_interior_weak")
        action = "fill" if score >= 74.0 else "review"
    else:
        action = "fill" if score >= 72.0 else "review"

    score = int(round(max(0.0, min(100.0, score))))
    if score >= 85:
        confidence = "very_high"
    elif score >= 72:
        confidence = "high"
    elif score >= 58:
        confidence = "medium"
    else:
        confidence = "low"

    if not reasons:
        reasons.append("coherent_exterior_shell")
    return action, score, reasons + [f"quality_{confidence}"]


def _distance_xy(a: dict[str, Any], b: dict[str, Any]) -> float:
    pa, pb = a.get("position") or {}, b.get("position") or {}
    return math.hypot(float(pa.get("x", 0.0)) - float(pb.get("x", 0.0)), float(pa.get("y", 0.0)) - float(pb.get("y", 0.0)))


def refine_candidates(report: dict[str, Any]) -> dict[str, Any]:
    raw = [dict(c) for c in report.get("candidates", []) if isinstance(c, dict)]
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for candidate in raw:
        action, quality, reasons = _candidate_quality(candidate)
        c = dict(candidate)
        c["detector_score"] = int(candidate.get("score", 0) or 0)
        c["score"] = quality
        c["confidence"] = "high" if quality >= 72 else ("medium" if quality >= 58 else "low")
        c["quality"] = {
            "version": VERSION,
            "buildability_score": quality,
            "reasons": reasons,
            "existing_interior_nodes": int((candidate.get("evidence") or {}).get("interior_nodes", 0)),
            "action": action,
        }
        c["suggested_action"] = action
        if action == "reject":
            rejected.append(c)
        else:
            accepted.append(c)

    accepted.sort(key=lambda c: (-int(c.get("score", 0)), str(c.get("id", ""))))
    deduped: list[dict[str, Any]] = []
    suppressed = 0
    for candidate in accepted:
        pos = candidate.get("position") or {}
        duplicate = False
        for kept in deduped:
            if _distance_xy(candidate, kept) <= 6.5:
                duplicate = True
                candidate.setdefault("quality", {})["action"] = "suppressed_duplicate"
                candidate.setdefault("quality", {}).setdefault("reasons", []).append("nearby_better_candidate")
                suppressed += 1
                break
        if not duplicate:
            deduped.append(candidate)

    for rank, c in enumerate(deduped, start=1):
        q = c.setdefault("quality", {})
        q["rank"] = rank
        if int(c.get("score", 0)) >= 72 and c.get("suggested_action") == "fill":
            c["suggested_action"] = "fill"
        else:
            c["suggested_action"] = "review"

    return {
        "format": CANDIDATE_FORMAT,
        "source_format": report.get("format"),
        "version": VERSION,
        "input_candidate_count": len(raw),
        "output_candidate_count": len(deduped),
        "strong_rejections": len(rejected),
        "duplicate_suppressed": suppressed,
        "candidates": deduped,
        "rejected": rejected[:500],
        "notes": [
            "Exterior facade strength now matters more than raw nearby-node count.",
            "Strong existing interior evidence prevents automatic filling.",
            "Candidates closer than 6.5 m are de-duplicated in descending quality order.",
        ],
    }


def _path_text(item: dict[str, Any]) -> str:
    return (str(item.get("path", "")) + " " + str(item.get("family", ""))).lower().replace("/", "\\")


def _has_complete_dims(item: dict[str, Any]) -> bool:
    dims = item.get("bounds", {}).get("dimensions_m") if isinstance(item.get("bounds"), dict) else None
    if isinstance(dims, dict):
        try:
            return all(float(dims.get(k, 0.0)) > 0.01 for k in ("x", "y", "z"))
        except (TypeError, ValueError):
            return False
    dims = item.get("dimensions") or {}
    return bool(dims.get("complete"))


def _dimension_triplet(item: dict[str, Any], cls: str) -> tuple[float, float, float] | None:
    bounds = item.get("bounds") if isinstance(item.get("bounds"), dict) else None
    if bounds and isinstance(bounds.get("dimensions_m"), dict):
        d = bounds["dimensions_m"]
        try:
            return abs(float(d.get("x", 0.0))), abs(float(d.get("y", 0.0))), abs(float(d.get("z", 0.0)))
        except (TypeError, ValueError):
            return None
    d = item.get("dimensions") or {}
    metres = d.get("metres") or d
    try:
        l = float(metres.get("l", 0.0) or 0.0)
        w = float(metres.get("w", 0.0) or 0.0)
        h = float(metres.get("h", 0.0) or 0.0)
    except (TypeError, ValueError):
        return None
    if cls in {"wall_piece", "door_frame", "door_piece", "window_piece"}:
        return max(l, w), min(l, w), h
    return l, w, h


def _sane_item(item: dict[str, Any], cls: str) -> bool:
    dims = _dimension_triplet(item, cls)
    if not dims:
        return False
    a, b, h = dims
    if cls in {"floor_piece", "ceiling_piece"}:
        return 0.5 <= a <= 12.5 and 0.5 <= b <= 12.5 and (h <= 1.6 or h == 0.0)
    if cls == "wall_piece":
        return 0.5 <= a <= 12.5 and 1.8 <= h <= 6.0
    if cls in {"door_frame", "door_piece"}:
        return 0.5 <= a <= 2.6 and 1.6 <= h <= 3.6
    if cls == "window_piece":
        return 0.4 <= a <= 5.0 and 0.5 <= h <= 3.2
    return True


def clean_catalog(catalog: dict[str, Any]) -> dict[str, Any]:
    items = [dict(x) for x in (catalog.get("items") or []) if isinstance(x, dict)]
    kept: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    by_class_original: Counter[str] = Counter()
    by_class_clean: Counter[str] = Counter()
    for item in items:
        cls = str(item.get("class") or "")
        by_class_original[cls] += 1
        text = _path_text(item)
        bans = QUALITY_BANS.get(cls, ())
        if any(token in text for token in bans) or not _sane_item(item, cls):
            rejected.append({"path": item.get("path"), "class": cls, "reason": "semantic_or_dimension_reject"})
            continue
        quality = 0.0
        for token in QUALITY_GOOD.get(cls, ()):
            if token in text:
                quality += 5.0
        if _has_complete_dims(item):
            quality += 8.0
        if isinstance(item.get("bounds"), dict):
            quality += 10.0
        item["quality_v0230"] = round(quality, 2)
        kept.append(item)
        by_class_clean[cls] += 1

    # Never re-introduce a semantically rejected structural piece merely to hit a
    # minimum pool size. A single good floor/wall/ceiling is preferable to silently
    # putting triangles, corners, frames or pillars back into the structural pool.
    structural = {"floor_piece", "wall_piece", "ceiling_piece", "door_frame", "door_piece", "window_piece"}
    for cls in sorted(structural):
        if by_class_clean[cls] > 0:
            continue
        fallback = [
            x for x in items
            if str(x.get("class")) == cls
            and _sane_item(x, cls)
            and not any(token in _path_text(x) for token in QUALITY_BANS.get(cls, ()))
        ]
        fallback.sort(key=lambda x: (-float((x.get("score") or 0.0)), str(x.get("path", ""))))
        if fallback:
            row = dict(fallback[0])
            row["quality_v0230"] = 0.0
            row["quality_fallback"] = True
            kept.append(row)
            by_class_clean[cls] += 1

    # Re-sort so assembly still sees the strongest real/bounded assets first.
    kept.sort(key=lambda x: (-float(x.get("quality_v0230", 0.0)), -float(x.get("score", 0.0)), str(x.get("class", "")), str(x.get("path", ""))))
    out = dict(catalog)
    out["format"] = CATALOG_FORMAT
    out["version"] = VERSION
    out["source_format"] = catalog.get("format")
    out["items"] = kept
    out["selected_count"] = len(kept)
    out["quality"] = {
        "original_count": len(items),
        "clean_count": len(kept),
        "rejected_count": len(rejected),
        "original_class_counts": dict(sorted(by_class_original.items())),
        "clean_class_counts": dict(sorted(by_class_clean.items())),
        "rejected_examples": rejected[:250],
    }
    return out


def _weighted_kind(rng: random.Random, template: str, banned: set[str]) -> str:
    rules = {
        "residential": [("living", 8), ("bedroom", 8), ("kitchen", 6), ("bathroom", 4), ("utility", 2)],
        "commercial": [("shopfloor", 10), ("stockroom", 7), ("office", 4), ("bathroom", 3)],
        "office": [("open_office", 10), ("meeting", 5), ("private_office", 5), ("server", 2), ("bathroom", 3)],
        "industrial": [("workshop", 10), ("storage", 9), ("office", 3), ("utility", 4), ("bathroom", 2)],
        "mixed": [("shopfloor", 8), ("office", 4), ("stockroom", 4), ("bathroom", 3), ("living", 3)],
    }.get(template, [])
    choices = [(k, w) for k, w in rules if k not in banned] or rules
    total = sum(w for _, w in choices)
    point = rng.uniform(0.0, total)
    acc = 0.0
    for kind, weight in choices:
        acc += weight
        if point <= acc:
            return kind
    return choices[-1][0]


def _partition(total: float, count: int, rng: random.Random, min_size: float) -> list[float]:
    count = max(1, min(count, int(total / max(min_size, 0.1))))
    if count == 1:
        return [total]
    weights = [rng.uniform(0.78, 1.22) for _ in range(count)]
    values = [total * w / sum(weights) for w in weights]
    # A few passes move mass away from undersized bays while preserving the total.
    for _ in range(4):
        small = [i for i, v in enumerate(values) if v < min_size]
        if not small:
            break
        for i in small:
            need = min_size - values[i]
            donors = sorted((j for j in range(count) if j != i), key=lambda j: values[j], reverse=True)
            for j in donors:
                give = min(need, max(0.0, values[j] - min_size))
                if give <= 0:
                    continue
                values[j] -= give
                values[i] += give
                need -= give
                if need <= 1e-5:
                    break
    return values


def _world(anchor: dict[str, Any], lx: float, ly: float, lz: float) -> dict[str, float]:
    yaw = math.radians(float(anchor.get("yaw_deg", 0.0)))
    c, s = math.cos(yaw), math.sin(yaw)
    p = anchor.get("position") or {}
    return {
        "x": float(p.get("x", 0.0)) + c * lx - s * ly,
        "y": float(p.get("y", 0.0)) + s * lx + c * ly,
        "z": float(p.get("z", 0.0)) + lz,
    }


def _make_sockets(anchor: dict[str, Any], rooms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    interactions = {
        "living": "sit", "bedroom": "sleep", "kitchen": "use_sink", "bathroom": "use_sink",
        "utility": "use_washer", "shopfloor": "talk_to_vendor", "stockroom": "loot_shelf",
        "office": "use_computer", "open_office": "use_computer", "meeting": "use_screen",
        "private_office": "use_computer", "server": "use_terminal", "workshop": "use_workbench", "storage": "loot_shelf",
    }
    sockets: list[dict[str, Any]] = []
    ground = [r for r in rooms if int(r.get("floor", 0)) == 0]
    if ground:
        entry_x = anchor.get("entry_local_x")
        entry_y = anchor.get("entry_local_y")
        ex = float(entry_x if entry_x is not None else 0.0)
        ey = float(entry_y if entry_y is not None else 0.0)
        entry_room = min(ground, key=lambda r: math.hypot(max(float(r["x"]) - ex, 0.0, ex - (float(r["x"]) + float(r["width"]))), max(float(r["y"]) - ey, 0.0, ey - (float(r["y"]) + float(r["depth"])))))["id"]
        wp = _world(anchor, ex, ey, 0.02)
        sockets.append({"id": f"{anchor['id']}_building_entry", "kind": "entry", "room_id": entry_room, "x": wp["x"], "y": wp["y"], "z": wp["z"], "rotation_deg": float(anchor.get("entry_yaw_deg") or anchor.get("yaw_deg") or 0.0), "semantic": "building_entry", "properties": {"detected": entry_x is not None}})
    for room in rooms:
        cx = float(room["x"]) + float(room["width"]) * 0.5
        cy = float(room["y"]) + float(room["depth"]) * 0.5
        wp = _world(anchor, cx, cy, int(room.get("floor", 0)) * FLOOR_HEIGHT + 0.02)
        sockets.append({"id": f"{room['id']}_activity", "kind": "activity", "room_id": room["id"], "x": wp["x"], "y": wp["y"], "z": wp["z"], "semantic": interactions.get(str(room.get("kind")), "loot_container"), "properties": {}})
        if float(room["y"]) >= 0:
            door_y = float(room["y"])
            rot = float(anchor.get("yaw_deg", 0.0))
        else:
            door_y = float(room["y"]) + float(room["depth"])
            rot = float(anchor.get("yaw_deg", 0.0)) + 180.0
        dp = _world(anchor, cx, door_y, int(room.get("floor", 0)) * FLOOR_HEIGHT + 0.02)
        sockets.append({"id": f"{room['id']}_door", "kind": "door", "room_id": room["id"], "x": dp["x"], "y": dp["y"], "z": dp["z"], "rotation_deg": rot, "semantic": "single_door", "properties": {}})
    return sockets


def _make_sector(anchor: dict[str, Any], building_id: str, floor: int, rooms: list[dict[str, Any]]) -> dict[str, Any]:
    corners: list[dict[str, float]] = []
    for room in rooms:
        for x, y in ((float(room["x"]), float(room["y"])), (float(room["x"]) + float(room["width"]), float(room["y"]) + float(room["depth"]))):
            corners.append(_world(anchor, x, y, floor * FLOOR_HEIGHT))
    xs, ys = [p["x"] for p in corners], [p["y"] for p in corners]
    z0 = float((anchor.get("position") or {}).get("z", 0.0)) + floor * FLOOR_HEIGHT
    return {
        "id": f"{building_id}_sector_F{floor+1:02d}",
        "building_id": building_id,
        "floor": floor,
        "category": "interior",
        "min_xyz": {"x": min(xs) - 1.0, "y": min(ys) - 1.0, "z": z0 - 0.2},
        "max_xyz": {"x": max(xs) + 1.0, "y": max(ys) + 1.0, "z": z0 + FLOOR_HEIGHT + 0.8},
        "rooms": [r["id"] for r in rooms],
    }


def refine_layouts(bundle: dict[str, Any]) -> dict[str, Any]:
    outputs: list[dict[str, Any]] = []
    topology_counts: Counter[str] = Counter()
    for raw in bundle.get("layouts", []) or []:
        if not isinstance(raw, dict):
            continue
        building = dict(raw.get("building") or {})
        bw = float(building.get("width_m", 0.0) or 0.0)
        bd = float(building.get("depth_m", 0.0) or 0.0)
        floors = max(1, int(building.get("floors", 1) or 1))
        seed = int(building.get("seed") or _hash_int(str(building.get("id", "building"))))
        rng = random.Random(seed)
        topology_names = ("balanced_bilateral", "staggered_bilateral", "asymmetric_bilateral", "wide_front", "wide_back")
        topology = topology_names[_hash_int(f"{building.get('id')}|topology") % len(topology_names)]
        topology_counts[topology] += 1
        rooms: list[dict[str, Any]] = []
        room_counter = 0
        for floor in range(floors):
            if bw < 4.5 or bd < 4.5:
                raise ValueError(f"{building.get('id')}: footprint too small for refined layout")
            if bd < 9.0:
                side_specs = [("single", -bd / 2.0, bd)]
                counts = [1]
            else:
                corridor = CORRIDOR_CHOICES[_hash_int(f"{building.get('id')}|F{floor}|corridor") % len(CORRIDOR_CHOICES)]
                side_depth = (bd - corridor) / 2.0
                # Keep whole building envelope closed; each side owns one exterior strip.
                side_specs = [("back", -corridor / 2.0 - side_depth, side_depth), ("front", corridor / 2.0, side_depth)]
                base_count = max(2, min(5, int(round(bw / 3.8))))
                left_count = base_count
                right_count = base_count
                if topology == "asymmetric_bilateral":
                    left_count = max(2, base_count - 1)
                    right_count = min(5, base_count + (1 if bw >= 14 else 0))
                elif topology == "wide_front":
                    left_count = max(2, base_count - 1)
                    right_count = base_count
                elif topology == "wide_back":
                    left_count = base_count
                    right_count = max(2, base_count - 1)
                elif topology == "staggered_bilateral" and floor % 2 == 1:
                    left_count = min(5, base_count + 1)
                    right_count = max(2, base_count - 1)
                counts = [left_count, right_count]
            banned: set[str] = set()
            for side_index, (side, y0, depth) in enumerate(side_specs):
                count = counts[min(side_index, len(counts) - 1)]
                min_size = 2.15 if depth >= 4.5 else 1.8
                widths = _partition(bw, count, rng, min_size)
                cursor = -bw / 2.0
                for part_index, width in enumerate(widths):
                    room_counter += 1
                    kind = _weighted_kind(rng, str(building.get("type", "mixed")), banned if len(banned) < 4 else set())
                    # First floor room near the entry is always a public/front room.
                    if floor == 0 and room_counter == 1:
                        preferred = {"commercial": "shopfloor", "office": "open_office", "industrial": "workshop", "residential": "living", "mixed": "shopfloor"}.get(str(building.get("type", "mixed")), "living")
                        kind = preferred
                    room = {
                        "id": f"{building['id']}_F{floor+1}_R{room_counter:02d}",
                        "kind": kind,
                        "floor": floor,
                        "x": round(cursor, 5),
                        "y": round(y0, 5),
                        "width": round(width, 5),
                        "depth": round(depth, 5),
                        "rotation_deg": 0.0,
                        "is_start": False,
                        "is_exit": False,
                    }
                    rooms.append(room)
                    banned.add(kind)
                    cursor += width

        # Bathroom/utility becomes a dedicated small bay rather than stealing the entire largest room.
        for floor in range(floors):
            floor_rooms = [r for r in rooms if int(r["floor"]) == floor]
            desired = "utility" if str(building.get("type")) == "industrial" else "bathroom"
            if any(r["kind"] == desired for r in floor_rooms):
                continue
            candidates = [r for r in floor_rooms if float(r["width"]) >= 2.8]
            if candidates:
                donor = max(candidates, key=lambda r: float(r["width"]) * float(r["depth"]))
                split = max(1.8, min(2.4, float(donor["width"]) * 0.30))
                if float(donor["width"]) - split >= 1.8:
                    old_w = float(donor["width"])
                    donor["width"] = round(old_w - split, 5)
                    mini = dict(donor)
                    room_counter += 1
                    mini.update({
                        "id": f"{building['id']}_F{floor+1}_R{room_counter:02d}",
                        "kind": desired,
                        "x": round(float(donor["x"]) + float(donor["width"]), 5),
                        "width": round(split, 5),
                    })
                    rooms.append(mini)

        # Start/exit flags use actual detected entrance proximity, not room list order.
        if rooms:
            ex = float(building.get("entry_local_x") if building.get("entry_local_x") is not None else 0.0)
            ey = float(building.get("entry_local_y") if building.get("entry_local_y") is not None else 0.0)
            ground = [r for r in rooms if int(r["floor"]) == 0]
            start = min(ground, key=lambda r: math.hypot(max(float(r["x"]) - ex, 0.0, ex - (float(r["x"]) + float(r["width"]))), max(float(r["y"]) - ey, 0.0, ey - (float(r["y"]) + float(r["depth"])))) ) if ground else None
            if start:
                start["is_start"] = True
            top = [r for r in rooms if int(r["floor"]) == floors - 1]
            if top:
                max(top, key=lambda r: float(r["width"]) * float(r["depth"]))["is_exit"] = True

        new = dict(raw)
        new["building"] = building
        new["rooms"] = rooms
        new["sockets"] = _make_sockets(building, rooms)
        new["sectors"] = [_make_sector(building, str(building["id"]), floor, [r for r in rooms if int(r["floor"]) == floor]) for floor in range(floors)]
        new["warnings"] = list(raw.get("warnings") or []) + [f"v{VERSION}: topology={topology}; corridor/bays remain envelope-closed."]
        outputs.append(new)

    return {
        "format": LAYOUT_FORMAT,
        "version": VERSION,
        "source_format": bundle.get("format"),
        "layout_count": len(outputs),
        "topology_counts": dict(sorted(topology_counts.items())),
        "layouts": outputs,
        "notes": [
            "All generated floor strips still span the building envelope, avoiding facade holes.",
            "Variation changes bay counts, widths, corridor width and front/back asymmetry while preserving room adjacency.",
            "A bathroom/utility is carved into a dedicated bay when footprint permits instead of repurposing an entire room.",
        ],
    }


def _load(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write(path: str | Path, data: dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def cmd_candidates(args: argparse.Namespace) -> int:
    report = refine_candidates(_load(args.input))
    _write(args.out, report)
    print(json.dumps({k: report[k] for k in ("output_candidate_count", "strong_rejections", "duplicate_suppressed")}, indent=2))
    return 0


def cmd_catalog(args: argparse.Namespace) -> int:
    result = clean_catalog(_load(args.input))
    _write(args.out, result)
    print(json.dumps(result["quality"], indent=2, ensure_ascii=False))
    return 0


def cmd_layouts(args: argparse.Namespace) -> int:
    result = refine_layouts(_load(args.input))
    _write(args.out, result)
    print(json.dumps({"layout_count": result["layout_count"], "topology_counts": result["topology_counts"]}, indent=2, ensure_ascii=False))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="NCIG 0.23.0 quality/variation refinement stages")
    sub = p.add_subparsers(dest="stage", required=True)
    for name, func in (("candidates", cmd_candidates), ("catalog", cmd_catalog), ("layouts", cmd_layouts)):
        s = sub.add_parser(name)
        s.add_argument("--input", required=True)
        s.add_argument("--out", required=True)
        s.set_defaults(func=func)
    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
