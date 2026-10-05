from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from dataclasses import replace

from .architecture_assembler import build_architecture_assembly
from .model import BuildingAnchor, Layout, Room, Sector, Socket, Vec3

VERSION = "0.24.0"


def _load(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _layout(raw: dict) -> Layout:
    b = raw["building"]
    building = BuildingAnchor(
        id=b["id"], district=b.get("district", ""), type=b.get("type", "mixed"),
        position=Vec3(**b["position"]), yaw_deg=b.get("yaw_deg", 0.0),
        width_m=b["width_m"], depth_m=b["depth_m"], floors=b.get("floors", 1),
        entry_width_m=b.get("entry_width_m", 1.0), entry_height_m=b.get("entry_height_m", 2.1),
        seed=b.get("seed"), tags=tuple(b.get("tags", [])),
        entry_local_x=b.get("entry_local_x"), entry_local_y=b.get("entry_local_y"),
        entry_yaw_deg=b.get("entry_yaw_deg"),
        detected_openings=tuple(x for x in b.get("detected_openings", []) if isinstance(x, dict)),
    )
    rooms = [Room(**x) for x in raw.get("rooms", [])]
    sockets = [Socket(**x) for x in raw.get("sockets", [])]
    sectors = [Sector(
        id=x["id"], building_id=x["building_id"], floor=x["floor"], category=x["category"],
        min_xyz=Vec3(**x["min_xyz"]), max_xyz=Vec3(**x["max_xyz"]), rooms=x.get("rooms", []),
    ) for x in raw.get("sectors", [])]
    return Layout(building, rooms, sockets, sectors, raw.get("warnings", []))


def build_style_aware_assembly(layouts_path: str | Path, profiles_path: str | Path, catalog_path: str | Path, out_path: str | Path) -> dict:
    bundle = _load(layouts_path)
    profiles = _load(profiles_path)
    catalog_raw = _load(catalog_path)
    catalog = catalog_raw.get("catalog", catalog_raw)
    profile_map = {str(c.get("id")): c.get("style_profile", {}) for c in profiles.get("candidates", []) if isinstance(c, dict)}
    import ncig.architecture_assembler as aa
    original_district_tokens = copy.deepcopy(aa._DISTRICT_STYLE_TOKENS)
    adapted: list[Layout] = []
    synthetic_keys: list[str] = []
    try:
        for raw in bundle.get("layouts", []) or []:
            layout = _layout(raw)
            profile = profile_map.get(layout.building.id, {})
            tokens = tuple(str(x).lower() for x in profile.get("style_tokens", []) if x)
            if tokens:
                key = f"__ncig_style_{layout.building.id}"
                aa._DISTRICT_STYLE_TOKENS[key] = tokens
                adapted.append(replace(layout, building=replace(layout.building, district=key)))
                synthetic_keys.append(key)
            else:
                adapted.append(layout)
        result = build_architecture_assembly(adapted, catalog)
        for building in result.get("buildings", []) or []:
            bid = str(building.get("id"))
            profile = profile_map.get(bid)
            if profile:
                building["exterior_style_profile"] = profile
                building.setdefault("architecture_kit", {})["exterior_style_profile"] = profile
        result["format"] = "ncig-architecture-assembly-style-aware-v1"
        result["version"] = VERSION
        result["style_profiles_consumed"] = len(profile_map)
    finally:
        aa._DISTRICT_STYLE_TOKENS.clear()
        aa._DISTRICT_STYLE_TOKENS.update(original_district_tokens)
    p = Path(out_path); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


def main() -> int:
    p = argparse.ArgumentParser(description="NCIG 0.24.0 style-aware architecture assembly")
    p.add_argument("--layouts", required=True)
    p.add_argument("--profiles", required=True)
    p.add_argument("--catalog", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args()
    result = build_style_aware_assembly(args.layouts, args.profiles, args.catalog, args.out)
    print(json.dumps({"buildings": len(result.get("buildings", [])), "placements": sum(int(x.get("placement_count", 0)) for x in result.get("buildings", [])), "style_profiles_consumed": result.get("style_profiles_consumed", 0)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
