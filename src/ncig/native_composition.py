from __future__ import annotations

import copy
import json
import math
import re
from pathlib import Path
from typing import Any

from .io import write_json
from .native_architecture import _load, _q_yaw, build_native_architecture_export
from .native_collision import build_room_collisions
from .object_spawner import clean_native_export

FORMAT = "ncig-native-composition-v1"


def _entity_template(templates: dict[str, Any]) -> dict[str, Any]:
    pool = (templates.get("templates") or {}).get("worldEntityNode")
    if not isinstance(pool, list) or not pool or not isinstance(pool[0], dict):
        raise ValueError("template harvest contains no real worldEntityNode template")
    t = copy.deepcopy(pool[0])
    if t.get("type") != "worldEntityNode":
        raise ValueError("worldEntityNode template has unexpected type")
    data = t.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("entityTemplate"), dict):
        raise ValueError("worldEntityNode template has no data.entityTemplate")
    return t


def _set_entity_resource(node: dict[str, Any], resource: str) -> None:
    node["data"]["entityTemplate"]["DepotPath"]["$value"] = str(resource).replace("/", "\\")


def _materialize_entity(template: dict[str, Any], placement: dict[str, Any], building_id: str) -> dict[str, Any]:
    resource = str(placement.get("resource", ""))
    if not resource.lower().endswith(".ent"):
        raise ValueError(f"decoration {placement.get('id')!r} has no .ent resource")
    out = copy.deepcopy(template)
    name = str(placement.get("id") or "entity")
    pos = placement.get("position") or {}
    out["name"] = f"[NCIG] {name}"
    out["nodeRef"] = f"$/#{building_id}_{name}"
    out["position"] = {"x": float(pos["x"]), "y": float(pos["y"]), "z": float(pos["z"]), "w": 0}
    out["streamingRefPoint"] = {"x": float(pos["x"]), "y": float(pos["y"]), "z": float(pos["z"]), "w": 0}
    out["rotation"] = _q_yaw(float(placement.get("rotation_deg", 0.0)))
    scale = placement.get("scale")
    if isinstance(scale, dict) and all(k in scale for k in ("x", "y", "z")):
        out["scale"] = {"x": float(scale["x"]), "y": float(scale["y"]), "z": float(scale["z"])}
    _set_entity_resource(out, resource)
    appearance = placement.get("appearance")
    if appearance and isinstance(out.get("data", {}).get("appearanceName"), dict):
        out["data"]["appearanceName"]["$value"] = str(appearance)
    return out


def _expand_sector_bounds(sector: dict[str, Any], margin: float) -> None:
    if margin <= 0:
        return
    for key in ("min", "max"):
        if not isinstance(sector.get(key), dict):
            sector[key] = {}
    mn, mx = sector["min"], sector["max"]
    mn["x"] = float(mn.get("x", 0.0)) - margin
    mn["y"] = float(mn.get("y", 0.0)) - margin
    mn["z"] = float(mn.get("z", 0.0)) - margin
    mx["x"] = float(mx.get("x", 0.0)) + margin
    mx["y"] = float(mx.get("y", 0.0)) + margin
    mx["z"] = float(mx.get("z", 0.0)) + margin


def _layout_for_building(layouts: dict[str, Any], building_id: str) -> dict[str, Any]:
    for layout in layouts.get("layouts", []) or []:
        if isinstance(layout, dict) and str((layout.get("building") or {}).get("id")) == building_id:
            return layout
    raise ValueError(f"layout not found for building {building_id!r}")


def _decoration_for_building(decoration: dict[str, Any] | None, building_id: str) -> list[dict[str, Any]]:
    if not decoration:
        return []
    if str(decoration.get("building_id")) != building_id:
        return []
    return [p for p in decoration.get("placements", []) or [] if isinstance(p, dict) and str(p.get("resource", "")).lower().endswith(".ent")]


def build_native_composition(
    layouts: dict[str, Any],
    assembly: dict[str, Any],
    templates: dict[str, Any],
    base_export: dict[str, Any],
    *,
    decoration: dict[str, Any] | None = None,
    include_collisions: bool = True,
    streaming_margin_m: float = 32.0,
    building_id: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    native, mesh_report = build_native_architecture_export(
        layouts, assembly, templates, base_export, building_id=building_id
    )
    ids = mesh_report["building_ids"]
    ent_template = _entity_template(templates) if decoration and _decoration_for_building(decoration, ids[0]) else None
    col_template = None
    pool = (templates.get("templates") or {}).get("worldCollisionNode")
    if isinstance(pool, list) and pool and isinstance(pool[0], dict):
        col_template = copy.deepcopy(pool[0])

    layouts_by = {str((x.get("building") or {}).get("id")): x for x in layouts.get("layouts", []) if isinstance(x, dict)}
    decor_count = 0
    collision_count = 0
    collision_meta: list[dict[str, Any]] = []
    for bid in ids:
        layout = layouts_by.get(bid) or _layout_for_building(layouts, bid)
        decor = _decoration_for_building(decoration, bid)
        decor_by_floor: dict[int, list[dict[str, Any]]] = {}
        for p in decor:
            decor_by_floor.setdefault(int(p.get("floor", 0)), []).append(p)
        all_collisions, cm = build_room_collisions(layout, template=col_template)
        by_coll_floor: dict[int, list[dict[str, Any]]] = {}
        for node in all_collisions:
            ref = str(node.get("nodeRef", ""))
            floor = 0
            # Refs use <building>_<room>_COLL_... and room IDs contain F##.
            match = re.search(r"_F(\d{1,2})_R", ref)
            if match:
                floor = max(0, int(match.group(1)) - 1)
            by_coll_floor.setdefault(floor, []).append(node)
        for sector in native.get("sectors", []) or []:
            if not isinstance(sector, dict):
                continue
            _expand_sector_bounds(sector, streaming_margin_m)
            floor = max(0, int(sector.get("level", 1)) - 1)
            if include_collisions:
                for node in by_coll_floor.get(floor, []):
                    sector.setdefault("nodes", []).append(node)
                    collision_count += 1
            if ent_template:
                for p in decor_by_floor.get(floor, []):
                    sector.setdefault("nodes", []).append(_materialize_entity(ent_template, p, bid))
                    decor_count += 1
        collision_meta.append(cm)

    native["name"] = f"ncig_composition_{'_'.join(ids)}"
    clean = clean_native_export(native)
    report = {
        "format": FORMAT,
        "building_ids": ids,
        "mesh_nodes": int(mesh_report.get("emitted_node_count", 0)),
        "collision_nodes": collision_count,
        "decoration_nodes": decor_count,
        "streaming_margin_m": float(streaming_margin_m),
        "include_collisions": bool(include_collisions),
        "decoration_supplied": bool(decoration),
        "collision_policy": "room_shell_boxes_with_door_openings" if include_collisions else "disabled",
        "native_export_generated": True,
        "note": "Mesh nodes are cloned from the real worldMeshNode template; collision boxes use the observed entSpawner serializer shape; decoration nodes use the real worldEntityNode template. Physical fit still requires in-game validation.",
    }
    return clean, report


def write_native_composition(
    layouts_path: str | Path,
    assembly_path: str | Path,
    templates_path: str | Path,
    base_export_path: str | Path,
    out_path: str | Path,
    report_path: str | Path | None = None,
    *,
    decoration_path: str | Path | None = None,
    include_collisions: bool = True,
    streaming_margin_m: float = 32.0,
    building_id: str | None = None,
) -> dict[str, Any]:
    layouts = _load(layouts_path)
    assembly = _load(assembly_path)
    templates = _load(templates_path)
    base = _load(base_export_path)
    decoration = _load(decoration_path) if decoration_path else None
    result, report = build_native_composition(
        layouts, assembly, templates, base, decoration=decoration,
        include_collisions=include_collisions, streaming_margin_m=streaming_margin_m,
        building_id=building_id,
    )
    write_json(out_path, result)
    if report_path:
        write_json(report_path, report)
    return report
