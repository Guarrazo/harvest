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
from .reference_nodes import entity_node, interior_trigger_node

FORMAT = "ncig-native-composition-v1"


def _materialize_entity(placement: dict[str, Any], building_id: str) -> dict[str, Any]:
    resource = str(placement.get("resource", ""))
    if not resource.lower().endswith(".ent"):
        raise ValueError(f"decoration {placement.get('id')!r} has no .ent resource")
    pos = placement.get("position") or {}
    if not all(k in pos for k in ("x", "y", "z")):
        raise ValueError(f"decoration {placement.get('id')!r} has no complete position")
    data = placement.get("data") if isinstance(placement.get("data"), dict) else {}
    appearance = str(data.get("appearanceName") or placement.get("appearance") or "default")
    return entity_node(
        name=f"[NCIG] {placement.get('id') or 'entity'}",
        node_ref=f"$/#{building_id}_{placement.get('id') or 'entity'}",
        position={"x": float(pos["x"]), "y": float(pos["y"]), "z": float(pos["z"])},
        entity_path=resource,
        appearance=appearance,
        rotation=_q_yaw(float(placement.get("rotation_deg", 0.0))),
        scale=placement.get("scale") if isinstance(placement.get("scale"), dict) else None,
    )


def _interior_trigger_for_floor(layout: dict[str, Any], floor: int) -> dict[str, Any]:
    building = layout.get("building") or {}
    width = float(building.get("width_m", 0.0) or 0.0)
    depth = float(building.get("depth_m", 0.0) or 0.0)
    if width <= 0.0 or depth <= 0.0:
        raise ValueError(f"building {building.get('id')!r} has invalid footprint for interior trigger")
    z = float((building.get("position") or {}).get("z", 0.0)) + floor * 3.2 + 0.05
    x = float((building.get("position") or {}).get("x", 0.0))
    y = float((building.get("position") or {}).get("y", 0.0))
    yaw = math.radians(float(building.get("yaw_deg", 0.0)))
    c, s = math.cos(yaw), math.sin(yaw)
    local = [
        (-width * 0.5, -depth * 0.5),
        ( width * 0.5, -depth * 0.5),
        ( width * 0.5,  depth * 0.5),
        (-width * 0.5,  depth * 0.5),
    ]
    markers = []
    for lx, ly in local:
        markers.append((x + c * lx - s * ly, y + s * lx + c * ly, z))
    bid = str(building.get("id") or "building")
    ref = f"$/#{bid}_F{floor + 1:02d}_INTERIOR_TRIGGER"
    return interior_trigger_node(
        name=f"[NCIG INTERIOR] {bid}_F{floor + 1:02d}",
        node_ref=ref,
        markers=markers,
        height=3.0,
    )


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
            match = re.search(r"_f(\d{1,2})(?:_r|_coll_floor)", ref, re.IGNORECASE)
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
            for p in decor_by_floor.get(floor, []):
                sector.setdefault("nodes", []).append(_materialize_entity(p, bid))
                decor_count += 1
            # Mark each generated floor as a gameplay interior. This supplies the
            # Interior notifier while keeping the generated footprint aligned with
            # the same building bounds used by the structural layout.
            trigger = _interior_trigger_for_floor(layout, floor)
            sector.setdefault("nodes", []).append(trigger)
        collision_meta.append(cm)

    native["name"] = f"ncig_composition_{'_'.join(ids)}"
    clean = clean_native_export(native)
    report = {
        "format": FORMAT,
        "building_ids": ids,
        "mesh_nodes": int(mesh_report.get("emitted_node_count", 0)),
        "collision_nodes": collision_count,
        "decoration_nodes": decor_count,
        "interior_trigger_nodes": len(ids) and sum(len([s for s in native.get("sectors", []) if str(s.get("name","")).startswith(f"{bid}_")]) for bid in ids) or 0,
        "streaming_margin_m": float(streaming_margin_m),
        "include_collisions": bool(include_collisions),
        "decoration_supplied": bool(decoration),
        "collision_policy": "continuous_floor_per_floor_plus_room_shell_walls_with_door_openings" if include_collisions else "disabled",
        "native_export_generated": True,
        "note": "Mesh, entity and interior-trigger nodes use public entSpawner export shapes; collisions use the observed collision serializer shape. Physical fit and walkability still require in-game validation.",
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
