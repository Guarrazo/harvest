from __future__ import annotations

import copy
import json
import math
from pathlib import Path
from typing import Any

from .io import write_json
from .reference_nodes import entity_node, mesh_node, light_node, collision_node, area_shape_node, SUPPORTED_SCHEMAS, schema_summary
from .resource_resolver import resolve_resource

FORMAT = "ncig-object-spawner-v2"


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def is_wb_export(data: dict[str, Any]) -> bool:
    return (
        isinstance(data, dict)
        and isinstance(data.get("sectors"), list)
        and isinstance(data.get("version"), str)
        and "xlFormat" in data
    )


def sector_nodes(sector: dict[str, Any]) -> list[dict[str, Any]]:
    return [n for n in (sector.get("nodes") or []) if isinstance(n, dict)]


def all_template_nodes(data: dict[str, Any]) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    for sector in data.get("sectors", []) or []:
        nodes.extend(sector_nodes(sector))
    return nodes


def node_type(node: dict[str, Any]) -> str:
    value = node.get("type")
    return value if isinstance(value, str) else "unknown"


def strip_ncig_metadata(node: dict[str, Any]) -> dict[str, Any]:
    """Remove NCIG-only annotations before a payload is handed to WolvenKit."""
    out = copy.deepcopy(node)
    for key in list(out.keys()):
        if key.lower().startswith("ncig"):
            out.pop(key, None)
    return out


def classify_node(node: dict[str, Any]) -> str:
    t = node_type(node)
    if t == "worldEntityNode":
        return "entity"
    if t in {"worldMeshNode", "worldStaticMeshNode"}:
        return "mesh"
    if t == "worldCollisionNode":
        return "collision"
    if t.endswith("LightNode"):
        return "light"
    if "Community" in t:
        return "community"
    if t in {"worldInteriorAreaNode", "worldAmbientAreaNode", "worldTriggerAreaNode"}:
        return "area"
    if t == "worldAISpotNode":
        return "ai_spot"
    if t == "worldStaticMarkerNode":
        return "marker"
    return "unknown"


def fingerprint_exact_export(data: dict[str, Any]) -> dict[str, Any]:
    if not is_wb_export(data):
        raise ValueError("Input does not match the observed World Builder/Object Spawner envelope")
    sectors = data.get("sectors", [])
    counts: dict[str, int] = {}
    samples: list[dict[str, Any]] = []
    for s_idx, sector in enumerate(sectors):
        for n_idx, node in enumerate(sector_nodes(sector)):
            t = node_type(node)
            counts[t] = counts.get(t, 0) + 1
            if len(samples) < 30:
                samples.append({
                    "sector": s_idx,
                    "node": n_idx,
                    "type": t,
                    "class": classify_node(node),
                    "keys": sorted(node.keys()),
                    "data_keys": sorted((node.get("data") or {}).keys()) if isinstance(node.get("data"), dict) else [],
                })
    return {
        "format": "ncig-exact-object-spawner-fingerprint-v2",
        "xlFormat": data.get("xlFormat"),
        "version": data.get("version"),
        "name": data.get("name"),
        "sector_count": len(sectors),
        "node_counts": counts,
        "categories": sorted({s.get("category") for s in sectors if s.get("category") is not None}),
        "samples": samples,
        "top_level_keys": sorted(data.keys()),
    }


def _offset_pos(pos: dict[str, Any], dx: float, dy: float, dz: float) -> dict[str, Any]:
    out = dict(pos)
    for axis, delta in (("x", dx), ("y", dy), ("z", dz)):
        if axis in out:
            out[axis] = float(out[axis]) + delta
    return out


def relocate_entity_probe(
    template: dict[str, Any],
    *,
    dx: float,
    dy: float,
    dz: float,
    output_name: str = "ncig_entity_probe",
) -> dict[str, Any]:
    """Relocate an actual worldEntityNode while preserving the exact WB JSON envelope."""
    if not is_wb_export(template):
        raise ValueError("Template is not a recognized World Builder export")
    out = copy.deepcopy(template)
    out["name"] = output_name
    changed = 0
    for sector in out.get("sectors", []) or []:
        new_nodes = []
        for node in sector_nodes(sector):
            if node_type(node) != "worldEntityNode":
                continue
            n = copy.deepcopy(node)
            if isinstance(n.get("position"), dict):
                n["position"] = _offset_pos(n["position"], dx, dy, dz)
            if isinstance(n.get("streamingRefPoint"), dict):
                n["streamingRefPoint"] = _offset_pos(n["streamingRefPoint"], dx, dy, dz)
            n["name"] = f"[NCIG PROBE] {n.get('name', 'entity')}"
            new_nodes.append(n)
            changed += 1
        sector["nodes"] = new_nodes
    if changed == 0:
        raise ValueError("The supplied export contains no worldEntityNode to use as a probe template")
    out["ncig"] = {
        "generator": "NCIG",
        "format": FORMAT,
        "mode": "exact-probe-relocation",
        "relocation": {"dx": dx, "dy": dy, "dz": dz},
        "entity_nodes_changed": changed,
    }
    return out


def _yaw_from_quaternion(q: dict[str, Any] | None) -> float:
    if not isinstance(q, dict):
        return 0.0
    # Works for the yaw-only quaternions NCIG currently emits.
    z = float(q.get("k", q.get("z", 0.0)))
    w = float(q.get("r", q.get("w", 1.0)))
    return math.degrees(2.0 * math.atan2(z, w))


def _sector_dict_from_layout(sector: dict[str, Any], template_sector: dict[str, Any], name: str) -> dict[str, Any]:
    out = copy.deepcopy(template_sector)
    out["name"] = name
    out["category"] = "Interior"
    out["level"] = int(sector.get("floor", 0)) + 1
    out["variantIndices"] = list(template_sector.get("variantIndices", [0]))
    ext = sector.get("extents", {})
    if "min" in ext and "max" in ext:
        out["min"] = copy.deepcopy(ext["min"])
        out["max"] = copy.deepcopy(ext["max"])
    elif "min" in sector and "max" in sector:
        out["min"] = copy.deepcopy(sector["min"])
        out["max"] = copy.deepcopy(sector["max"])
    elif "min_xyz" in sector and "max_xyz" in sector:
        mn, mx = sector["min_xyz"], sector["max_xyz"]
        out["min"] = {"x": mn["x"], "y": mn["y"], "z": mn["z"]}
        out["max"] = {"x": mx["x"], "y": mx["y"], "z": mx["z"]}
    out["prefabRef"] = template_sector.get("prefabRef", "")
    return out


def _replace_entity_payload(node: dict[str, Any], spec: dict[str, Any]) -> None:
    """Update only fields known to exist in the real Entity Template export."""
    data = spec.get("data") or {}
    resource = data.get("resource")
    if not resource:
        return
    nd = node.get("data")
    if not isinstance(nd, dict):
        return
    entity_template = nd.get("entityTemplate")
    if not isinstance(entity_template, dict):
        return
    depot = entity_template.get("DepotPath")
    if isinstance(depot, dict) and "$value" in depot:
        depot["$value"] = str(resource)
    appearance = data.get("appearanceName")
    if appearance is not None and isinstance(nd.get("appearanceName"), dict):
        nd["appearanceName"]["$value"] = str(appearance)


def _materialize_from_template(base: dict[str, Any], spec: dict[str, Any], building_id: str) -> dict[str, Any]:
    out = copy.deepcopy(base)
    out["name"] = str(spec.get("name", "ncig_node"))
    out["nodeRef"] = f"$/#{building_id}_{out['name']}"
    pos = spec.get("position") or {"x": 0.0, "y": 0.0, "z": 0.0}
    template_pos = base.get("position") if isinstance(base.get("position"), dict) else {}
    position = {"x": pos["x"], "y": pos["y"], "z": pos["z"]}
    if "w" in template_pos:
        position["w"] = pos.get("w", template_pos.get("w", 0))
    out["position"] = position
    if isinstance(spec.get("streamingRefPoint"), dict):
        out["streamingRefPoint"] = copy.deepcopy(spec["streamingRefPoint"])
    else:
        template_stream = base.get("streamingRefPoint") if isinstance(base.get("streamingRefPoint"), dict) else {}
        streaming = {"x": pos["x"], "y": pos["y"], "z": pos["z"]}
        if "w" in template_stream:
            streaming["w"] = template_stream.get("w", 0)
        out["streamingRefPoint"] = streaming
    if spec.get("rotation") is not None:
        out["rotation"] = copy.deepcopy(spec["rotation"])
    if spec.get("scale") is not None:
        out["scale"] = copy.deepcopy(spec["scale"])
    if "primaryRange" in spec:
        out["primaryRange"] = spec["primaryRange"]
    if "secondaryRange" in spec:
        out["secondaryRange"] = spec["secondaryRange"]
    typ = node_type(out)
    data = spec.get("data") or {}
    out_data = out.get("data") if isinstance(out.get("data"), dict) else {}

    # Known WB entity export: update only the actual entity payload shape.
    if typ == "worldEntityNode":
        _replace_entity_payload(out, spec)

    # Preserve harvested mesh/light/collision enum values while patching the concrete
    # resource/transform payload requested by the generated plan.
    if typ == "worldMeshNode":
        resource = data.get("resource")
        mesh = out_data.get("mesh") if isinstance(out_data, dict) else None
        depot = mesh.get("DepotPath") if isinstance(mesh, dict) else None
        if isinstance(resource, str) and isinstance(depot, dict) and "$value" in depot:
            depot["$value"] = resource
        appearance = data.get("appearance") or data.get("meshAppearance")
        if appearance and isinstance(out_data.get("meshAppearance"), dict):
            out_data["meshAppearance"]["$value"] = str(appearance)

    if typ == "worldStaticLightNode":
        profile = data.get("lightProfile")
        if isinstance(profile, dict) and isinstance(out_data, dict):
            # Do not erase harvested enum defaults; explicit plan values override only keys supplied.
            for key, value in profile.items():
                out_data[key] = copy.deepcopy(value)

    if typ == "worldCollisionNode":
        size = data.get("size")
        compiled = out_data.get("compiledData") if isinstance(out_data, dict) else None
        cdata = compiled.get("Data") if isinstance(compiled, dict) else None
        actors = cdata.get("Actors") if isinstance(cdata, dict) else None
        shapes = actors[0].get("Shapes") if actors and isinstance(actors[0], dict) else None
        shape = shapes[0] if shapes and isinstance(shapes[0], dict) else None
        if shape is not None and isinstance(size, dict):
            shape["Size"] = {"$type": "Vector3", "X": float(size.get("x", 1.0)), "Y": float(size.get("y", 1.0)), "Z": float(size.get("z", 1.0))}
            if "preset" in data:
                shape["Preset"] = {"$type": "CName", "$value": str(data["preset"]), "$storage": "string"}
            if "material" in data:
                shape["Materials"] = [{"$type": "CName", "$value": str(data["material"]), "$storage": "string"}]
        extents = out_data.get("extents") if isinstance(out_data, dict) else None
        if isinstance(extents, dict) and isinstance(size, dict):
            extents["X"], extents["Y"], extents["Z"] = float(size.get("x", 1.0)), float(size.get("y", 1.0)), float(size.get("z", 1.0))

    # Area nodes are synthesized from explicit markers so the binary outline corresponds
    # to the generated room footprint rather than to the arbitrary harvested template.
    if typ == "worldAreaShapeNode" and isinstance(data.get("markers"), list):
        markers = [tuple(float(v) for v in m[:3]) for m in data["markers"] if isinstance(m, (list, tuple)) and len(m) >= 3]
        if markers:
            from .reference_nodes import area_outline_base64
            pos0 = out.get("position") or {"x": 0.0, "y": 0.0, "z": 0.0}
            center = (float(pos0.get("x", 0)), float(pos0.get("y", 0)), float(pos0.get("z", 0)))
            out_data["outline"] = {"Data": {"$type": "AreaShapeOutline", "buffer": area_outline_base64(center, markers, float(data.get("height", 2.0)))}}

    out["data"] = out_data
    return out


def build_exact_object_spawner(plan: dict[str, Any], template: dict[str, Any]) -> dict[str, Any]:
    """Build an Object Spawner JSON using real template nodes from the supplied WB export.

    Unsupported NCIG node types are skipped and reported rather than synthesized.
    This guarantees that every emitted node started from a real exported node shape.
    """
    if not is_wb_export(template):
        raise ValueError("Template is not a recognized World Builder export")
    template_sectors = template.get("sectors") or []
    if not template_sectors:
        raise ValueError("Template contains no sectors")
    templates: dict[str, dict[str, Any]] = {}
    for node in all_template_nodes(template):
        templates.setdefault(node_type(node), node)

    generated_sectors: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    # NCIG plan sectors are the authoritative partition for generated content.
    layout_sectors = plan.get("sectors") or []
    if not layout_sectors:
        raise ValueError("NCIG plan contains no sectors")
    building_id = str(plan.get("building_id") or (plan.get("building") or {}).get("id") or template.get("name", "interior"))

    for s_idx, layout_sector in enumerate(layout_sectors):
        template_sector = template_sectors[min(s_idx, len(template_sectors) - 1)]
        sector_name = str(layout_sector.get("id") or layout_sector.get("name") or f"sector_{s_idx+1:02d}")
        out_sector = _sector_dict_from_layout(layout_sector, template_sector, sector_name)
        out_nodes: list[dict[str, Any]] = []
        for spec in plan.get("nodes", []):
            floor = spec.get("floor")
            if floor is not None and int(floor) != int(layout_sector.get("floor", floor)):
                continue
            wanted = str(spec.get("type", "unknown"))
            base = templates.get(wanted)
            if base is None:
                skipped.append({"id": spec.get("name"), "type": wanted, "sector": sector_name})
                continue
            out_nodes.append(_materialize_from_template(base, spec, building_id))
        out_sector["nodes"] = out_nodes
        generated_sectors.append(out_sector)

    result = copy.deepcopy(template)
    building_id = str(plan.get("building_id") or (plan.get("building") or {}).get("id") or template.get("name", "interior"))
    result["name"] = f"ncig_{building_id}"
    result["sectors"] = generated_sectors
    result["ncig"] = {
        "generator": "NCIG",
        "format": FORMAT,
        "source_template": template.get("name"),
        "template_version": template.get("version"),
        "generated_sector_count": len(generated_sectors),
        "emitted_node_count": sum(len(s["nodes"]) for s in generated_sectors),
        "skipped_node_count": len(skipped),
        "skipped": skipped,
        "note": "Every emitted node is cloned from a real World Builder export template. Missing node classes are not fabricated.",
    }
    return result


def build_exact_manifest(plan: dict[str, Any], template: dict[str, Any]) -> dict[str, Any]:
    if not is_wb_export(template):
        raise ValueError("Template is not a recognized World Builder export")
    available = sorted({node_type(n) for n in all_template_nodes(template)})
    supported, unresolved = [], []
    for node in plan.get("nodes", []):
        wanted = node.get("type", "unknown")
        if wanted in available:
            supported.append({"id": node.get("name"), "type": wanted})
        else:
            unresolved.append({"id": node.get("name"), "type": wanted, "reason": "no matching real template node in supplied export"})
    return {
        "format": "ncig-native-readiness-manifest-v2",
        "template": {"version": template.get("version"), "xlFormat": template.get("xlFormat"), "available_node_types": available},
        "supported_count": len(supported),
        "unresolved_count": len(unresolved),
        "supported": supported,
        "unresolved": unresolved,
        "next_probe_types": [
            x for x in ["worldMeshNode", "worldCollisionNode", "worldStaticLightNode", "worldStaticMarkerNode", "worldInteriorAreaNode", "worldCompiledCommunityAreaNode_Streamable"]
            if x not in available
        ],
    }


def write_probe_relocation(template_path: str | Path, out_path: str | Path, dx: float, dy: float, dz: float) -> dict[str, Any]:
    data = load_json(template_path)
    result = relocate_entity_probe(data, dx=dx, dy=dy, dz=dz)
    write_json(out_path, result)
    return result.get("ncig", {})


def write_exact_object_spawner(plan_path: str | Path, template_path: str | Path, out_path: str | Path) -> dict[str, Any]:
    plan = load_json(plan_path)
    template = load_json(template_path)
    result = build_exact_object_spawner(plan, template)
    write_json(out_path, result)
    return result.get("ncig", {})



def _resource_for_spec(spec: dict[str, Any], assets: dict[str, Any] | None, role: str | None = None) -> str | None:
    data = spec.setdefault("data", {})
    if role and not data.get("resourceRole"):
        data["resourceRole"] = role
    return resolve_resource(spec, assets).get("resource")


def _harvested_template_for_type(templates: dict[str, Any] | None, wanted: str) -> dict[str, Any] | None:
    if not templates:
        return None
    pool = templates.get("templates", {}).get(wanted, [])
    return copy.deepcopy(pool[0]) if pool else None


def synthesize_schema_node(spec: dict[str, Any], building_id: str, *, assets: dict[str, Any] | None = None, templates: dict[str, Any] | None = None) -> tuple[dict[str, Any] | None, str | None]:
    """Create a node from the public exporter schema, preferring harvested real templates.

    Returns (node, warning). If a runtime-sensitive enum/resource is unavailable, the node is
    omitted instead of silently creating a shape that may be rejected by WolvenKit.
    """
    wanted = str(spec.get("type", "unknown"))
    name = str(spec.get("name", "ncig_node"))
    ref = f"$/#{building_id}_{name}"
    pos = spec.get("position") or {"x": 0.0, "y": 0.0, "z": 0.0}
    rot = spec.get("rotation")
    scale = spec.get("scale")
    tmpl = _harvested_template_for_type(templates, wanted)
    if tmpl is not None:
        out = _materialize_from_template(tmpl, spec, building_id)
        return strip_ncig_metadata(out), None

    if wanted == "worldEntityNode":
        resource = _resource_for_spec(spec, assets, "entity")
        if not resource:
            return None, f"{name}: no .ent resource available from plan or harvested assets"
        app = (spec.get("data") or {}).get("appearanceName", "default")
        return entity_node(name=name, node_ref=ref, position=pos, entity_path=resource, appearance=str(app), rotation=rot, scale=scale), None

    if wanted == "worldMeshNode":
        resource = _resource_for_spec(spec, assets, "geometry") or _resource_for_spec(spec, assets, "mesh")
        if not resource:
            return None, f"{name}: no .mesh resource available from plan or harvested assets"
        return None, f"{name}: mesh serializer exists, but a real World Builder mesh template is required for runtime-safe render enum values; harvest one from installed favorites/mods"

    if wanted == "worldStaticLightNode":
        profile = (spec.get("data") or {}).get("lightProfile")
        if not profile:
            return None, f"{name}: light serializer exists, but a real World Builder light template is required for runtime-safe enum values; harvest one from installed favorites/mods"
        return strip_ncig_metadata(light_node(name=name, node_ref=ref, position=pos, profile=profile, rotation=rot, scale=scale)), None

    if wanted == "worldCollisionNode":
        data = spec.get("data") or {}
        if not data.get("preset") or not data.get("material"):
            return None, f"{name}: collision serializer exists, but a harvested collision preset/material is required for runtime-safe export"
        size = data.get("size") or {"x": 1.0, "y": 1.0, "z": 1.0}
        return strip_ncig_metadata(collision_node(name=name, node_ref=ref, position=pos, size=size, preset=str(data["preset"]), material=str(data["material"]), rotation=rot, scale=scale)), None

    if wanted == "worldAreaShapeNode":
        data = spec.get("data") or {}
        markers = data.get("markers") or []
        markers = [tuple(float(v) for v in marker[:3]) for marker in markers]
        if not markers:
            return None, f"{name}: area node requires data.markers"
        return area_shape_node(name=name, node_ref=ref, markers=markers, height=float(data.get("height", 2.0))), None

    return None, f"{name}: node type {wanted} has no schema serializer yet"


def build_schema_backed_object_spawner(plan: dict[str, Any], base_export: dict[str, Any] | None = None, *, assets: dict[str, Any] | None = None, templates: dict[str, Any] | None = None, decoration: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build the exact Object Spawner envelope without requiring manual probe groups.

    The sector envelope comes from a real export when supplied. Node payloads are taken from
    harvested WB templates where available; otherwise NCIG uses serializer schemas for the
    node types whose structure is known. Missing runtime-sensitive resources are reported.
    """
    building_id = str(plan.get("building_id") or (plan.get("building") or {}).get("id") or "interior")
    if base_export is not None:
        if not is_wb_export(base_export):
            raise ValueError("base_export must be a World Builder/Object Spawner JSON export")
        envelope = copy.deepcopy(base_export)
        template_sector = envelope.get("sectors", [{}])[0] if envelope.get("sectors") else {}
        version = envelope.get("version", "1.0.4")
        xl_format = envelope.get("xlFormat", 0)
    else:
        envelope = {"xlFormat": 0, "sectors": [], "variants": [], "version": "1.0.4", "name": f"ncig_{building_id}", "devices": [], "psEntries": []}
        template_sector = {"min": {"x": 0.0, "y": 0.0, "z": 0.0}, "max": {"x": 0.0, "y": 0.0, "z": 0.0}, "variantIndices": [0], "nodes": [], "variants": [], "category": "Interior", "level": 1, "prefabRef": "", "name": "new_group"}
        version = envelope["version"]
        xl_format = envelope["xlFormat"]

    generated_sectors: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    emitted = 0
    per_sector_emitted: dict[str, int] = {}
    for idx, ps in enumerate(plan.get("sectors", []) or []):
        sector = copy.deepcopy(template_sector)
        sector["name"] = str(ps.get("id") or ps.get("name") or f"{building_id}_F{idx+1:02d}")
        sector["category"] = "Interior"
        sector["level"] = int(ps.get("floor", idx)) + 1
        ext = ps.get("extents") or ps
        sector["min"] = copy.deepcopy(ext.get("min") or {"x": 0.0, "y": 0.0, "z": 0.0})
        sector["max"] = copy.deepcopy(ext.get("max") or {"x": 0.0, "y": 0.0, "z": 0.0})
        sector["variantIndices"] = [0]
        nodes: list[dict[str, Any]] = []
        floor = int(ps.get("floor", idx))
        for spec in plan.get("nodes", []) or []:
            sf = spec.get("floor")
            if sf is not None and int(sf) != floor:
                continue
            node, warning = synthesize_schema_node(spec, building_id, assets=assets, templates=templates)
            if node is None:
                skipped.append({"name": spec.get("name"), "type": spec.get("type"), "sector": sector["name"], "reason": warning})
                continue
            if warning:
                skipped.append({"name": spec.get("name"), "type": spec.get("type"), "sector": sector["name"], "reason": warning})
                continue
            nodes.append(node)
            emitted += 1
        if decoration:
            for dec_layout in decoration.get("layouts", []) or []:
                if str(dec_layout.get("building_id")) != building_id:
                    continue
                extra = (dec_layout.get("sector_nodes") or {}).get(sector["name"], [])
                for raw_node in extra:
                    if not isinstance(raw_node, dict):
                        continue
                    nodes.append(strip_ncig_metadata(raw_node))
                    emitted += 1
        sector["nodes"] = nodes
        per_sector_emitted[sector["name"]] = len(nodes)
        generated_sectors.append(sector)

    envelope["name"] = f"ncig_{building_id}"
    envelope["sectors"] = generated_sectors
    envelope["xlFormat"] = xl_format
    envelope["version"] = version
    envelope.setdefault("devices", [])
    envelope.setdefault("psEntries", [])
    envelope["ncig"] = {
        "generator": "NCIG",
        "format": "ncig-object-spawner-v3",
        "schema": schema_summary(),
        "base_export": base_export is not None,
        "template_harvested": bool(templates),
        "asset_harvested": bool(assets),
        "decoration_composed": bool(decoration),
        "generated_sector_count": len(generated_sectors),
        "emitted_node_count": emitted,
        "emitted_nodes_by_sector": per_sector_emitted,
        "skipped_node_count": len(skipped),
        "skipped": skipped,
    }
    return envelope


def clean_native_export(data: dict[str, Any]) -> dict[str, Any]:
    """Return a JSON envelope intended for WolvenKit with all NCIG-only metadata removed."""
    out = copy.deepcopy(data)
    def scrub(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: scrub(v) for k, v in obj.items() if not k.lower().startswith("ncig")}
        if isinstance(obj, list):
            return [scrub(v) for v in obj]
        return obj
    out = scrub(out)
    return out


def write_schema_object_spawner(plan_path: str | Path, out_path: str | Path, *, base_export_path: str | Path | None = None, assets_path: str | Path | None = None, templates_path: str | Path | None = None, decoration_path: str | Path | None = None, report_path: str | Path | None = None) -> dict[str, Any]:
    plan = load_json(plan_path)
    base = load_json(base_export_path) if base_export_path else None
    assets = load_json(assets_path) if assets_path else None
    templates = load_json(templates_path) if templates_path else None
    decoration = load_json(decoration_path) if decoration_path else None
    result = build_schema_backed_object_spawner(plan, base, assets=assets, templates=templates, decoration=decoration)
    meta = copy.deepcopy(result.get("ncig", {}))
    clean = clean_native_export(result)
    write_json(out_path, clean)
    if report_path:
        write_json(report_path, meta)
    return meta
