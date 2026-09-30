from __future__ import annotations

import hashlib
from typing import Any

from .generator import world_pos
from .model import Layout, Room

FORMAT = "ncig-decoration-plan-v2"

RECIPES: dict[str, tuple[tuple[str, float, float, float], ...]] = {
    "shopfloor": (("counter", 0.50, 0.82, 0.0), ("display", 0.20, 0.55, 0.0), ("display", 0.80, 0.55, 0.0), ("shelf", 0.85, 0.20, 0.0), ("light", 0.50, 0.50, 2.70)),
    "stockroom": (("shelf", 0.20, 0.30, 0.0), ("shelf", 0.50, 0.30, 0.0), ("crate", 0.80, 0.30, 0.0), ("light", 0.50, 0.50, 2.70)),
    "office": (("desk", 0.25, 0.30, 0.0), ("chair", 0.25, 0.48, 0.0), ("computer", 0.25, 0.30, 0.85), ("light", 0.50, 0.50, 2.70)),
    "open_office": (("desk", 0.30, 0.30, 0.0), ("chair", 0.30, 0.50, 0.0), ("computer", 0.30, 0.30, 0.85), ("desk", 0.70, 0.30, 0.0), ("chair", 0.70, 0.50, 0.0), ("computer", 0.70, 0.30, 0.85), ("light", 0.50, 0.50, 2.70)),
    "private_office": (("desk", 0.30, 0.30, 0.0), ("chair", 0.30, 0.50, 0.0), ("computer", 0.30, 0.30, 0.85), ("light", 0.50, 0.50, 2.70)),
    "meeting": (("table", 0.50, 0.50, 0.0), ("chair", 0.28, 0.50, 0.0), ("chair", 0.72, 0.50, 0.0), ("chair", 0.50, 0.25, 0.0), ("screen", 0.50, 0.12, 1.10), ("light", 0.50, 0.50, 2.70)),
    "living": (("sofa", 0.50, 0.20, 0.0), ("tv", 0.50, 0.82, 1.0), ("table", 0.50, 0.50, 0.0), ("light", 0.50, 0.50, 2.70)),
    "bedroom": (("bed", 0.50, 0.35, 0.0), ("wardrobe", 0.82, 0.20, 0.0), ("nightstand", 0.24, 0.40, 0.0), ("light", 0.50, 0.50, 2.70)),
    "kitchen": (("counter", 0.20, 0.22, 0.0), ("sink", 0.40, 0.22, 0.90), ("fridge", 0.82, 0.22, 0.0), ("table", 0.50, 0.65, 0.0), ("light", 0.50, 0.50, 2.70)),
    "bathroom": (("toilet", 0.25, 0.28, 0.0), ("sink", 0.70, 0.28, 0.0), ("shower", 0.50, 0.75, 0.0), ("light", 0.50, 0.50, 2.70)),
    "utility": (("washer", 0.25, 0.25, 0.0), ("shelf", 0.75, 0.25, 0.0), ("light", 0.50, 0.50, 2.70)),
    "workshop": (("workbench", 0.25, 0.25, 0.0), ("tool_rack", 0.25, 0.12, 1.40), ("crate", 0.75, 0.25, 0.0), ("light", 0.50, 0.50, 2.70)),
    "storage": (("shelf", 0.20, 0.25, 0.0), ("shelf", 0.50, 0.25, 0.0), ("crate", 0.80, 0.25, 0.0), ("light", 0.50, 0.50, 2.70)),
}


def _stable_index(seed: str, n: int) -> int:
    if n <= 0:
        return 0
    return int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16], 16) % n


def _by_role(catalog: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for item in catalog.get("items", []) or []:
        if isinstance(item, dict):
            out.setdefault(str(item.get("role", "")), []).append(item)
    return out




def _family_group(value: str | None) -> str:
    if not value:
        return ""
    parts = [p for p in str(value).replace("\\", "/").split("/") if p]
    return "/".join(parts[:2]).lower() if len(parts) >= 2 else (parts[0].lower() if parts else "")


def _choose_kit_family(room: Room, layout: Layout, required_roles: list[str], by_role: dict[str, list[dict[str, Any]]]) -> tuple[str | None, str]:
    """Pick one furniture family for a room before selecting individual roles."""
    families: dict[str, dict[str, Any]] = {}
    for role in required_roles:
        for row in by_role.get(role, []):
            fam = str(row.get("family") or "")
            if not fam:
                continue
            rec = families.setdefault(fam, {"roles": set(), "score": 0.0, "styles": set(), "group": _family_group(fam)})
            rec["roles"].add(role)
            rec["score"] += float(row.get("score", 0.0))
            rec["styles"].update(row.get("styles") or [])
    if not families:
        return None, "none"
    wanted_style = str(layout.building.type)
    ranked = []
    for fam, rec in families.items():
        coverage = len(rec["roles"])
        style_hit = 1 if wanted_style in rec["styles"] else 0
        ranked.append((coverage * 1000 + style_hit * 120 + rec["score"] / max(1, len(rec["roles"])), fam, rec))
    ranked.sort(key=lambda x: (-x[0], x[1]))
    best_score, best_family, best = ranked[0]
    # Prefer a family-group when it covers nearly as many roles; this prevents tiny
    # path-specific families from mixing unrelated furniture sets.
    best_group = best["group"]
    group_rows = []
    for score, fam, rec in ranked:
        if rec["group"] == best_group:
            group_rows.append((score, fam, rec))
    if group_rows and group_rows[0][0] >= best_score - 250:
        return group_rows[0][1], "family_or_group"
    return best_family, "family"

def _choose(role: str, room: Room, layout: Layout, by_role: dict[str, list[dict[str, Any]]], arch_family: str | None, kit_family: str | None) -> dict[str, Any] | None:
    rows = by_role.get(role, [])
    if not rows:
        return None
    arch_group = arch_family.split("/")[:2] if arch_family else []
    filtered = [r for r in rows if not kit_family or str(r.get("family")) == kit_family]
    if not filtered and kit_family:
        kg = _family_group(kit_family)
        filtered = [r for r in rows if _family_group(str(r.get("family"))) == kg]
    if not filtered:
        filtered = rows
    scored: list[tuple[float, str, dict[str, Any]]] = []
    for row in filtered:
        score = float(row.get("score", 0.0))
        styles = set(row.get("styles") or [])
        if str(layout.building.type) in styles:
            score += 40
        family = str(row.get("family", ""))
        if arch_group and family.split("/")[:2] == arch_group:
            score += 25
        if row.get("family") == arch_family:
            score += 50
        if kit_family and family == kit_family:
            score += 160
        elif kit_family and _family_group(family) == _family_group(kit_family):
            score += 60
        scored.append((score, family, row))
    scored.sort(key=lambda x: (-x[0], x[1], str(x[2].get("path", ""))))
    top_score = scored[0][0]
    top = [row for score, _, row in scored if score >= top_score - 25]
    return top[_stable_index(f"{layout.building.id}|{room.id}|{role}", len(top))]


def build_decoration_plan(layout: Layout, catalog: dict[str, Any], *, architecture_family: str | None = None, density: float = 1.0) -> dict[str, Any]:
    by_role = _by_role(catalog)
    placements: list[dict[str, Any]] = []
    missing: list[str] = []
    for room in layout.rooms:
        recipe = RECIPES.get(room.kind, (("light", 0.50, 0.50, 2.70),))
        required_roles = [role for role, *_ in recipe]
        kit_family, kit_mode = _choose_kit_family(room, layout, required_roles, by_role)
        for n, (role, fx, fy, z) in enumerate(recipe, start=1):
            # Density removes complete recipe slots, not arbitrary individual meshes.
            if density < 1.0:
                gate = int(hashlib.sha256(f"{layout.building.id}|{room.id}|{role}|{n}".encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
                if gate > density:
                    continue
            item = _choose(role, room, layout, by_role, architecture_family, kit_family)
            if item is None:
                if role != "light":
                    missing.append(f"{room.id}:{role}")
                continue
            lx = room.x + room.width * fx
            ly = room.y + room.depth * fy
            wp = world_pos(layout.building, lx, ly, room.floor * 3.2 + z)
            rotation = layout.building.yaw_deg
            # Furniture is oriented according to the room recipe. Wall-adjacent objects face inward.
            if fx <= 0.25:
                rotation += 90
            elif fx >= 0.75:
                rotation -= 90
            elif fy <= 0.25:
                rotation += 180
            placements.append({
                "id": f"{room.id}_DEC_{role}_{n:02d}",
                "resource": item["path"],
                "role": role,
                "room_id": room.id,
                "floor": room.floor,
                "position": {"x": wp.x, "y": wp.y, "z": wp.z},
                "rotation_deg": rotation,
                "scale": {"x": 1.0, "y": 1.0, "z": 1.0},
                "family": item.get("family"),
                "styles": item.get("styles", []),
                "architecture_family": architecture_family,
                "decoration_kit_family": kit_family,
                "decoration_kit_mode": kit_mode,
            })
    return {
        "format": FORMAT,
        "building_id": layout.building.id,
        "architecture_family": architecture_family,
        "placement_count": len(placements),
        "kit_family_count": len({str(p.get("decoration_kit_family")) for p in placements if p.get("decoration_kit_family")}),
        "placements": placements,
        "missing_roles": sorted(set(missing)),
        "warnings": [] if not missing else [f"No real .ent resource matched: {x}" for x in sorted(set(missing))],
    }
