from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

from .io import write_json


def _walk(obj: Any, path: str = "$"):
    yield path, obj
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk(v, f"{path}[{i}]")


def _looks_like_node(d: dict[str, Any]) -> bool:
    keys = {k.lower() for k in d}
    typeish = keys & {"type", "nodetype", "node_type", "worldnodetype", "variant"}
    posish = keys & {"position", "transform", "translation", "worldposition", "world_position"}
    return bool(typeish) and bool(posish)


def find_node_lists(data: Any) -> list[tuple[str, list[dict[str, Any]]]]:
    found: list[tuple[str, list[dict[str, Any]]]] = []
    for path, value in _walk(data):
        if isinstance(value, list) and value and all(isinstance(x, dict) for x in value):
            score = sum(_looks_like_node(x) for x in value)
            if score >= max(1, min(3, len(value))):
                found.append((path, value))
    return found


def _get_ci(d: dict[str, Any], names: tuple[str, ...]):
    lower = {k.lower(): k for k in d}
    for name in names:
        if name.lower() in lower:
            return lower[name.lower()], d[lower[name.lower()]]
    return None, None


def _set_ci(d: dict[str, Any], names: tuple[str, ...], value: Any) -> bool:
    key, _ = _get_ci(d, names)
    if key is None:
        return False
    d[key] = value
    return True


def _set_path_if_present(d: dict[str, Any], path: tuple[str, ...], value: Any) -> bool:
    cur: Any = d
    for part in path[:-1]:
        if not isinstance(cur, dict):
            return False
        key, nxt = _get_ci(cur, (part,))
        if key is None:
            return False
        cur = nxt
    if not isinstance(cur, dict):
        return False
    return _set_ci(cur, (path[-1],), value)


def _position_from_node(n: dict[str, Any]) -> dict[str, float] | None:
    for key in ("position", "worldPosition", "world_position", "translation"):
        _, value = _get_ci(n, (key,))
        if isinstance(value, dict) and all(x in value for x in ("x", "y", "z")):
            return {"x": float(value["x"]), "y": float(value["y"]), "z": float(value["z"])}
    _, transform = _get_ci(n, ("transform",))
    if isinstance(transform, dict):
        return _position_from_node(transform)
    return None


def _node_type(n: dict[str, Any]) -> str:
    for key in ("type", "nodeType", "node_type", "worldNodeType", "variant"):
        _, value = _get_ci(n, (key,))
        if isinstance(value, str):
            return value
    return "unknown"


def _replace_known_fields(node: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(node)
    name = str(spec["name"])
    node_ref = str(spec["nodeRef"])
    pos = spec["position"]
    rot = spec.get("rotation")
    scale = spec.get("scale")

    _set_ci(out, ("name", "debugName", "displayName", "id"), name)
    _set_ci(out, ("nodeRef", "node_ref", "ref"), node_ref)
    if not _set_ci(out, ("position", "worldPosition", "world_position", "translation"), pos):
        _set_path_if_present(out, ("transform", "position"), pos)
    if rot is not None:
        if not _set_ci(out, ("rotation", "orientation", "quaternion"), rot):
            _set_path_if_present(out, ("transform", "rotation"), rot)
    if scale is not None:
        if not _set_ci(out, ("scale",), scale):
            _set_path_if_present(out, ("transform", "scale"), scale)
    for src, aliases in (("primaryRange", ("primaryRange", "streamingDistance", "streaming_distance")),
                         ("secondaryRange", ("secondaryRange", "streamingDistance2", "secondary_distance"))):
        if src in spec:
            _set_ci(out, aliases, spec[src])
    data = spec.get("data") or {}
    resource = data.get("resource")
    if resource:
        _set_ci(out, ("resource", "depotPath", "depot_path", "mesh", "entity"), resource)
        _set_path_if_present(out, ("data", "resource"), resource)
    return out


def fingerprint_export(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    lists = find_node_lists(data)
    node_types: dict[str, int] = {}
    samples: list[dict[str, Any]] = []
    for p, items in lists:
        for n in items[:20]:
            t = _node_type(n)
            node_types[t] = node_types.get(t, 0) + 1
            if len(samples) < 12:
                samples.append({"path": p, "type": t, "keys": sorted(n.keys()), "position": _position_from_node(n)})
    return {"format": "ncig-object-spawner-fingerprint-v1", "source": str(Path(path)), "node_lists": [p for p, _ in lists], "node_types": node_types, "samples": samples}


def _load_at_path(root: Any, path: str) -> Any:
    if path == "$":
        return root
    cur = root
    tokens = re.findall(r"\.([^\.\[]+)|\[(\d+)\]", path[1:])
    for key, idx in tokens:
        cur = cur[key] if key else cur[int(idx)]
    return cur


def build_template_export(plan: dict[str, Any], template_path: str | Path) -> dict[str, Any]:
    template = json.loads(Path(template_path).read_text(encoding="utf-8"))
    lists = find_node_lists(template)
    if not lists:
        raise ValueError("Could not find a node list in the Object Spawner export template")
    node_path, template_nodes = max(lists, key=lambda x: len(x[1]))
    by_type: dict[str, dict[str, Any]] = {}
    for n in template_nodes:
        by_type.setdefault(_node_type(n), n)
    generated = []
    warnings = []
    for spec in plan.get("nodes", []):
        wanted = spec.get("type", "unknown")
        base = by_type.get(wanted)
        if base is None:
            # World Builder export variants may use a different discriminator; use a generic template only as a last resort.
            base = next(iter(by_type.values()), None)
            warnings.append(f"No template node for {wanted}; used {_node_type(base) if base else 'none'}")
        if base is None:
            continue
        generated.append(_replace_known_fields(base, spec))
    result = copy.deepcopy(template)
    target = _load_at_path(result, node_path)
    target[:] = generated
    meta = result.setdefault("ncig", {}) if isinstance(result, dict) else {}
    if isinstance(meta, dict):
        meta.update({"generator": "NCIG", "format": "ncig-object-spawner-export-v1", "template_node_path": node_path, "warnings": warnings})
    return result


def write_template_bridge(plan_path: str | Path, template_path: str | Path, out_path: str | Path) -> dict[str, Any]:
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    result = build_template_export(plan, template_path)
    write_json(out_path, result)
    return {"written": str(out_path), "warnings": len(result.get("ncig", {}).get("warnings", [])), "format": "ncig-object-spawner-export-v1"}
