from __future__ import annotations

import hashlib
import re
from typing import Any, Iterable


FORMAT = "ncig-interior-quality-v1"

# These are engineering targets for generated human-scale openings, not claims about
# an official Cyberpunk 2077 player-collision specification.
MIN_CLEAR_WIDTH_M = 0.95
PREFERRED_CLEAR_WIDTH_M = 1.05
PREFERRED_CLEAR_HEIGHT_M = 2.10

# The generator's structural taxonomy is intentionally broader than the style layer.
# Style is inferred from harvested resource/family names and is always explainable in
# the placement report.
_STYLE_PROFILES: dict[str, dict[str, tuple[str, ...]]] = {
    "residential": {
        "preferred": ("apartment", "res", "housing", "home", "flat", "common\\int", "domestic"),
        "door_avoid": ("prison", "jail", "cell", "cage", "grate", "grille"),
        "wall_avoid": ("prison", "jail", "cell", "fence", "cage", "grille", "grating", "railing"),
    },
    "commercial": {
        "preferred": ("shop", "store", "market", "retail", "mall", "restaurant", "bar", "common\\int"),
        "door_avoid": ("prison", "jail", "cell", "cage"),
        "wall_avoid": ("prison", "jail", "cell", "fence", "cage", "grille", "grating", "railing"),
    },
    "office": {
        "preferred": ("office", "corp", "corporate", "business", "common\\int"),
        "door_avoid": ("prison", "jail", "cell", "cage", "grate", "grille"),
        "wall_avoid": ("prison", "jail", "cell", "fence", "cage", "grille", "grating", "railing"),
    },
    "industrial": {
        "preferred": ("industrial", "factory", "warehouse", "workshop", "garage"),
        "door_avoid": ("prison", "jail", "cell"),
        "wall_avoid": ("prison", "jail", "cell", "fence", "cage"),
    },
    "mixed": {
        "preferred": ("shop", "office", "apartment", "common\\int", "mixed"),
        "door_avoid": ("prison", "jail", "cell", "cage", "grate", "grille"),
        "wall_avoid": ("prison", "jail", "cell", "fence", "cage", "grille", "grating", "railing"),
    },
}


def _text(item: dict[str, Any]) -> str:
    values = [
        str(item.get("path") or ""),
        str(item.get("family") or ""),
        " ".join(str(x) for x in (item.get("signals") or [])),
        " ".join(str(x) for x in (item.get("roles") or [])),
    ]
    return " ".join(values).replace("/", "\\").lower()


def _has(text: str, token: str) -> bool:
    # Resource paths are not natural-language strings, so substring matching is
    # preferable to word-boundary matching for names such as common\\int.
    return token.lower() in text


def style_profile(building_type: str) -> dict[str, Any]:
    profile = _STYLE_PROFILES.get(str(building_type), _STYLE_PROFILES["mixed"])
    return {
        "building_type": str(building_type),
        "preferred_tokens": tuple(profile["preferred"]),
        "door_avoid_tokens": tuple(profile["door_avoid"]),
        "wall_avoid_tokens": tuple(profile["wall_avoid"]),
    }


def asset_quality(item: dict[str, Any], cls: str, building_type: str) -> dict[str, Any]:
    profile = style_profile(building_type)
    text = _text(item)
    preferred = [t for t in profile["preferred_tokens"] if _has(text, t)]
    avoid_tokens = profile["wall_avoid_tokens"] if cls == "wall_piece" else profile["door_avoid_tokens"] if cls in {"door_frame", "door_piece"} else ()

    hard_block = False
    reasons: list[str] = []
    adjustment = 0.0

    # Hard blocks are deliberately limited to unmistakable semantic mismatches.
    # If a catalog contains only a weak candidate, the caller can still fall back,
    # but the report will expose that decision rather than silently using it.
    if cls == "wall_piece":
        if any(_has(text, token) for token in ("prison", "jail", "cell", "fence", "cage")):
            hard_block = True
            reasons.append("non_partition_wall_semantics")
        if any(_has(text, token) for token in ("grille", "grating", "railing", "rail")):
            hard_block = True
            reasons.append("open_or_guard_wall_semantics")
        if any(_has(text, token) for token in ("window", "skylight")):
            hard_block = True
            reasons.append("glazed_opening_not_partition")
    elif cls in {"door_frame", "door_piece"}:
        if any(_has(text, token) for token in ("prison", "jail", "cell")):
            hard_block = True
            reasons.append("prison_semantics")
        if any(_has(text, token) for token in ("window", "skylight")):
            hard_block = True
            reasons.append("window_not_door")
        if any(_has(text, token) for token in ("grille", "grating", "cage", "bars", "barred", "gate")):
            adjustment -= 350.0
            reasons.append("security_or_barred_door_penalty")

    if preferred:
        adjustment += min(3, len(preferred)) * 35.0
        reasons.append("style_token_match")

    for token in avoid_tokens:
        if _has(text, token):
            adjustment -= 300.0
            reasons.append(f"style_avoid:{token}")

    if item.get("collisionless_variant"):
        adjustment -= 25.0
        reasons.append("collisionless_variant_penalty")

    return {
        "format": FORMAT,
        "hard_block": hard_block,
        "adjustment": adjustment,
        "preferred_matches": preferred,
        "reasons": reasons,
        "profile": profile["building_type"],
    }


def filter_asset_candidates(
    items: Iterable[dict[str, Any]],
    *,
    cls: str,
    building_type: str,
) -> list[dict[str, Any]]:
    rows = [dict(x) for x in items if isinstance(x, dict)]
    for item in rows:
        item["_ncig_quality"] = asset_quality(item, cls, building_type)

    accepted = [x for x in rows if not x["_ncig_quality"]["hard_block"]]
    accepted.sort(
        key=lambda x: (
            -float(x["_ncig_quality"]["adjustment"]),
            -float(x.get("score", 0.0)),
            str(x.get("family") or ""),
            str(x.get("path") or ""),
        )
    )
    return accepted


def choose_variety_index(key: str, count: int) -> int:
    if count <= 1:
        return 0
    digest = hashlib.sha256(str(key).encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % count


def door_opening_width(room_width_m: float) -> float:
    available = max(0.0, float(room_width_m) - 0.8)
    if available < MIN_CLEAR_WIDTH_M:
        return round(available, 3)
    return round(min(PREFERRED_CLEAR_WIDTH_M, available), 3)


def door_clearance_report(width_m: float, height_m: float = PREFERRED_CLEAR_HEIGHT_M) -> dict[str, Any]:
    width = float(width_m)
    height = float(height_m)
    return {
        "clear_width_m": width,
        "clear_height_m": height,
        "minimum_clear_width_m": MIN_CLEAR_WIDTH_M,
        "preferred_clear_width_m": PREFERRED_CLEAR_WIDTH_M,
        "minimum_height_m": PREFERRED_CLEAR_HEIGHT_M,
        "usable_for_standard_character": width >= MIN_CLEAR_WIDTH_M and height >= PREFERRED_CLEAR_HEIGHT_M,
    }
