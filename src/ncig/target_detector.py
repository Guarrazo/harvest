from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

FORMAT = "ncig-building-candidates-v1"

_BUILDING_TOKENS = (
    "building", "bldg", "tower", "apartment", "apt", "block", "plaza",
    "mall", "shop", "store", "market", "bar", "restaurant", "clinic",
    "hotel", "office", "warehouse", "factory", "industrial", "garage",
)
_ENTRANCE_TOKENS = ("door", "doorway", "entrance", "entry", "gate", "shutter", "shopfront")
_INTERIOR_TOKENS = (
    "interior", "\\interior\\", "\\int\\", "common\\int", "indoors",
    "bathroom", "kitchen", "corridor", "lobby", "bedroom", "office_int",
)
_EXTERIOR_NEGATIVE = ("road", "street", "sidewalk", "curb", "bridge", "terrain", "fence")
_TYPE_TOKENS = {
    "commercial": ("shop", "store", "market", "restaurant", "bar", "cafe", "retail", "mall"),
    "residential": ("apartment", "residential", "housing", "home", "flat"),
    "office": ("office", "corp", "corporate", "bureau"),
    "industrial": ("factory", "industrial", "warehouse", "workshop", "garage"),
}


def _walk(obj: Any) -> Iterable[Any]:
    yield obj
    if isinstance(obj, dict):
        for value in obj.values():
            yield from _walk(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _walk(value)


def _first(obj: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = obj.get(key)
        if value is not None:
            return value
    return default


def _vec3(value: Any) -> tuple[float, float, float] | None:
    if isinstance(value, dict):
        try:
            x = _first(value, "x", "X", "XCoord")
            y = _first(value, "y", "Y", "YCoord")
            z = _first(value, "z", "Z", "ZCoord")
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


def _resource_path(node: dict[str, Any]) -> str:
    data = node.get("data")
    if isinstance(data, dict):
        mesh = data.get("mesh")
        if isinstance(mesh, dict):
            depot = mesh.get("DepotPath")
            if isinstance(depot, dict) and isinstance(depot.get("$value"), str):
                return depot["$value"].replace("/", "\\")
        ent = data.get("entityTemplate")
        if isinstance(ent, dict):
            depot = ent.get("DepotPath")
            if isinstance(depot, dict) and isinstance(depot.get("$value"), str):
                return depot["$value"].replace("/", "\\")
    return ""


def _flatten_sector_nodes(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize both Object-Spawner-like direct nodes and native node/nodeData arrays."""
    direct: list[dict[str, Any]] = []
    for item in raw.get("nodes", []) or []:
        if isinstance(item, dict) and "type" in item:
            direct.append(dict(item))

    node_defs = raw.get("nodes") if isinstance(raw.get("nodes"), list) else []
    placements = raw.get("nodeData") if isinstance(raw.get("nodeData"), list) else []
    if placements and node_defs:
        by_index = {i: item for i, item in enumerate(node_defs) if isinstance(item, dict)}
        normalized: list[dict[str, Any]] = []
        for p in placements:
            if not isinstance(p, dict):
                continue
            idx = _first(p, "NodeIndex", "nodeIndex", "node_index", default=None)
            try:
                base = by_index.get(int(idx)) if idx is not None else None
            except (TypeError, ValueError):
                base = None
            if not isinstance(base, dict):
                continue
            merged = dict(base)
            merged.update({k: v for k, v in p.items() if k not in {"NodeIndex", "nodeIndex", "node_index"}})
            if "data" not in merged and isinstance(base.get("data"), dict):
                merged["data"] = base["data"]
            normalized.append(merged)
        if normalized:
            return normalized
    return direct


def _sector_objects(raw: Any, source_file: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not isinstance(raw, dict):
        return records
    sectors = raw.get("sectors")
    if isinstance(sectors, list):
        for sector in sectors:
            if not isinstance(sector, dict):
                continue
            sector_name = str(sector.get("name") or Path(source_file).stem)
            category = str(sector.get("category") or "")
            for node in _flatten_sector_nodes(sector):
                pos = _vec3(node.get("position") or node.get("worldPosition") or node.get("nodePosition"))
                if pos is None:
                    continue
                node_type = str(node.get("type") or node.get("nodeType") or "")
                name = str(node.get("name") or node.get("nodeName") or "")
                resource = _resource_path(node)
                text = " ".join((name, node_type, resource, sector_name, category)).lower().replace("/", "\\")
                records.append({
                    "source_file": source_file,
                    "sector": sector_name,
                    "category": category,
                    "type": node_type,
                    "name": name,
                    "resource": resource,
                    "x": pos[0], "y": pos[1], "z": pos[2],
                    "yaw_deg": _node_yaw(node),
                    "scale": _node_scale(node),
                    "dimensions_m": _resource_dimensions(resource),
                    "text": text,
                })
    return records


def _iter_input_files(input_path: str | Path) -> list[Path]:
    p = Path(input_path)
    if p.is_file():
        return [p]
    if p.is_dir():
        return sorted(p.rglob("*.json"))
    raise FileNotFoundError(p)


def load_world_records(input_path: str | Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in _iter_input_files(input_path):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        records.extend(_sector_objects(raw, str(path)))
    return records


def _has_token(text: str, tokens: Iterable[str]) -> bool:
    return any(token in text for token in tokens)


_DIMENSION_RE = re.compile(r"(?:^|[_-])([lwh])([0-9]+(?:\.[0-9]+)?)(?=$|[_-])", re.IGNORECASE)


def _node_yaw(node: dict[str, Any]) -> float:
    direct = _first(node, "yaw_deg", "yaw", "Yaw", default=None)
    if direct is not None:
        try:
            return float(direct)
        except (TypeError, ValueError):
            pass
    rot = node.get("rotation")
    if isinstance(rot, dict):
        try:
            x = float(_first(rot, "i", "x", default=0.0))
            y = float(_first(rot, "j", "y", default=0.0))
            z = float(_first(rot, "k", "z", default=0.0))
            w = float(_first(rot, "r", "w", default=1.0))
            return math.degrees(math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z)))
        except (TypeError, ValueError):
            pass
    return 0.0


def _node_scale(node: dict[str, Any]) -> tuple[float, float, float]:
    value = node.get("scale")
    if isinstance(value, dict):
        try:
            return (
                abs(float(_first(value, "x", "X", default=1.0))),
                abs(float(_first(value, "y", "Y", default=1.0))),
                abs(float(_first(value, "z", "Z", default=1.0))),
            )
        except (TypeError, ValueError):
            pass
    return 1.0, 1.0, 1.0


def _resource_dimensions(path: str) -> dict[str, float]:
    stem = Path(path.replace("\\", "/")).stem.lower()
    out: dict[str, float] = {}
    for match in _DIMENSION_RE.finditer(stem):
        out.setdefault(match.group(1).lower(), float(match.group(2)) / 100.0)
    return out


def _record_kind(record: dict[str, Any]) -> str:
    hay = " ".join(
        str(record.get(k, ""))
        for k in ("name", "type", "resource", "text")
    ).lower()
    if any(t in hay for t in ("window", "shopwindow", "skylight")):
        return "window"
    if any(t in hay for t in ("door", "doorway", "entrance", "entry", "gate", "shutter", "shopfront")):
        return "door"
    if any(t in hay for t in ("wall", "partition", "bulkhead", "facade", "building")):
        return "wall"
    if any(t in hay for t in ("floor", "ground", "walkway")):
        return "floor"
    if any(t in hay for t in ("roof", "ceiling")):
        return "ceiling"
    return "other"


def _district_from_text(text: str) -> str:
    hay = text.lower().replace("_", " ").replace("\\", " ")
    aliases = (
        ("dogtown", ("dogtown",)),
        ("watson", ("watson", "kabuki", "little china")),
        ("westbrook", ("westbrook", "jig jig street", "japan town", "north oak", "charter hill")),
        ("heywood", ("heywood", "the glen", "vista del rey", "wellprings")),
        ("santo_domingo", ("santo domingo", "arroyo", "rancho coronado")),
        ("pacifica", ("pacifica", "coastview", "coast view")),
        ("city_center", ("city center", "corporate plaza", "downtown")),
        ("badlands", ("badlands", "rockridge", "biotechnica flats", "medeski")),
    )
    for district, tokens in aliases:
        if any(token in hay for token in tokens):
            return district
    return "unknown"


def _record_footprint(record: dict[str, Any]) -> tuple[float, float, float, float, float, float] | None:
    """Return a conservative world AABB from resource dimensions and node transform."""
    x, y, z = (float(record[k]) for k in ("x", "y", "z"))
    dims = record.get("dimensions_m") if isinstance(record.get("dimensions_m"), dict) else {}
    kind = _record_kind(record)
    a = math.radians(float(record.get("yaw_deg", 0.0)))
    sx, sy, sz = record.get("scale", (1.0, 1.0, 1.0))
    sx, sy, sz = abs(float(sx)), abs(float(sy)), abs(float(sz))

    if kind in {"wall", "door", "window"}:
        span = max(float(dims.get("l", 0.0)), float(dims.get("w", 0.0)))
        thickness_values = [float(v) for v in (dims.get("l", 0.0), dims.get("w", 0.0)) if float(v) > 0.01]
        thickness = min(thickness_values, default=0.12)
        # CP77 architecture filenames commonly use w/l as span/thickness for wall-like pieces.
        if len(thickness_values) == 1:
            thickness = min(0.16, max(0.06, thickness_values[0] * 0.10))
        lx, ly = max(0.10, span) * sx, max(0.04, thickness) * sy
    elif kind in {"floor", "ceiling"}:
        lx = max(float(dims.get("l", 0.0)), float(dims.get("w", 0.0))) * sx
        ly = min(
            max(float(dims.get("l", 0.0)), float(dims.get("w", 0.0))),
            max(float(dims.get("w", 0.0)), 0.10),
        ) * sy
        if lx <= 0.01 or ly <= 0.01:
            return None
    else:
        lx = float(dims.get("l", 0.0) or dims.get("w", 0.0)) * sx
        ly = float(dims.get("w", 0.0) or dims.get("l", 0.0)) * sy

    h = float(dims.get("h", 0.0)) * sz
    if lx <= 0.01 or ly <= 0.01:
        return None
    ex = abs(math.cos(a)) * lx * 0.5 + abs(math.sin(a)) * ly * 0.5
    ey = abs(math.sin(a)) * lx * 0.5 + abs(math.cos(a)) * ly * 0.5
    ez = h * 0.5 if h > 0.01 else 0.0
    return x - ex, x + ex, y - ey, y + ey, z - ez, z + ez


def _is_architecture(record: dict[str, Any]) -> bool:
    resource = str(record.get("resource", "")).lower()
    text = str(record.get("text", "")).lower()
    if _has_token(text, _EXTERIOR_NEGATIVE):
        return False
    return "\\environment\\architecture\\" in resource or _has_token(text, _BUILDING_TOKENS)


def _is_window(record: dict[str, Any]) -> bool:
    return _record_kind(record) == "window" and not _is_interior(record)


def _is_entrance(record: dict[str, Any]) -> bool:
    text = str(record.get("text", "")).lower()
    if _has_token(text, _EXTERIOR_NEGATIVE):
        return False
    return (_record_kind(record) == "door") and (
        "\\environment\\architecture\\" in str(record.get("resource", "")).lower()
        or _has_token(text, _BUILDING_TOKENS)
    )


def _is_interior(record: dict[str, Any]) -> bool:
    text = str(record.get("text", "")).lower().replace("/", "\\")
    if _has_token(text, _INTERIOR_TOKENS):
        return True
    category = str(record.get("category", "")).lower()
    if category in {"interior", "interiors", "navigation"}:
        return True
    return str(record.get("type", "")).lower() in {"worldinteriorareanode", "worldambientareanode"}


def _building_type(text: str) -> str:
    t = text.lower()
    scores = {k: sum(1 for token in tokens if token in t) for k, tokens in _TYPE_TOKENS.items()}
    best = max(scores.items(), key=lambda kv: (kv[1], kv[0]))
    return best[0] if best[1] else "mixed"


def _distance(a: dict[str, Any], b: dict[str, Any]) -> float:
    return math.dist((a["x"], a["y"], a["z"]), (b["x"], b["y"], b["z"]))


def _clusters(records: list[dict[str, Any]], radius_m: float) -> list[list[dict[str, Any]]]:
    remaining = list(records)
    clusters: list[list[dict[str, Any]]] = []
    while remaining:
        seed = remaining.pop(0)
        cluster = [seed]
        changed = True
        while changed:
            changed = False
            keep: list[dict[str, Any]] = []
            for candidate in remaining:
                if any(_distance(candidate, member) <= radius_m for member in cluster):
                    cluster.append(candidate)
                    changed = True
                else:
                    keep.append(candidate)
            remaining = keep
        clusters.append(cluster)
    return clusters


def _oriented_bounds(records: list[dict[str, Any]]) -> tuple[float, float, float, float, float, float, float]:
    """Return min/max in a PCA frame plus PCA yaw."""
    xs = [float(r["x"]) for r in records]
    ys = [float(r["y"]) for r in records]
    cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
    cxx = sum((x - cx) ** 2 for x in xs) / max(1, len(xs))
    cyy = sum((y - cy) ** 2 for y in ys) / max(1, len(xs))
    cxy = sum((x - cx) * (y - cy) for x, y in zip(xs, ys)) / max(1, len(xs))
    theta = 0.5 * math.atan2(2.0 * cxy, cxx - cyy) if abs(cxy) > 1e-9 else (0.0 if cxx >= cyy else math.pi / 2.0)
    ct, st = math.cos(theta), math.sin(theta)
    u_min = v_min = float("inf")
    u_max = v_max = float("-inf")
    z_min = float("inf")
    z_max = float("-inf")
    for r in records:
        rx, ry = float(r["x"]) - cx, float(r["y"]) - cy
        u = rx * ct + ry * st
        v = -rx * st + ry * ct
        bounds = _record_footprint(r)
        if bounds is not None:
            bx0, bx1, by0, by1, bz0, bz1 = bounds
            for px, py in ((bx0, by0), (bx0, by1), (bx1, by0), (bx1, by1)):
                prx, pry = px - cx, py - cy
                pu = prx * ct + pry * st
                pv = -prx * st + pry * ct
                u_min, u_max = min(u_min, pu), max(u_max, pu)
                v_min, v_max = min(v_min, pv), max(v_max, pv)
            z_min, z_max = min(z_min, bz0), max(z_max, bz1)
        else:
            u_min, u_max = min(u_min, u), max(u_max, u)
            v_min, v_max = min(v_min, v), max(v_max, v)
            z_min, z_max = min(z_min, float(r["z"])), max(z_max, float(r["z"]))
    if not math.isfinite(z_min):
        z_min = min(float(r["z"]) for r in records)
        z_max = max(float(r["z"]) for r in records)
    center_u, center_v = (u_min + u_max) * 0.5, (v_min + v_max) * 0.5
    center_x = cx + center_u * ct - center_v * st
    center_y = cy + center_u * st + center_v * ct
    return center_x, center_y, u_min, u_max, v_min, v_max, math.degrees(theta)


def detect_building_candidates(records: list[dict[str, Any]], *, cluster_radius_m: float = 18.0) -> dict[str, Any]:
    """Detect exterior building shells around entrance evidence, with geometry-aware footprints."""
    exterior_architecture = [r for r in records if _is_architecture(r) and not _is_interior(r)]
    entrances = [r for r in records if _is_entrance(r) and not _is_interior(r)]
    entrance_groups = _clusters(entrances, min(8.0, cluster_radius_m * 0.5))
    candidates: list[dict[str, Any]] = []

    for idx, entrance_group in enumerate(entrance_groups, start=1):
        ex = sum(r["x"] for r in entrance_group) / len(entrance_group)
        ey = sum(r["y"] for r in entrance_group) / len(entrance_group)
        ez = sum(r["z"] for r in entrance_group) / len(entrance_group)
        nearby = [
            r for r in exterior_architecture
            if math.dist((r["x"], r["y"], r["z"]), (ex, ey, ez)) <= cluster_radius_m
        ]
        if len(nearby) < 3:
            continue

        interiors = [
            r for r in records
            if _is_interior(r) and math.dist((r["x"], r["y"], r["z"]), (ex, ey, ez)) <= min(20.0, cluster_radius_m + 2.0)
        ]
        group = nearby + entrance_group
        building_text = " ".join(str(r.get("text", "")) for r in group)
        btype = _building_type(building_text)
        district = _district_from_text(building_text)
        center_x, center_y, u_min, u_max, v_min, v_max, yaw_deg = _oriented_bounds(nearby)
        width = max(4.5, (u_max - u_min) + 0.80)
        depth = max(4.5, (v_max - v_min) + 0.80)
        z_values = [float(r["z"]) for r in nearby]
        min_z, max_z = min(z_values), max(z_values)
        for r in nearby:
            bounds = _record_footprint(r)
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

        token_counts = Counter()
        for r in group:
            token_text = str(r.get("text", "")).lower()
            for token in _BUILDING_TOKENS + _ENTRANCE_TOKENS:
                if token in token_text:
                    token_counts[token] += 1

        detected_openings: list[dict[str, Any]] = []
        for wr in [r for r in nearby if _is_window(r)]:
            theta_w = math.radians(float(yaw_deg))
            ct_w, st_w = math.cos(theta_w), math.sin(theta_w)
            wx, wy = float(wr["x"]), float(wr["y"])
            local_x = (wx - center_x) * ct_w + (wy - center_y) * st_w
            local_y = -(wx - center_x) * st_w + (wy - center_y) * ct_w
            half_w = width * 0.5
            half_d = depth * 0.5
            dists = {
                "north": abs(local_y + half_d),
                "south": abs(local_y - half_d),
                "west": abs(local_x + half_w),
                "east": abs(local_x - half_w),
            }
            side = min(dists, key=dists.get)
            dims_w = _resource_dimensions(str(wr.get("resource", "")))
            span = max(dims_w.get("l", 0.0), dims_w.get("w", 0.0))
            height_w = dims_w.get("h", 0.0)
            detected_openings.append({
                "kind": "window",
                "side": side,
                "local_x": round(local_x, 3),
                "local_y": round(local_y, 3),
                "width_m": round(max(0.6, min(6.0, span or 1.5)), 3),
                "height_m": round(max(0.8, min(3.0, height_w or 1.4)), 3),
                "yaw_deg": round(float(wr.get("yaw_deg", yaw_deg)), 3),
                "resource": str(wr.get("resource", "")),
            })

        entry_dims = [_resource_dimensions(str(r.get("resource", ""))) for r in entrance_group]
        entry_spans = [max(d.get("l", 0.0), d.get("w", 0.0)) for d in entry_dims]
        entry_heights = [d.get("h", 0.0) for d in entry_dims]
        entry_width = max(0.8, min(2.5, max(entry_spans, default=1.1)))
        entry_height = max(1.8, min(3.0, max(entry_heights, default=2.1)))

        score = min(42, len(nearby) * 1.8)
        score += min(30, len(entrance_group) * 12)
        score += 18 if not interiors else 5
        score -= min(18, len(interiors) * 3)
        if any(t in token_counts for t in ("building", "tower", "shop", "store", "apartment", "office", "factory")):
            score += 8
        negative = sum(1 for r in nearby if _has_token(str(r.get("text", "")).lower(), _EXTERIOR_NEGATIVE))
        score -= min(10, negative * 2)
        score = max(0, min(100, int(round(score))))

        confidence = "high" if score >= 80 else "medium" if score >= 60 else "low"
        candidate_id = f"auto_{idx:04d}_{re.sub(r'[^a-z0-9]+', '_', btype.lower()).strip('_') or 'mixed'}"
        candidates.append({
            "id": candidate_id,
            "confidence": confidence,
            "score": score,
            "type": btype,
            "district": district,
            "position": {"x": round(center_x, 3), "y": round(center_y, 3), "z": round(min_z, 3)},
            "yaw_deg": round(yaw_deg, 3),
            "width_m": round(width, 3),
            "depth_m": round(depth, 3),
            "height_m": round(height, 3),
            "floors": floors,
            "entry_side": entry_side,
            "entry_local_x": round(entry_local_x, 3),
            "entry_local_y": round(entry_local_y, 3),
            "entry_world": {"x": round(ex, 3), "y": round(ey, 3), "z": round(ez, 3)},
            "entry_facing_deg": round(entry_facing_deg, 3),
            "entry_yaw_deg": round(entry_facing_deg, 3),
            "entry_width_m": round(entry_width, 3),
            "entry_height_m": round(entry_height, 3),
            "detected_openings": detected_openings[:24],
            "exterior_bounds": {
                "width_m": round(width, 3),
                "depth_m": round(depth, 3),
                "z_min": round(min_z, 3),
                "z_max": round(max_z, 3),
            },
            "evidence": {
                "architecture_nodes": len(nearby),
                "entrance_nodes": len(entrance_group),
                "interior_nodes": len(interiors),
                "sectors": sorted({str(r.get("sector")) for r in group}),
                "source_files": sorted({str(r.get("source_file")) for r in group}),
                "token_counts": dict(sorted(token_counts.items())),
                "negative_exterior_signals": negative,
                "geometry_estimated_from": "node_position_plus_filename_lwh_hints_when_available",
            },
            "suggested_action": "fill" if confidence in {"high", "medium"} and not interiors else "review",
        })
    candidates.sort(key=lambda c: (-int(c["score"]), c["id"]))
    return {
        "format": FORMAT,
        "input_record_count": len(records),
        "architecture_record_count": len(exterior_architecture),
        "entrance_record_count": len(entrances),
        "cluster_radius_m": cluster_radius_m,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "notes": [
            "Entrances seed candidates; unrelated street architecture is excluded when it carries road/street/sidewalk/terrain signals.",
            "Footprints use runtime node positions and, when available, dimensions encoded in resource filenames; these remain estimates until mesh bounds are available.",
            "Existing interior evidence downgrades a candidate to review instead of treating the building as empty.",
        ],
    }



def candidates_to_buildings(report: dict[str, Any], *, min_score: int = 75, max_count: int | None = None, include_review: bool = False) -> dict[str, Any]:
    """Convert detector candidates into the exact building-anchor input consumed by NCIG."""
    candidates = []
    for candidate in report.get("candidates", []) or []:
        if not isinstance(candidate, dict):
            continue
        if int(candidate.get("score", 0)) < min_score:
            continue
        if not include_review and candidate.get("suggested_action") != "fill":
            continue
        candidates.append(candidate)
    candidates.sort(key=lambda c: (-int(c.get("score", 0)), str(c.get("id", ""))))
    if max_count is not None:
        candidates = candidates[: max(0, int(max_count))]
    buildings = []
    for candidate in candidates:
        evidence = candidate.get("evidence") or {}
        buildings.append({
            "id": str(candidate["id"]),
            "district": candidate.get("district", "auto_detected"),
            "type": candidate.get("type", "mixed"),
            "position": candidate.get("position", {"x": 0, "y": 0, "z": 0}),
            "yaw_deg": float(candidate.get("yaw_deg", 0.0)),
            "width_m": float(candidate.get("width_m", 10.0)),
            "depth_m": float(candidate.get("depth_m", 10.0)),
            "floors": max(1, int(candidate.get("floors", 1))),
            "entry_local_x": float(candidate.get("entry_local_x", 0.0)),
            "entry_local_y": float(candidate.get("entry_local_y", 0.0)),
            "entry_yaw_deg": float(candidate.get("entry_yaw_deg", candidate.get("yaw_deg", 0.0))),
            "entry_width_m": float(candidate.get("entry_width_m", 1.15)),
            "entry_height_m": float(candidate.get("entry_height_m", 2.10)),
            "detected_openings": candidate.get("detected_openings", []),
            "tags": [
                "auto_detected",
                "ncig_target",
                f"confidence_{candidate.get('confidence', 'unknown')}",
            ],
            "seed": int(hashlib.sha256(str(candidate["id"]).encode("utf-8")).hexdigest()[:8], 16),
            "detection": evidence,
        })
    return {
        "format": "ncig-building-targets-v1",
        "source_candidate_format": report.get("format"),
        "candidate_input_count": len(report.get("candidates", []) or []),
        "selected_count": len(buildings),
        "buildings": buildings,
    }
