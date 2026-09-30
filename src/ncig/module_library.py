from __future__ import annotations

import copy
import math
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

ROLE_TOKENS = {
    "bathroom": ("bath", "toilet", "shower", "wash", "lavatory", "sink"),
    "kitchen": ("kitchen", "fridge", "stove", "counter", "sink"),
    "bedroom": ("bedroom", "bed", "mattress", "wardrobe"),
    "office": ("office", "desk", "workstation", "computer", "corporate"),
    "shop": ("shop", "store", "counter", "display", "retail"),
    "workshop": ("workshop", "factory", "warehouse", "tool", "workbench"),
    "living": ("living", "lounge", "sofa", "couch", "tv"),
    "corridor": ("corridor", "hall", "hallway", "lobby"),
    "exterior": ("street", "exterior", "alley", "roof", "facade"),
}


def _node_type(node: dict[str, Any]) -> str:
    return str(node.get("type", "unknown"))


def _pos(node: dict[str, Any]) -> tuple[float, float, float]:
    p = node.get("position") or {"x": 0, "y": 0, "z": 0}
    return float(p.get("x", 0)), float(p.get("y", 0)), float(p.get("z", 0))


def _classify(text: str) -> list[str]:
    t = text.lower().replace("\\", "/")
    return sorted(role for role, tokens in ROLE_TOKENS.items() if any(tok in t for tok in tokens))


@dataclass(frozen=True)
class Module:
    id: str
    source_file: str
    roles: tuple[str, ...]
    node_types: tuple[str, ...]
    node_count: int
    min_xyz: tuple[float, float, float]
    max_xyz: tuple[float, float, float]
    nodes: tuple[dict[str, Any], ...]

    @property
    def width(self) -> float:
        return max(0.0, self.max_xyz[0] - self.min_xyz[0])

    @property
    def depth(self) -> float:
        return max(0.0, self.max_xyz[1] - self.min_xyz[1])

    @property
    def height(self) -> float:
        return max(0.0, self.max_xyz[2] - self.min_xyz[2])



def build_module_library(template_harvest: dict[str, Any]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for node_type, nodes in (template_harvest.get("templates") or {}).items():
        for node in nodes:
            src = str(node.get("ncigSourceFile", "unknown.json"))
            clone = copy.deepcopy(node)
            clone["type"] = str(node_type)
            grouped.setdefault(src, []).append(clone)

    modules: list[dict[str, Any]] = []
    for idx, (source, nodes) in enumerate(sorted(grouped.items()), start=1):
        points = [_pos(n) for n in nodes]
        mins = tuple(min(p[i] for p in points) for i in range(3))
        maxs = tuple(max(p[i] for p in points) for i in range(3))
        roles = set(_classify(source))
        for n in nodes:
            roles.update(_classify(str(n.get("name", ""))))
        if not roles:
            roles.add("generic")
        module = Module(
            id=f"module_{idx:04d}",
            source_file=source,
            roles=tuple(sorted(roles)),
            node_types=tuple(sorted({_node_type(n) for n in nodes})),
            node_count=len(nodes),
            min_xyz=mins,
            max_xyz=maxs,
            nodes=tuple(nodes),
        )
        modules.append(asdict(module))
        modules[-1]["width_m"] = module.width
        modules[-1]["depth_m"] = module.depth
        modules[-1]["height_m"] = module.height
    roles_index: dict[str, list[str]] = {}
    for m in modules:
        for role in m["roles"]:
            roles_index.setdefault(role, []).append(m["id"])
    for role in roles_index:
        roles_index[role].sort()
    return {
        "format": "ncig-module-library-v1",
        "module_count": len(modules),
        "role_index": roles_index,
        "modules": modules,
    }


def _score(module: dict[str, Any], room_kind: str, max_width: float, max_depth: float) -> float:
    roles = set(module.get("roles", []))
    score = 0.0
    if room_kind in roles:
        score += 100.0
    if room_kind == "residential" and roles & {"bedroom", "living", "kitchen", "bathroom"}:
        score += 25.0
    if room_kind == "commercial" and roles & {"shop", "office"}:
        score += 25.0
    if room_kind == "office" and "office" in roles:
        score += 40.0
    if room_kind == "industrial" and "workshop" in roles:
        score += 40.0
    if module.get("width_m", 999) <= max_width and module.get("depth_m", 999) <= max_depth:
        score += 10.0
    else:
        score -= 50.0
    score += min(10.0, float(module.get("node_count", 0)) * 0.25)
    return score


def choose_module(library: dict[str, Any], room_kind: str, max_width: float, max_depth: float) -> dict[str, Any] | None:
    modules = library.get("modules", [])
    if not modules:
        return None
    ranked = sorted(modules, key=lambda m: (-_score(m, room_kind, max_width, max_depth), m.get("id", "")))
    return copy.deepcopy(ranked[0])


def instantiate_module(module: dict[str, Any], *, anchor: tuple[float, float, float], yaw_deg: float = 0.0, prefix: str = "module") -> list[dict[str, Any]]:
    """Reposition a harvested module around an anchor without changing its resource payload."""
    nodes = copy.deepcopy(module.get("nodes") or [])
    if not nodes:
        return []
    min_xyz = module.get("min_xyz", (0, 0, 0))
    max_xyz = module.get("max_xyz", (0, 0, 0))
    cx = (float(min_xyz[0]) + float(max_xyz[0])) / 2.0
    cy = (float(min_xyz[1]) + float(max_xyz[1])) / 2.0
    rad = math.radians(float(yaw_deg))
    c, s = math.cos(rad), math.sin(rad)
    ax, ay, az = anchor
    out: list[dict[str, Any]] = []
    for idx, node in enumerate(nodes, start=1):
        x, y, z = _pos(node)
        lx, ly = x - cx, y - cy
        wx = ax + lx * c - ly * s
        wy = ay + lx * s + ly * c
        wz = az + (z - float(min_xyz[2]))
        node["position"] = {"x": wx, "y": wy, "z": wz, "w": 0}
        node["streamingRefPoint"] = {"x": wx, "y": wy, "z": wz, "w": 0}
        old_ref = str(node.get("nodeRef") or "")
        node["nodeRef"] = f"$/#{prefix}_{idx:03d}"
        if "name" in node:
            node["name"] = f"[NCIG MODULE] {prefix}_{idx:03d} {node['name']}"
        if isinstance(node.get("rotation"), dict) and yaw_deg:
            q = node["rotation"]
            ox, oy, oz, ow = (
                float(q.get("i", 0)), float(q.get("j", 0)),
                float(q.get("k", 0)), float(q.get("r", 1)),
            )
            h = rad / 2.0
            rz, rw = math.sin(h), math.cos(h)
            # Compose yaw * original quaternion. This preserves pitch/roll from harvested
            # modules instead of silently discarding them.
            node["rotation"] = {
                "i": rw * ox - rz * oy,
                "j": rw * oy + rz * ox,
                "k": rw * oz + rz * ow,
                "r": rw * ow - rz * oz,
            }
        node["ncigModuleSourceRef"] = old_ref
        out.append(node)
    return out


def library_report(library: dict[str, Any]) -> dict[str, Any]:
    modules = library.get("modules", [])
    return {
        "format": library.get("format", "ncig-module-library-v1"),
        "modules": len(modules),
        "roles": {role: len(ids) for role, ids in sorted((library.get("role_index") or {}).items())},
        "node_types": sorted({t for m in modules for t in m.get("node_types", [])}),
    }
