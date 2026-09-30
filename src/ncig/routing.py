from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from .model import BuildingAnchor, Layout, Socket
from .scanner import NodeObservation


@dataclass(frozen=True)
class EntranceRoute:
    route_id: str
    building_id: str
    existing_node_name: str
    existing_node_ref: str
    sector_path: str
    action: str
    target_floor: int
    target_socket_id: str
    distance_m: float
    properties: dict[str, Any]


def nearest_start_socket(layout: Layout) -> Socket | None:
    entries = [s for s in layout.sockets if s.kind == "entry"]
    if entries:
        return entries[0]
    starts = [s for s in layout.sockets if s.kind == "door"]
    if not starts:
        return None
    return starts[0]


def build_entrance_route(anchor: BuildingAnchor, layout: Layout, observation: NodeObservation) -> EntranceRoute:
    target = nearest_start_socket(layout)
    if target is None:
        raise ValueError(f"{anchor.id}: generated layout has no door socket")
    dx = target.x - observation.position.x
    dy = target.y - observation.position.y
    dz = target.z - observation.position.z
    return EntranceRoute(
        route_id=f"{anchor.id}_entrance_route",
        building_id=anchor.id,
        existing_node_name=observation.name,
        existing_node_ref=observation.node_ref,
        sector_path=observation.sector_path,
        action="link_existing_node",
        target_floor=0,
        target_socket_id=target.id,
        distance_m=(dx * dx + dy * dy + dz * dz) ** 0.5,
        properties={
            "runtime_strategy": "existing_door_or_proxy",
            "fallback": "spawn_proxy_door",
            "same_position_threshold_m": 1.5,
        },
    )


def route_to_dict(route: EntranceRoute) -> dict[str, Any]:
    return asdict(route)
