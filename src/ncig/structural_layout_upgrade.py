from __future__ import annotations

import hashlib
import json
import math
import random
from pathlib import Path
from typing import Any

VERSION = "0.28.0"
FLOOR_HEIGHT = 3.2
CORE_WIDTH = 2.6
CORE_DEPTH = 3.2
CORRIDOR_CHOICES = (1.55, 1.70, 1.85, 2.00)


def _hash_int(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16)


def _world(building: dict[str, Any], lx: float, ly: float, lz: float = 0.0) -> dict[str, float]:
    yaw = math.radians(float(building.get("yaw_deg", 0.0)))
    c, s = math.cos(yaw), math.sin(yaw)
    p = building.get("position") or {}
    return {
        "x": float(p.get("x", 0.0)) + c * lx - s * ly,
        "y": float(p.get("y", 0.0)) + s * lx + c * ly,
        "z": float(p.get("z", 0.0)) + lz,
    }


def _entry_side(building: dict[str, Any]) -> str:
    hw = float(building.get("width_m", 0.0)) * 0.5
    hd = float(building.get("depth_m", 0.0)) * 0.5
    x = float(building.get("entry_local_x", 0.0) or 0.0)
    y = float(building.get("entry_local_y", 0.0) or 0.0)
    d = {
        "north": abs(y + hd), "south": abs(y - hd),
        "west": abs(x + hw), "east": abs(x - hw),
    }
    return min(d, key=d.get)


def _shape_profile(building: dict[str, Any]) -> dict[str, Any]:
    width = float(building.get("width_m", 0.0) or 0.0)
    depth = float(building.get("depth_m", 0.0) or 0.0)
    ratio = max(width, depth) / max(0.1, min(width, depth))
    if ratio >= 2.25:
        kind = "long_strip"
    elif ratio >= 1.55:
        kind = "elongated"
    else:
        kind = "compact"
    return {"kind": kind, "aspect_ratio": round(ratio, 3), "rectangular_envelope": True}


def _partition(total: float, count: int, seed: str, min_size: float = 1.6) -> list[float]:
    count = max(1, int(count))
    if count == 1:
        return [total]
    count = min(count, max(1, int(total / max(min_size, 0.1))))
    if count <= 1:
        return [total]
    rng = random.Random(_hash_int(seed))
    weights = [rng.uniform(0.82, 1.18) for _ in range(count)]
    values = [total * w / sum(weights) for w in weights]
    for _ in range(8):
        small = [i for i, v in enumerate(values) if v < min_size]
        if not small:
            break
        i = small[0]
        donor = max((j for j in range(count) if j != i), key=lambda j: values[j])
        take = min(min_size - values[i], max(0.0, values[donor] - min_size))
        values[i] += take
        values[donor] -= take
    scale = total / max(sum(values), 1e-9)
    return [v * scale for v in values]


def _corridor_geometry(building: dict[str, Any]) -> tuple[float, float]:
    depth = float(building.get("depth_m", 0.0) or 0.0)
    if depth < 9.0:
        return 0.0, 0.0
    corridor = CORRIDOR_CHOICES[_hash_int(str(building.get("id", "building")) + "|corridor") % len(CORRIDOR_CHOICES)]
    corridor = min(corridor, max(1.35, depth - 5.0))
    offset = ((_hash_int(str(building.get("id", "building")) + "|corridor-offset") % 1001) / 1000.0 - 0.5) * 0.50
    max_offset = max(0.0, (depth - corridor) * 0.5 - 2.35)
    offset = max(-max_offset, min(max_offset, offset))
    return corridor, offset


def _side_geometry(building: dict[str, Any], side: str, corridor: float, offset: float) -> tuple[float, float]:
    depth = float(building.get("depth_m", 0.0) or 0.0)
    if corridor <= 0.0:
        return -depth * 0.5, depth
    usable = depth - corridor
    if side == "north":
        return offset + corridor * 0.5, usable * 0.5 - offset
    return offset - corridor * 0.5 - (usable * 0.5 + offset), usable * 0.5 + offset


def _core_side(building: dict[str, Any], existing_sides: set[str]) -> str:
    entry = _entry_side(building)
    if entry == "north" and "south" in existing_sides:
        return "south"
    if entry == "south" and "north" in existing_sides:
        return "north"
    if entry == "east" and "north" in existing_sides:
        return "north"
    if "south" in existing_sides:
        return "south"
    return "north" if "north" in existing_sides else next(iter(existing_sides), "south")


def _make_core_side_rooms(building: dict[str, Any], floor: int, source_rooms: list[dict[str, Any]], side: str, corridor: float, offset: float) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    width = float(building.get("width_m", 0.0) or 0.0)
    y0, side_depth = _side_geometry(building, side, corridor, offset)
    core_w = min(CORE_WIDTH, max(2.2, width * 0.22))
    if width - core_w < 3.2:
        core_w = max(1.8, width - 3.2)
    core_w = min(core_w, width - 2.0)
    regular_count = max(1, len(source_rooms) - 1)
    available = max(1.2, width - core_w)
    min_reg = 1.35
    if available < regular_count * min_reg:
        regular_count = max(1, int(available / min_reg))
    left_count = regular_count // 2
    right_count = regular_count - left_count
    if left_count == 0 and regular_count > 1:
        left_count, right_count = 1, regular_count - 1
    # A fixed center core gives every floor exactly the same vertical shaft footprint.
    core_x0 = -core_w * 0.5
    core_x1 = core_w * 0.5
    left_total = core_x0 + width * 0.5
    right_total = width * 0.5 - core_x1
    left_widths = _partition(left_total, left_count, f"{building['id']}|F{floor}|core-left") if left_count else []
    right_widths = _partition(right_total, right_count, f"{building['id']}|F{floor}|core-right") if right_count else []

    kinds = [str(r.get("kind", "office")) for r in source_rooms]
    if kinds:
        # Remove the room role closest to the center for the stairwell reservation.
        center_idx = min(range(len(source_rooms)), key=lambda i: abs(float(source_rooms[i].get("x", 0.0)) + float(source_rooms[i].get("width", 0.0)) * 0.5))
        kinds.pop(center_idx)
    new_rooms: list[dict[str, Any]] = []
    cursor = -width * 0.5
    order = 1
    for part, part_width in enumerate(left_widths):
        kind = kinds[(order - 1) % len(kinds)] if kinds else "office"
        new_rooms.append({
            "id": f"{building['id']}_F{floor+1}_S{side}_R{order:02d}", "kind": kind, "floor": floor,
            "x": round(cursor, 5), "y": round(y0, 5), "width": round(part_width, 5), "depth": round(side_depth, 5),
            "rotation_deg": 0.0, "is_start": False, "is_exit": False,
        })
        cursor += part_width; order += 1
    core = {
        "id": f"{building['id']}_F{floor+1}_ST_R{order:02d}", "kind": "stairwell", "floor": floor,
        "x": round(core_x0, 5), "y": round(y0 + max(0.0, (side_depth - min(CORE_DEPTH, side_depth - 0.10)) * 0.38), 5),
        "width": round(core_x1 - core_x0, 5), "depth": round(min(CORE_DEPTH, max(1.8, side_depth - 0.10)), 5),
        "rotation_deg": 0.0, "is_start": False, "is_exit": False, "structural_role": "vertical_core",
    }
    new_rooms.append(core)
    order += 1
    cursor = core_x1
    for part, part_width in enumerate(right_widths):
        kind = kinds[(order - 2) % len(kinds)] if kinds else "office"
        new_rooms.append({
            "id": f"{building['id']}_F{floor+1}_S{side}_R{order:02d}", "kind": kind, "floor": floor,
            "x": round(cursor, 5), "y": round(y0, 5), "width": round(part_width, 5), "depth": round(side_depth, 5),
            "rotation_deg": 0.0, "is_start": False, "is_exit": False,
        })
        cursor += part_width; order += 1
    return new_rooms, {
        "room_id": core["id"], "floor": floor, "side": side,
        "x": core["x"], "y": core["y"], "width": core["width"], "depth": core["depth"],
    }


def _normalize_other_side_rooms(building: dict[str, Any], floor: int, rooms: list[dict[str, Any]], side: str, corridor: float, offset: float) -> None:
    y0, depth = _side_geometry(building, side, corridor, offset)
    for room in rooms:
        room["y"] = round(y0, 5)
        room["depth"] = round(depth, 5)
        room["floor"] = floor
        room["rotation_deg"] = 0.0


def _entry_room(rooms: list[dict[str, Any]], building: dict[str, Any]) -> str | None:
    ground = [r for r in rooms if int(r.get("floor", 0)) == 0]
    if not ground:
        return None
    ex = float(building.get("entry_local_x", 0.0) or 0.0)
    ey = float(building.get("entry_local_y", 0.0) or 0.0)
    return min(ground, key=lambda r: math.hypot(
        max(float(r["x"]) - ex, 0.0, ex - (float(r["x"]) + float(r["width"]))),
        max(float(r["y"]) - ey, 0.0, ey - (float(r["y"]) + float(r["depth"]))),
    )).get("id")


def _make_sockets(building: dict[str, Any], rooms: list[dict[str, Any]], cores: list[dict[str, Any]]) -> list[dict[str, Any]]:
    interactions = {
        "living": "sit", "bedroom": "sleep", "kitchen": "use_sink", "bathroom": "use_sink",
        "utility": "use_washer", "shopfloor": "talk_to_vendor", "stockroom": "loot_shelf",
        "office": "use_computer", "open_office": "use_computer", "meeting": "use_screen",
        "private_office": "use_computer", "server": "use_terminal", "workshop": "use_workbench", "storage": "loot_shelf",
    }
    sockets: list[dict[str, Any]] = []
    entry_room = _entry_room(rooms, building)
    if entry_room:
        ex = float(building.get("entry_local_x", 0.0) or 0.0)
        ey = float(building.get("entry_local_y", 0.0) or 0.0)
        pos = _world(building, ex, ey, 0.02)
        sockets.append({"id": f"{building['id']}_building_entry", "kind": "entry", "room_id": entry_room, "x": pos["x"], "y": pos["y"], "z": pos["z"], "rotation_deg": float(building.get("entry_yaw_deg") or building.get("yaw_deg") or 0.0), "semantic": "building_entry", "properties": {"detected": building.get("entry_local_x") is not None}})
    for room in rooms:
        floor = int(room.get("floor", 0))
        cx = float(room["x"]) + float(room["width"]) * 0.5
        cy = float(room["y"]) + float(room["depth"]) * 0.5
        center = _world(building, cx, cy, floor * FLOOR_HEIGHT + 0.02)
        if room.get("kind") != "stairwell":
            sockets.append({"id": f"{room['id']}_activity", "kind": "activity", "room_id": room["id"], "x": center["x"], "y": center["y"], "z": center["z"], "rotation_deg": float(building.get("yaw_deg", 0.0)), "semantic": interactions.get(str(room.get("kind")), "loot_container"), "properties": {"zone": room.get("kind")}})
        door_y = float(room["y"]) if float(room.get("y", 0.0)) >= 0.0 else float(room["y"]) + float(room["depth"])
        door = _world(building, cx, door_y, floor * FLOOR_HEIGHT + 0.02)
        sockets.append({"id": f"{room['id']}_door", "kind": "door", "room_id": room["id"], "x": door["x"], "y": door["y"], "z": door["z"], "rotation_deg": float(building.get("yaw_deg", 0.0)) + (180.0 if float(room.get("y", 0.0)) < 0.0 else 0.0), "semantic": "single_door", "properties": {"access": "internal", "corridor_facing": True, "room_role": room.get("kind")}})
    by_floor = {int(c["floor"]): c for c in cores}
    for floor, core in sorted(by_floor.items()):
        cx = float(core["x"]) + float(core["width"]) * 0.5
        cy = float(core["y"]) + float(core["depth"]) * 0.5
        center = _world(building, cx, cy, floor * FLOOR_HEIGHT + 0.05)
        if floor > 0:
            sockets.append({"id": f"{building['id']}_vertical_F{floor+1:02d}_down", "kind": "vertical_link", "room_id": core["room_id"], "x": center["x"], "y": center["y"], "z": center["z"], "rotation_deg": float(building.get("yaw_deg", 0.0)), "semantic": "stairs_down", "properties": {"from_floor": floor, "to_floor": floor - 1, "connector": "stairs", "paired_room": by_floor[floor-1]["room_id"]}})
        if floor + 1 in by_floor:
            sockets.append({"id": f"{building['id']}_vertical_F{floor+1:02d}_up", "kind": "vertical_link", "room_id": core["room_id"], "x": center["x"], "y": center["y"], "z": center["z"], "rotation_deg": float(building.get("yaw_deg", 0.0)), "semantic": "stairs_up", "properties": {"from_floor": floor, "to_floor": floor + 1, "connector": "stairs", "paired_room": by_floor[floor+1]["room_id"]}})
    return sockets


def upgrade_layout_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    outputs: list[dict[str, Any]] = []
    for raw in bundle.get("layouts", []) or []:
        if not isinstance(raw, dict):
            continue
        building = dict(raw.get("building") or {})
        floors = max(1, int(building.get("floors", 1) or 1))
        original_rooms = [dict(x) for x in raw.get("rooms", []) if isinstance(x, dict)]
        corridor, offset = _corridor_geometry(building)
        existing_sides = {"north" if float(r.get("y", 0.0)) >= 0 else "south" for r in original_rooms}
        if corridor <= 0.0 and not existing_sides:
            existing_sides = {"south"}
        core_side = _core_side(building, existing_sides)
        rooms: list[dict[str, Any]] = []
        cores: list[dict[str, Any]] = []
        zones: list[dict[str, Any]] = []
        for floor in range(floors):
            floor_original = [r for r in original_rooms if int(r.get("floor", 0)) == floor]
            side_rooms = {"north": [dict(r) for r in floor_original if float(r.get("y", 0.0)) >= 0], "south": [dict(r) for r in floor_original if float(r.get("y", 0.0)) < 0]}
            rebuilt_core, core = _make_core_side_rooms(building, floor, side_rooms.get(core_side, []), core_side, corridor, offset)
            cores.append(core)
            rooms.extend(rebuilt_core)
            for side in ("north", "south"):
                if side == core_side:
                    continue
                if side_rooms[side]:
                    _normalize_other_side_rooms(building, floor, side_rooms[side], side, corridor, offset)
                    rooms.extend(side_rooms[side])
            if corridor > 0:
                y = offset - corridor * 0.5
                zones.append({"id": f"{building['id']}_F{floor+1}_corridor", "kind": "corridor", "floor": floor, "x": -float(building["width_m"]) * 0.5, "y": round(y, 5), "width": float(building["width_m"]), "depth": corridor, "structural": True, "walkable": True, "center_world": _world(building, 0.0, offset, floor * FLOOR_HEIGHT)})
            zones.append({"id": f"{building['id']}_F{floor+1}_stairwell", "kind": "stairwell_void", "floor": floor, "x": core["x"], "y": core["y"], "width": core["width"], "depth": core["depth"], "walkable": True, "vertical": True})
            if floor == 0 and corridor > 0:
                entry = _entry_side(building)
                if entry in {"north", "south"}:
                    ex = float(building.get("entry_local_x", 0.0) or 0.0)
                    zones.append({"id": f"{building['id']}_F01_entry_lobby", "kind": "entry_lobby", "floor": 0, "x": round(ex - 1.0, 5), "y": round(offset - corridor * 0.5, 5), "width": 2.0, "depth": corridor, "structural": False, "walkable": True})
        rooms.sort(key=lambda r: (int(r.get("floor", 0)), float(r.get("x", 0.0)), float(r.get("y", 0.0)), str(r.get("id"))))
        # Preserve entry/exit semantics after rebuilding the core side.
        if rooms:
            entry_id = _entry_room(rooms, building)
            if entry_id:
                for r in rooms:
                    r["is_start"] = str(r.get("id")) == entry_id
            top = [r for r in rooms if int(r.get("floor", 0)) == floors - 1 and r.get("kind") != "stairwell"]
            if top:
                max(top, key=lambda r: float(r.get("width", 0.0)) * float(r.get("depth", 0.0)))["is_exit"] = True
        sockets = _make_sockets(building, rooms, cores)
        shape = _shape_profile(building)
        same_xy = len({(round(float(c["x"]), 3), round(float(c["y"]), 3)) for c in cores}) == 1 if cores else False
        building["interior_structure_version"] = VERSION
        building["footprint_profile"] = shape
        building["vertical_core"] = {
            "type": "stairs", "continuous": floors > 1 and len(cores) == floors,
            "room_ids_by_floor": {str(int(c["floor"]) + 1): c["room_id"] for c in cores},
            "same_xy_across_floors": same_xy,
            "core_width_m": round(float(cores[0]["width"]), 3) if cores else 0.0,
            "core_depth_m": round(float(cores[0]["depth"]), 3) if cores else 0.0,
        }
        warnings = list(raw.get("warnings") or [])
        warnings.append(f"v{VERSION}: structural circulation; vertical_links={sum(1 for s in sockets if s.get('kind') == 'vertical_link')}; core_continuous={building['vertical_core']['continuous']}; footprint={shape['kind']}")
        new = dict(raw)
        new["building"] = building; new["rooms"] = rooms; new["sockets"] = sockets; new["zones"] = zones
        new["sectors"] = [dict(s, zones=[z["id"] for z in zones if int(z.get("floor", -1)) == int(s.get("floor", -2))]) for s in raw.get("sectors", []) if isinstance(s, dict)]
        new["warnings"] = warnings
        outputs.append(new)
    return {
        "format": "ncig-layout-structural-v1", "version": VERSION, "source_format": bundle.get("format"),
        "layout_count": len(outputs), "vertical_buildings": sum(1 for x in outputs if (x.get("building") or {}).get("vertical_core", {}).get("continuous")),
        "layouts": outputs,
        "notes": [
            "Corridors and entry lobbies are explicit circulation zones; they are not counted as activity rooms.",
            "A deterministic stairwell shaft is reserved at the same local XY position on every floor so vertical traversal can be physically continuous.",
            "Building aspect ratios are used to adapt bay counts and proportions; arbitrary non-rectangular facade polygons remain intentionally conservative until real mesh bounds are available.",
        ],
    }


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="NCIG 0.28 structural circulation/layout upgrade")
    p.add_argument("--input", required=True); p.add_argument("--out", required=True)
    args = p.parse_args()
    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    out = upgrade_layout_bundle(data)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"written": args.out, "layout_count": out["layout_count"], "vertical_buildings": out["vertical_buildings"]}, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
