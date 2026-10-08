from __future__ import annotations

import copy
import json
import math
import re
from pathlib import Path
from typing import Any

from .io import write_json
from .object_spawner import clean_native_export, strip_ncig_metadata

FORMAT = "ncig-native-architecture-v1"


def _load(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def _mesh_template(templates: dict[str, Any] | None, *, allow_schema_fallback: bool = True) -> dict[str, Any]:
    if not isinstance(templates, dict):
        raise ValueError("A real ncig-template-harvest-v1 file is required")
    pool = (templates.get("templates") or {}).get("worldMeshNode")
    if not isinstance(pool, list) or not pool or not isinstance(pool[0], dict):
        if not allow_schema_fallback:
            raise ValueError("The template harvest contains no usable worldMeshNode template")
        # Reference serializer fallback. This is deliberately marked as a fallback
        # because exporter-specific render enum values are not known until a real
        # worldMeshNode is harvested from a sector/WB export.
        from .reference_nodes import mesh_node
        base = mesh_node(
            name="[NCIG TEMPLATE] worldMeshNode",
            node_ref="$/#NCIG_TEMPLATE_WORLD_MESH",
            position={"x": 0.0, "y": 0.0, "z": 0.0},
            mesh_path="base\\environment\\architecture\\common\\int\\int_common_a\\int_common_a_floor_l600_w600_a.mesh",
        )
    else:
        base = copy.deepcopy(pool[0])
    required = ("type", "position", "rotation", "scale", "streamingRefPoint", "data")
    missing = [key for key in required if key not in base]
    if missing:
        raise ValueError(f"worldMeshNode template is incomplete; missing: {', '.join(missing)}")
    if base.get("type") != "worldMeshNode":
        raise ValueError("worldMeshNode template has an unexpected type")
    data = base.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("mesh"), dict):
        raise ValueError("worldMeshNode template has no data.mesh object")
    depot = data["mesh"].get("DepotPath")
    if not isinstance(depot, dict) or "$value" not in depot:
        raise ValueError("worldMeshNode template has no data.mesh.DepotPath.$value")
    return base


def _q_yaw(degrees: float) -> dict[str, float]:
    half = math.radians(float(degrees)) / 2.0
    return {"i": 0.0, "j": 0.0, "k": math.sin(half), "r": math.cos(half)}


def _with_w(source: dict[str, Any], position: dict[str, Any]) -> dict[str, Any]:
    out = {"x": float(position["x"]), "y": float(position["y"]), "z": float(position["z"])}
    if "w" in source:
        out["w"] = float(position.get("w", source.get("w", 0)))
    return out


def _set_mesh_resource(node: dict[str, Any], resource: str) -> None:
    data = node.get("data")
    if not isinstance(data, dict):
        raise ValueError("worldMeshNode template has invalid data payload")
    mesh = data.get("mesh")
    if not isinstance(mesh, dict):
        raise ValueError("worldMeshNode template has invalid data.mesh payload")
    depot = mesh.get("DepotPath")
    if not isinstance(depot, dict) or "$value" not in depot:
        raise ValueError("worldMeshNode template has invalid DepotPath payload")
    depot["$value"] = str(resource).replace("/", "\\")


def _layout_by_building(layouts: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for raw in layouts.get("layouts", []) or []:
        if not isinstance(raw, dict):
            continue
        building = raw.get("building")
        if isinstance(building, dict) and building.get("id") is not None:
            result[str(building["id"])] = raw
    return result


def _assembly_by_building(assembly: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for raw in assembly.get("buildings", []) or []:
        if isinstance(raw, dict) and raw.get("id") is not None:
            result[str(raw["id"])] = raw
    return result


def _extents_for_sector(raw: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    min_xyz = raw.get("min_xyz")
    max_xyz = raw.get("max_xyz")
    if isinstance(min_xyz, dict) and isinstance(max_xyz, dict):
        return (
            {"x": float(min_xyz["x"]), "y": float(min_xyz["y"]), "z": float(min_xyz["z"])},
            {"x": float(max_xyz["x"]), "y": float(max_xyz["y"]), "z": float(max_xyz["z"])},
        )
    ext = raw.get("extents")
    if isinstance(ext, dict) and isinstance(ext.get("min"), dict) and isinstance(ext.get("max"), dict):
        return copy.deepcopy(ext["min"]), copy.deepcopy(ext["max"])
    raise ValueError(f"sector {raw.get('id')!r} has no min_xyz/max_xyz or extents")


def _materialize_mesh(template: dict[str, Any], placement: dict[str, Any], building_id: str) -> dict[str, Any]:
    resource = placement.get("resource")
    if not isinstance(resource, str) or not resource.lower().endswith(".mesh"):
        raise ValueError(f"placement {placement.get('id')!r} has no usable .mesh resource")
    pos = placement.get("position")
    if not isinstance(pos, dict) or not all(k in pos for k in ("x", "y", "z")):
        raise ValueError(f"placement {placement.get('id')!r} has no complete position")

    out = copy.deepcopy(template)
    name = str(placement.get("id") or "mesh")
    out["name"] = f"[NCIG] {name}"
    out["nodeRef"] = f"$/#{building_id}_{name}"
    out["position"] = _with_w(template.get("position") or {}, pos)
    stream_template = template.get("streamingRefPoint") if isinstance(template.get("streamingRefPoint"), dict) else {}
    out["streamingRefPoint"] = _with_w(stream_template, pos)
    out["rotation"] = _q_yaw(float(placement.get("rotation_deg", 0.0)))
    scale = placement.get("scale")
    if isinstance(scale, dict) and all(k in scale for k in ("x", "y", "z")):
        out["scale"] = {"x": float(scale["x"]), "y": float(scale["y"]), "z": float(scale["z"])}
    _set_mesh_resource(out, resource)

    # The harvested mesh template is authoritative for render enum fields and other
    # exporter-specific payload members. We deliberately do not synthesize them here.
    data = out.get("data")
    source_data = placement.get("data") if isinstance(placement.get("data"), dict) else {}
    appearance = source_data.get("meshAppearance") or source_data.get("appearance")
    if appearance is not None and isinstance(data, dict) and isinstance(data.get("meshAppearance"), dict):
        data["meshAppearance"]["$value"] = str(appearance)
    return strip_ncig_metadata(out)


def _build_sector(template_sector: dict[str, Any], layout_sector: dict[str, Any], *, building_id: str) -> dict[str, Any]:
    out = copy.deepcopy(template_sector)
    floor = int(layout_sector.get("floor", 0))
    out["name"] = re.sub(r"[\s]+", "_", str(layout_sector.get("id") or f"{building_id}_sector_f{floor + 1:02d}").lower())
    out["category"] = "Interior"
    out["level"] = floor + 1
    out["variantIndices"] = copy.deepcopy(template_sector.get("variantIndices", [0]))
    out["prefabRef"] = copy.deepcopy(template_sector.get("prefabRef", ""))
    out["min"], out["max"] = _extents_for_sector(layout_sector)
    out["nodes"] = []
    return out


def build_native_architecture_export(
    layouts: dict[str, Any],
    assembly: dict[str, Any],
    templates: dict[str, Any],
    base_export: dict[str, Any],
    *,
    building_id: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Clone a real worldMeshNode template into a native Object Spawner envelope.

    Only transform, node identity and mesh resource are changed on the harvested node.
    Sector/envelope structure is cloned from a real World Builder export.
    """
    if not isinstance(base_export, dict) or not isinstance(base_export.get("sectors"), list):
        raise ValueError("base export must be a real World Builder/Object Spawner export")
    if not base_export.get("sectors"):
        raise ValueError("base export contains no sectors")

    mesh_template = _mesh_template(templates, allow_schema_fallback=True)
    layouts_map = _layout_by_building(layouts)
    assembly_map = _assembly_by_building(assembly)
    ids = [building_id] if building_id else sorted(set(layouts_map) & set(assembly_map))
    if not ids:
        raise ValueError("no building exists in both layouts and architecture assembly")

    template_sector = base_export["sectors"][0]
    if not isinstance(template_sector, dict):
        raise ValueError("base export first sector is invalid")

    generated_sectors: list[dict[str, Any]] = []
    emitted = 0
    by_building: dict[str, int] = {}
    by_class: dict[str, int] = {}
    failures: list[dict[str, Any]] = []

    for bid in ids:
        layout = layouts_map.get(bid)
        asm = assembly_map.get(bid)
        if layout is None or asm is None:
            raise ValueError(f"building {bid!r} missing layout or assembly")
        placements = [p for p in asm.get("placements", []) if isinstance(p, dict)]
        unresolved = [str(p.get("id")) for p in placements if not p.get("resource")]
        if unresolved:
            failures.append({"building_id": bid, "unresolved": unresolved})
            continue
        placements_by_floor: dict[int, list[dict[str, Any]]] = {}
        for p in placements:
            placements_by_floor.setdefault(int(p.get("floor", 0)), []).append(p)
        sector_rows = layout.get("sectors") or []
        for raw_sector in sector_rows:
            if not isinstance(raw_sector, dict):
                continue
            floor = int(raw_sector.get("floor", 0))
            sector = _build_sector(template_sector, raw_sector, building_id=bid)
            for p in sorted(placements_by_floor.get(floor, []), key=lambda item: str(item.get("id", ""))):
                node = _materialize_mesh(mesh_template, p, bid)
                sector["nodes"].append(node)
                emitted += 1
                cls = str(p.get("class") or "unknown")
                by_class[cls] = by_class.get(cls, 0) + 1
            generated_sectors.append(sector)
        by_building[bid] = sum(len(s["nodes"]) for s in generated_sectors if str(s.get("name", "")).startswith(f"{bid}_"))

    if failures:
        raise ValueError(f"assembly contains unresolved placements: {json.dumps(failures, ensure_ascii=False)}")
    if emitted == 0:
        raise ValueError("native architecture export would contain zero mesh nodes")

    result = copy.deepcopy(base_export)
    result["name"] = f"ncig_architecture_{'_'.join(ids)}"
    result["sectors"] = generated_sectors
    result["devices"] = copy.deepcopy(base_export.get("devices", []))
    result["psEntries"] = copy.deepcopy(base_export.get("psEntries", []))
    report = {
        "format": FORMAT,
        "building_ids": ids,
        "building_count": len(ids),
        "sector_count": len(generated_sectors),
        "emitted_node_count": emitted,
        "emitted_nodes_by_building": by_building,
        "emitted_nodes_by_class": dict(sorted(by_class.items())),
        "source_mesh_template": {
            "type": mesh_template.get("type"),
            "uk10": mesh_template.get("uk10"),
            "uk11": mesh_template.get("uk11"),
            "primaryRange": mesh_template.get("primaryRange"),
            "secondaryRange": mesh_template.get("secondaryRange"),
            "mesh_template_resource": mesh_template["data"]["mesh"]["DepotPath"].get("$value"),
            "source_mode": (
                "harvested_worldMeshNode"
                if isinstance(((templates or {}).get("templates") or {}).get("worldMeshNode"), list)
                and ((templates or {}).get("templates") or {}).get("worldMeshNode")
                and not bool(((templates or {}).get("templates") or {}).get("worldMeshNode")[0].get("ncigTemplateMode"))
                else "upstream_entSpawner_serializer"
            ),
        },
        "bounds_validation_required": True,
        "scale_policy": "assembly_scale_only",
        "native_export_generated": True,
        "note": "Mesh nodes use a harvested worldMeshNode when available; otherwise NCIG uses the public entSpawner export schema with exact default render enums. Mesh bounds and placement correctness still require in-game validation.",
    }
    return result, report


def write_native_architecture_export(
    layouts_path: str | Path,
    assembly_path: str | Path,
    templates_path: str | Path,
    base_export_path: str | Path,
    out_path: str | Path,
    report_path: str | Path | None = None,
    *,
    building_id: str | None = None,
) -> dict[str, Any]:
    result, report = build_native_architecture_export(
        _load(layouts_path), _load(assembly_path), _load(templates_path), _load(base_export_path), building_id=building_id
    )
    # Strip NCIG-only annotations from the file handed to WolvenKit.
    clean = clean_native_export(result)
    write_json(out_path, clean)
    if report_path:
        write_json(report_path, report)
    return report
