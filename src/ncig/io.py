from __future__ import annotations

from . import __version__

import json
from pathlib import Path
from typing import Any

from .model import BuildingAnchor, Vec3, Layout


def load_buildings(path: str | Path) -> list[BuildingAnchor]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    result: list[BuildingAnchor] = []
    for raw in data.get("buildings", []):
        result.append(BuildingAnchor(
            id=raw["id"],
            district=raw.get("district", "unknown"),
            type=raw.get("type", "residential"),
            position=Vec3(**raw.get("position", {"x": 0, "y": 0, "z": 0})),
            yaw_deg=float(raw.get("yaw_deg", 0)),
            width_m=float(raw["width_m"]),
            depth_m=float(raw["depth_m"]),
            floors=int(raw.get("floors", 1)),
            entry_width_m=float(raw.get("entry_width_m", 1.0)),
            entry_height_m=float(raw.get("entry_height_m", 2.1)),
            seed=raw.get("seed"),
            tags=tuple(raw.get("tags", [])),
            entry_local_x=raw.get("entry_local_x"),
            entry_local_y=raw.get("entry_local_y"),
            entry_yaw_deg=raw.get("entry_yaw_deg"),
        ))
    return result


def write_json(path: str | Path, obj: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def bundle_layouts(layouts: list[Layout]) -> dict[str, Any]:
    return {
        "format": "ncig-layout-v1",
        "generator_version": __version__,
        "layouts": [x.to_dict() for x in layouts],
    }
