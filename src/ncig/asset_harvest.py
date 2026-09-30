from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

RESOURCE_RE = re.compile(r"(?i)(?:^|[^a-z0-9_])((?:base|mods|r6|ep1|archive|dlc|tweaks|resources)[\\/][^\"'\s\r\n]+?\.(?:ent|mesh|app|mi|mat|xbm|streamingsector|streamingblock))(?:$|[^a-z0-9_])")
JSON_RESOURCE_KEYS = {
    "DepotPath", "spawnData", "resource", "mesh", "entity", "entityTemplate", "meshAppearance",
    "appearanceName", "modulePath", "assetPath", "path", "prefabRef",
}
NODE_TYPES = {
    "worldEntityNode", "worldMeshNode", "worldStaticLightNode", "worldCollisionNode",
    "worldStaticMarkerNode", "worldAreaShapeNode", "worldTriggerAreaNode",
    "worldInteriorAreaNode", "worldAmbientAreaNode", "worldAISpotNode",
    "worldCompiledCommunityAreaNode_Streamable",
}


def _walk(obj: Any) -> Iterable[Any]:
    yield obj
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v)


def _normalize_path(value: str) -> str:
    return value.replace("/", "\\")


def _resource_from_value(value: Any) -> str | None:
    if isinstance(value, str):
        text = value
    elif isinstance(value, dict):
        if "$value" in value and isinstance(value["$value"], str):
            text = value["$value"]
        else:
            return None
    else:
        return None
    if re.search(r"\.(ent|mesh|app|mi|mat|xbm|streamingsector|streamingblock)$", text, re.I):
        return _normalize_path(text)
    return None


def extract_resources_from_obj(obj: Any) -> set[str]:
    found: set[str] = set()
    for item in _walk(obj):
        if isinstance(item, dict):
            for key, value in item.items():
                if key in JSON_RESOURCE_KEYS:
                    r = _resource_from_value(value)
                    if r:
                        found.add(r)
                    if isinstance(value, dict) and key in {"entityTemplate", "mesh"}:
                        for sub in _walk(value):
                            r = _resource_from_value(sub)
                            if r:
                                found.add(r)
        elif isinstance(item, str):
            r = _resource_from_value(item)
            if r:
                found.add(r)
    return found


def classify_resource(path: str) -> set[str]:
    p = path.lower()
    name = Path(path).stem.lower()
    roles: set[str] = set()
    patterns = {
        "mesh": [".mesh"],
        "entity": [".ent"],
        "light": ["light", "lamp", "fixture"],
        "door": ["door", "doorframe", "door_frame"],
        "floor": ["floor", "ground", "tile", "plank"],
        "wall": ["wall", "partition", "panel", "concrete"],
        "ceiling": ["ceiling", "roof", "panel"],
        "bed": ["bed", "mattress"],
        "chair": ["chair", "stool", "seat"],
        "sofa": ["sofa", "couch"],
        "table": ["table", "desk"],
        "computer": ["computer", "pc", "terminal", "laptop"],
        "tv": ["tv", "screen", "television"],
        "kitchen": ["kitchen", "fridge", "sink", "counter"],
        "bathroom": ["bathroom", "toilet", "shower", "sink"],
        "industrial": ["factory", "industrial", "workshop", "warehouse"],
        "office": ["office", "corporate", "workstation"],
    }
    for role, tokens in patterns.items():
        if any(token in name or token in p for token in tokens):
            roles.add(role)
    if ".mesh" in p:
        roles.add("geometry")
    return roles


def harvest(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    if not root.exists():
        raise FileNotFoundError(root)
    resources: dict[str, dict[str, Any]] = {}
    files_scanned = 0
    source_files = {"json": 0, "text": 0, "lua": 0, "other": 0}
    node_types: dict[str, int] = {}

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        files_scanned += 1
        suffix = path.suffix.lower()
        try:
            raw = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        found: set[str] = set()
        if suffix == ".json":
            source_files["json"] += 1
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                obj = None
            if obj is not None:
                found |= extract_resources_from_obj(obj)
                for item in _walk(obj):
                    if isinstance(item, dict) and isinstance(item.get("type"), str) and item["type"] in NODE_TYPES:
                        node_types[item["type"]] = node_types.get(item["type"], 0) + 1
        elif suffix in {".lua", ".reds", ".txt", ".yaml", ".yml"}:
            source_files["lua" if suffix == ".lua" else "text"] += 1
            found |= {m.group(1) for m in RESOURCE_RE.finditer(raw)}
            for m in re.finditer(r'(?i)world[A-Za-z0-9_]+Node', raw):
                t = m.group(0)
                if t in NODE_TYPES:
                    node_types[t] = node_types.get(t, 0) + 1
        else:
            source_files["other"] += 1
        rel = str(path.relative_to(root)).replace("\\", "/")
        for resource in sorted(found):
            item = resources.setdefault(resource, {"path": resource, "roles": [], "sources": [], "extensions": [Path(resource).suffix.lower()]})
            item["sources"].append(rel)
            item["roles"] = sorted(set(item["roles"]) | classify_resource(resource))

    by_role: dict[str, list[str]] = {}
    for r, meta in resources.items():
        for role in meta["roles"]:
            by_role.setdefault(role, []).append(r)
    for role in by_role:
        by_role[role] = sorted(set(by_role[role]))
    return {
        "format": "ncig-harvest-v1",
        "root": str(root.resolve()),
        "files_scanned": files_scanned,
        "source_files": source_files,
        "resource_count": len(resources),
        "node_type_mentions": node_types,
        "resources": dict(sorted(resources.items())),
        "by_role": by_role,
    }


def template_nodes_from_json(obj: Any) -> dict[str, list[dict[str, Any]]]:
    """Collect real exported node payloads from arbitrary WB/favorite JSON."""
    result: dict[str, list[dict[str, Any]]] = {}
    for item in _walk(obj):
        if isinstance(item, dict):
            node_type = item.get("type")
            if isinstance(node_type, str) and node_type in NODE_TYPES and "position" in item:
                result.setdefault(node_type, []).append(item)
    return result


def harvest_templates(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    templates: dict[str, list[dict[str, Any]]] = {}
    files: list[str] = []
    for path in root.rglob("*.json"):
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        found = template_nodes_from_json(obj)
        if found:
            rel = str(path.relative_to(root)).replace("\\", "/")
            files.append(rel)
            for node_type, nodes in found.items():
                for node in nodes:
                    clone = json.loads(json.dumps(node))
                    clone.setdefault("ncigSourceFile", rel)
                    templates.setdefault(node_type, []).append(clone)
    return {
        "format": "ncig-template-harvest-v1",
        "root": str(root.resolve()),
        "source_files": sorted(files),
        "counts": {k: len(v) for k, v in sorted(templates.items())},
        "templates": templates,
    }
