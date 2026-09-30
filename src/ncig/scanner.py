from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable

from .model import BuildingAnchor, Vec3


@dataclass(frozen=True)
class NodeObservation:
    name: str
    node_type: str
    node_instance: str
    sector_path: str
    position: Vec3
    yaw_deg: float = 0.0
    node_ref: str = ""
    tags: tuple[str, ...] = ()


def _first(raw: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = raw.get(key)
        if value is not None:
            return value
    return default


def _vec3(value: Any) -> Vec3 | None:
    if value is None:
        return None
    if isinstance(value, dict):
        x = _first(value, "x", "X", "XCoord", default=None)
        y = _first(value, "y", "Y", "YCoord", default=None)
        z = _first(value, "z", "Z", "ZCoord", default=None)
        if x is not None and y is not None and z is not None:
            try:
                return Vec3(float(x), float(y), float(z))
            except (TypeError, ValueError):
                return None
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        try:
            return Vec3(float(value[0]), float(value[1]), float(value[2]))
        except (TypeError, ValueError):
            return None
    return None


def parse_observation(raw: dict[str, Any]) -> NodeObservation | None:
    pos = _vec3(_first(raw, "position", "worldPosition", "nodePosition", "Position"))
    if pos is None:
        return None
    name = str(_first(raw, "name", "nodeName", "Name", default="unnamed"))
    node_type = str(_first(raw, "nodeType", "type", "NodeType", default=""))
    node_instance = str(_first(raw, "nodeInstance", "instance", "NodeInstance", default=""))
    sector_path = str(_first(raw, "sectorPath", "sector", "SectorPath", default=""))
    node_ref = str(_first(raw, "nodeRef", "NodeRef", "questPrefabNodeRef", default=""))
    yaw = _first(raw, "yaw_deg", "yaw", "Yaw", default=0.0)
    try:
        yaw = float(yaw)
    except (TypeError, ValueError):
        yaw = 0.0
    tags = tuple(str(t) for t in _first(raw, "tags", "Tags", default=[]))
    return NodeObservation(name, node_type, node_instance, sector_path, pos, yaw, node_ref, tags)


def load_observations(path: str | Path) -> list[NodeObservation]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        items = raw.get("observations", raw.get("nodes", raw.get("items", [])))
    else:
        items = raw
    observations = []
    for item in items:
        if isinstance(item, dict):
            obs = parse_observation(item)
            if obs is not None:
                observations.append(obs)
    return observations


def _looks_like_door(obs: NodeObservation) -> bool:
    hay = " ".join([obs.name, obs.node_type, obs.node_instance, *obs.tags]).lower()
    return any(token in hay for token in ("door", "gate", "entry", "entrance", "shutter"))


def find_entry_nodes(observations: Iterable[NodeObservation]) -> list[NodeObservation]:
    return [obs for obs in observations if _looks_like_door(obs)]


def _building_type(haystack: str) -> str:
    h = haystack.lower()
    if any(k in h for k in ("factory", "warehouse", "industrial", "workshop", "manufactur")):
        return "industrial"
    if any(k in h for k in ("office", "corporate", "corp", "bureau")):
        return "office"
    if any(k in h for k in ("shop", "store", "market", "restaurant", "bar", "clinic")):
        return "commercial"
    return "residential"


def infer_anchor_from_entry(
    entry: NodeObservation,
    *,
    default_width_m: float = 10.0,
    default_depth_m: float = 10.0,
    default_floors: int = 1,
    district: str = "unknown",
) -> BuildingAnchor:
    hay = " ".join([entry.name, entry.node_type, entry.node_instance, *entry.tags])
    safe_id = re.sub(r"[^a-zA-Z0-9_]+", "_", entry.name).strip("_").lower() or "entry"
    return BuildingAnchor(
        id=f"scan_{safe_id}",
        district=district,
        type=_building_type(hay),
        position=entry.position,
        yaw_deg=entry.yaw_deg,
        width_m=default_width_m,
        depth_m=default_depth_m,
        floors=default_floors,
        tags=("scanned", "heuristic", *entry.tags),
    )


def proximity_groups(observations: Iterable[NodeObservation], radius_m: float = 12.0) -> list[list[NodeObservation]]:
    remaining = list(observations)
    groups: list[list[NodeObservation]] = []
    while remaining:
        seed = remaining.pop(0)
        group = [seed]
        changed = True
        while changed:
            changed = False
            keep: list[NodeObservation] = []
            for candidate in remaining:
                near = any(
                    math.dist(
                        (candidate.position.x, candidate.position.y, candidate.position.z),
                        (other.position.x, other.position.y, other.position.z),
                    ) <= radius_m
                    for other in group
                )
                if near:
                    group.append(candidate)
                    changed = True
                else:
                    keep.append(candidate)
            remaining = keep
        groups.append(group)
    return groups


def _is_interior_observation(obs: NodeObservation) -> bool:
    hay = " ".join([obs.node_type, obs.sector_path, obs.name, obs.node_instance]).lower()
    return "interior" in hay or "indoors" in hay


def build_scan_report(observations: list[NodeObservation]) -> dict[str, Any]:
    entries = find_entry_nodes(observations)
    groups = proximity_groups(entries)

    annotated_entries = []
    for entry in entries:
        nearby_interior = [
            obs for obs in observations
            if obs is not entry
            and _is_interior_observation(obs)
            and math.dist((entry.position.x, entry.position.y, entry.position.z),
                          (obs.position.x, obs.position.y, obs.position.z)) <= 35.0
        ]
        record = asdict(entry)
        record["likely_existing_interior"] = bool(nearby_interior)
        record["nearby_interior_evidence"] = [obs.sector_path for obs in nearby_interior[:5]]
        annotated_entries.append(record)
    return {
        "format": "ncig-scan-report-v1",
        "observations": len(observations),
        "candidate_entries": len(entries),
        "entry_groups": len(groups),
        "entries": annotated_entries,
        "groups": [[x.name for x in group] for group in groups],
    }
