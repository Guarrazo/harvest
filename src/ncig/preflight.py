from __future__ import annotations

import copy
from collections import Counter
from typing import Any

RUNTIME_SENSITIVE = {
    "worldMeshNode": "template-required",
    "worldCollisionNode": "template-required",
    "worldStaticLightNode": "template-required",
    "worldStaticMarkerNode": "template-required",
    "worldInteriorAreaNode": "template-required",
    "worldAmbientAreaNode": "template-required",
    "worldTriggerAreaNode": "template-required",
    "worldAISpotNode": "template-required",
    "worldCompiledCommunityAreaNode_Streamable": "template-required",
}

EXT_REQUIRED = {
    "worldMeshNode": {".mesh"},
    "worldEntityNode": {".ent"},
}


def _template_counts(templates: dict[str, Any] | None) -> Counter[str]:
    raw = (templates or {}).get("counts")
    if isinstance(raw, dict):
        return Counter({str(k): int(v) for k, v in raw.items()})
    pools = (templates or {}).get("templates") or {}
    return Counter({str(k): len(v) for k, v in pools.items() if isinstance(v, list)})


def _resource_paths(assets: dict[str, Any] | None) -> list[str]:
    if not assets:
        return []
    resources = assets.get("resources")
    if isinstance(resources, dict):
        return [str(p) for p in resources]
    catalog = assets.get("catalog", assets)
    out: list[str] = []
    if isinstance(catalog, dict):
        for paths in catalog.values():
            if isinstance(paths, list):
                out.extend(str(x) for x in paths if isinstance(x, str))
    return sorted(set(out))


def _assigned_resource(node: dict[str, Any]) -> str | None:
    data = node.get("data") or {}
    value = data.get("resource") or node.get("resource")
    return str(value) if isinstance(value, str) and value.strip() else None


def _assets_extensions(paths: list[str]) -> Counter[str]:
    from pathlib import Path
    return Counter(Path(p.replace("\\", "/")).suffix.lower() for p in paths)


def build_preflight(plan: dict[str, Any], *, assets: dict[str, Any] | None = None, templates: dict[str, Any] | None = None, base_export: dict[str, Any] | None = None) -> dict[str, Any]:
    nodes = [n for n in plan.get("nodes", []) or [] if isinstance(n, dict)]
    node_types = Counter(str(n.get("type", "unknown")) for n in nodes)
    template_counts = _template_counts(templates)
    paths = _resource_paths(assets)
    extensions = _assets_extensions(paths)

    node_reports: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    for node in nodes:
        node_type = str(node.get("type", "unknown"))
        name = str(node.get("name", "?"))
        resource = _assigned_resource(node)
        template_count = int(template_counts.get(node_type, 0))
        required_exts = EXT_REQUIRED.get(node_type, set())

        status = "ready"
        reasons: list[str] = []
        if node_type in RUNTIME_SENSITIVE and template_count <= 0:
            status = "blocked"
            reasons.append(f"no harvested template for {node_type}")
        if node_type in required_exts and not resource:
            # A node can still become resolvable from the asset harvest. We call this a blocker
            # only when there is no candidate extension at all.
            if not any(ext in extensions for ext in required_exts):
                status = "blocked"
                reasons.append(f"no harvested resource with extension {sorted(required_exts)}")
            else:
                warnings.append({"name": name, "type": node_type, "message": "resource not explicitly assigned; bind-resources can resolve it from the harvest"})
        if node_type == "worldAreaShapeNode":
            data = node.get("data") or {}
            if not data.get("markers"):
                status = "blocked"
                reasons.append("area node has no data.markers")
        if status == "blocked":
            blockers.append({"name": name, "type": node_type, "reasons": reasons})

        node_reports.append({
            "name": name,
            "type": node_type,
            "status": status,
            "template_count": template_count,
            "resource": resource,
            "reasons": reasons,
        })

    base_types: list[str] = []
    if isinstance(base_export, dict):
        def walk(x: Any) -> None:
            if isinstance(x, dict):
                t = x.get("type")
                if isinstance(t, str):
                    base_types.append(t)
                for v in x.values():
                    walk(v)
            elif isinstance(x, list):
                for v in x:
                    walk(v)
        walk(base_export)

    return {
        "format": "ncig-preflight-v1",
        "ready": not blockers,
        "plan": {
            "building_id": plan.get("building_id") or (plan.get("building") or {}).get("id"),
            "node_count": len(nodes),
            "node_types": dict(sorted(node_types.items())),
        },
        "inputs": {
            "assets_present": bool(assets),
            "asset_resource_count": len(paths),
            "asset_extensions": dict(sorted(extensions.items())),
            "templates_present": bool(templates),
            "template_counts": dict(sorted(template_counts.items())),
            "base_export_present": bool(base_export),
            "base_export_node_types": dict(sorted(Counter(base_types).items())),
        },
        "summary": {
            "ready_nodes": sum(x["status"] == "ready" for x in node_reports),
            "blocked_nodes": sum(x["status"] == "blocked" for x in node_reports),
            "warnings": len(warnings),
        },
        "blockers": blockers,
        "warnings": warnings,
        "nodes": node_reports,
    }


def merge_harvests(*harvests: dict[str, Any]) -> dict[str, Any]:
    """Merge multiple ncig-harvest-v1 outputs deterministically."""
    resources: dict[str, dict[str, Any]] = {}
    node_types: Counter[str] = Counter()
    files_scanned = 0
    roots: list[str] = []
    source_files = Counter()
    for harvest in harvests:
        if not harvest:
            continue
        roots.append(str(harvest.get("root", "")))
        files_scanned += int(harvest.get("files_scanned", 0) or 0)
        for k, v in (harvest.get("source_files") or {}).items():
            source_files[k] += int(v or 0)
        node_types.update({str(k): int(v) for k, v in (harvest.get("node_type_mentions") or {}).items()})
        for path, raw_meta in (harvest.get("resources") or {}).items():
            meta = copy.deepcopy(raw_meta) if isinstance(raw_meta, dict) else {}
            item = resources.setdefault(str(path), {"path": str(path), "roles": [], "sources": [], "extensions": meta.get("extensions", [])})
            item["roles"] = sorted(set(item.get("roles", [])) | set(meta.get("roles", [])))
            item["sources"] = sorted(set(item.get("sources", [])) | set(meta.get("sources", [])))
            item["extensions"] = sorted(set(item.get("extensions", [])) | set(meta.get("extensions", [])))
    by_role: dict[str, list[str]] = {}
    for path, meta in resources.items():
        for role in meta.get("roles", []):
            by_role.setdefault(role, []).append(path)
    for role in by_role:
        by_role[role] = sorted(set(by_role[role]))
    return {
        "format": "ncig-harvest-v1",
        "roots": sorted(set(x for x in roots if x)),
        "files_scanned": files_scanned,
        "source_files": dict(sorted(source_files.items())),
        "resource_count": len(resources),
        "node_type_mentions": dict(sorted(node_types.items())),
        "resources": dict(sorted(resources.items())),
        "by_role": dict(sorted(by_role.items())),
    }
