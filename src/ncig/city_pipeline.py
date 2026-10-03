from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

from . import target_detector as td

FORMAT = "ncig-city-building-candidates-v1"


def _vec3(value: Any) -> tuple[float, float, float] | None:
    if isinstance(value, dict):
        try:
            x = next((value[k] for k in ("x", "X", "XCoord") if value.get(k) is not None), None)
            y = next((value[k] for k in ("y", "Y", "YCoord") if value.get(k) is not None), None)
            z = next((value[k] for k in ("z", "Z", "ZCoord") if value.get(k) is not None), None)
            if x is None or y is None or z is None:
                return None
            return float(x), float(y), float(z)
        except (TypeError, ValueError):
            return None
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        try:
            return float(value[0]), float(value[1]), float(value[2])
        except (TypeError, ValueError):
            return None
    return None


def _node_position(node: dict[str, Any]) -> tuple[float, float, float] | None:
    containers = [node]
    for key in ("data", "Data", "transform", "Transform"):
        value = node.get(key)
        if isinstance(value, dict):
            containers.append(value)
    for container in containers:
        for key in ("position", "worldPosition", "nodePosition", "Position", "WorldPosition", "NodePosition", "pos", "Pivot"):
            pos = _vec3(container.get(key))
            if pos is not None:
                return pos
    return None


def _depot_path(value: Any) -> str:
    if isinstance(value, dict):
        depot = value.get("DepotPath") or value.get("depotPath") or value.get("path")
        if isinstance(depot, dict):
            depot = depot.get("$value")
        if isinstance(depot, str) and depot:
            return depot.replace("/", "\\")
    if isinstance(value, str) and value:
        return value.replace("/", "\\")
    return ""


def _resource_path(node: dict[str, Any]) -> str:
    containers = [node]
    for key in ("data", "Data"):
        value = node.get(key)
        if isinstance(value, dict):
            containers.append(value)
    for container in containers:
        for key in (
            "mesh", "Mesh", "entityTemplate", "EntityTemplate",
            "resource", "Resource", "meshResource", "MeshResource",
        ):
            path = _depot_path(container.get(key))
            if path:
                return path
    return ""


def _node_yaw(node: dict[str, Any]) -> float:
    containers = [node]
    for key in ("data", "Data", "transform", "Transform"):
        value = node.get(key)
        if isinstance(value, dict):
            containers.append(value)
    for container in containers:
        for key in ("yaw_deg", "yaw", "Yaw", "YawDeg"):
            if container.get(key) is not None:
                try:
                    return float(container[key])
                except (TypeError, ValueError):
                    pass
        rot = next((container.get(k) for k in ("rotation", "Rotation", "rot", "Rot", "Orientation") if isinstance(container.get(k), dict)), None)
        if isinstance(rot, dict):
            try:
                x = float(rot.get("i", rot.get("x", rot.get("I", 0.0))))
                y = float(rot.get("j", rot.get("y", rot.get("J", 0.0))))
                z = float(rot.get("k", rot.get("z", rot.get("K", 0.0))))
                w = float(rot.get("r", rot.get("w", rot.get("R", 1.0))))
                return math.degrees(math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z)))
            except (TypeError, ValueError):
                pass
    return 0.0


def _node_scale(node: dict[str, Any]) -> tuple[float, float, float]:
    containers = [node]
    for key in ("data", "Data", "transform", "Transform"):
        value = node.get(key)
        if isinstance(value, dict):
            containers.append(value)
    for container in containers:
        value = container.get("scale", container.get("Scale"))
        if isinstance(value, dict):
            try:
                return (
                    abs(float(value.get("x", value.get("X", 1.0)))),
                    abs(float(value.get("y", value.get("Y", 1.0)))),
                    abs(float(value.get("z", value.get("Z", 1.0)))),
                )
            except (TypeError, ValueError):
                pass
    return 1.0, 1.0, 1.0


def _flatten_nodes(container: dict[str, Any]) -> list[dict[str, Any]]:
    node_defs = container.get("nodes") if isinstance(container.get("nodes"), list) else []
    if node_defs:
        return [dict(item) for item in node_defs if isinstance(item, dict)]
    return []


def _node_type(node: dict[str, Any]) -> str:
    for key in ("type", "nodeType", "Type", "NodeType", "$type"):
        value = node.get(key)
        if isinstance(value, str) and value:
            return value.rsplit(".", 1)[-1].split(",")[0]
    return ""


def _node_name(node: dict[str, Any]) -> str:
    for key in ("name", "nodeName", "Name", "NodeName", "debugName", "DebugName"):
        value = node.get(key)
        if isinstance(value, str):
            return value
    return ""


def _node_index(value: Any) -> int | None:
    try:
        if isinstance(value, dict):
            value = value.get("$value", value.get("value"))
        return int(value)
    except (TypeError, ValueError):
        return None


def _node_data_entries(container: dict[str, Any]) -> list[dict[str, Any]]:
    raw = container.get("nodeData") if "nodeData" in container else container.get("NodeData")
    if isinstance(raw, list):
        return [dict(item) for item in raw if isinstance(item, dict)]
    if isinstance(raw, dict):
        data = raw.get("Data")
        if isinstance(data, list):
            return [dict(item) for item in data if isinstance(item, dict)]
        elements = raw.get("Elements")
        if isinstance(elements, list):
            return [dict(item) for item in elements if isinstance(item, dict)]
    return []


def _unwrap_sector(raw: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(raw.get("sectors"), list):
        return [x for x in raw["sectors"] if isinstance(x, dict)]
    if isinstance(raw.get("sector"), dict):
        return [raw["sector"]]
    data = raw.get("Data")
    if isinstance(data, dict) and (
        isinstance(data.get("nodes"), list) or isinstance(data.get("nodeData"), (dict, list))
    ):
        return [data]
    if isinstance(raw.get("nodes"), list) or isinstance(raw.get("nodeData"), (dict, list)):
        return [raw]
    return []


def _records_from_sector(sector: dict[str, Any], source_file: str) -> list[dict[str, Any]]:
    nodes = _flatten_nodes(sector)
    if not nodes:
        return []
    by_index = {idx: node for idx, node in enumerate(nodes)}
    placements = _node_data_entries(sector)
    # A raw sector export can sometimes expose a structured placement list instead of
    # the binary buffer. The nodeData reader in WolvenKit maps each placement to NodeIndex.
    records: list[dict[str, Any]] = []
    for placement in placements:
        idx = _node_index(
            placement.get("NodeIndex", placement.get("nodeIndex", placement.get("node_index")))
        )
        node = by_index.get(idx) if idx is not None else None
        if not isinstance(node, dict):
            continue
        pos = _node_position(placement)
        if pos is None:
            continue
        node_type = _node_type(node)
        name = _node_name(node)
        resource = _resource_path(node)
        record = {
            "source_file": source_file,
            "sector": str(sector.get("name") or sector.get("sectorName") or Path(source_file).stem),
            "category": str(sector.get("category") or sector.get("sectorCategory") or ""),
            "type": node_type,
            "name": name,
            "resource": resource,
            "x": pos[0], "y": pos[1], "z": pos[2],
            "yaw_deg": _node_yaw(placement),
            "scale": _node_scale(placement),
            "dimensions_m": td._resource_dimensions(resource),
            "text": " ".join((name, node_type, resource, str(sector.get("category") or ""))).lower().replace("/", "\\"),
            "node_index": idx,
        }
        records.append(record)
    # Some lightweight/Object-Spawner-style inputs put transforms directly on nodes.
    if not records:
        for node in nodes:
            pos = _node_position(node)
            if pos is None:
                continue
            node_type = _node_type(node)
            name = _node_name(node)
            resource = _resource_path(node)
            records.append({
                "source_file": source_file,
                "sector": str(sector.get("name") or sector.get("sectorName") or Path(source_file).stem),
                "category": str(sector.get("category") or sector.get("sectorCategory") or ""),
                "type": node_type,
                "name": name,
                "resource": resource,
                "x": pos[0], "y": pos[1], "z": pos[2],
                "yaw_deg": _node_yaw(node),
                "scale": _node_scale(node),
                "dimensions_m": td._resource_dimensions(resource),
                "text": " ".join((name, node_type, resource, str(sector.get("category") or ""))).lower().replace("/", "\\"),
                "node_index": None,
            })
    return records


def _records_from_json(raw: Any, source_file: str) -> list[dict[str, Any]]:
    if not isinstance(raw, dict):
        return []
    records: list[dict[str, Any]] = []
    for sector in _unwrap_sector(raw):
        records.extend(_records_from_sector(sector, source_file))
    return records



def _sector_files(input_path: str | Path) -> list[Path]:
    p = Path(input_path)
    if p.is_file():
        return [p]
    if not p.is_dir():
        return []
    candidates = sorted(
        x for x in p.rglob("*.json")
        if x.name.lower().endswith(".streamingsector.json")
    )
    if candidates:
        return candidates
    # Fallback for exports whose converter removed the original extension.
    return sorted(x for x in p.rglob("*.json") if "streamingsector" in x.name.lower())


def _read_records_file(path: Path) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return _records_from_json(raw, str(path))


def _compact_manifest(input_path: str | Path, files: list[Path], invalid: list[dict[str, str]], file_counts: dict[str, int], record_count: int, phase: str) -> dict[str, Any]:
    return {
        "format": "ncig-world-manifest-v3",
        "input": str(Path(input_path).resolve()),
        "phase": phase,
        "json_file_count": len(files),
        "valid_file_count": len(files) - len(invalid),
        "invalid_file_count": len(invalid),
        "invalid_files": invalid[:200],
        "record_count": record_count,
        "sector_file_candidates": len(files),
        "largest_input_files": [
            {"path": path, "record_count": count}
            for path, count in sorted(file_counts.items(), key=lambda item: -item[1])[:20]
        ],
    }


def load_city_records(input_path: str | Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Load only records relevant to building detection; do not retain all exported JSON data."""
    files = _sector_files(input_path)
    invalid: list[dict[str, str]] = []
    file_counts: dict[str, int] = {}
    entrances: list[dict[str, Any]] = []

    # Pass 1: only entrances are kept. This is normally tiny compared with all world data.
    for path in files:
        try:
            parsed = _read_records_file(path)
        except (OSError, json.JSONDecodeError) as exc:
            invalid.append({"path": str(path), "error": type(exc).__name__, "message": str(exc)[:240]})
            continue
        file_counts[str(path)] = len(parsed)
        entrances.extend(r for r in parsed if td._is_entrance(r) and not td._is_interior(r))

    entrance_groups = _clusters(entrances, 4.0)
    entrance_centers = [
        {
            "x": sum(r["x"] for r in group) / len(group),
            "y": sum(r["y"] for r in group) / len(group),
            "z": sum(r["z"] for r in group) / len(group),
        }
        for group in entrance_groups
        if group
    ]
    entrance_index = SpatialIndex(entrances, 16.0) if entrances else None

    # Pass 2: keep only architecture/interior evidence near a discovered entrance.
    relevant: list[dict[str, Any]] = list(entrances)
    kept_files = 0
    kept_count = len(entrances)
    for path in files:
        try:
            parsed = _read_records_file(path)
        except (OSError, json.JSONDecodeError):
            continue
        kept_here = 0
        for record in parsed:
            if td._is_interior(record):
                include = entrance_index is not None and bool(
                    entrance_index.query(float(record["x"]), float(record["y"]), 24.0)
                )
            elif td._is_architecture(record):
                include = entrance_index is not None and bool(
                    entrance_index.query(float(record["x"]), float(record["y"]), 24.0)
                )
            else:
                include = False
            if include:
                relevant.append(record)
                kept_here += 1
        if kept_here:
            kept_files += 1
            kept_count += kept_here

    manifest = _compact_manifest(input_path, files, invalid, file_counts, kept_count, "two_pass_reduced")
    manifest.update({
        "all_entrance_count": len(entrances),
        "entrance_group_count": len(entrance_groups),
        "relevant_record_count": len(relevant),
        "relevant_file_count": kept_files,
        "reduction_ratio": round((1.0 - (len(relevant) / max(1, sum(file_counts.values())))), 6),
        "notes": [
            "WolvenKit exports a worldStreamingSector under a top-level Data object.",
            "nodeData is a structured worldNodeDataBuffer; each placement references nodes by NodeIndex.",
            "The city pipeline scans JSON files twice but retains only entrances and nearby architecture/interior evidence for detection.",
        ],
    })
    return relevant, manifest


class SpatialIndex:
    def __init__(self, records: list[dict[str, Any]], cell_size_m: float = 16.0) -> None:
        self.records = records
        self.cell_size_m = max(1.0, float(cell_size_m))
        self.cells: dict[tuple[int, int], list[int]] = {}
        for idx, record in enumerate(records):
            key = self._cell(float(record["x"]), float(record["y"]))
            self.cells.setdefault(key, []).append(idx)

    def _cell(self, x: float, y: float) -> tuple[int, int]:
        return math.floor(x / self.cell_size_m), math.floor(y / self.cell_size_m)

    def query(self, x: float, y: float, radius_m: float) -> list[int]:
        radius = max(0.0, float(radius_m))
        cx, cy = self._cell(x, y)
        span = max(1, int(math.ceil(radius / self.cell_size_m)))
        radius_sq = radius * radius
        out: list[int] = []
        for gx in range(cx - span, cx + span + 1):
            for gy in range(cy - span, cy + span + 1):
                for idx in self.cells.get((gx, gy), ()):
                    record = self.records[idx]
                    dx = float(record["x"]) - x
                    dy = float(record["y"]) - y
                    if dx * dx + dy * dy <= radius_sq:
                        out.append(idx)
        return out


def _distance_xy(a: dict[str, Any], b: dict[str, Any]) -> float:
    return math.hypot(float(a["x"]) - float(b["x"]), float(a["y"]) - float(b["y"]))


def _clusters(records: list[dict[str, Any]], radius_m: float) -> list[list[dict[str, Any]]]:
    if not records:
        return []
    index = SpatialIndex(records, radius_m)
    visited: set[int] = set()
    result: list[list[dict[str, Any]]] = []
    for seed in range(len(records)):
        if seed in visited:
            continue
        queue = [seed]
        visited.add(seed)
        cluster: list[dict[str, Any]] = []
        while queue:
            current = queue.pop()
            cluster.append(records[current])
            for neighbour in index.query(float(records[current]["x"]), float(records[current]["y"]), radius_m):
                if neighbour in visited:
                    continue
                if math.dist(
                    (records[current]["x"], records[current]["y"], records[current]["z"]),
                    (records[neighbour]["x"], records[neighbour]["y"], records[neighbour]["z"]),
                ) <= radius_m:
                    visited.add(neighbour)
                    queue.append(neighbour)
        result.append(cluster)
    return result


def _point_in_box(record: dict[str, Any], cx: float, cy: float, yaw_deg: float, width: float, depth: float, margin: float = 0.0) -> bool:
    theta = math.radians(yaw_deg)
    ct, st = math.cos(theta), math.sin(theta)
    dx, dy = float(record["x"]) - cx, float(record["y"]) - cy
    lx = dx * ct + dy * st
    ly = -dx * st + dy * ct
    return abs(lx) <= width * 0.5 + margin and abs(ly) <= depth * 0.5 + margin


def _candidate_from_group(
    entrance_group: list[dict[str, Any]],
    nearby: list[dict[str, Any]],
    interior_index: SpatialIndex,
    interiors: list[dict[str, Any]],
    idx: int,
) -> dict[str, Any] | None:
    if len(nearby) < 3:
        return None
    ex = sum(r["x"] for r in entrance_group) / len(entrance_group)
    ey = sum(r["y"] for r in entrance_group) / len(entrance_group)
    ez = sum(r["z"] for r in entrance_group) / len(entrance_group)
    group = nearby + entrance_group
    building_text = " ".join(str(r.get("text", "")) for r in group)
    btype = td._building_type(building_text)
    district = td._district_from_text(building_text)
    center_x, center_y, u_min, u_max, v_min, v_max, yaw_deg = td._oriented_bounds(nearby)
    width = max(4.5, (u_max - u_min) + 0.80)
    depth = max(4.5, (v_max - v_min) + 0.80)

    local_interiors: list[dict[str, Any]] = []
    interior_radius = min(24.0, max(8.0, max(width, depth) * 0.70 + 4.0))
    for interior_idx in interior_index.query(center_x, center_y, interior_radius):
        record = interiors[interior_idx]
        if _point_in_box(record, center_x, center_y, yaw_deg, width, depth, 1.5) or _distance_xy(record, {"x": ex, "y": ey}) <= 4.0:
            local_interiors.append(record)

    z_values = [float(r["z"]) for r in nearby]
    min_z, max_z = min(z_values), max(z_values)
    for record in nearby:
        bounds = td._record_footprint(record)
        if bounds is not None:
            min_z = min(min_z, bounds[4])
            max_z = max(max_z, bounds[5])
    height = max(3.2, (max_z - min_z) + 0.5)
    floors = max(1, min(20, int(round(height / 3.2))))

    theta = math.radians(yaw_deg)
    ct, st = math.cos(theta), math.sin(theta)
    entry_local_x = (ex - center_x) * ct + (ey - center_y) * st
    entry_local_y = -(ex - center_x) * st + (ey - center_y) * ct
    half_w, half_d = width * 0.5, depth * 0.5
    entry_local_x = max(-half_w, min(half_w, entry_local_x))
    entry_local_y = max(-half_d, min(half_d, entry_local_y))
    side_dist = {
        "north": abs(entry_local_y + half_d),
        "south": abs(entry_local_y - half_d),
        "west": abs(entry_local_x + half_w),
        "east": abs(entry_local_x - half_w),
    }
    entry_side = min(side_dist, key=side_dist.get)
    entry_facing_deg = math.degrees(math.atan2(ey - center_y, ex - center_x))

    wall_records = [r for r in nearby if td._record_kind(r) == "wall"]
    wall_sides: set[str] = set()
    for record in wall_records:
        wx, wy = float(record["x"]), float(record["y"])
        local_x = (wx - center_x) * ct + (wy - center_y) * st
        local_y = -(wx - center_x) * st + (wy - center_y) * ct
        dists = {
            "north": abs(local_y + half_d), "south": abs(local_y - half_d),
            "west": abs(local_x + half_w), "east": abs(local_x - half_w),
        }
        wall_sides.add(min(dists, key=dists.get))
    geometry_ready = (
        len(wall_records) >= 2 and len(wall_sides) >= 2
        and 4.5 <= width <= 32.0 and 4.5 <= depth <= 32.0
        and 3.2 <= height <= 64.0 and floors <= 20
    )

    detected_openings: list[dict[str, Any]] = []
    for record in (r for r in nearby if td._is_window(r)):
        local_x = (float(record["x"]) - center_x) * ct + (float(record["y"]) - center_y) * st
        local_y = -(float(record["x"]) - center_x) * st + (float(record["y"]) - center_y) * ct
        dists = {
            "north": abs(local_y + half_d), "south": abs(local_y - half_d),
            "west": abs(local_x + half_w), "east": abs(local_x - half_w),
        }
        side = min(dists, key=dists.get)
        dims = td._resource_dimensions(str(record.get("resource", "")))
        span = max(dims.get("l", 0.0), dims.get("w", 0.0))
        height_w = dims.get("h", 0.0)
        detected_openings.append({
            "kind": "window", "side": side,
            "local_x": round(local_x, 3), "local_y": round(local_y, 3),
            "width_m": round(max(0.6, min(6.0, span or 1.5)), 3),
            "height_m": round(max(0.8, min(3.0, height_w or 1.4)), 3),
            "yaw_deg": round(float(record.get("yaw_deg", yaw_deg)), 3),
            "resource": str(record.get("resource", "")),
        })

    entry_dims = [td._resource_dimensions(str(r.get("resource", ""))) for r in entrance_group]
    entry_spans = [max(d.get("l", 0.0), d.get("w", 0.0)) for d in entry_dims]
    entry_heights = [d.get("h", 0.0) for d in entry_dims]
    entry_width = max(0.8, min(2.5, max(entry_spans, default=1.1)))
    entry_height = max(1.8, min(3.0, max(entry_heights, default=2.1)))

    token_counts = Counter()
    for record in group:
        token_text = str(record.get("text", "")).lower()
        for token in td._BUILDING_TOKENS + td._ENTRANCE_TOKENS:
            if token in token_text:
                token_counts[token] += 1

    score = min(42, len(nearby) * 1.8)
    score += min(30, len(entrance_group) * 12)
    score += 18 if not local_interiors else 5
    score -= min(18, len(local_interiors) * 3)
    if any(t in token_counts for t in ("building", "tower", "shop", "store", "apartment", "office", "factory")):
        score += 8
    confidence = "high" if score >= 80 else "medium" if score >= 60 else "low"
    candidate_id = f"auto_{idx:05d}_{re.sub(r'[^a-z0-9]+', '_', btype.lower()).strip('_') or 'mixed'}"
    return {
        "id": candidate_id, "confidence": confidence, "score": max(0, min(100, int(round(score)))),
        "type": btype, "district": district,
        "position": {"x": round(center_x, 3), "y": round(center_y, 3), "z": round(min_z, 3)},
        "yaw_deg": round(yaw_deg, 3), "width_m": round(width, 3), "depth_m": round(depth, 3),
        "height_m": round(height, 3), "floors": floors, "entry_side": entry_side,
        "entry_local_x": round(entry_local_x, 3), "entry_local_y": round(entry_local_y, 3),
        "entry_world": {"x": round(ex, 3), "y": round(ey, 3), "z": round(ez, 3)},
        "entry_facing_deg": round(entry_facing_deg, 3), "entry_yaw_deg": round(entry_facing_deg, 3),
        "entry_width_m": round(entry_width, 3), "entry_height_m": round(entry_height, 3),
        "detected_openings": detected_openings[:24],
        "exterior_bounds": {
            "width_m": round(width, 3), "depth_m": round(depth, 3),
            "z_min": round(min_z, 3), "z_max": round(max_z, 3),
        },
        "evidence": {
            "architecture_nodes": len(nearby), "entrance_nodes": len(entrance_group),
            "wall_nodes": len(wall_records), "wall_sides": sorted(wall_sides),
            "geometry_ready": geometry_ready, "interior_nodes": len(local_interiors),
            "sectors": sorted({str(r.get("sector")) for r in group}),
            "source_files": sorted({str(r.get("source_file")) for r in group}),
            "token_counts": dict(sorted(token_counts.items())),
            "geometry_estimated_from": "node_position_plus_filename_lwh_hints_when_available",
        },
        "suggested_action": "fill" if confidence in {"high", "medium"} and geometry_ready and not local_interiors else "review",
    }


def detect_city_buildings(records: list[dict[str, Any]], *, cluster_radius_m: float = 18.0) -> dict[str, Any]:
    architecture = [r for r in records if td._is_architecture(r) and not td._is_interior(r)]
    entrances = [r for r in records if td._is_entrance(r) and not td._is_interior(r)]
    interiors = [r for r in records if td._is_interior(r)]
    entrance_groups = _clusters(entrances, min(8.0, cluster_radius_m * 0.5))
    architecture_index = SpatialIndex(architecture, cluster_radius_m)
    interior_index = SpatialIndex(interiors, max(8.0, min(20.0, cluster_radius_m)))
    candidates: list[dict[str, Any]] = []

    for idx, group in enumerate(entrance_groups, start=1):
        ex = sum(r["x"] for r in group) / len(group)
        ey = sum(r["y"] for r in group) / len(group)
        ez = sum(r["z"] for r in group) / len(group)
        nearby = [
            architecture[i]
            for i in architecture_index.query(ex, ey, cluster_radius_m)
            if math.dist((ex, ey, ez), (architecture[i]["x"], architecture[i]["y"], architecture[i]["z"])) <= cluster_radius_m
        ]
        candidate = _candidate_from_group(group, nearby, interior_index, interiors, idx)
        if candidate is not None:
            candidates.append(candidate)

    candidates.sort(key=lambda c: (-int(c["score"]), c["id"]))
    return {
        "format": FORMAT,
        "input_record_count": len(records),
        "architecture_record_count": len(architecture),
        "entrance_record_count": len(entrances),
        "interior_record_count": len(interiors),
        "entrance_group_count": len(entrance_groups),
        "cluster_radius_m": cluster_radius_m,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "notes": [
            "City-scale detection uses an XY spatial grid for entrance clustering, nearby architecture and interior evidence.",
            "Both World Builder/Object Spawner envelopes and direct single-sector JSON are accepted.",
            "Existing interior evidence is tested against the estimated oriented footprint rather than only the doorway distance.",
        ],
    }


def build_city_manifest(
    records: list[dict[str, Any]],
    files: list[Path],
    invalid: list[dict[str, str]],
    file_record_counts: dict[str, int],
    input_path: str,
) -> dict[str, Any]:
    node_types = Counter(str(r.get("type", "") or "unknown") for r in records)
    kinds = Counter(td._record_kind(r) for r in records)
    districts = Counter(td._district_from_text(str(r.get("text", ""))) for r in records)
    sectors = {str(r.get("sector", "")) for r in records if r.get("sector")}
    if records:
        bounds = {
            "x_min": min(float(r["x"]) for r in records), "x_max": max(float(r["x"]) for r in records),
            "y_min": min(float(r["y"]) for r in records), "y_max": max(float(r["y"]) for r in records),
            "z_min": min(float(r["z"]) for r in records), "z_max": max(float(r["z"]) for r in records),
        }
    else:
        bounds = {k: None for k in ("x_min", "x_max", "y_min", "y_max", "z_min", "z_max")}
    return {
        "format": "ncig-world-manifest-v2",
        "input": str(Path(input_path).resolve()),
        "json_file_count": len(files),
        "valid_file_count": len(files) - len(invalid),
        "invalid_file_count": len(invalid),
        "invalid_files": invalid,
        "record_count": len(records),
        "sector_count": len(sectors),
        "node_type_counts": dict(sorted(node_types.items())),
        "kind_counts": dict(sorted(kinds.items())),
        "district_counts": dict(sorted(districts.items())),
        "world_bounds": bounds,
        "largest_input_files": [
            {"path": path, "record_count": count}
            for path, count in sorted(file_record_counts.items(), key=lambda x: -x[1])[:20]
        ],
    }
