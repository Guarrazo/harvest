from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from .generator import world_pos
from .architecture_geometry import compatible_family_candidates, dimension_hint_scale, planar_dimensions, rank_family_options, sane_dimensions
from .model import Layout, Room, Vec3
from .interior_quality import door_clearance_report, door_opening_width, filter_asset_candidates, choose_variety_index
from .runtime_geometry import (
    align_node_local_position,
    linear_fit,
    preferred_surface_rotation,
    scaled_bbox_height,
    surface_scale,
    surface_world_dimensions,
)

FORMAT = "ncig-architecture-assembly-v1"
FLOOR_HEIGHT = 3.2
CEILING_Z = 3.0
DEFAULT_DOOR_WIDTH = 1.2


def _items(
    catalog: dict[str, Any],
    cls: str,
    family: str | None = None,
    building_type: str | None = None,
    *,
    room_kind: str | None = None,
) -> list[dict[str, Any]]:
    building_type = building_type or "mixed"
    tokens = _style_tokens(building_type)
    candidates = compatible_family_candidates(catalog, cls, family, building_tokens=tokens)
    return filter_asset_candidates(
        candidates,
        cls=cls,
        building_type=building_type,
        room_kind=room_kind,
    )


def _style_tokens(building_type: str) -> tuple[str, ...]:
    return {
        "commercial": ("shop", "store", "market", "retail", "mall", "restaurant", "bar", "int"),
        "residential": ("apartment", "res", "housing", "home", "flat", "common\\int"),
        "office": ("office", "corp", "corporate", "business", "int"),
        "industrial": ("industrial", "factory", "warehouse", "workshop", "garage"),
        "mixed": ("shop", "office", "apartment", "common\\int"),
    }.get(building_type, ("int",))


def _door_candidate_pool(
    candidates_or_catalog: dict[str, Any] | list[dict[str, Any]],
    cls: str = "door_piece",
    family: str | None = None,
    building_type: str = "mixed",
    room_kind: str | None = None,
    target_width: float = DEFAULT_DOOR_WIDTH,
    target_height: float = 2.1,
) -> list[dict[str, Any]]:
    """Return door/frame candidates that can fit without extreme down-scaling.

    Security/gate assets are excluded for ordinary rooms, but remain valid for explicit
    security/checkpoint rooms. Candidates with dimensions unavailable are retained.
    """
    if isinstance(candidates_or_catalog, dict):
        candidates = _items(
            candidates_or_catalog,
            cls,
            family,
            building_type,
            room_kind=room_kind,
        )
    else:
        candidates = list(candidates_or_catalog)

    security_room = str(room_kind or "").lower() in {
        "security", "checkpoint", "guard", "guardroom", "security_room"
    }
    out: list[dict[str, Any]] = []
    max_source_width = float(target_width) / 0.72 if target_width > 0 else float("inf")
    max_source_height = float(target_height) / 0.80 if target_height > 0 else float("inf")
    for item in candidates:
        text = " ".join(
            str(v) for v in (
                item.get("path"),
                item.get("family"),
                *(item.get("signals") or []),
                *(item.get("roles") or []),
            )
        ).lower()
        security_asset = any(token in text for token in (
            "security", "checkpoint", "guard", "gate", "grille", "grating", "bars", "barred"
        ))
        if security_asset and not security_room:
            continue

        span = _length_hint(item)
        height = _height_hint(item)
        if span is not None and span > max_source_width:
            continue
        if height is not None and height > max_source_height:
            continue
        out.append(item)
    return out or candidates


def choose_architecture_family(catalog: dict[str, Any], building_type: str) -> tuple[str | None, dict[str, Any]]:
    """Pick one architectural kit family for a whole building, rather than one unrelated family per piece."""
    items = [x for x in catalog.get("items", []) if isinstance(x, dict) and x.get("class")]
    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        family = str(item.get("family") or "unknown")
        if family != "unknown":
            by_family[family].append(item)

    core = ("floor_piece", "wall_piece", "ceiling_piece")
    secondary = ("door_frame", "door_piece", "window_piece")
    candidates: list[tuple[float, str, dict[str, Any]]] = []
    tokens = _style_tokens(building_type)
    for family, family_items in by_family.items():
        classes = {str(x.get("class")) for x in family_items}
        core_cov = sum(1 for cls in core if cls in classes)
        sec_cov = sum(1 for cls in secondary if cls in classes)
        if core_cov < 2:
            continue
        complete = sum(1 for x in family_items if bool((x.get("dimensions") or {}).get("complete")))
        score_mean = sum(float(x.get("score", 0)) for x in family_items) / max(1, len(family_items))
        style_hits = sum(1 for token in tokens if token in family.lower())
        sane_core = sum(1 for x in family_items if str(x.get("class")) in core and sane_dimensions(x, str(x.get("class"))))
        # Core coverage and sane dimensions dominate. A family that has only a token
        # match but no usable floor/wall/ceiling is not a valid building kit.
        total = core_cov * 850 + sane_core * 180 + sec_cov * 70 + min(20, complete) * 8 + score_mean
        total += style_hits * 80
        info = {
            "family": family,
            "core_coverage": core_cov,
            "sane_core_coverage": sane_core,
            "secondary_coverage": sec_cov,
            "complete_dimension_items": complete,
            "style_hits": style_hits,
            "family_item_count": len(family_items),
            "style_tokens": tokens,
        }
        candidates.append((total, family, info))
    if not candidates:
        return None, {"family": None, "reason": "no_family_with_structural_coverage"}
    candidates.sort(key=lambda row: (-row[0], row[1]))
    _, family, info = candidates[0]
    info["selection_score"] = round(candidates[0][0], 3)
    return family, info



def choose_class_families(catalog: dict[str, Any], primary_family: str | None, building_type: str) -> tuple[dict[str, str], dict[str, Any]]:
    tokens = _style_tokens(building_type)
    classes = (
        "floor_piece", "wall_piece", "ceiling_piece", "door_frame", "door_piece",
        "window_piece", "pillar_piece", "stairs_piece", "rail_piece", "trim_piece",
    )
    families: dict[str, str] = {}
    report: dict[str, Any] = {}
    for cls in classes:
        ranked = rank_family_options(catalog, cls, primary_family, building_tokens=tokens)
        if not ranked:
            continue
        score, family, mode = ranked[0]
        families[cls] = family
        report[cls] = {"family": family, "mode": mode, "selection_score": round(score, 3), "candidates": len(ranked)}
    return families, report

def _dims(item: dict[str, Any]) -> dict[str, float]:
    span, secondary, height = planar_dimensions(item, str(item.get("class") or ""))
    return {
        "l": float(span or 0.0),
        "w": float(secondary or 0.0),
        "h": float(height or 0.0),
    }


def _length_hint(item: dict[str, Any]) -> float | None:
    span, _, _ = planar_dimensions(item, str(item.get("class") or ""))
    return float(span) if isinstance(span, (int, float)) and span > 0 else None


def _floor_dims(item: dict[str, Any]) -> tuple[float | None, float | None]:
    span, secondary, _ = planar_dimensions(item, str(item.get("class") or ""))
    return (
        float(span) if isinstance(span, (int, float)) and span > 0 else None,
        float(secondary) if isinstance(secondary, (int, float)) and secondary > 0 else None,
    )


def _height_hint(item: dict[str, Any]) -> float | None:
    _, _, height = planar_dimensions(item, str(item.get("class") or ""))
    return float(height) if isinstance(height, (int, float)) and height > 0 else None


def _best_item(items: list[dict[str, Any]], *, target_length: float | None = None,
               target_width: float | None = None, target_height: float | None = None,
               variety_key: str | None = None) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    if not items:
        return None, {"confidence": "none", "reason": "no_catalog_candidates"}
    ranked: list[tuple[float, int, str, dict[str, Any], dict[str, Any]]] = []
    required = []
    if target_length is not None:
        required.append("length")
    if target_width is not None:
        required.append("width")
    if target_height is not None:
        required.append("height")
    for item in items:
        d = _dims(item)
        score = float(item.get("score", 0)) + float((item.get("_ncig_quality") or {}).get("adjustment", 0.0))
        errors: list[float] = []
        missing = 0