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


def _is_architecture(record: dict[str, Any]) -> bool:
    resource = str(record.get("resource", "")).lower()
    text = str(record.get("text", "")).lower()
    return "\\environment\\architecture\\" in resource or _has_token(text, _BUILDING_TOKENS)


def _is_entrance(record: dict[str, Any]) -> bool:
    text = str(record.get("text", "")).lower()
    return _has_token(text, _ENTRANCE_TOKENS)


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
    seeds = list(records)
    clusters: list[list[dict[str, Any]]] = []
    while seeds:
        seed = seeds.pop()
        cluster = [seed]
        changed = True
        while changed:
            changed = False
            keep: list[dict[str, Any]] = []
            for candidate in seeds:
                if any(_distance(candidate, member) <= radius_m for member in cluster):
                    cluster.append(candidate)
                    changed = True
                else:
                    keep.append(candidate)
            seeds = keep
        clusters.append(cluster)
    return clusters


def detect_building_candidates(records: list[dict[str, Any]], *, cluster_radius_m: float = 22.0) -> dict[str, Any]:
    """Find likely exterior buildings with entrances and little/no interior evidence.

    Entrances are the seeds: architecture is attached to nearby entrances instead of
    clustering every architecture node globally. This avoids one long facade or street
    dressing chain swallowing multiple neighbouring buildings into one candidate.
    """
    architecture = [r for r in records if _is_architecture(r)]
    entrances = [r for r in records if _is_entrance(r)]

    # Group entrances first. Two doors within a few metres are normally one storefront/building.
    entrance_groups = _clusters(entrances, min(10.0, cluster_radius_m * 0.5))
    candidates: list[dict[str, Any]] = []

    for idx, entrance_group in enumerate(entrance_groups, start=1):
        ex = sum(r["x"] for r in entrance_group) / len(entrance_group)
        ey = sum(r["y"] for r in entrance_group) / len(entrance_group)
        ez = sum(r["z"] for r in entrance_group) / len(entrance_group)
        nearby = [
            r for r in architecture
            if math.dist((r["x"], r["y"], r["z"]), (ex, ey, ez)) <= cluster_radius_m
        ]
        if len(nearby) < 3:
            continue
        group = nearby + entrance_group
        interiors = [r for r in group if _is_interior(r)]
        building_text = " ".join(str(r.get("text", "")) for r in group)
        btype = _building_type(building_text)
        xs = [r["x"] for r in group]
        ys = [r["y"] for r in group]
        zs = [r["z"] for r in group]
        min_z, max_z = min(zs), max(zs)

        # Estimate the building's principal horizontal axis with a 2x2 covariance/PCA.
        # This gives NCIG a usable yaw instead of assuming north/east alignment.
        cx = sum(xs) / len(xs)
        cy = sum(ys) / len(ys)
        cxx = sum((x - cx) ** 2 for x in xs) / max(1, len(xs))
        cyy = sum((y - cy) ** 2 for y in ys) / max(1, len(ys))
        cxy = sum((x - cx) * (y - cy) for x, y in zip(xs, ys)) / max(1, len(xs))
        if abs(cxy) < 1e-9 and cxx >= cyy:
            theta = 0.0
        elif abs(cxy) < 1e-9:
            theta = math.pi / 2.0
        else:
            theta = 0.5 * math.atan2(2.0 * cxy, cxx - cyy)
        ct, st = math.cos(theta), math.sin(theta)
        local_points = [((r["x"] - cx) * ct + (r["y"] - cy) * st,
                         -(r["x"] - cx) * st + (r["y"] - cy) * ct) for r in group]
        us = [p[0] for p in local_points]
        vs = [p[1] for p in local_points]
        min_u, max_u = min(us), max(us)
        min_v, max_v = min(vs), max(vs)
        width = max(4.0, (max_u - min_u) + 3.0)
        depth = max(4.0, (max_v - min_v) + 3.0)
        height = max(3.2, (max_z - min_z) + 3.0)
        floors = max(1, int(round(height / 3.2)))
        center_u = (min_u + max_u) / 2.0
        center_v = (min_v + max_v) / 2.0
        center_x = cx + center_u * ct - center_v * st
        center_y = cy + center_u * st + center_v * ct

        # Preserve the detected entrance in building-local coordinates so the generated
        # interior can later align its lobby/door instead of assuming a centered entry.
        entry_local_x = (ex - center_x) * ct + (ey - center_y) * st
        entry_local_y = -(ex - center_x) * st + (ey - center_y) * ct
        half_w = max(0.5, width * 0.5)
        half_d = max(0.5, depth * 0.5)
        # Clamp only to the inferred footprint margin; the raw entrance remains in evidence.
        entry_local_x = max(-half_w, min(half_w, entry_local_x))
        entry_local_y = max(-half_d, min(half_d, entry_local_y))

        token_counts = Counter()
        for r in group:
            token_text = str(r.get("text", "")).lower()
            for token in _BUILDING_TOKENS + _ENTRANCE_TOKENS:
                if token in token_text:
                    token_counts[token] += 1

        score = min(50, len(nearby) * 2)
        score += min(30, len(entrance_group) * 10)
        if not interiors:
            score += 20
        else:
            score -= min(20, len(interiors) * 3)
        if any(t in token_counts for t in ("building", "tower", "shop", "store", "apartment", "office", "factory")):
            score += 10
        negative = sum(1 for r in nearby if _has_token(str(r.get("text", "")).lower(), _EXTERIOR_NEGATIVE))
        score -= min(15, negative * 2)

        confidence = "high" if score >= 75 else "medium" if score >= 50 else "low"
        candidate_id = f"auto_{idx:04d}_{re.sub(r'[^a-z0-9]+', '_', btype.lower()).strip('_') or 'mixed'}"
        candidates.append({
            "id": candidate_id,
            "confidence": confidence,
            "score": score,
            "type": btype,
            "position": {"x": round(center_x, 3), "y": round(center_y, 3), "z": round(min_z, 3)},
            "yaw_deg": round(math.degrees(theta), 3),
            "width_m": round(width, 3),
            "depth_m": round(depth, 3),
            "height_m": round(height, 3),
            "floors": floors,
            "entry_local_x": round(entry_local_x, 3),
            "entry_local_y": round(entry_local_y, 3),
            "entry_world": {"x": round(ex, 3), "y": round(ey, 3), "z": round(ez, 3)},
            "entry_yaw_deg": round(math.degrees(theta), 3),
            "evidence": {
                "architecture_nodes": len(nearby),
                "entrance_nodes": len(entrance_group),
                "interior_nodes": len(interiors),
                "sectors": sorted({str(r.get("sector")) for r in group}),
                "token_counts": dict(sorted(token_counts.items())),
                "negative_exterior_signals": negative,
            },
            "suggested_action": "fill" if confidence in {"high", "medium"} else "review",
        })
    candidates.sort(key=lambda c: (-int(c["score"]), c["id"]))
    return {
        "format": FORMAT,
        "input_record_count": len(records),
        "architecture_record_count": len(architecture),
        "entrance_record_count": len(entrances),
        "cluster_radius_m": cluster_radius_m,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "notes": [
            "Detection is evidence-based and conservative; it does not claim that every candidate is a facade with a missing interior.",
            "Entrances seed candidates so neighbouring facade dressing does not automatically merge unrelated buildings.",
            "A candidate should be built only after its exterior footprint and existing interior evidence are inspected.",
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
            "district": "auto_detected",
            "type": candidate.get("type", "mixed"),
            "position": candidate.get("position", {"x": 0, "y": 0, "z": 0}),
            "yaw_deg": float(candidate.get("yaw_deg", 0.0)),
            "width_m": float(candidate.get("width_m", 10.0)),
            "depth_m": float(candidate.get("depth_m", 10.0)),
            "floors": max(1, int(candidate.get("floors", 1))),
            "entry_local_x": float(candidate.get("entry_local_x", 0.0)),
            "entry_local_y": float(candidate.get("entry_local_y", 0.0)),
            "entry_yaw_deg": float(candidate.get("entry_yaw_deg", candidate.get("yaw_deg", 0.0))),
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
