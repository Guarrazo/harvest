from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Iterable

from .asset_harvest import NODE_TYPES, template_nodes_from_json
from .native_probe import merge_template_harvests
from .reference_nodes import mesh_node


def _valid_template(node: dict[str, Any], node_type: str) -> bool:
    if node.get("type") != node_type:
        return False
    required = ("position", "rotation", "scale", "streamingRefPoint", "data")
    if any(k not in node for k in required):
        return False
    data = node.get("data")
    if not isinstance(data, dict):
        return False
    if node_type == "worldMeshNode":
        mesh = data.get("mesh")
        depot = mesh.get("DepotPath") if isinstance(mesh, dict) else None
        return isinstance(depot, dict) and isinstance(depot.get("$value"), str) and depot["$value"].lower().endswith(".mesh")
    if node_type == "worldEntityNode":
        ent = data.get("entityTemplate")
        depot = ent.get("DepotPath") if isinstance(ent, dict) else None
        return isinstance(depot, dict) and isinstance(depot.get("$value"), str)
    return True


def harvest_native_templates(
    root: str | Path,
    *,
    base_templates: dict[str, Any] | None = None,
    required_types: Iterable[str] = ("worldMeshNode", "worldCollisionNode", "worldEntityNode"),
    max_files: int | None = 2048,
) -> dict[str, Any]:
    root_path = Path(root)
    if not root_path.exists():
        raise FileNotFoundError(root_path)

    needed = {str(x) for x in required_types}
    found: dict[str, list[dict[str, Any]]] = {}
    source_files: list[str] = []
    scanned = 0

    for path in sorted(root_path.rglob("*.json")):
        if max_files is not None and scanned >= max_files:
            break
        scanned += 1
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        nodes = template_nodes_from_json(obj)
        selected = False
        for node_type in sorted(needed):
            if node_type in found:
                continue
            for node in nodes.get(node_type, []):
                if not isinstance(node, dict) or not _valid_template(node, node_type):
                    continue
                clone = copy.deepcopy(node)
                clone["ncigSourceFile"] = str(path.relative_to(root_path)).replace("\\", "/")
                found[node_type] = [clone]
                selected = True
                break
        if selected:
            source_files.append(str(path.relative_to(root_path)).replace("\\", "/"))
        if needed.issubset(found.keys()):
            break

    harvested = {
        "format": "ncig-template-harvest-v1",
        "root": str(root_path.resolve()),
        "source_files": sorted(source_files),
        "counts": {k: len(v) for k, v in sorted(found.items())},
        "templates": {k: found[k] for k in sorted(found)},
        "harvest": {
            "mode": "streamingsector_recursive",
            "files_scanned": scanned,
            "required_types": sorted(needed),
            "real_types_found": sorted(found),
        },
    }

    if base_templates:
        harvested = merge_template_harvests(base_templates, harvested)

    # Mesh is the only hard rendering dependency. When the supplied world export
    # set does not contain one, provide the known reference serializer as an
    # explicit fallback. The native audit reports this as fallback mode rather
    # than pretending it is a harvested exporter payload.
    if not harvested.get("templates", {}).get("worldMeshNode"):
        fallback = mesh_node(
            name="[NCIG FALLBACK TEMPLATE] worldMeshNode",
            node_ref="$/#NCIG_FALLBACK_WORLD_MESH",
            position={"x": 0.0, "y": 0.0, "z": 0.0},
            mesh_path="base\\\\environment\\\\architecture\\\\common\\\\int\\\\int_common_a\\\\int_common_a_floor_l600_w600_a.mesh",
        )
        fallback["ncigTemplateMode"] = "reference_serializer_fallback"
        harvested.setdefault("templates", {})["worldMeshNode"] = [fallback]
        harvested.setdefault("counts", {})["worldMeshNode"] = 1
        harvested["harvest"]["mesh_fallback"] = True
    else:
        harvested["harvest"]["mesh_fallback"] = False

    return harvested


def write_native_template_harvest(
    root: str | Path,
    out: str | Path,
    *,
    base_templates_path: str | Path | None = None,
    max_files: int | None = 2048,
) -> dict[str, Any]:
    base = None
    if base_templates_path:
        base = json.loads(Path(base_templates_path).read_text(encoding="utf-8"))
    result = harvest_native_templates(root, base_templates=base, max_files=max_files)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result
