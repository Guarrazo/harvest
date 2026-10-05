from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

VERSION = "0.28.0"
FLOOR_HEIGHT = 3.2


def _load(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _dims(item: dict[str, Any]) -> tuple[float, float, float]:
    bounds = item.get("bounds") if isinstance(item.get("bounds"), dict) else None
    if bounds and isinstance(bounds.get("dimensions_m"), dict):
        d = bounds["dimensions_m"]
        try:
            return abs(float(d.get("x", 0.0))), abs(float(d.get("y", 0.0))), abs(float(d.get("z", 0.0)))
        except (TypeError, ValueError):
            pass
    d = item.get("dimensions") or {}
    d = d.get("metres") or d
    try:
        return abs(float(d.get("l", 0.0))), abs(float(d.get("w", 0.0))), abs(float(d.get("h", 0.0)))
    except (TypeError, ValueError):
        return 0.0, 0.0, 0.0


def _world_to_local(building: dict[str, Any], x: float, y: float) -> tuple[float, float]:
    p = building.get("position") or {}
    dx = x - float(p.get("x", 0.0))
    dy = y - float(p.get("y", 0.0))
    a = math.radians(float(building.get("yaw_deg", 0.0)))
    return dx * math.cos(a) + dy * math.sin(a), -dx * math.sin(a) + dy * math.cos(a)


def _overlap(a0: float, a1: float, b0: float, b1: float) -> bool:
    return min(a1, b1) - max(a0, b0) > 0.05


def _placement_overlaps_void(p: dict[str, Any], void: dict[str, Any], building: dict[str, Any], catalog_by_path: dict[str, dict[str, Any]]) -> bool:
    pos = p.get("position") or {}
    lx, ly = _world_to_local(building, float(pos.get("x", 0.0)), float(pos.get("y", 0.0)))
    item = catalog_by_path.get(str(p.get("resource", "")), {})
    dx, dy, _ = _dims(item)
    scale = p.get("scale") or {}
    sx, sy = abs(float(scale.get("x", 1.0))), abs(float(scale.get("y", 1.0)))
    hx = max(0.35, dx * sx * 0.5)
    hy = max(0.35, dy * sy * 0.5)
    return _overlap(lx - hx, lx + hx, float(void["x"]), float(void["x"]) + float(void["width"])) and _overlap(
        ly - hy, ly + hy, float(void["y"]), float(void["y"]) + float(void["depth"])
    )


def _score_stair(item: dict[str, Any], target_w: float, target_d: float, target_h: float, desired_family: str | None) -> tuple[float, str]:
    w, d, h = _dims(item)
    if w <= 0 or d <= 0:
        return 99999.0, "unknown_dimensions"
    span = max(w, d)
    cross = min(w, d)
    score = abs(span - target_d) * 30.0 + abs(cross - target_w) * 20.0 + abs(h - target_h) * 15.0
    if desired_family and str(item.get("family")) == desired_family:
        score -= 25.0
    if bool(item.get("collisionless_variant")):
        score += 8.0
    return score, "dimension_family_fit"


def _stable_choice(rows: list[dict[str, Any]], seed: str) -> dict[str, Any] | None:
    if not rows:
        return None
    rows = sorted(rows, key=lambda x: (float(x[0]), str(x[1].get("path", ""))))
    best = rows[: min(6, len(rows))]
    idx = int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8], 16) % len(best)
    return best[idx][1]


def upgrade_assembly(layouts_path: str | Path, assembly_path: str | Path, catalog_path: str | Path, out_path: str | Path) -> dict[str, Any]:
    layouts = _load(layouts_path)
    assembly = _load(assembly_path)
    catalog_raw = _load(catalog_path)
    catalog = catalog_raw.get("catalog", catalog_raw)
    items = [x for x in catalog.get("items", []) or [] if isinstance(x, dict)]
    catalog_by_path = {str(x.get("path", "")).replace("/", "\\"): x for x in items}
    stairs = [x for x in items if str(x.get("class")) == "stairs_piece"]
    layout_by = {str((x.get("building") or {}).get("id")): x for x in layouts.get("layouts", []) if isinstance(x, dict)}
    out_buildings: list[dict[str, Any]] = []
    total_stairs = 0
    removed_surfaces = 0

    for building_asm in assembly.get("buildings", []) or []:
        if not isinstance(building_asm, dict):
            continue
        bid = str(building_asm.get("id"))
        raw = layout_by.get(bid)
        if not raw:
            out_buildings.append(dict(building_asm))
            continue
        building = dict(raw.get("building") or {})
        rooms = [x for x in raw.get("rooms", []) if isinstance(x, dict) and x.get("kind") == "stairwell"]
        placements = [dict(x) for x in building_asm.get("placements", []) if isinstance(x, dict)]
        voids = [{"floor": int(r.get("floor", 0)), "x": float(r.get("x", 0.0)), "y": float(r.get("y", 0.0)), "width": float(r.get("width", 0.0)), "depth": float(r.get("depth", 0.0))} for r in rooms]

        kept: list[dict[str, Any]] = []
        for p in placements:
            if str(p.get("class")) in {"floor_piece", "ceiling_piece"}:
                floor = int(p.get("floor", 0))
                matched = next((v for v in voids if v["floor"] == floor), None)
                if matched and _placement_overlaps_void(p, matched, building, catalog_by_path):
                    removed_surfaces += 1
                    continue
            kept.append(p)
        placements = kept

        class_families = building_asm.get("class_families") or {}
        desired_family = class_families.get("stairs_piece") if isinstance(class_families, dict) else None
        for room in rooms:
            floor = int(room.get("floor", 0))
            w = float(room.get("width", 2.8))
            d = float(room.get("depth", 3.4))
            candidates = []
            for item in stairs:
                score, mode = _score_stair(item, w * 0.90, d * 0.90, FLOOR_HEIGHT, desired_family)
                candidates.append((score, item, mode))
            top = sorted(candidates, key=lambda x: (x[0], str(x[1].get("path", ""))))
            item = _stable_choice(top, f"{bid}|stairs|F{floor}")
            if item is None:
                continue
            iw, id_, ih = _dims(item)
            scale = {"x": 1.0, "y": 1.0, "z": 1.0}
            if iw > 0 and id_ > 0:
                target_span = max(w, d) * 0.90
                source_span = max(iw, id_)
                scale_xy = max(0.75, min(1.25, target_span / source_span))
                scale = {"x": scale_xy, "y": scale_xy, "z": (FLOOR_HEIGHT / ih if ih > 0 else 1.0)}
            cx = float(room.get("x", 0.0)) + w * 0.5
            cy = float(room.get("y", 0.0)) + d * 0.5
            pos = {
                "x": float(building.get("position", {}).get("x", 0.0)),
                "y": float(building.get("position", {}).get("y", 0.0)),
                "z": float(building.get("position", {}).get("z", 0.0)) + floor * FLOOR_HEIGHT,
            }
            yaw = math.radians(float(building.get("yaw_deg", 0.0)))
            pos["x"] += math.cos(yaw) * cx - math.sin(yaw) * cy
            pos["y"] += math.sin(yaw) * cx + math.cos(yaw) * cy
            direction = 0.0 if float(room.get("y", 0.0)) >= 0.0 else 180.0
            placements.append({
                "id": f"{room['id']}_ARCH_stairs",
                "class": "stairs_piece",
                "semantic": "vertical_stairs",
                "resource": str(item.get("path", "")),
                "family": item.get("family"),
                "kit_family": item.get("family"),
                "room_id": room.get("id"),
                "floor": floor,
                "position": pos,
                "rotation_deg": float(building.get("yaw_deg", 0.0)) + direction,
                "scale": scale,
                "target": {
                    "vertical": True,
                    "from_floor": floor,
                    "to_floor": floor + 1 if floor + 1 < int(building.get("floors", 1)) else None,
                    "stairwell": True,
                    "width_m": w,
                    "depth_m": d,
                    "height_m": FLOOR_HEIGHT,
                },
                "selection": {"mode": "structural_v028", "source_family": desired_family, "dimensions_m": {"x": iw, "y": id_, "z": ih}},
                "requires_bounds_validation": True,
            })
            total_stairs += 1

        by_class = {}
        unresolved = []
        for p in placements:
            cls = str(p.get("class"))
            by_class[cls] = by_class.get(cls, 0) + 1
            if not p.get("resource"):
                unresolved.append(str(p.get("id")))
        upgraded = dict(building_asm)
        upgraded["placements"] = placements
        upgraded["placement_count"] = len(placements)
        upgraded["placement_counts"] = dict(sorted(by_class.items()))
        upgraded["unresolved"] = unresolved
        upgraded["unresolved_count"] = len(unresolved)
        upgraded["vertical_structure"] = {
            "stairs_count": len(rooms),
            "continuous_core": bool((building.get("vertical_core") or {}).get("continuous")),
            "room_ids": [str(r.get("id")) for r in rooms],
            "floor_holes_requested": len(rooms),
        }
        upgraded["family_coherence"] = upgraded.get("family_coherence", False)
        out_buildings.append(upgraded)

    result = dict(assembly)
    result["format"] = "ncig-architecture-assembly-structural-v1"
    result["version"] = VERSION
    result["buildings"] = out_buildings
    result["structural_upgrade"] = {"stairs_placements": total_stairs, "surface_placements_removed_for_stairwells": removed_surfaces}
    result["notes"] = list(result.get("notes") or []) + [
        "Vertical stair placements are generated from the real stairs_piece catalog; physical dimensions remain bounds-validation dependent.",
        "Floor/ceiling surface placements overlapping the stairwell are removed conservatively to create a vertical void.",
    ]
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="NCIG 0.28 structural architecture upgrade")
    p.add_argument("--layouts", required=True)
    p.add_argument("--assembly", required=True)
    p.add_argument("--catalog", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args()
    result = upgrade_assembly(args.layouts, args.assembly, args.catalog, args.out)
    print(json.dumps(result.get("structural_upgrade", {}), indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
