from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .export import write_wb_plans
from .catalog import build_catalog, catalog_report
from .generator import generate_layout, validate_layout
from .io import bundle_layouts, load_buildings, write_json
from .preview import write_previews
from .scanner import build_scan_report, find_entry_nodes, load_observations, infer_anchor_from_entry, proximity_groups
from .viewer import build_viewer
from .routing import build_entrance_route, route_to_dict
from .worldplan import build_world_plan
from .bridge import fingerprint_export, write_template_bridge
from .object_spawner import load_json as load_spawner_json, fingerprint_exact_export, write_probe_relocation, build_exact_manifest, write_exact_object_spawner, write_schema_object_spawner
from .asset_harvest import harvest, harvest_templates
from .reference_nodes import schema_summary
from .module_library import build_module_library, library_report
from .decorator import decorate_layout
from .plan_lint import lint_report
from .resource_resolver import bind_resources, resolve_resource
from .preflight import build_preflight, merge_harvests
from .remote import sync_github_harvest
from .architecture_catalog import build_architecture_catalog, architecture_catalog_report
from .architecture_assembler import build_architecture_assembly, apply_architecture_to_world_plan
from .decoration_catalog import build_decoration_catalog
from .decoration_plan import build_decoration_plan
from .native_composition import write_native_composition
from .native_probe import write_native_probe
from .native_architecture import write_native_architecture_export
from .native_architecture_audit import write_native_architecture_audit
from .architecture_bounds import build_bounds_targets, merge_bounds_file
from .target_detector import load_world_records, detect_building_candidates, candidates_to_buildings
from .city_pipeline import load_city_records, detect_city_buildings
from .city_index import build_city_index, inspect_city_json


def cmd_generate(args: argparse.Namespace) -> int:
    buildings = load_buildings(args.input)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    layouts = []
    all_errors = []
    catalog = None
    if args.catalog:
        catalog_raw = json.loads(Path(args.catalog).read_text(encoding="utf-8"))
        catalog = catalog_raw.get("catalog", catalog_raw)
    routes = []
    for building in buildings:
        try:
            layout = generate_layout(building)
            errors = validate_layout(layout)
            if errors:
                all_errors.append({"building": building.id, "errors": errors})
                continue
            layouts.append(layout)
        except Exception as exc:  # noqa: BLE001
            all_errors.append({"building": building.id, "errors": [str(exc)]})

    write_json(out / "layouts.json", bundle_layouts(layouts))
    write_wb_plans(layouts, out / "wb_plans")
    for layout in layouts:
        write_previews(layout, out / "previews")
        write_json(
            out / "wb_plans" / f"{layout.building.id}_world_plan_v2.json",
            build_world_plan(
                layout,
                catalog,
                playable_shell=args.playable_shell,
                collision_preset=args.collision_preset,
                collision_material=args.collision_material,
            ),
        )
        if args.playable_shell:
            from .shell import build_playable_shell
            write_json(
                out / "shells" / f"{layout.building.id}_playable_shell.json",
                build_playable_shell(layout, collision_preset=args.collision_preset, collision_material=args.collision_material),
            )

    summary = {
        "generator_version": "0.22.7",
        "input_buildings": len(buildings),
        "generated": len(layouts),
        "failed": len(all_errors),
        "failures": all_errors,
        "world_plan_format": "ncig-world-plan-v3",
        "real_asset_catalog": bool(args.catalog),
        "playable_shell": bool(args.playable_shell),
        "collision_shell": bool(args.collision_preset and args.collision_material),
    }
    write_json(out / "summary.json", summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if not all_errors else 2


def cmd_scan(args: argparse.Namespace) -> int:
    observations = load_observations(args.input)
    report = build_scan_report(observations)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    write_json(out, report)
    if args.anchors_out:
        entries = find_entry_nodes(observations)
        groups = proximity_groups(entries, args.group_radius)
        anchors = []
        for idx, group in enumerate(groups, start=1):
            if not group:
                continue
            entry = group[0]
            a = infer_anchor_from_entry(
                entry,
                default_width_m=args.width,
                default_depth_m=args.depth,
                default_floors=args.floors,
                district=args.district,
            )
            # Make IDs unique even when the runtime exposes multiple nodes with the same name.
            if any(x["id"] == a.id for x in anchors):
                a = a.__class__(**{**a.__dict__, "id": f"{a.id}_{idx:03d}"})
            record = asdict(a)
            record["tags"] = list(record["tags"])
            anchors.append(record)
        write_json(args.anchors_out, {"buildings": anchors, "format": "ncig-buildings-v1"})
        report["generated_anchors"] = len(anchors)
        write_json(out, report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


def cmd_routes(args: argparse.Namespace) -> int:
    buildings = {b.id: b for b in load_buildings(args.buildings)}
    observations = load_observations(args.scan)
    routes = []
    for entry in find_entry_nodes(observations):
        matches = sorted(
            buildings.values(),
            key=lambda b: (b.position.x-entry.position.x) ** 2 + (b.position.y-entry.position.y) ** 2 + (b.position.z-entry.position.z) ** 2,
        )
        if not matches:
            continue
        building = matches[0]
        layout = generate_layout(building)
        routes.append(route_to_dict(build_entrance_route(building, layout, entry)))
    write_json(args.out, {"format": "ncig-entrance-routes-v1", "routes": routes})
    print(json.dumps({"routes": len(routes), "written": args.out}, indent=2, ensure_ascii=False))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    data = json.loads(Path(args.layout).read_text(encoding="utf-8"))
    failures = []
    for raw in data.get("layouts", []):
        if not raw.get("building", {}).get("id"):
            failures.append("layout with missing building.id")
        if not raw.get("rooms"):
            failures.append(f"{raw.get('building', {}).get('id', '?')}: no rooms")
        if not raw.get("sectors"):
            failures.append(f"{raw.get('building', {}).get('id', '?')}: no sectors")
        sockets = raw.get("sockets", [])
        if raw.get("building", {}).get("floors", 1) >= 1 and not any(s.get("kind") == "entry" for s in sockets):
            failures.append(f"{raw.get('building', {}).get('id', '?')}: no generated building entry")
    print(json.dumps({"valid": not failures, "failures": failures}, indent=2, ensure_ascii=False))
    return 0 if not failures else 2


def cmd_viewer(args: argparse.Namespace) -> int:
    path = build_viewer(args.preview_dir, args.out)
    print(path)
    return 0


def cmd_catalog(args: argparse.Namespace) -> int:
    catalog = build_catalog(args.root)
    write_json(args.out, {"format": "ncig-resource-catalog-v2", "root": str(Path(args.root).resolve()), "catalog": catalog})
    print(json.dumps({"written": args.out, **catalog_report(catalog)}, indent=2, ensure_ascii=False))
    return 0


def cmd_preview(args: argparse.Namespace) -> int:
    data = json.loads(Path(args.layout).read_text(encoding="utf-8"))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    from .model import BuildingAnchor, Layout, Room, Sector, Socket, Vec3
    for raw in data.get("layouts", []):
        braw = raw["building"]
        pos = braw["position"]
        b = BuildingAnchor(
            id=braw["id"], district=braw.get("district", ""), type=braw.get("type", "residential"),
            position=Vec3(**pos), yaw_deg=braw.get("yaw_deg", 0), width_m=braw["width_m"], depth_m=braw["depth_m"],
            floors=braw.get("floors", 1), entry_width_m=braw.get("entry_width_m", 1),
            entry_height_m=braw.get("entry_height_m", 2.1), seed=braw.get("seed"), tags=tuple(braw.get("tags", [])),
            entry_local_x=braw.get("entry_local_x"), entry_local_y=braw.get("entry_local_y"), entry_yaw_deg=braw.get("entry_yaw_deg"),
        )
        rooms = [Room(**x) for x in raw["rooms"]]
        sockets = [Socket(**x) for x in raw.get("sockets", [])]
        sectors = [Sector(
            id=x["id"], building_id=x["building_id"], floor=x["floor"], category=x["category"],
            min_xyz=Vec3(**x["min_xyz"]), max_xyz=Vec3(**x["max_xyz"]), rooms=x["rooms"]
        ) for x in raw.get("sectors", [])]
        layout = Layout(b, rooms, sockets, sectors, raw.get("warnings", []))
        write_previews(layout, out)
    return 0


def _cmd_fingerprint(args: argparse.Namespace) -> int:
    report = fingerprint_export(args.input)
    write_json(args.out, report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


def _cmd_bridge(args: argparse.Namespace) -> int:
    result = write_template_bridge(args.plan, args.template, args.out)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def _cmd_exact_fingerprint(args: argparse.Namespace) -> int:
    data = load_spawner_json(args.input)
    report = fingerprint_exact_export(data)
    write_json(args.out, report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


def _cmd_probe(args: argparse.Namespace) -> int:
    meta = write_probe_relocation(args.template, args.out, args.dx, args.dy, args.dz)
    print(json.dumps({"written": args.out, **meta}, indent=2, ensure_ascii=False))
    return 0


def _cmd_readiness(args: argparse.Namespace) -> int:
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    template = load_spawner_json(args.template)
    report = build_exact_manifest(plan, template)
    write_json(args.out, report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


def _cmd_exact_bridge(args: argparse.Namespace) -> int:
    meta = write_exact_object_spawner(args.plan, args.template, args.out)
    print(json.dumps({"written": args.out, **meta}, indent=2, ensure_ascii=False))
    return 0



def _cmd_harvest(args: argparse.Namespace) -> int:
    report = harvest(args.root)
    if args.templates_out:
        write_json(args.templates_out, harvest_templates(args.root))
    write_json(args.out, report)
    print(json.dumps({"written": args.out, "resource_count": report["resource_count"], "node_type_mentions": report["node_type_mentions"]}, indent=2, ensure_ascii=False))
    return 0


def _cmd_schema(args: argparse.Namespace) -> int:
    report = schema_summary()
    write_json(args.out, report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


def _cmd_schema_bridge(args: argparse.Namespace) -> int:
    meta = write_schema_object_spawner(args.plan, args.out, base_export_path=args.base, assets_path=args.assets, templates_path=args.templates, decoration_path=args.decoration, report_path=args.report)
    print(json.dumps({"written": args.out, **meta}, indent=2, ensure_ascii=False))
    return 0



def _cmd_bind_resources(args: argparse.Namespace) -> int:
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    assets = json.loads(Path(args.assets).read_text(encoding="utf-8"))
    bound_plan, report = bind_resources(plan, assets, overwrite=args.overwrite)
    write_json(args.out, bound_plan)
    if args.report:
        write_json(args.report, report)
    print(json.dumps({"written": args.out, "bound": report["bound_count"], "unresolved": report["unresolved_count"], "skipped": report["skipped_count"]}, indent=2, ensure_ascii=False))
    return 0 if report["unresolved_count"] == 0 else 2


def _cmd_resource_check(args: argparse.Namespace) -> int:
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    assets = json.loads(Path(args.assets).read_text(encoding="utf-8"))
    nodes = []
    for node in plan.get("nodes", []) or []:
        if not isinstance(node, dict) or node.get("type") not in {"worldMeshNode", "worldEntityNode"}:
            continue
        result = resolve_resource(node, assets)
        nodes.append({"name": node.get("name"), "type": node.get("type"), **result})
    report = {
        "format": "ncig-resource-check-v1",
        "node_count": len(nodes),
        "resolved": sum(bool(x.get("resource")) for x in nodes),
        "unresolved": sum(not bool(x.get("resource")) for x in nodes),
        "nodes": nodes,
    }
    write_json(args.out, report)
    print(json.dumps({"written": args.out, "node_count": report["node_count"], "resolved": report["resolved"], "unresolved": report["unresolved"]}, indent=2, ensure_ascii=False))
    return 0 if report["unresolved"] == 0 else 2



def _cmd_preflight(args: argparse.Namespace) -> int:
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    assets = json.loads(Path(args.assets).read_text(encoding="utf-8")) if args.assets else None
    templates = json.loads(Path(args.templates).read_text(encoding="utf-8")) if args.templates else None
    base = load_spawner_json(args.base) if args.base else None
    report = build_preflight(plan, assets=assets, templates=templates, base_export=base)
    write_json(args.out, report)
    print(json.dumps({"written": args.out, "ready": report["ready"], **report["summary"]}, indent=2, ensure_ascii=False))
    return 0 if report["ready"] else 2



def _cmd_sync_harvest(args: argparse.Namespace) -> int:
    manifest = sync_github_harvest(args.source, args.out, ref=args.ref, include_optional=not args.required_only)
    print(json.dumps({"written": str(Path(args.out).resolve()), **manifest}, indent=2, ensure_ascii=False))
    return 0


def _cmd_architecture_catalog(args: argparse.Namespace) -> int:
    harvest_data = json.loads(Path(args.harvest).read_text(encoding="utf-8"))
    catalog = build_architecture_catalog(
        harvest_data,
        max_per_class=args.max_per_class,
        max_total=args.max_total,
        interior_only=args.interior_only,
    )
    write_json(args.out, catalog)
    print(json.dumps({"written": args.out, **architecture_catalog_report(catalog)}, indent=2, ensure_ascii=False))
    return 0



def _cmd_architecture_assemble(args: argparse.Namespace) -> int:
    from .model import BuildingAnchor, Layout, Room, Sector, Socket, Vec3
    raw = json.loads(Path(args.layouts).read_text(encoding="utf-8"))
    catalog_raw = json.loads(Path(args.catalog).read_text(encoding="utf-8"))
    catalog = catalog_raw.get("catalog", catalog_raw)
    layouts = []
    for raw_layout in raw.get("layouts", []):
        braw = raw_layout["building"]
        b = BuildingAnchor(
            id=braw["id"], district=braw.get("district", ""), type=braw.get("type", "residential"),
            position=Vec3(**braw["position"]), yaw_deg=braw.get("yaw_deg", 0),
            width_m=braw["width_m"], depth_m=braw["depth_m"], floors=braw.get("floors", 1),
            entry_width_m=braw.get("entry_width_m", 1), entry_height_m=braw.get("entry_height_m", 2.1),
            seed=braw.get("seed"), tags=tuple(braw.get("tags", [])),
        )
        rooms=[Room(**x) for x in raw_layout["rooms"]]
        sockets=[Socket(**x) for x in raw_layout.get("sockets", [])]
        sectors=[Sector(id=x["id"], building_id=x["building_id"], floor=x["floor"], category=x["category"],
                        min_xyz=Vec3(**x["min_xyz"]), max_xyz=Vec3(**x["max_xyz"]), rooms=x["rooms"])
                 for x in raw_layout.get("sectors", [])]
        layouts.append(Layout(b, rooms, sockets, sectors, raw_layout.get("warnings", [])))
    result = build_architecture_assembly(layouts, catalog)
    write_json(args.out, result)
    print(json.dumps({"written": args.out, "buildings": len(result.get("buildings", [])),
                      "placements": sum(int(b.get("placement_count", 0)) for b in result.get("buildings", []))}, indent=2, ensure_ascii=False))
    return 0


def _cmd_architecture_apply(args: argparse.Namespace) -> int:
    plan=json.loads(Path(args.plan).read_text(encoding="utf-8"))
    assembly=json.loads(Path(args.assembly).read_text(encoding="utf-8"))
    result=apply_architecture_to_world_plan(plan, assembly)
    write_json(args.out, result)
    print(json.dumps({"written": args.out, "nodes": len(result.get("nodes", [])),
                      "added_architecture_nodes": result.get("architecture", {}).get("added_node_count", 0),
                      "skipped_unresolved": result.get("architecture", {}).get("skipped_unresolved_count", 0)}, indent=2, ensure_ascii=False))
    return 0

def _cmd_architecture_audit(args: argparse.Namespace) -> int:
    catalog_raw = json.loads(Path(args.catalog).read_text(encoding="utf-8"))
    catalog = catalog_raw.get("catalog", catalog_raw)
    assembly = json.loads(Path(args.assembly).read_text(encoding="utf-8"))
    templates = json.loads(Path(args.templates).read_text(encoding="utf-8")) if args.templates else None
    items = catalog.get("items", []) if isinstance(catalog, dict) else []
    complete = sum(bool((x.get("dimensions") or {}).get("complete")) for x in items if isinstance(x, dict))
    by_class = {}
    for cls in ["floor_piece", "wall_piece", "ceiling_piece", "door_frame", "door_piece", "window_piece", "pillar_piece", "stairs_piece"]:
        by_class[cls] = sum(1 for x in items if isinstance(x, dict) and x.get("class") == cls)
    unresolved = sum(int(b.get("unresolved_count", 0)) for b in assembly.get("buildings", []))
    placements = sum(int(b.get("placement_count", 0)) for b in assembly.get("buildings", []))
    template_counts = {}
    if isinstance(templates, dict):
        raw_counts = templates.get("counts")
        if isinstance(raw_counts, dict):
            template_counts = {str(k): int(v) for k, v in raw_counts.items()}
        else:
            pools = templates.get("templates") or {}
            if isinstance(pools, dict):
                template_counts = {str(k): len(v) for k, v in pools.items() if isinstance(v, list)}
    mesh_template_count = int(template_counts.get("worldMeshNode", 0))
    ready = mesh_template_count > 0 and unresolved == 0
    if ready:
        reason = "A real worldMeshNode template is available and the architecture assembly has no unresolved placements; mesh bounds still require validation before final placement."
    else:
        reason = "A real worldMeshNode template from the installed World Builder/entSpawner export is still required before native Object Spawner export."
    report = {
        "format": "ncig-architecture-audit-v2",
        "catalog_selected_count": catalog.get("selected_count"),
        "catalog_complete_dimension_hints": complete,
        "catalog_class_counts": by_class,
        "assembly_buildings": len(assembly.get("buildings", [])),
        "assembly_placements": placements,
        "assembly_unresolved": unresolved,
        "bounds_validation_required": True,
        "templates_supplied": bool(templates),
        "template_counts": template_counts,
        "native_worldMesh_template_required": mesh_template_count <= 0,
        "native_worldMesh_template_count": mesh_template_count,
        "ready_for_native_mesh_export": ready,
        "reason": reason,
    }
    write_json(args.out, report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


def _cmd_native_probe(args: argparse.Namespace) -> int:
    report = write_native_probe(args.input, args.out, args.templates_out, args.base_templates)
    print(json.dumps({"written": args.out, "node_count": report["node_count"], "node_type_counts": report["node_type_counts"], "templates_out": args.templates_out}, indent=2, ensure_ascii=False))
    return 0


def _cmd_architecture_native_audit(args: argparse.Namespace) -> int:
    report = write_native_architecture_audit(
        args.native, args.layouts, args.assembly, args.templates, args.out, building_id=args.building_id, decoration_path=args.decoration
    )
    print(json.dumps({"written": args.out, **report}, indent=2, ensure_ascii=False))
    return 0 if report["passed"] else 2


def _cmd_architecture_native_export(args: argparse.Namespace) -> int:
    report = write_native_architecture_export(
        args.layouts, args.assembly, args.templates, args.base, args.out, args.report, building_id=args.building_id
    )
    print(json.dumps({"written": args.out, **report}, indent=2, ensure_ascii=False))
    return 0

def _cmd_decoration_catalog(args: argparse.Namespace) -> int:
    harvest_data = json.loads(Path(args.harvest).read_text(encoding="utf-8"))
    catalog = build_decoration_catalog(harvest_data, max_per_role=args.max_per_role)
    write_json(args.out, catalog)
    print(json.dumps({"written": args.out, "selected_count": catalog["selected_count"], "role_counts": catalog["role_counts"]}, indent=2, ensure_ascii=False))
    return 0


def _cmd_decoration_plan(args: argparse.Namespace) -> int:
    layouts = json.loads(Path(args.layout).read_text(encoding="utf-8"))
    catalog = json.loads(Path(args.catalog).read_text(encoding="utf-8"))
    target = next((x for x in layouts.get("layouts", []) if isinstance(x, dict) and (not args.building_id or str((x.get("building") or {}).get("id")) == args.building_id)), None)
    if target is None:
        raise ValueError("requested building layout not found")
    plan = build_decoration_plan(_layout_from_raw(target), catalog, architecture_family=args.architecture_family, density=args.density)
    write_json(args.out, plan)
    print(json.dumps({"written": args.out, "building_id": plan["building_id"], "placements": plan["placement_count"], "missing_roles": plan["missing_roles"]}, indent=2, ensure_ascii=False))
    return 0


def _layout_from_raw(raw: dict[str, Any]):
    from .model import BuildingAnchor, Layout, Room, Sector, Socket, Vec3
    braw = raw["building"]
    b = BuildingAnchor(
        id=braw["id"], district=braw.get("district", ""), type=braw.get("type", "residential"),
        position=Vec3(**braw["position"]), yaw_deg=braw.get("yaw_deg", 0), width_m=braw["width_m"], depth_m=braw["depth_m"],
        floors=braw.get("floors", 1), entry_width_m=braw.get("entry_width_m", 1), entry_height_m=braw.get("entry_height_m", 2.1),
        seed=braw.get("seed"), tags=tuple(braw.get("tags", [])),
        entry_local_x=braw.get("entry_local_x"), entry_local_y=braw.get("entry_local_y"), entry_yaw_deg=braw.get("entry_yaw_deg"),
    )
    rooms = [Room(**x) for x in raw.get("rooms", [])]
    sockets = [Socket(**x) for x in raw.get("sockets", [])]
    sectors = [Sector(id=x["id"], building_id=x["building_id"], floor=x["floor"], category=x["category"], min_xyz=Vec3(**x["min_xyz"]), max_xyz=Vec3(**x["max_xyz"]), rooms=x["rooms"]) for x in raw.get("sectors", [])]
    return Layout(b, rooms, sockets, sectors, raw.get("warnings", []))


def _cmd_native_composition(args: argparse.Namespace) -> int:
    report = write_native_composition(args.layouts, args.assembly, args.templates, args.base, args.out, args.report, decoration_path=args.decoration, include_collisions=not args.no_collisions, streaming_margin_m=args.streaming_margin, building_id=args.building_id)
    print(json.dumps({"written": args.out, **report}, indent=2, ensure_ascii=False))
    return 0


def _cmd_build_bounds_targets(args: argparse.Namespace) -> int:
    catalog_raw = json.loads(Path(args.catalog).read_text(encoding="utf-8"))
    catalog = catalog_raw.get("catalog", catalog_raw)
    report = build_bounds_targets(catalog, args.out)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


def _cmd_merge_bounds(args: argparse.Namespace) -> int:
    report = merge_bounds_file(args.catalog, args.bounds, args.out, args.report)
    print(json.dumps({"written": args.out, **report}, indent=2, ensure_ascii=False))
    return 0


def _cmd_detect_buildings(args: argparse.Namespace) -> int:
    records = load_world_records(args.input)
    report = detect_building_candidates(records, cluster_radius_m=args.radius)
    write_json(args.out, report)
    print(json.dumps({"written": args.out, "input_records": len(records), "candidate_count": report["candidate_count"]}, indent=2, ensure_ascii=False))
    return 0


def _cmd_detect_city_buildings(args: argparse.Namespace) -> int:
    input_path = Path(args.input)
    if input_path.suffix.lower() in {".sqlite", ".db"}:
        from .city_index import load_index_records
        records = load_index_records(input_path)
        manifest = {
            "format": "ncig-city-index-runtime-load-v1",
            "database": str(input_path.resolve()),
            "indexed_records_loaded": len(records),
        }
    else:
        records, manifest = load_city_records(input_path)
    report = detect_city_buildings(records, cluster_radius_m=args.radius)
    report["world_manifest"] = manifest
    write_json(args.out, report)
    manifest_out = Path(args.out).with_name("world_manifest.json")
    write_json(manifest_out, manifest)
    print(json.dumps({
        "written": args.out,
        "manifest": str(manifest_out),
        "json_files": manifest["json_file_count"],
        "input_records": len(records),
        "candidate_count": report["candidate_count"],
        "invalid_files": manifest["invalid_file_count"],
    }, indent=2, ensure_ascii=False))
    return 0


def _cmd_index_city(args: argparse.Namespace) -> int:
    manifest = build_city_index(args.input, args.out)
    write_json(args.manifest_out, manifest)
    print(json.dumps({
        "database": args.out,
        "manifest": args.manifest_out,
        "json_files": manifest["json_file_count"],
        "parsed_records": manifest["parsed_records"],
        "indexed_records": manifest["indexed_records"],
        "entrances": manifest["entrances"],
        "architecture": manifest["architecture"],
        "interior": manifest["interior"],
        "invalid_files": manifest["invalid_file_count"],
    }, indent=2, ensure_ascii=False))
    return 0


def _cmd_inspect_city_json(args: argparse.Namespace) -> int:
    report = inspect_city_json(args.input)
    write_json(args.out, report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


def _cmd_candidates_to_buildings(args: argparse.Namespace) -> int:
    report = json.loads(Path(args.input).read_text(encoding="utf-8"))
    result = candidates_to_buildings(report, min_score=args.min_score, max_count=args.max_count, include_review=args.include_review)
    write_json(args.out, result)
    print(json.dumps({"written": args.out, "selected_count": result["selected_count"]}, indent=2, ensure_ascii=False))
    return 0


def _cmd_probe_plan(args: argparse.Namespace) -> int:
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    templates = json.loads(Path(args.templates).read_text(encoding="utf-8"))
    available = sorted({str(n.get("type")) for s in (templates.get("templates") or {}).values() if isinstance(s, list) for n in s if isinstance(n, dict)})
    wanted = sorted({str(n.get("type")) for n in plan.get("nodes", []) if isinstance(n, dict)})
    missing = [x for x in wanted if x not in available]
    probe_rows = []
    labels = {
        "worldMeshNode": "Create/export one simple mesh node (e.g. cube/plane) from World Builder/entSpawner.",
        "worldCollisionNode": "Create/export one small collision box with known preset/material.",
        "worldStaticMarkerNode": "Create/export one empty/static marker.",
        "worldStaticLightNode": "Create/export one static light with default profile.",
        "worldInteriorAreaNode": "Create/export one small interior area if the exporter exposes it.",
        "worldAmbientAreaNode": "Create/export one ambient area if the exporter exposes it.",
    }
    for typ in missing:
        probe_rows.append({"node_type": typ, "action": labels.get(typ, "Export one real node of this type from the installed toolchain."), "required": True})
    report = {
        "format": "ncig-native-probe-plan-v1",
        "available_node_types": available,
        "required_node_types": wanted,
        "missing_node_types": missing,
        "probes": probe_rows,
        "note": "The probe plan does not fabricate runtime payload fields; it identifies the smallest real exports needed to learn them.",
    }
    write_json(args.out, report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0

def _cmd_merge_harvest(args: argparse.Namespace) -> int:
    harvests = [json.loads(Path(path).read_text(encoding="utf-8")) for path in args.inputs]
    merged = merge_harvests(*harvests)
    write_json(args.out, merged)
    print(json.dumps({"written": args.out, "resource_count": merged["resource_count"], "node_type_mentions": merged["node_type_mentions"]}, indent=2, ensure_ascii=False))
    return 0

def _cmd_plan_lint(args: argparse.Namespace) -> int:
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    report = lint_report(plan)
    write_json(args.out, report)
    print(json.dumps({"written": args.out, **{k: report[k] for k in ("valid", "errors", "warnings")}}, indent=2, ensure_ascii=False))
    return 0 if report["valid"] else 2

def _cmd_modules(args: argparse.Namespace) -> int:
    harvest_path = Path(args.harvest)
    data = json.loads(harvest_path.read_text(encoding="utf-8"))
    library = build_module_library(data)
    write_json(args.out, library)
    print(json.dumps({"written": args.out, **library_report(library)}, indent=2, ensure_ascii=False))
    return 0


def _cmd_decorate(args: argparse.Namespace) -> int:
    data = json.loads(Path(args.layout).read_text(encoding="utf-8"))
    library = json.loads(Path(args.library).read_text(encoding="utf-8"))
    from .model import BuildingAnchor, Layout, Room, Sector, Socket, Vec3
    outputs = []
    for raw in data.get("layouts", []):
        braw = raw["building"]
        bpos = braw["position"]
        b = BuildingAnchor(
            id=braw["id"], district=braw.get("district", ""), type=braw.get("type", "residential"),
            position=Vec3(**bpos), yaw_deg=braw.get("yaw_deg", 0), width_m=braw["width_m"], depth_m=braw["depth_m"],
            floors=braw.get("floors", 1), entry_width_m=braw.get("entry_width_m", 1),
            entry_height_m=braw.get("entry_height_m", 2.1), seed=braw.get("seed"), tags=tuple(braw.get("tags", [])),
            entry_local_x=braw.get("entry_local_x"), entry_local_y=braw.get("entry_local_y"), entry_yaw_deg=braw.get("entry_yaw_deg"),
        )
        layout = Layout(
            b, [Room(**x) for x in raw.get("rooms", [])], [Socket(**x) for x in raw.get("sockets", [])],
            [Sector(id=x["id"], building_id=x["building_id"], floor=x["floor"], category=x["category"], min_xyz=Vec3(**x["min_xyz"]), max_xyz=Vec3(**x["max_xyz"]), rooms=x.get("rooms", [])) for x in raw.get("sectors", [])],
            raw.get("warnings", []),
        )
        outputs.append(decorate_layout(layout, library, density=args.density))
    write_json(args.out, {"format": "ncig-decoration-bundle-v1", "layouts": outputs})
    print(json.dumps({"written": args.out, "buildings": len(outputs), "total_placements": sum(x["placement_count"] for x in outputs), "total_nodes": sum(x["node_count"] for x in outputs)}, indent=2, ensure_ascii=False))
    return 0

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ncig", description="Night City Interior Generator")
    sub = p.add_subparsers(dest="command", required=True)

    g = sub.add_parser("generate")
    g.add_argument("--input", required=True)
    g.add_argument("--out", required=True)
    g.add_argument("--catalog", help="NCIG resource catalog JSON")
    g.add_argument("--playable-shell", action="store_true", help="Add room areas and optional collision shell specs")
    g.add_argument("--collision-preset", help="Exact verified World Builder collision preset; enables collision nodes with --collision-material")
    g.add_argument("--collision-material", help="Exact verified collision material; used with --collision-preset")
    g.set_defaults(func=cmd_generate)

    s = sub.add_parser("scan", help="Turn runtime node observations into entry candidates/anchors")
    s.add_argument("--input", required=True)
    s.add_argument("--out", required=True)
    s.add_argument("--anchors-out")
    s.add_argument("--district", default="unknown")
    s.add_argument("--width", type=float, default=10.0)
    s.add_argument("--depth", type=float, default=10.0)
    s.add_argument("--floors", type=int, default=1)
    s.add_argument("--group-radius", type=float, default=12.0)
    s.set_defaults(func=cmd_scan)

    r = sub.add_parser("routes", help="Match scanned doors to generated building anchors")
    r.add_argument("--buildings", required=True)
    r.add_argument("--scan", required=True)
    r.add_argument("--out", required=True)
    r.set_defaults(func=cmd_routes)

    v = sub.add_parser("validate")
    v.add_argument("--layout", required=True)
    v.set_defaults(func=cmd_validate)

    pv = sub.add_parser("preview")
    pv.add_argument("--layout", required=True)
    pv.add_argument("--out", required=True)
    pv.set_defaults(func=cmd_preview)

    c = sub.add_parser("catalog")
    c.add_argument("--root", required=True, help="Root of a directory extracted/uncooked with WolvenKit")
    c.add_argument("--out", required=True)
    c.set_defaults(func=cmd_catalog)

    xfp = sub.add_parser("exact-fingerprint", help="Fingerprint the exact World Builder Object Spawner envelope")
    xfp.add_argument("--input", required=True)
    xfp.add_argument("--out", required=True)
    xfp.set_defaults(func=_cmd_exact_fingerprint)

    pr = sub.add_parser("probe-relocate", help="Relocate the real worldEntityNode from a supplied World Builder export")
    pr.add_argument("--template", required=True)
    pr.add_argument("--out", required=True)
    pr.add_argument("--dx", type=float, default=0.0)
    pr.add_argument("--dy", type=float, default=0.0)
    pr.add_argument("--dz", type=float, default=3.2)
    pr.set_defaults(func=_cmd_probe)

    ex = sub.add_parser("exact-bridge", help="Build an exact World Builder/Object Spawner JSON from real node templates")
    ex.add_argument("--plan", required=True)
    ex.add_argument("--template", required=True)
    ex.add_argument("--out", required=True)
    ex.set_defaults(func=_cmd_exact_bridge)

    rd = sub.add_parser("readiness", help="Report which NCIG node classes have real templates in a World Builder export")
    rd.add_argument("--plan", required=True)
    rd.add_argument("--template", required=True)
    rd.add_argument("--out", required=True)
    rd.set_defaults(func=_cmd_readiness)

    fp = sub.add_parser("fingerprint", help="Inspect an actual World Builder/Object Spawner export JSON")
    fp.add_argument("--input", required=True)
    fp.add_argument("--out", required=True)
    fp.set_defaults(func=lambda a: _cmd_fingerprint(a))

    br = sub.add_parser("bridge", help="Apply an NCIG world plan to a real Object Spawner export template")
    br.add_argument("--plan", required=True)
    br.add_argument("--template", required=True)
    br.add_argument("--out", required=True)
    br.set_defaults(func=lambda a: _cmd_bridge(a))

    hv = sub.add_parser("harvest", help="Harvest resources and real WB/Object Spawner templates from a World Builder/mod data directory")
    hv.add_argument("--root", required=True, help="Root such as ...\\entSpawner or a mod data folder")
    hv.add_argument("--out", required=True)
    hv.add_argument("--templates-out", help="Also write collected real node templates")
    hv.set_defaults(func=_cmd_harvest)

    sc = sub.add_parser("schema-report", help="Write the public/reference node schema registry used by NCIG")
    sc.add_argument("--out", required=True)
    sc.set_defaults(func=_cmd_schema)

    sb = sub.add_parser("schema-bridge", help="Build Object Spawner JSON from NCIG using public exporter schemas and harvested templates/assets")
    sb.add_argument("--plan", required=True)
    sb.add_argument("--out", required=True)
    sb.add_argument("--base", help="Optional real WB export JSON used only for sector/envelope fields")
    sb.add_argument("--assets", help="ncig-harvest-v1 JSON")
    sb.add_argument("--templates", help="ncig-template-harvest-v1 JSON")
    sb.add_argument("--decoration", help="ncig-decoration-bundle-v1 JSON to compose harvested modules into the native export")
    sb.add_argument("--report", help="Optional sidecar NCIG diagnostics JSON; omitted from the native export itself")
    sb.set_defaults(func=_cmd_schema_bridge)

    rb = sub.add_parser("bind-resources", help="Bind unassigned mesh/entity nodes to deterministic harvested resources")
    rb.add_argument("--plan", required=True)
    rb.add_argument("--assets", required=True, help="ncig-harvest-v1 or ncig-resource-catalog-v2 JSON")
    rb.add_argument("--out", required=True)
    rb.add_argument("--report")
    rb.add_argument("--overwrite", action="store_true")
    rb.set_defaults(func=_cmd_bind_resources)

    rc = sub.add_parser("resource-check", help="Audit resource resolution against a harvested asset catalog")
    rc.add_argument("--plan", required=True)
    rc.add_argument("--assets", required=True)
    rc.add_argument("--out", required=True)
    rc.set_defaults(func=_cmd_resource_check)

    pf = sub.add_parser("preflight", help="Gate native export on template/resource readiness")
    pf.add_argument("--plan", required=True)
    pf.add_argument("--out", required=True)
    pf.add_argument("--assets", help="ncig-harvest-v1 JSON")
    pf.add_argument("--templates", help="ncig-template-harvest-v1 JSON")
    pf.add_argument("--base", help="Optional real World Builder/Object Spawner export")
    pf.set_defaults(func=_cmd_preflight)

    sh = sub.add_parser("sync-harvest", help="Download a public GitHub harvest into a local NCIG cache")
    sh.add_argument("--source", required=True, help="Public GitHub repository URL, e.g. https://github.com/owner/repo")
    sh.add_argument("--out", required=True, help="Destination directory for the local harvest cache")
    sh.add_argument("--ref", default="main")
    sh.add_argument("--required-only", action="store_true", help="Download only harvest.json and templates.json")
    sh.set_defaults(func=_cmd_sync_harvest)

    ac = sub.add_parser("architecture-catalog", help="Build a compact structural/interior asset catalog from ncig-harvest-v1")
    ac.add_argument("--harvest", required=True, help="ncig-harvest-v1 JSON from the harvest command")
    ac.add_argument("--out", required=True)
    ac.add_argument("--max-per-class", type=int, default=250)
    ac.add_argument("--max-total", type=int)
    ac.add_argument("--interior-only", action="store_true", help="Keep only resources classified as interior architecture")
    ac.set_defaults(func=_cmd_architecture_catalog)

    aa = sub.add_parser("architecture-assemble", help="Assemble real harvested architecture pieces around generated rooms")
    aa.add_argument("--layouts", required=True, help="NCIG layouts.json")
    aa.add_argument("--catalog", required=True, help="ncig-architecture-catalog-v1 JSON")
    aa.add_argument("--out", required=True)
    aa.set_defaults(func=_cmd_architecture_assemble)

    ap = sub.add_parser("architecture-apply", help="Apply an architecture assembly to an NCIG world plan")
    ap.add_argument("--plan", required=True)
    ap.add_argument("--assembly", required=True)
    ap.add_argument("--out", required=True)
    ap.set_defaults(func=_cmd_architecture_apply)

    aud = sub.add_parser("architecture-audit", help="Audit catalog/assembly coverage and native export readiness")
    aud.add_argument("--catalog", required=True)
    aud.add_argument("--assembly", required=True)
    aud.add_argument("--out", required=True)
    aud.add_argument("--templates", help="Optional ncig-template-harvest-v1 JSON used to detect real worldMeshNode readiness")
    aud.set_defaults(func=_cmd_architecture_audit)

    np = sub.add_parser("native-probe", help="Inspect one real World Builder/Object Spawner export and optionally extract its node templates")
    np.add_argument("--input", required=True)
    np.add_argument("--out", required=True, help="ncig-native-probe-v1 diagnostic JSON")
    np.add_argument("--templates-out", help="Optional ncig-template-harvest-v1 JSON extracted directly from this export")
    np.add_argument("--base-templates", help="Optional existing ncig-template-harvest-v1 JSON to merge into --templates-out")
    np.set_defaults(func=_cmd_native_probe)

    ane = sub.add_parser("architecture-native-export", help="Emit native Object Spawner mesh nodes from the real harvested worldMeshNode template")
    ane.add_argument("--layouts", required=True, help="NCIG layouts.json")
    ane.add_argument("--assembly", required=True, help="ncig-architecture-assembly-v1 JSON")
    ane.add_argument("--templates", required=True, help="ncig-template-harvest-v1 containing a real worldMeshNode")
    ane.add_argument("--base", required=True, help="Real World Builder/Object Spawner export used for the native envelope/sector schema")
    ane.add_argument("--out", required=True, help="Native Object Spawner JSON output")
    ane.add_argument("--report", help="Optional sidecar diagnostic report")
    ane.add_argument("--building-id", help="Emit only one building; otherwise all buildings present in layouts and assembly")
    ane.set_defaults(func=_cmd_architecture_native_export)

    ana = sub.add_parser("architecture-native-audit", help="Validate native architecture output against the real worldMeshNode template and assembly")
    ana.add_argument("--native", required=True, help="Native Object Spawner JSON produced by architecture-native-export")
    ana.add_argument("--layouts", required=True, help="NCIG layouts.json")
    ana.add_argument("--assembly", required=True, help="ncig-architecture-assembly-v1 JSON")
    ana.add_argument("--templates", required=True, help="ncig-template-harvest-v1 containing a real worldMeshNode")
    ana.add_argument("--out", required=True, help="Audit report JSON")
    ana.add_argument("--building-id", help="Audit only one building")
    ana.add_argument("--decoration", help="Optional ncig-decoration-plan-v2 JSON used to validate emitted worldEntityNode entries")
    ana.set_defaults(func=_cmd_architecture_native_audit)

    dcg = sub.add_parser("decoration-catalog", help="Build a deterministic .ent decoration catalog from a real ncig harvest")
    dcg.add_argument("--harvest", required=True)
    dcg.add_argument("--out", required=True)
    dcg.add_argument("--max-per-role", type=int, default=80)
    dcg.set_defaults(func=_cmd_decoration_catalog)

    dcp = sub.add_parser("decoration-plan", help="Build a room-grammar-driven decoration plan from real .ent resources")
    dcp.add_argument("--layout", required=True)
    dcp.add_argument("--catalog", required=True)
    dcp.add_argument("--out", required=True)
    dcp.add_argument("--building-id")
    dcp.add_argument("--architecture-family")
    dcp.add_argument("--density", type=float, default=1.0)
    dcp.set_defaults(func=_cmd_decoration_plan)

    nco = sub.add_parser("architecture-native-compose", help="Compose native mesh architecture with streaming bounds, optional collisions and real entity decoration")
    nco.add_argument("--layouts", required=True)
    nco.add_argument("--assembly", required=True)
    nco.add_argument("--templates", required=True)
    nco.add_argument("--base", required=True)
    nco.add_argument("--out", required=True)
    nco.add_argument("--report")
    nco.add_argument("--decoration")
    nco.add_argument("--no-collisions", action="store_true")
    nco.add_argument("--streaming-margin", type=float, default=32.0)
    nco.add_argument("--building-id")
    nco.set_defaults(func=_cmd_native_composition)

    bt = sub.add_parser("bounds-targets", help="Write the list of runtime .mesh resources whose real bounding boxes should be harvested")
    bt.add_argument("--catalog", required=True, help="ncig-architecture-catalog-v1 JSON")
    bt.add_argument("--out", required=True, help="ncig-architecture-bounds-targets-v1 JSON")
    bt.set_defaults(func=_cmd_build_bounds_targets)

    mb = sub.add_parser("merge-bounds", help="Merge runtime mesh bounding boxes into an architecture catalog")
    mb.add_argument("--catalog", required=True)
    mb.add_argument("--bounds", required=True, help="ncig-architecture-bounds-v1 JSON")
    mb.add_argument("--out", required=True)
    mb.add_argument("--report")
    mb.set_defaults(func=_cmd_merge_bounds)

    db = sub.add_parser("detect-buildings", help="Detect probable decorative/missing-interior building candidates from exported streamingsector JSON")
    db.add_argument("--input", required=True, help="A .streamingsector JSON file or a directory containing exported sector JSONs")
    db.add_argument("--out", required=True, help="ncig-building-candidates-v1 JSON")
    db.add_argument("--radius", type=float, default=18.0, help="Architecture-to-entrance search radius in metres")
    db.set_defaults(func=_cmd_detect_buildings)

    dcity = sub.add_parser("detect-city-buildings", help="City-scale detector for a large default/streamingsector JSON export")
    dcity.add_argument("--input", required=True, help="Directory or single JSON export from the base-game world")
    dcity.add_argument("--out", required=True, help="ncig-city-building-candidates-v1 JSON")
    dcity.add_argument("--radius", type=float, default=18.0, help="Architecture-to-entrance search radius in metres")
    dcity.set_defaults(func=_cmd_detect_city_buildings)

    ic = sub.add_parser("index-city-world", help="Build a persistent SQLite index from a large native streamingsector JSON export")
    ic.add_argument("--input", required=True)
    ic.add_argument("--out", required=True, help="SQLite database output")
    ic.add_argument("--manifest-out", required=True, help="JSON manifest output")
    ic.set_defaults(func=_cmd_index_city)

    ij = sub.add_parser("inspect-city-json", help="Inspect one WolvenKit streamingsector JSON without scanning the whole export")
    ij.add_argument("--input", required=True)
    ij.add_argument("--out", required=True)
    ij.set_defaults(func=_cmd_inspect_city_json)

    cb = sub.add_parser("candidates-to-buildings", help="Convert automatic building candidates into NCIG building anchors")
    cb.add_argument("--input", required=True, help="ncig-building-candidates-v1 JSON")
    cb.add_argument("--out", required=True, help="buildings.json")
    cb.add_argument("--min-score", type=int, default=75)
    cb.add_argument("--max-count", type=int)
    cb.add_argument("--include-review", action="store_true", help="Include candidates marked for manual review")
    cb.set_defaults(func=_cmd_candidates_to_buildings)

    pp = sub.add_parser("probe-plan", help="List missing real World Builder node templates needed by a plan")
    pp.add_argument("--plan", required=True)
    pp.add_argument("--templates", required=True)
    pp.add_argument("--out", required=True)
    pp.set_defaults(func=_cmd_probe_plan)


    mh = sub.add_parser("merge-harvest", help="Merge multiple ncig-harvest-v1 JSON catalogs")
    mh.add_argument("--inputs", nargs="+", required=True)
    mh.add_argument("--out", required=True)
    mh.set_defaults(func=_cmd_merge_harvest)

    pl = sub.add_parser("plan-lint", help="Validate floor assignments, sectors and nodeRef invariants in an NCIG world plan")
    pl.add_argument("--plan", required=True)
    pl.add_argument("--out", required=True)
    pl.set_defaults(func=_cmd_plan_lint)

    ml = sub.add_parser("modules", help="Build a reusable module library from harvested World Builder/mod templates")
    ml.add_argument("--harvest", required=True, help="ncig-template-harvest-v1 JSON from the harvest command")
    ml.add_argument("--out", required=True)
    ml.set_defaults(func=_cmd_modules)

    dc = sub.add_parser("decorate", help="Place harvested modules into generated rooms")
    dc.add_argument("--layout", required=True, help="NCIG layouts.json")
    dc.add_argument("--library", required=True, help="ncig-module-library-v1 JSON")
    dc.add_argument("--out", required=True)
    dc.add_argument("--density", type=float, default=0.65)
    dc.set_defaults(func=_cmd_decorate)

    vw = sub.add_parser("viewer")
    vw.add_argument("--preview-dir", required=True)
    vw.add_argument("--out", required=True)
    vw.set_defaults(func=cmd_viewer)
    return p


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)

if __name__ == "__main__":
    raise SystemExit(main())
