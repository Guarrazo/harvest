from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from .native_architecture import _mesh_template, _layout_by_building, _assembly_by_building
from .native_collision import build_room_collisions


def _load(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected JSON object")
    return data


def _has_ncig(obj: Any) -> bool:
    if isinstance(obj, dict):
        return any(str(k).lower().startswith("ncig") or _has_ncig(v) for k, v in obj.items())
    if isinstance(obj, list):
        return any(_has_ncig(v) for v in obj)
    return False


def _node_keys_without_ncig(node: dict[str, Any]) -> set[str]:
    return {str(k) for k in node if not str(k).lower().startswith("ncig")}


def _inside(pos: dict[str, Any], sector: dict[str, Any], eps: float = 0.05) -> bool:
    mn, mx = sector.get("min", {}), sector.get("max", {})
    try:
        return all(float(mn[a]) - eps <= float(pos[a]) <= float(mx[a]) + eps for a in ("x", "y", "z"))
    except (KeyError, TypeError, ValueError):
        return False


def _quat_norm(q: dict[str, Any]) -> float:
    return math.sqrt(sum(float(q.get(k, 0.0)) ** 2 for k in ("i", "j", "k", "r")))


def _entity_template(templates: dict[str, Any]) -> dict[str, Any] | None:
    pool = (templates.get("templates") or {}).get("worldEntityNode")
    if isinstance(pool, list) and pool and isinstance(pool[0], dict):
        return pool[0]
    return None


def audit_native_architecture(
    native: dict[str, Any],
    layouts: dict[str, Any],
    assembly: dict[str, Any],
    templates: dict[str, Any],
    *,
    building_id: str | None = None,
    decoration: dict[str, Any] | None = None,
) -> dict[str, Any]:
    template = _mesh_template(templates)
    entity_template = _entity_template(templates)
    layout_map = _layout_by_building(layouts)
    assembly_map = _assembly_by_building(assembly)
    ids = [building_id] if building_id else sorted(set(layout_map) & set(assembly_map))
    expected_mesh = []
    for bid in ids:
        asm = assembly_map.get(bid)
        if asm is None:
            continue
        expected_mesh.extend((bid, p) for p in asm.get("placements", []) if isinstance(p, dict) and p.get("resource"))

    expected_entity_refs: set[str] = set()
    if decoration:
        for bid in ids:
            if str(decoration.get("building_id")) != bid:
                continue
            for p in decoration.get("placements", []) or []:
                if isinstance(p, dict) and str(p.get("resource", "")).lower().endswith(".ent"):
                    expected_entity_refs.add(f"$/#{bid}_{str(p.get('id'))}")

    emitted_all = []
    emitted_mesh = []
    emitted_collisions = []
    emitted_entities = []
    for sector in native.get("sectors", []) or []:
        if not isinstance(sector, dict):
            continue
        for node in sector.get("nodes", []) or []:
            if not isinstance(node, dict):
                continue
            item = (str(sector.get("name", "")), node)
            emitted_all.append(item)
            typ = node.get("type")
            if typ == "worldMeshNode":
                emitted_mesh.append(item)
            elif typ == "worldCollisionNode":
                emitted_collisions.append(item)
            elif typ == "worldEntityNode":
                emitted_entities.append(item)

    errors: list[str] = []
    warnings: list[str] = []
    template_keys = _node_keys_without_ncig(template)
    template_data_keys = set(template.get("data", {}).keys()) if isinstance(template.get("data"), dict) else set()
    expected_by_ref = {f"$/#{bid}_{str(p.get('id'))}": (bid, p) for bid, p in expected_mesh}
    seen_refs: set[str] = set()
    matched = 0
    out_of_bounds = 0
    bad_quats = 0
    bad_scales = 0
    resource_mismatches = 0
    key_mismatches = 0
    data_key_mismatches = 0

    for sector_name, node in emitted_mesh:
        ref = str(node.get("nodeRef", ""))
        if ref in seen_refs:
            errors.append(f"duplicate nodeRef: {ref}")
        seen_refs.add(ref)
        if _node_keys_without_ncig(node) != template_keys:
            key_mismatches += 1
        data = node.get("data")
        if not isinstance(data, dict) or set(data.keys()) != template_data_keys:
            data_key_mismatches += 1
        if not isinstance(node.get("position"), dict) or not all(k in node["position"] for k in ("x", "y", "z")):
            errors.append(f"node {ref}: invalid position")
        else:
            sector = next((s for s in native.get("sectors", []) or [] if isinstance(s, dict) and str(s.get("name", "")) == sector_name), None)
            if sector and not _inside(node["position"], sector):
                out_of_bounds += 1
        if not isinstance(node.get("rotation"), dict) or abs(_quat_norm(node["rotation"]) - 1.0) > 1e-5:
            bad_quats += 1
        scale = node.get("scale")
        try:
            if not isinstance(scale, dict) or any(float(scale[k]) <= 0 for k in ("x", "y", "z")):
                bad_scales += 1
        except (TypeError, ValueError, KeyError):
            bad_scales += 1
        try:
            resource = data["mesh"]["DepotPath"]["$value"]
        except (KeyError, TypeError):
            resource = None
            errors.append(f"node {ref}: missing data.mesh.DepotPath.$value")
        if not isinstance(resource, str) or not resource.lower().endswith(".mesh"):
            resource_mismatches += 1
        if ref in expected_by_ref:
            matched += 1
            expected_resource = str(expected_by_ref[ref][1].get("resource", "")).replace("/", "\\")
            if resource != expected_resource:
                resource_mismatches += 1
        else:
            errors.append(f"unexpected mesh nodeRef not present in assembly: {ref}")
        if _has_ncig(node):
            errors.append(f"node {ref}: NCIG metadata leaked into native output")

    # Collision nodes are generated from the known entSpawner box serializer and are
    # validated for complete shape payloads plus unique refs. Their physical accuracy
    # is necessarily geometric/scene-level rather than resource-level.
    collision_refs: set[str] = set()
    for _, node in emitted_collisions:
        ref = str(node.get("nodeRef", ""))
        if ref in seen_refs or ref in collision_refs:
            errors.append(f"duplicate collision nodeRef: {ref}")
        collision_refs.add(ref)
        if node.get("type") != "worldCollisionNode":
            errors.append(f"unexpected collision node type {node.get('type')!r}: {ref}")
        data = node.get("data")
        if not isinstance(data, dict) or not isinstance(data.get("compiledData"), dict):
            errors.append(f"collision {ref}: missing compiledData")
        if not isinstance(node.get("position"), dict) or not all(k in node["position"] for k in ("x", "y", "z")):
            errors.append(f"collision {ref}: invalid position")
        if _has_ncig(node):
            errors.append(f"collision {ref}: NCIG metadata leaked into native output")

    actual_entity_refs = set()
    for _, node in emitted_entities:
        ref = str(node.get("nodeRef", ""))
        actual_entity_refs.add(ref)
        if node.get("type") != "worldEntityNode":
            errors.append(f"unexpected entity node type {node.get('type')!r}: {ref}")
        data = node.get("data")
        if not isinstance(data, dict) or not isinstance(data.get("entityTemplate"), dict):
            errors.append(f"entity {ref}: missing data.entityTemplate")
        elif not isinstance(data["entityTemplate"].get("DepotPath"), dict):
            errors.append(f"entity {ref}: missing entityTemplate DepotPath")
        if _has_ncig(node):
            errors.append(f"entity {ref}: NCIG metadata leaked into native output")
    if expected_entity_refs:
        missing = expected_entity_refs - actual_entity_refs
        extra = actual_entity_refs - expected_entity_refs
        if missing:
            errors.append(f"missing decoration entity nodes: {len(missing)}")
        if extra:
            errors.append(f"unexpected decoration entity nodes: {len(extra)}")
    elif emitted_entities:
        errors.append("native output contains worldEntityNode entries but no decoration plan was supplied to the audit")

    if key_mismatches:
        errors.append(f"{key_mismatches} mesh nodes do not preserve the real worldMeshNode top-level key set")
    if data_key_mismatches:
        errors.append(f"{data_key_mismatches} mesh nodes do not preserve the real worldMeshNode data key set")
    if out_of_bounds:
        errors.append(f"{out_of_bounds} emitted mesh nodes lie outside their generated sector bounds")
    if bad_quats:
        errors.append(f"{bad_quats} mesh nodes have non-unit/invalid quaternions")
    if bad_scales:
        errors.append(f"{bad_scales} mesh nodes have invalid scale values")
    if resource_mismatches:
        errors.append(f"{resource_mismatches} mesh node resource paths are missing or differ from the assembly")
    if _has_ncig(native):
        errors.append("NCIG metadata leaked into the native export envelope")

    return {
        "format": "ncig-native-architecture-audit-v2",
        "building_ids": ids,
        "expected_resolved_placements": len(expected_mesh),
        "emitted_nodes": len(emitted_all),
        "emitted_mesh_nodes": len(emitted_mesh),
        "emitted_collision_nodes": len(emitted_collisions),
        "emitted_entity_nodes": len(emitted_entities),
        "matched_placements": matched,
        "expected_decoration_entities": len(expected_entity_refs),
        "matched_decoration_entities": len(expected_entity_refs & actual_entity_refs),
        "template_type": template.get("type"),
        "template_uk10": template.get("uk10"),
        "template_uk11": template.get("uk11"),
        "top_level_key_mismatches": key_mismatches,
        "data_key_mismatches": data_key_mismatches,
        "out_of_bounds_nodes": out_of_bounds,
        "quaternion_errors": bad_quats,
        "scale_errors": bad_scales,
        "resource_errors": resource_mismatches,
        "errors": errors,
        "warnings": warnings,
        "passed": not errors,
        "bounds_validation_required": True,
        "note": "Mesh schema/resources/transforms are checked against the real worldMeshNode template; collisions use the observed entSpawner serializer shape; decoration entities use the real worldEntityNode template. Physical fit and walkability still require in-game validation.",
    }


def write_native_architecture_audit(native_path: str | Path, layouts_path: str | Path, assembly_path: str | Path, templates_path: str | Path, out_path: str | Path, *, building_id: str | None = None, decoration_path: str | Path | None = None) -> dict[str, Any]:
    decoration = _load(decoration_path) if decoration_path else None
    report = audit_native_architecture(_load(native_path), _load(layouts_path), _load(assembly_path), _load(templates_path), building_id=building_id, decoration=decoration)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report
