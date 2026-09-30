from __future__ import annotations

from pathlib import Path
from typing import Any

from .model import Layout
from .io import write_json
from .worldplan import build_world_plan


def build_wb_plan(layout: Layout, resource_catalog: dict[str, str] | None = None) -> dict[str, Any]:
    catalog = resource_catalog or {}
    objects = []
    for room in layout.rooms:
        objects.append({
            "logical_type": "room_shell",
            "id": room.id,
            "source_room_kind": room.kind,
            "floor": room.floor,
            "local_rect": {"x": room.x, "y": room.y, "w": room.width, "d": room.depth},
        })
    for socket in layout.sockets:
        objects.append({
            "logical_type": socket.kind,
            "id": socket.id,
            "room_id": socket.room_id,
            "world": {"x": socket.x, "y": socket.y, "z": socket.z},
            "rotation_deg": socket.rotation_deg,
            "semantic": socket.semantic,
            "resource": catalog.get(socket.semantic or ""),
            "properties": socket.properties,
        })
    return {
        "format": "ncig-wb-plan-v1",
        "native_world_builder_file": False,
        "note": "Legacy intermediate representation; use ncig-world-plan-v3 for v0.2.",
        "building_id": layout.building.id,
        "district": layout.building.district,
        "sectors": [
            {
                "id": s.id,
                "category": s.category,
                "floor": s.floor,
                "extents": {
                    "min": {"x": s.min_xyz.x, "y": s.min_xyz.y, "z": s.min_xyz.z},
                    "max": {"x": s.max_xyz.x, "y": s.max_xyz.y, "z": s.max_xyz.z},
                },
                "rooms": s.rooms,
            }
            for s in layout.sectors
        ],
        "objects": objects,
    }


def write_wb_plans(layouts: list[Layout], out_dir: str | Path, resource_catalog: dict[str, str] | None = None) -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for layout in layouts:
        path = out / f"{layout.building.id}_wb_plan.json"
        write_json(path, build_wb_plan(layout, resource_catalog))
        paths.append(path)
        world_path = out / f"{layout.building.id}_world_plan_v2.json"
        write_json(world_path, build_world_plan(layout))
        paths.append(world_path)
    return paths
