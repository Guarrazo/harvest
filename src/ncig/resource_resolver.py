from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any

# Semantic aliases used by the procedural planner and common harvested names.
ALIASES: dict[str, tuple[str, ...]] = {
    "opening": ("opening", "door", "doorframe"),
    "door": ("door", "opening", "doorframe"),
    "floor": ("floor", "ground", "tile", "plank"),
    "ceiling": ("ceiling", "roof"),
    "wall": ("wall", "partition", "panel", "concrete"),
    "sofa": ("sofa", "couch", "seat"),
    "chair": ("chair", "stool", "seat"),
    "table": ("table", "desk"),
    "desk": ("desk", "workstation", "table"),
    "computer": ("computer", "pc", "terminal", "laptop"),
    "tv": ("tv", "television", "screen"),
    "screen": ("screen", "display", "tv"),
    "fridge": ("fridge", "refrigerator"),
    "sink": ("sink", "washbasin", "lavatory"),
    "toilet": ("toilet", "wc", "toilette"),
    "wardrobe": ("wardrobe", "closet", "cabinet"),
    "shelf": ("shelf", "shelving", "rack"),
    "counter": ("counter", "checkout"),
    "display": ("display", "showcase", "screen"),
    "light": ("light", "lamp", "fixture", "ceiling"),
    "bed": ("bed", "mattress"),
    "washer": ("washer", "washing_machine"),
    "crate": ("crate", "box", "container"),
    "workbench": ("workbench", "work_bench", "bench"),
    "tool_rack": ("tool_rack", "tool", "rack", "pegboard"),
    "server_rack": ("server_rack", "server", "rack"),
}

_NODE_ROLE_FALLBACKS = {
    "worldMeshNode": ("mesh",),
    "worldEntityNode": ("entity",),
}

_EXT_BY_ROLE = {
    "mesh": {".mesh"},
    "geometry": {".mesh"},
    "entity": {".ent"},
}


def _stem_tokens(text: str) -> set[str]:
    stem = Path(text.replace("\\", "/")).stem.lower()
    return {x for x in re.split(r"[^a-z0-9]+", stem) if x}


def infer_semantics(spec: dict[str, Any]) -> list[str]:
    data = spec.get("data") or {}
    primary_values = [
        data.get("materialRole"),
        data.get("resourceRole"),
        data.get("semantic"),
        spec.get("semantic"),
        spec.get("resourceRole"),
    ]
    primary: list[str] = []
    for value in primary_values:
        if not isinstance(value, str) or not value.strip():
            continue
        value = value.strip().lower()
        if value in ALIASES:
            primary.append(value)
        else:
            tokens = _stem_tokens(value)
            for alias in ALIASES:
                if alias in tokens:
                    primary.append(alias)
    if primary:
        # Explicit planner semantics are authoritative; do not let a generic logicalType
        # (for example wall_segment) override a materialRole such as opening.
        return list(dict.fromkeys(primary))

    secondary_values = [data.get("logicalType"), spec.get("name")]
    secondary: list[str] = []
    for value in secondary_values:
        if not isinstance(value, str) or not value.strip():
            continue
        tokens = _stem_tokens(value)
        for alias in ALIASES:
            if alias in tokens:
                secondary.append(alias)
    if secondary:
        return list(dict.fromkeys(secondary))
    return list(_NODE_ROLE_FALLBACKS.get(str(spec.get("type")), ()))


def _asset_items(assets: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not assets:
        return []
    resources = assets.get("resources")
    if isinstance(resources, dict):
        result: list[dict[str, Any]] = []
        for path, meta in resources.items():
            item = copy.deepcopy(meta) if isinstance(meta, dict) else {}
            item.setdefault("path", path)
            item.setdefault("roles", [])
            result.append(item)
        return result

    catalog = assets.get("catalog", assets)
    if isinstance(catalog, dict):
        result = []
        for role, paths in catalog.items():
            if not isinstance(paths, list):
                continue
            for path in paths:
                if isinstance(path, str):
                    result.append({"path": path, "roles": [role]})
        return result
    return []


def _role_match(candidate: dict[str, Any], semantic: str) -> int:
    roles = {str(x).lower() for x in candidate.get("roles", []) if isinstance(x, str)}
    aliases = set(ALIASES.get(semantic, (semantic,)))
    score = 0
    if semantic in roles:
        score += 100
    # An alias is strong evidence, but intentionally weaker than an exact role.
    score += 80 * len((roles & aliases) - {semantic})
    return score


def _path_match(path: str, semantic: str) -> int:
    tokens = _stem_tokens(path)
    aliases = set(ALIASES.get(semantic, (semantic,)))
    score = 12 if semantic in tokens else 0
    score += 2 * len((aliases - {semantic}) & tokens)
    return score


def _context_match(spec: dict[str, Any], path: str) -> int:
    """Prefer an asset whose filename agrees with the generated node name."""
    name_tokens = _stem_tokens(str(spec.get("name", "")))
    path_tokens = _stem_tokens(path)
    ignored = {"f", "r", "node", "segment", "opening", "prop", "floor", "ceiling"}
    return min(24, 6 * len((name_tokens - ignored) & path_tokens))


def resolve_resource(spec: dict[str, Any], assets: dict[str, Any] | None) -> dict[str, Any]:
    """Resolve the most plausible real resource without fabricating a path.

    Returns a structured decision so callers can audit why an asset was selected.
    """
    data = spec.get("data") or {}
    explicit = data.get("resource") or spec.get("resource")
    if isinstance(explicit, str) and explicit.strip():
        return {"resource": explicit, "status": "explicit", "score": 1000, "semantic": None, "candidates": []}

    semantics = infer_semantics(spec)
    # A bare node-type fallback (mesh/entity) is not enough information to bind a concrete
    # asset safely. Require an actual semantic such as floor/wall/door/chair/etc.
    if semantics and set(semantics).issubset({"mesh", "entity"}):
        return {
            "resource": None,
            "status": "unresolved",
            "score": 0,
            "semantic": semantics[0],
            "candidates": [],
            "reason": "no-semantic-intent",
        }
    items = _asset_items(assets)
    ext_allowed: set[str] = set()
    for role in _NODE_ROLE_FALLBACKS.get(str(spec.get("type")), ()):
        ext_allowed |= _EXT_BY_ROLE.get(role, set())
    ranked: list[dict[str, Any]] = []
    for item in items:
        path = item.get("path")
        if not isinstance(path, str) or not path:
            continue
        ext = Path(path).suffix.lower()
        if ext_allowed and ext not in ext_allowed:
            continue
        best_semantic = None
        best_role_score = 0
        best_path_score = 0
        best_base = -1
        best_index = 999
        for index, semantic in enumerate(semantics):
            rs = _role_match(item, semantic)
            ps = _path_match(path, semantic)
            base = rs + ps
            # Earlier signals (materialRole/resourceRole/semantic) outrank broad logical-type
            # hints such as `wall_segment`. This matters for door openings and similar nodes.
            priority_bonus = max(0, 120 - index * 20) if base > 0 else 0
            effective = base + priority_bonus
            if effective > best_base or (effective == best_base and index < best_index):
                best_semantic, best_role_score, best_path_score = semantic, rs, ps
                best_base, best_index = effective, index
        # Filename/context alone is not enough to bind an unrelated asset.
        if best_role_score + best_path_score <= 0:
            continue
        score = best_role_score + best_path_score + _context_match(spec, path)
        score += min(10, len(item.get("sources", [])) if isinstance(item.get("sources"), list) else 0)
        if score > 0:
            ranked.append({
                "resource": path,
                "score": score,
                "semantic": best_semantic,
                "roles": item.get("roles", []),
                "sources": item.get("sources", []),
            })
    ranked.sort(key=lambda x: (-x["score"], x["resource"]))
    if not ranked:
        return {
            "resource": None,
            "status": "unresolved",
            "score": 0,
            "semantic": semantics[0] if semantics else None,
            "candidates": [],
        }
    top = ranked[0]
    confidence = "high" if top["score"] >= 100 else "medium" if top["score"] >= 35 else "low"
    return {**top, "status": "resolved", "confidence": confidence, "candidates": ranked[:5]}


def bind_resources(plan: dict[str, Any], assets: dict[str, Any] | None, *, overwrite: bool = False) -> tuple[dict[str, Any], dict[str, Any]]:
    """Bind unassigned resource-bearing nodes to deterministic harvested assets."""
    out = copy.deepcopy(plan)
    report: dict[str, Any] = {
        "format": "ncig-resource-bind-v1",
        "overwrite": overwrite,
        "bound": [],
        "unresolved": [],
        "skipped": [],
    }
    for node in out.get("nodes", []) or []:
        if not isinstance(node, dict) or node.get("type") not in {"worldMeshNode", "worldEntityNode"}:
            continue
        data = node.setdefault("data", {})
        existing = data.get("resource") or node.get("resource")
        if existing and not overwrite:
            report["skipped"].append({"name": node.get("name"), "resource": existing, "reason": "already-assigned"})
            continue
        result = resolve_resource(node, assets)
        if result.get("resource"):
            data["resource"] = result["resource"]
            node["ncigResourceBinding"] = {
                "semantic": result.get("semantic"),
                "score": result.get("score", 0),
                "confidence": result.get("confidence", "unknown"),
                "candidates": result.get("candidates", [])[:3],
            }
            report["bound"].append({"name": node.get("name"), **result})
        else:
            report["unresolved"].append({"name": node.get("name"), "type": node.get("type"), **result})
    report["bound_count"] = len(report["bound"])
    report["unresolved_count"] = len(report["unresolved"])
    report["skipped_count"] = len(report["skipped"])
    return out, report
