from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Literal, Any

BuildingType = Literal["residential", "commercial", "office", "industrial", "mixed"]


@dataclass(frozen=True)
class Vec3:
    x: float
    y: float
    z: float


@dataclass(frozen=True)
class BuildingAnchor:
    id: str
    district: str
    type: BuildingType
    position: Vec3
    yaw_deg: float
    width_m: float
    depth_m: float
    floors: int = 1
    entry_width_m: float = 1.0
    entry_height_m: float = 2.1
    seed: int | None = None
    tags: tuple[str, ...] = ()
    # Optional local-space entrance anchor populated by automatic exterior detection.
    entry_local_x: float | None = None
    entry_local_y: float | None = None
    entry_yaw_deg: float | None = None
    # Exterior facade openings discovered in the real-world sector export.
    detected_openings: tuple[dict[str, Any], ...] = ()


@dataclass
class Room:
    id: str
    kind: str
    floor: int
    x: float
    y: float
    width: float
    depth: float
    rotation_deg: float = 0.0
    is_start: bool = False
    is_exit: bool = False


@dataclass
class Socket:
    id: str
    kind: str
    room_id: str
    x: float
    y: float
    z: float
    rotation_deg: float = 0.0
    semantic: str | None = None
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class Sector:
    id: str
    building_id: str
    floor: int
    category: str
    min_xyz: Vec3
    max_xyz: Vec3
    rooms: list[str] = field(default_factory=list)


@dataclass
class Layout:
    building: BuildingAnchor
    rooms: list[Room]
    sockets: list[Socket]
    sectors: list[Sector]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "building": asdict(self.building),
            "rooms": [asdict(x) for x in self.rooms],
            "sockets": [asdict(x) for x in self.sockets],
            "sectors": [asdict(x) for x in self.sectors],
            "warnings": self.warnings,
        }
