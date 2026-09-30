from __future__ import annotations

import hashlib
import math
import random
from typing import Iterable

from .model import BuildingAnchor, Layout, Room, Sector, Socket, Vec3
from .templates import ALIASES, FURNITURE_BY_ROOM, INTERACTION_BY_ROOM, RoomRule, TEMPLATES


EPS = 0.08


def stable_seed(building: BuildingAnchor) -> int:
    if building.seed is not None:
        return building.seed
    raw = f"{building.id}|{building.type}|{building.position.x:.3f}|{building.position.y:.3f}|{building.yaw_deg:.3f}"
    return int(hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16], 16)


def weighted_rule(rng: random.Random, rules: list[RoomRule], banned: set[str]) -> RoomRule:
    candidates = [r for r in rules if r.kind not in banned]
    if not candidates:
        candidates = rules
    total = sum(r.weight for r in candidates)
    point = rng.uniform(0, total)
    acc = 0.0
    for rule in candidates:
        acc += rule.weight
        if point <= acc:
            return rule
    return candidates[-1]


def rotate_local(x: float, y: float, yaw_deg: float) -> tuple[float, float]:
    a = math.radians(yaw_deg)
    c, s = math.cos(a), math.sin(a)
    return c * x - s * y, s * x + c * y


def world_pos(anchor: BuildingAnchor, lx: float, ly: float, lz: float) -> Vec3:
    rx, ry = rotate_local(lx, ly, anchor.yaw_deg)
    return Vec3(anchor.position.x + rx, anchor.position.y + ry, anchor.position.z + lz)


def room_overlap(a: Room, b: Room) -> bool:
    return not (
        a.x + a.width <= b.x + EPS
        or b.x + b.width <= a.x + EPS
        or a.y + a.depth <= b.y + EPS
        or b.y + b.depth <= a.y + EPS
    )


def generate_floor_rooms(
    anchor: BuildingAnchor,
    floor: int,
    rng: random.Random,
    template_name: str,
) -> list[Room]:
    margin = 0.5
    corridor = 1.6
    usable_w = anchor.width_m - 2 * margin
    usable_d = anchor.depth_m - 2 * margin
    if usable_w < 4.0 or usable_d < 4.0:
        raise ValueError(f"building {anchor.id}: footprint too small")

    # The generator uses a deterministic corridor-and-bays layout.
    # This is deliberately conservative: connectivity is more valuable than maximal packing.
    rooms: list[Room] = []
    rules = TEMPLATES[ALIASES.get(template_name, template_name)]

    # For narrow buildings, make one side of rooms; for wider buildings, use both sides.
    double_sided = usable_d >= 9.0
    side_depth = (usable_d - corridor) / 2 if double_sided else usable_d
    rows = max(1, int(round(usable_w / 3.6)))
    target_rows = min(6, max(1, rows))
    bay_width = usable_w / target_rows

    banned_once: set[str] = set()
    room_counter = 0
    for i in range(target_rows):
        x = -anchor.width_m / 2 + margin + i * bay_width
        w = bay_width - 0.18
        for side in ([-1, 1] if double_sided else [1]):
            y = side * corridor / 2
            if double_sided:
                y0 = y if side > 0 else -corridor / 2 - side_depth
            else:
                y0 = -anchor.depth_m / 2 + margin
            d = side_depth - 0.18
            if w < 1.4 or d < 1.4:
                continue
            rule = weighted_rule(rng, rules, banned_once if room_counter < 4 else set())
            if room_counter < 1:
                rule = next((r for r in rules if r.kind in {"shopfloor", "living", "open_office", "workshop"}), rule)
            room_w = min(w, rng.uniform(rule.min_w, rule.max_w))
            room_d = min(d, rng.uniform(rule.min_d, rule.max_d))
            room = Room(
                id=f"{anchor.id}_F{floor+1}_R{room_counter+1:02d}",
                kind=rule.kind,
                floor=floor,
                x=x + (w - room_w) / 2,
                y=y0 + (d - room_d) / 2,
                width=room_w,
                depth=room_d,
            )
            rooms.append(room)
            banned_once.add(rule.kind)
            room_counter += 1

    # Ensure a bathroom/utility exists when there is room.
    if rooms:
        desired = "bathroom" if template_name != "industrial" else "utility"
        if not any(r.kind == desired for r in rooms):
            donor = max(rooms, key=lambda r: r.width * r.depth)
            donor.kind = desired
    return rooms


def add_sockets(anchor: BuildingAnchor, rooms: list[Room], floor: int, rng: random.Random) -> list[Socket]:
    sockets: list[Socket] = []
    floor_height = 3.2
    if floor == 0:
        lx = anchor.entry_local_x if anchor.entry_local_x is not None else 0.0
        ly = anchor.entry_local_y if anchor.entry_local_y is not None else 0.0
        ep = world_pos(anchor, lx, ly, 0.02)
        entry_yaw = anchor.entry_yaw_deg if anchor.entry_yaw_deg is not None else anchor.yaw_deg
        entry_room = rooms[0].id if rooms else ""
        if rooms:
            def point_rect_distance(room: Room) -> float:
                px = max(room.x, min(lx, room.x + room.width))
                py = max(room.y, min(ly, room.y + room.depth))
                return math.hypot(px - lx, py - ly)
            entry_room = min(rooms, key=point_rect_distance).id
        sockets.append(Socket(
            id=f"{anchor.id}_building_entry",
            kind="entry",
            room_id=entry_room,
            x=ep.x, y=ep.y, z=ep.z,
            rotation_deg=entry_yaw,
            semantic="building_entry",
            properties={"access": "public_or_building_owned", "transition": "door_or_teleport", "detected": anchor.entry_local_x is not None},
        ))
    for room in rooms:
        # One gameplay socket at the room center.
        cx = room.x + room.width * 0.5
        cy = room.y + room.depth * 0.5
        wp = world_pos(anchor, cx, cy, floor * floor_height + 0.02)
        interactions = INTERACTION_BY_ROOM.get(room.kind, ["loot_container"])
        sockets.append(Socket(
            id=f"{room.id}_activity",
            kind="activity",
            room_id=room.id,
            x=wp.x, y=wp.y, z=wp.z,
            semantic=interactions[0],
            properties={"candidates": interactions},
        ))

        # Door anchor is placed on the room side facing the central corridor.
        door_y = room.y + (0.0 if room.y > 0 else room.depth)
        dp = world_pos(anchor, cx, door_y, floor * floor_height + 0.02)
        sockets.append(Socket(
            id=f"{room.id}_door",
            kind="door",
            room_id=room.id,
            x=dp.x, y=dp.y, z=dp.z,
            rotation_deg=anchor.yaw_deg + (180.0 if room.y < 0 else 0.0),
            semantic="single_door",
            properties={"access": "public_or_building_owned"},
        ))

        # Furniture sockets deliberately do not specify real asset paths yet.
        for n, item in enumerate(FURNITURE_BY_ROOM.get(room.kind, ["light"]), start=1):
            ox = (n % 2 - 0.5) * min(room.width * 0.35, 0.9)
            oy = ((n // 2) - 0.75) * min(room.depth * 0.30, 0.8)
            fp = world_pos(anchor, cx + ox, cy + oy, floor * floor_height + 0.02)
            sockets.append(Socket(
                id=f"{room.id}_prop_{n:02d}",
                kind="prop",
                room_id=room.id,
                x=fp.x, y=fp.y, z=fp.z,
                semantic=item,
                properties={"spawn_policy": "resource_catalog"},
            ))

        # Loot density is intentionally capped.
        if rng.random() < (0.55 if floor == 0 else 0.35):
            lp = world_pos(anchor, cx, room.y + room.depth * 0.75, floor * floor_height + 0.02)
            sockets.append(Socket(
                id=f"{room.id}_loot",
                kind="loot",
                room_id=room.id,
                x=lp.x, y=lp.y, z=lp.z,
                semantic="generic_loot",
                properties={"rarity_bias": "district"},
            ))
    return sockets


def make_sector(anchor: BuildingAnchor, rooms: list[Room], floor: int) -> Sector:
    floor_height = 3.2
    z0 = anchor.position.z + floor * floor_height
    # Whole-floor sector envelope with a modest margin.
    corners = []
    for r in rooms:
        for x, y in ((r.x, r.y), (r.x + r.width, r.y + r.depth)):
            wp = world_pos(anchor, x, y, floor * floor_height)
            corners.append(wp)
    if corners:
        xs = [p.x for p in corners]
        ys = [p.y for p in corners]
        min_xyz = Vec3(min(xs) - 1.0, min(ys) - 1.0, z0 - 0.2)
        max_xyz = Vec3(max(xs) + 1.0, max(ys) + 1.0, z0 + floor_height + 0.8)
    else:
        min_xyz = world_pos(anchor, -anchor.width_m/2, -anchor.depth_m/2, floor*floor_height)
        max_xyz = world_pos(anchor, anchor.width_m/2, anchor.depth_m/2, floor*floor_height + floor_height)
    return Sector(
        id=f"{anchor.id}_sector_F{floor+1:02d}",
        building_id=anchor.id,
        floor=floor,
        category="interior",
        min_xyz=min_xyz,
        max_xyz=max_xyz,
        rooms=[r.id for r in rooms],
    )


def generate_layout(anchor: BuildingAnchor) -> Layout:
    rng = random.Random(stable_seed(anchor))
    template = anchor.type
    all_rooms: list[Room] = []
    all_sockets: list[Socket] = []
    all_sectors: list[Sector] = []
    warnings: list[str] = []

    for floor in range(max(1, anchor.floors)):
        rooms = generate_floor_rooms(anchor, floor, rng, template)
        if floor == 0 and rooms:
            rooms[0].is_start = True
        if floor == anchor.floors - 1 and rooms:
            rooms[-1].is_exit = True
        all_rooms.extend(rooms)
        all_sockets.extend(add_sockets(anchor, rooms, floor, rng))
        all_sectors.append(make_sector(anchor, rooms, floor))

    # Very tall buildings should be split into lobby + floor sectors rather than one giant sector.
    if anchor.floors >= 6:
        warnings.append("Tall building: keep each floor in a separate streaming sector.")

    # Mixed/commercial naming is useful to downstream rules.
    if anchor.type == "mixed":
        warnings.append("Mixed building uses commercial base template in v0.1; add multi-zone zoning in v0.2.")

    return Layout(anchor, all_rooms, all_sockets, all_sectors, warnings)


def validate_layout(layout: Layout) -> list[str]:
    errors: list[str] = []
    b = layout.building
    if b.width_m < 4 or b.depth_m < 4:
        errors.append("footprint is too small")
    if b.floors < 1:
        errors.append("floors must be >= 1")

    for floor in range(max(1, b.floors)):
        floor_rooms = [r for r in layout.rooms if r.floor == floor]
        for i, a in enumerate(floor_rooms):
            for c in floor_rooms[i + 1:]:
                if room_overlap(a, c):
                    errors.append(f"room overlap on floor {floor+1}: {a.id} vs {c.id}")
        if floor == 0 and floor_rooms and not any(r.is_start for r in floor_rooms):
            errors.append("ground floor has no start room")

    if not layout.sectors:
        errors.append("no sectors generated")
    return errors
