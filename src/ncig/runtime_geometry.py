from __future__ import annotations

import math
from typing import Any

def runtime_bounds(item: dict[str, Any]) -> dict[str, Any] | None:
    bounds = item.get("bounds")
    if not isinstance(bounds, dict):
        return None
    mn, mx = bounds.get("min"), bounds.get("max")
    dims = bounds.get("dimensions_m")
    if not isinstance(mn, dict) or not isinstance(mx, dict):
        return None
    try:
        min_xyz = {k: float(mn[k]) for k in ("x", "y", "z")}
        max_xyz = {k: float(mx[k]) for k in ("x", "y", "z")}
        if not isinstance(dims, dict):
            dims = {k: max_xyz[k] - min_xyz[k] for k in ("x", "y", "z")}
        dimensions = {k: abs(float(dims[k])) for k in ("x", "y", "z")}
    except (KeyError, TypeError, ValueError):
        return None
    return {"min": min_xyz, "max": max_xyz, "dimensions": dimensions}

def scaled_bbox_height(item: dict[str, Any], scale: dict[str, float]) -> float:
    bounds = runtime_bounds(item)
    if bounds is None:
        return 0.0
    return bounds["dimensions"]["z"] * abs(float(scale.get("z", 1.0)))

def surface_world_dimensions(item: dict[str, Any], rotation_delta_deg: float) -> tuple[float | None, float | None]:
    bounds = runtime_bounds(item)
    if bounds is None:
        return None, None
    d = bounds["dimensions"]
    if int(round(rotation_delta_deg / 90.0)) % 2 == 0:
        return d["x"], d["y"]
    return d["y"], d["x"]

def preferred_surface_rotation(item: dict[str, Any], target_x: float, target_y: float) -> float:
    bounds = runtime_bounds(item)
    if bounds is None:
        return 0.0
    dx, dy = bounds["dimensions"]["x"], bounds["dimensions"]["y"]
    if dx <= 1e-6 or dy <= 1e-6:
        return 0.0
    scored = []
    for rotation in (0.0, 90.0):
        if rotation == 0.0:
            sx, sy = target_x / dx, target_y / dy
        else:
            sx, sy = target_y / dx, target_x / dy
        cost = abs(math.log(max(abs(sx), 1e-6))) + abs(math.log(max(abs(sy), 1e-6)))
        scored.append((cost, rotation))
    return min(scored, key=lambda row: (row[0], row[1]))[1]

def surface_scale(item: dict[str, Any], target_x: float, target_y: float, rotation_delta_deg: float) -> dict[str, float] | None:
    bounds = runtime_bounds(item)
    if bounds is None:
        return None
    dx, dy = bounds["dimensions"]["x"], bounds["dimensions"]["y"]
    if dx <= 1e-6 or dy <= 1e-6:
        return None
    if int(round(rotation_delta_deg / 90.0)) % 2 == 0:
        return {"x": target_x / dx, "y": target_y / dy, "z": 1.0}
    return {"x": target_y / dx, "y": target_x / dy, "z": 1.0}

def linear_fit(item: dict[str, Any], *, span: float, height: float, desired_rotation_deg: float) -> dict[str, Any] | None:
    bounds = runtime_bounds(item)
    if bounds is None:
        return None
    dx, dy, dz = (bounds["dimensions"][k] for k in ("x", "y", "z"))
    if min(dx, dy, dz) <= 1e-6:
        return None
    if dx >= dy:
        return {
            "rotation_deg": float(desired_rotation_deg),
            "scale": {"x": span / dx, "y": 1.0, "z": height / dz},
            "span_axis": "x",
        }
    return {
        "rotation_deg": float(desired_rotation_deg - 90.0),
        "scale": {"x": 1.0, "y": span / dy, "z": height / dz},
        "span_axis": "y",
    }

def align_node_local_position(
    item: dict[str, Any],
    scale: dict[str, float],
    relative_rotation_deg: float,
    target_bbox_center_local: tuple[float, float, float],
) -> tuple[float, float, float]:
    bounds = runtime_bounds(item)
    if bounds is None:
        return target_bbox_center_local
    cx = (bounds["min"]["x"] + bounds["max"]["x"]) * 0.5 * float(scale.get("x", 1.0))
    cy = (bounds["min"]["y"] + bounds["max"]["y"]) * 0.5 * float(scale.get("y", 1.0))
    cz = (bounds["min"]["z"] + bounds["max"]["z"]) * 0.5 * float(scale.get("z", 1.0))
    a = math.radians(float(relative_rotation_deg))
    rcx = math.cos(a) * cx - math.sin(a) * cy
    rcy = math.sin(a) * cx + math.cos(a) * cy
    return (
        target_bbox_center_local[0] - rcx,
        target_bbox_center_local[1] - rcy,
        target_bbox_center_local[2] - cz,
    )
