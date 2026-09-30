from __future__ import annotations

import copy
import hashlib
import math
from typing import Any

from .module_library import choose_module, instantiate_module
from .model import BuildingAnchor, Layout, Room, Vec3
from .generator import world_pos


def stable_pick(seed_text: str, count: int) -> int:
    if count <= 0:
        return 0
    digest = hashlib.sha256(seed_text.encode("utf-8")).hexdigest()
    return int(digest[:16], 16) % count


def _room_anchor(layout: Layout, room: Room) -> tuple[float, float, float]:
    center_x = room.x + room.width / 2.0
    center_y = room.y + room.depth / 2.0
    p = world_pos(layout.building, center_x, center_y, room.floor * 3.2 + 0.02)
    return p.x, p.y, p.z


def _module_fit(module: dict[str, Any], room: Room) -> bool:
    # Keep a small clearance so large prefab modules do not clip into the generated shell.
    return float(module.get("width_m", 999)) <= max(0.8, room.width - 0.6) and float(module.get("depth_m", 999)) <= max(0.8, room.depth - 0.6)


def decorate_layout(layout: Layout, library: dict[str, Any], *, density: float = 0.65) -> dict[str, Any]:
    """Choose and place harvested modules inside generated rooms.

    The output is raw Object Spawner node payloads taken from the harvested library, so
    enum-heavy fields remain those of a real existing module. Only transforms/refs/names
    are changed for the instance.
    """
    placements: list[dict[str, Any]] = []
    nodes: list[dict[str, Any]] = []
    sector_nodes: dict[str, list[dict[str, Any]]] = {s.id: [] for s in layout.sectors}
    available = library.get("modules", [])
    if not available:
        return {"format": "ncig-decoration-plan-v1", "building_id": layout.building.id, "placements": [], "nodes": [], "warnings": ["module library is empty"]}

    for room in layout.rooms:
        chance_seed = f"{layout.building.id}|{layout.building.seed}|{room.id}|decorate"
        chance = int(hashlib.sha256(chance_seed.encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF
        if chance > max(0.0, min(1.0, density)):
            continue
        candidates = []
        for module in available:
            if _module_fit(module, room):
                score_roles = set(module.get("roles", []))
                score = 0
                if room.kind in score_roles:
                    score += 100
                if room.kind in {"living", "bedroom"} and score_roles & {"living", "bedroom"}:
                    score += 25
                if room.kind in {"office", "open_office"} and "office" in score_roles:
                    score += 25
                if room.kind in {"shopfloor", "counter"} and "shop" in score_roles:
                    score += 25
                if room.kind == "workshop" and "workshop" in score_roles:
                    score += 25
                candidates.append((score, module))
        if not candidates:
            continue
        candidates.sort(key=lambda x: (-x[0], x[1].get("id", "")))
        top_score = candidates[0][0]
        top = [m for s, m in candidates if s == top_score]
        selected = copy.deepcopy(top[stable_pick(chance_seed, len(top))])
        anchor = _room_anchor(layout, room)
        local_yaw = room.rotation_deg
        instance_prefix = f"{layout.building.id}_{room.id}_mod"
        placed_nodes = instantiate_module(selected, anchor=anchor, yaw_deg=layout.building.yaw_deg + local_yaw, prefix=instance_prefix)
        sector_id = next((s.id for s in layout.sectors if s.floor == room.floor), None)
        placements.append({
            "room_id": room.id,
            "floor": room.floor,
            "sector_id": sector_id,
            "module_id": selected.get("id"),
            "source_file": selected.get("source_file"),
            "anchor": {"x": anchor[0], "y": anchor[1], "z": anchor[2]},
            "yaw_deg": layout.building.yaw_deg + local_yaw,
            "node_count": len(placed_nodes),
        })
        nodes.extend(placed_nodes)
        if sector_id:
            sector_nodes.setdefault(sector_id, []).extend(placed_nodes)

    return {
        "format": "ncig-decoration-plan-v1",
        "building_id": layout.building.id,
        "density": density,
        "placement_count": len(placements),
        "node_count": len(nodes),
        "placements": placements,
        "nodes": nodes,
        "sector_nodes": sector_nodes,
        "warnings": [],
    }
