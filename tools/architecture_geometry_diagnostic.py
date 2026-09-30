from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def load(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def inv_rotate(x: float, y: float, yaw_deg: float) -> tuple[float, float]:
    a = math.radians(yaw_deg)
    c, s = math.cos(a), math.sin(a)
    return c * x + s * y, -s * x + c * y


def rotate(x: float, y: float, yaw_deg: float) -> tuple[float, float]:
    a = math.radians(yaw_deg)
    c, s = math.cos(a), math.sin(a)
    return c * x - s * y, s * x + c * y


def world_to_building_local(pos: dict[str, Any], building: dict[str, Any]) -> tuple[float, float, float]:
    dx = float(pos["x"]) - float(building["position"]["x"])
    dy = float(pos["y"]) - float(building["position"]["y"])
    lx, ly = inv_rotate(dx, dy, float(building.get("yaw_deg", 0.0)))
    lz = float(pos["z"]) - float(building["position"]["z"])
    return lx, ly, lz


def actual_planar_bbox(item: dict[str, Any], scale: dict[str, Any], relative_yaw: float) -> tuple[float, float, float, float]:
    b = item.get("bounds") or {}
    mn, mx = b.get("min"), b.get("max")
    if not isinstance(mn, dict) or not isinstance(mx, dict):
        raise ValueError("missing runtime bounds")
    sx = float(scale.get("x", 1.0))
    sy = float(scale.get("y", 1.0))
    corners = []
    for x in (float(mn["x"]) * sx, float(mx["x"]) * sx):
        for y in (float(mn["y"]) * sy, float(mx["y"]) * sy):
            corners.append(rotate(x, y, relative_yaw))
    xs = [p[0] for p in corners]
    ys = [p[1] for p in corners]
    return min(xs), max(xs), min(ys), max(ys)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--layouts", default=r"build\generated\layouts.json")
    p.add_argument("--assembly", default=r"build\real_architecture_remote\architecture_assembly_bounded.json")
    p.add_argument("--catalog", default=r"build\real_architecture_remote\architecture_catalog_bounded.json")
    p.add_argument("--building-id", default="demo_shop_001")
    p.add_argument("--out", default=r"build\real_architecture_remote\geometry_diagnostic_demo_shop_001.json")
    args = p.parse_args()

    layouts = load(args.layouts)
    assembly = load(args.assembly)
    catalog = load(args.catalog)
    catalog = catalog.get("catalog", catalog)

    layout = next(x for x in layouts.get("layouts", []) if str(x.get("building", {}).get("id")) == args.building_id)
    asm = next(x for x in assembly.get("buildings", []) if str(x.get("id")) == args.building_id)
    building = layout["building"]
    rooms = layout.get("rooms", [])
    by_room = {str(r["id"]): r for r in rooms}
    by_resource = {}
    for item in catalog.get("items", []):
        if isinstance(item, dict) and item.get("path"):
            by_resource.setdefault(str(item["path"]), item)

    placements = [x for x in asm.get("placements", []) if isinstance(x, dict)]
    rows = []
    missing_bounds = []
    class_counts = Counter()
    resource_counts = Counter()
    scale_non_identity = 0

    for pmt in placements:
        cls = str(pmt.get("class", "unknown"))
        class_counts[cls] += 1
        resource = str(pmt.get("resource", ""))
        resource_counts[resource] += 1
        item = by_resource.get(resource)
        room = by_room.get(str(pmt.get("room_id")))
        pos = pmt.get("position") or {}
        try:
            lx, ly, lz = world_to_building_local(pos, building)
        except Exception:
            lx = ly = lz = float("nan")
        scale = pmt.get("scale") or {}
        if any(abs(float(scale.get(k, 1.0)) - 1.0) > 1e-5 for k in ("x", "y", "z")):
            scale_non_identity += 1

        row = {
            "id": pmt.get("id"),
            "class": cls,
            "room_id": pmt.get("room_id"),
            "resource": resource,
            "position_building_local": {"x": lx, "y": ly, "z": lz},
            "rotation_world_deg": float(pmt.get("rotation_deg", 0.0)),
            "rotation_relative_deg": float(pmt.get("rotation_deg", 0.0)) - float(building.get("yaw_deg", 0.0)),
            "scale": scale,
            "runtime_bounds_present": bool(item and isinstance(item.get("bounds"), dict)),
            "runtime_bounds_dimensions_m": (item or {}).get("bounds", {}).get("dimensions_m") if item else None,
        }

        if not item or not isinstance(item.get("bounds"), dict):
            missing_bounds.append(row)
            rows.append(row)
            continue

        try:
            aminx, amaxx, aminy, amaxy = actual_planar_bbox(
                item, scale, row["rotation_relative_deg"]
            )
            row["actual_bbox_local"] = {
                "min_x": lx + aminx, "max_x": lx + amaxx,
                "min_y": ly + aminy, "max_y": ly + amaxy,
                "width": amaxx - aminx, "depth": amaxy - aminy,
            }
            if cls == "wall_piece" and room:
                side = ((pmt.get("target") or {}).get("side"))
                if side in ("north", "south"):
                    expected_y = float(room["y"]) if side == "north" else float(room["y"]) + float(room["depth"])
                    row["expected_wall_line"] = {"axis": "y", "value": expected_y, "error_center_m": ((aminy + amaxy) * 0.5 + ly) - expected_y}
                elif side in ("west", "east"):
                    expected_x = float(room["x"]) if side == "west" else float(room["x"]) + float(room["width"])
                    row["expected_wall_line"] = {"axis": "x", "value": expected_x, "error_center_m": ((aminx + amaxx) * 0.5 + lx) - expected_x}
            elif cls in ("door_piece", "door_frame") and room:
                y = float(room["y"]) if room["y"] >= 0 else float(room["y"]) + float(room["depth"])
                expected_x = float(room["x"]) + float(room["width"]) * 0.5
                actual_cx = lx + (aminx + amaxx) * 0.5
                actual_cy = ly + (aminy + amaxy) * 0.5
                row["expected_door_center"] = {
                    "x": expected_x, "y": y,
                    "error_x_m": actual_cx - expected_x,
                    "error_y_m": actual_cy - y,
                }
        except Exception as exc:
            row["bbox_error"] = str(exc)

        rows.append(row)

    report = {
        "format": "ncig-architecture-geometry-diagnostic-v1",
        "building": {
            "id": args.building_id,
            "width_m": building.get("width_m"),
            "depth_m": building.get("depth_m"),
            "yaw_deg": building.get("yaw_deg"),
        },
        "room_count": len(rooms),
        "rooms": rooms,
        "placement_count": len(placements),
        "class_counts": dict(sorted(class_counts.items())),
        "unique_resources": len(resource_counts),
        "scale_non_identity_count": scale_non_identity,
        "runtime_bounds_missing_count": len(missing_bounds),
        "runtime_bounds_missing_examples": missing_bounds[:20],
        "placements": rows,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({
        "written": args.out,
        "building_id": args.building_id,
        "room_count": len(rooms),
        "placement_count": len(placements),
        "class_counts": dict(sorted(class_counts.items())),
        "scale_non_identity_count": scale_non_identity,
        "runtime_bounds_missing_count": len(missing_bounds),
    }, indent=2, ensure_ascii=False))
    print("Key: a wall error near 0.0 m means its runtime bbox center is on the intended wall line.")
    print("Key: a door error near 0.0 m means the actual door bbox center matches the room door socket.")
    print("Key: scale_non_identity_count should be > 0 when harvested runtime bounds are being used for fitting.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
