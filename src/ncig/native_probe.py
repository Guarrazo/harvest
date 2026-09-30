from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from .asset_harvest import template_nodes_from_json
from .object_spawner import all_template_nodes, is_wb_export, node_type


def _resource_path(value: Any) -> str | None:
    if isinstance(value, str) and value.lower().endswith((".mesh", ".ent")):
        return value.replace("/", "\\")
    if isinstance(value, dict) and isinstance(value.get("$value"), str):
        return _resource_path(value["$value"])
    return None


def _node_resource(node: dict[str, Any]) -> str | None:
    data = node.get("data")
    if not isinstance(data, dict):
        return None
    mesh = data.get("mesh")
    if isinstance(mesh, dict):
        depot = mesh.get("DepotPath")
        path = _resource_path(depot)
        if path:
            return path
    entity = data.get("entityTemplate")
    if isinstance(entity, dict):
        path = _resource_path(entity.get("DepotPath"))
        if path:
            return path
    return _resource_path(data.get("resource"))


def _fingerprint_node(node: dict[str, Any]) -> dict[str, Any]:
    data = node.get("data") if isinstance(node.get("data"), dict) else {}
    return {
        "type": node_type(node),
        "top_level_keys": sorted(str(k) for k in node.keys()),
        "data_keys": sorted(str(k) for k in data.keys()),
        "resource": _node_resource(node),
        "has_transform": all(k in node for k in ("position", "rotation", "scale")),
        "has_streaming_ref_point": "streamingRefPoint" in node,
        "has_node_ref": "nodeRef" in node,
    }


def summarize_native_probe(data: dict[str, Any], *, source: str = "") -> dict[str, Any]:
    if not is_wb_export(data):
        raise ValueError("Input does not match the observed World Builder/Object Spawner envelope")
    nodes = all_template_nodes(data)
    counts: dict[str, int] = {}
    templates: dict[str, list[dict[str, Any]]] = {}
    for node in nodes:
        typ = node_type(node)
        counts[typ] = counts.get(typ, 0) + 1
        templates.setdefault(typ, []).append(copy.deepcopy(node))
    samples = [_fingerprint_node(node) for node in nodes[:25]]
    return {
        "format": "ncig-native-probe-v1",
        "source": source,
        "envelope": {
            "xlFormat": data.get("xlFormat"),
            "version": data.get("version"),
            "name": data.get("name"),
            "sector_count": len(data.get("sectors", []) or []),
        },
        "node_type_counts": dict(sorted(counts.items())),
        "node_count": len(nodes),
        "samples": samples,
        "templates": templates,
        "note": "This report preserves real exported node payloads; NCIG does not synthesize missing native fields.",
    }


def build_template_harvest_from_export(data: dict[str, Any], *, source: str = "") -> dict[str, Any]:
    if not is_wb_export(data):
        raise ValueError("Input does not match the observed World Builder/Object Spawner envelope")
    found = template_nodes_from_json(data)
    templates: dict[str, list[dict[str, Any]]] = {}
    for typ, nodes in sorted(found.items()):
        for node in nodes:
            clone = copy.deepcopy(node)
            if source:
                clone.setdefault("ncigSourceFile", source)
            templates.setdefault(typ, []).append(clone)
    return {
        "format": "ncig-template-harvest-v1",
        "root": str(Path(source).parent.resolve()) if source else "",
        "source_files": [source] if source else [],
        "counts": {k: len(v) for k, v in sorted(templates.items())},
        "templates": templates,
    }


def merge_template_harvests(*harvests: dict[str, Any]) -> dict[str, Any]:
    """Merge ncig-template-harvest-v1 files without fabricating node payloads.

    Nodes are deduplicated by their JSON payload with the source marker removed.
    The first occurrence wins, preserving real exporter payloads verbatim.
    """
    merged: dict[str, list[dict[str, Any]]] = {}
    seen: dict[str, set[str]] = {}
    source_files: set[str] = set()
    roots: list[str] = []
    for harvest in harvests:
        if not isinstance(harvest, dict):
            continue
        if harvest.get("root"):
            roots.append(str(harvest["root"]))
        for src in harvest.get("source_files", []) or []:
            if isinstance(src, str):
                source_files.add(src)
        for typ, nodes in (harvest.get("templates") or {}).items():
            if not isinstance(nodes, list):
                continue
            merged.setdefault(str(typ), [])
            seen.setdefault(str(typ), set())
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                clone = json.loads(json.dumps(node))
                clone.pop("ncigSourceFile", None)
                key = json.dumps(clone, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
                if key in seen[str(typ)]:
                    continue
                seen[str(typ)].add(key)
                if node.get("ncigSourceFile"):
                    clone["ncigSourceFile"] = node["ncigSourceFile"]
                merged[str(typ)].append(clone)
    return {
        "format": "ncig-template-harvest-v1",
        "root": roots[0] if roots else "",
        "source_files": sorted(source_files),
        "counts": {k: len(v) for k, v in sorted(merged.items())},
        "templates": {k: merged[k] for k in sorted(merged)},
    }


def write_native_probe(input_path: str | Path, out_path: str | Path, templates_out: str | Path | None = None, base_templates: str | Path | None = None) -> dict[str, Any]:
    path = Path(input_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    report = summarize_native_probe(data, source=str(path))
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if templates_out:
        template_data = build_template_harvest_from_export(data, source=str(path.name).replace("\\", "/"))
        if base_templates:
            base_path = Path(base_templates)
            base_data = json.loads(base_path.read_text(encoding="utf-8"))
            template_data = merge_template_harvests(base_data, template_data)
        tp = Path(templates_out)
        tp.parent.mkdir(parents=True, exist_ok=True)
        tp.write_text(json.dumps(template_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report
