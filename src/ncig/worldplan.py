from __future__ import annotations

from . import __version__

from typing import Any

from .architecture import ArchElement, build_architecture
from .model import Layout
from .shell import build_playable_shell

SUPPORTED_NODE_TYPES = {
    "floor": "worldMeshNode",
    "ceiling": "worldMeshNode",
    "wall_segment": "worldMeshNode",
    "prop": "worldMeshNode",
    "door": "worldEntityNode",
    "entry": "worldStaticMarkerNode",
    "light": "worldStaticLightNode",
    "collision": "worldCollisionNode",
    "ai_spot": "worldAISpotNode",
    "community": "worldCompiledCommunityAreaNode_Streamable",
    "interior_area": "worldInteriorAreaNode",
    "ambient_area": "worldAmbientAreaNode",
    "marker": "worldStaticMarkerNode",
}


def _default_ranges(element_type: str) -> tuple[float, float]:
    if element_type in {"wall_segment", "floor", "ceiling", "collision"}:
        return 80.0, 120.0
    if element_type in {"prop", "light", "door"}:
        return 40.0, 60.0
    return 80.0, 120.0


def _quaternion_yaw(yaw_deg: float) -> dict[str, float]:
    # Yaw-only quaternion.
    import math
    half = math.radians(yaw_deg) / 2.0
    return {"i": 0.0, "j": 0.0, "k": math.sin(half), "r": math.cos(half)}


def build_connectivity(layout: Layout) -> dict[str, Any]:
    """Build a logical walk/connectivity graph for the generated interior.

    This is planner metadata, not a native game navigation mesh. It gives the runtime
    mod/export layer an explicit contract for entrance, room-door and vertical-core links.
    """
    by_room = {r.id: r for r in layout.rooms}
    edges: list[dict[str, Any]] = []
    graph_nodes: list[dict[str, Any]] = []

    entries = [s for s in layout.sockets if s.kind == "entry"]
    for entry in entries:
        graph_nodes.append({"id": entry.id, "kind": "entry", "floor": 0, "room_id": entry.room_id})

    doors = [s for s in layout.sockets if s.kind == "door"]
    activities = [s for s in layout.sockets if s.kind == "activity"]
    for socket in doors + activities:
        room = by_room.get(socket.room_id)
        if room is None:
            continue
        graph_nodes.append({"id": socket.id, "kind": socket.kind, "floor": room.floor, "room_id": room.id})

    # Each room's activity socket is reachable from its door socket.
    for room in layout.rooms:
        door = next((s for s in doors if s.room_id == room.id), None)
        activity = next((s for s in activities if s.room_id == room.id), None)
        if door and activity:
            edges.append({"from": door.id, "to": activity.id, "type": "room_access", "floor": room.floor})

    # The building entry reaches the first room on the ground floor.
    if entries and doors:
        ground_doors = [s for s in doors if by_room.get(s.room_id) and by_room[s.room_id].floor == 0]
        if ground_doors:
            first = min(ground_doors, key=lambda s: (by_room[s.room_id].x, by_room[s.room_id].y, s.id))
            edges.append({"from": entries[0].id, "to": first.id, "type": "entrance_access", "floor": 0})

    # All rooms on a floor connect to that floor's vertical core.
    core_ids = []
    for floor in range(max(1, layout.building.floors)):
        core_id = f"{layout.building.id}_F{floor+1:02d}_core"
        core_ids.append(core_id)
        graph_nodes.append({"id": core_id, "kind": "vertical_core", "floor": floor, "room_id": None})
        floor_doors = [s for s in doors if by_room.get(s.room_id) and by_room[s.room_id].floor == floor]
        for door in floor_doors:
            edges.append({"from": door.id, "to": core_id, "type": "corridor_access", "floor": floor})
            edges.append({"from": core_id, "to": door.id, "type": "corridor_access", "floor": floor})

    # Explicit vertical links give the runtime layer a deterministic traversal contract.
    for floor in range(len(core_ids) - 1):
        a, b = core_ids[floor], core_ids[floor + 1]
        edges.append({"from": a, "to": b, "type": "vertical_transition", "from_floor": floor, "to_floor": floor + 1})
        edges.append({"from": b, "to": a, "type": "vertical_transition", "from_floor": floor + 1, "to_floor": floor})

    return {
        "format": "ncig-connectivity-v1",
        "nodes": graph_nodes,
        "edges": edges,
        "validation": {
            "has_entry": bool(entries),
            "has_vertical_core": bool(core_ids),
            "vertical_link_count": max(0, len(core_ids) - 1) * 2,
        },
    }


def build_world_plan(
    layout: Layout,
    resource_catalog: dict[str, list[str] | str] | None = None,
    *,
    playable_shell: bool = False,
    collision_preset: str | None = None,
    collision_material: str | None = None,
) -> dict[str, Any]:
    catalog = resource_catalog or {}
    architecture = build_architecture(layout)
    nodes: list[dict[str, Any]] = []

    for element in architecture:
        primary, secondary = _default_ranges(element.element_type)
        semantic = element.material_role
        resource = catalog.get(semantic)
        if isinstance(resource, list):
            resource = resource[0] if resource else None
        node_type = SUPPORTED_NODE_TYPES[element.element_type]
        nodes.append({
            "name": element.id,
            "type": node_type,
            "floor": element.floor,
            "nodeRef": f"$/#{layout.building.id}_{element.id}",
            "position": {"x": element.position.x, "y": element.position.y, "z": element.position.z},
            "rotation": _quaternion_yaw(layout.building.yaw_deg + element.rotation_deg),
            "scale": {"x": 1.0, "y": 1.0, "z": 1.0},
            "primaryRange": primary,
            "secondaryRange": secondary,
            "uk10": 32,
            "uk11": 512,
            "streamingRefPoint": {"x": element.position.x, "y": element.position.y, "z": element.position.z},
            "data": {
                "logicalType": element.element_type,
                "materialRole": element.material_role,
                "roomId": element.room_id,
                "size": {"x": element.size.x, "y": element.size.y, "z": element.size.z},
                "resource": resource,
                "opening": element.opening,
                **(element.properties or {}),
            },
        })

    # Add a dedicated circulation/core plane per floor.
    floor_height = 3.2
    for floor in range(max(1, layout.building.floors)):
        floor_rooms = [r for r in layout.rooms if r.floor == floor]
        if not floor_rooms:
            continue
        min_x = min(r.x for r in floor_rooms)
        max_x = max(r.x + r.width for r in floor_rooms)
        corridor_y = 0.0
        z = layout.building.position.z + floor * floor_height + 0.02
        import math
        p = layout.building.position
        nodes.append({
            "name": f"{layout.building.id}_F{floor+1:02d}_circulation_floor",
            "type": "worldMeshNode",
            "nodeRef": f"$/#{layout.building.id}_F{floor+1:02d}_circulation_floor",
            "position": {"x": p.x, "y": p.y, "z": z},
            "rotation": _quaternion_yaw(layout.building.yaw_deg),
            "floor": floor,
            "scale": {"x": 1.0, "y": 1.0, "z": 1.0},
            "primaryRange": 80.0, "secondaryRange": 120.0,
            "uk10": 32, "uk11": 512,
            "data": {
                "logicalType": "circulation_floor",
                "localBounds": {"minX": min_x, "maxX": max_x, "halfWidth": 0.8, "floor": floor},
                "resourceRole": "floor",
            },
        })
        nodes.append({
            "name": f"{layout.building.id}_F{floor+1:02d}_core_marker",
            "type": "worldStaticMarkerNode",
            "nodeRef": f"$/#{layout.building.id}_F{floor+1:02d}_core",
            "position": {"x": p.x, "y": p.y, "z": z},
            "rotation": _quaternion_yaw(layout.building.yaw_deg),
            "floor": floor,
            "scale": {"x": 1.0, "y": 1.0, "z": 1.0},
            "primaryRange": 50.0, "secondaryRange": 75.0,
            "uk10": 32, "uk11": 512,
            "data": {"logicalType": "vertical_core", "stairs_or_elevator": True},
        })

    # Convert logical sockets to node specifications. Actual entity/mesh properties
    # are intentionally catalog-driven and kept isolated from the procedural core.
    for socket in layout.sockets:
        primary, secondary = _default_ranges(socket.kind)
        node_type = SUPPORTED_NODE_TYPES.get(socket.kind, "worldStaticMarkerNode")
        resource = catalog.get(socket.semantic or "")
        if isinstance(resource, list):
            resource = resource[0] if resource else None
        room_floor = next((r.floor for r in layout.rooms if r.id == socket.room_id), 0)
        nodes.append({
            "name": socket.id,
            "type": node_type,
            "floor": room_floor,
            "nodeRef": f"$/#{layout.building.id}_{socket.id}",
            "position": {"x": socket.x, "y": socket.y, "z": socket.z},
            "rotation": _quaternion_yaw(socket.rotation_deg),
            "scale": {"x": 1.0, "y": 1.0, "z": 1.0},
            "primaryRange": primary,
            "secondaryRange": secondary,
            "uk10": 32,
            "uk11": 512,
            "streamingRefPoint": {"x": socket.x, "y": socket.y, "z": socket.z},
            "data": {
                "semantic": socket.semantic,
                "resource": resource,
                "roomId": socket.room_id,
                "properties": socket.properties,
            },
        })

    shell = None
    if playable_shell:
        shell = build_playable_shell(
            layout,
            collision_preset=collision_preset,
            collision_material=collision_material,
        )
        # Shell node specs are part of the same floor-partitioned plan, so the existing
        # bridge/linter can validate and route them without a second export format.
        nodes.extend(shell.get("nodes", []))

    sectors = []
    for sector in layout.sectors:
        sectors.append({
            "name": sector.id,
            "floor": sector.floor,
            "category": "Interior",
            "level": 2 if sector.floor == 0 else 3,
            "min": {"x": sector.min_xyz.x, "y": sector.min_xyz.y, "z": sector.min_xyz.z},
            "max": {"x": sector.max_xyz.x, "y": sector.max_xyz.y, "z": sector.max_xyz.z},
            "nodeRefs": [n["nodeRef"] for n in nodes if n["name"].startswith(f"{layout.building.id}_F{sector.floor+1:02d}")],
        })

    return {
        "format": "ncig-world-plan-v3",
        "game_version_target": "2.31",
        "building_id": layout.building.id,
        "generator_version": __version__,
        "native_world_builder_file": False,
        "world_builder_export_shape": "entSpawner/object-spawner compatible plan",
        "notes": [
            "This file is an NCIG planning/export artifact, not a native CR2W file.",
            "Node type names follow the documented World Builder node model.",
            "Resource references must come from the user's extracted/catalogued game assets.",
        ],
        "sectors": sectors,
        "nodes": nodes,
        "connectivity": build_connectivity(layout),
        "playable_shell": shell,
    }
