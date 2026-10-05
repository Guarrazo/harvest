from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

FORMAT = "ncig-architecture-catalog-v1"

_STRUCTURAL_CLASSES = (
    "floor_piece",
    "wall_piece",
    "ceiling_piece",
    "door_frame",
    "door_piece",
    "opening_piece",
    "window_piece",
    "pillar_piece",
    "stairs_piece",
    "rail_piece",
    "trim_piece",
)

_DIMENSION_RE = re.compile(r"(?:^|[_-])([lwhd])([0-9]+(?:\.[0-9]+)?)(?=$|[_-])", re.IGNORECASE)

_EXCLUDE_TOKENS = {
    "character", "characters", "vehicle", "vehicles", "weapon", "weapons", "garment",
    "crowd", "npc", "cyberware", "hair", "head", "body", "face", "decal", "fx",
    "ui", "hud", "icon", "animation", "anim", "shadow", "audio", "sound",
}

_INTERIOR_MARKERS = (
    "\\interior\\",
    "\\interiors\\",
    "\\common\\int\\",
    "\\interior\\",
)


def normalize_path(value: str) -> str:
    return value.replace("/", "\\")


def _stem_tokens(path: str) -> set[str]:
    stem = Path(path.replace("\\", "/")).stem.lower()
    return {x for x in re.split(r"[^a-z0-9]+", stem) if x}


def parse_dimension_hints(path: str) -> dict[str, Any]:
    """Parse filename dimension hints such as _l600_w300_h300.

    The game resources commonly encode dimensions in centimetres in their filenames.
    We keep the source and mark the result as a filename hint; this is not a substitute
    for a mesh bounding box.
    """
    stem = Path(path.replace("\\", "/")).stem.lower()
    dimensions_cm: dict[str, float] = {}
    for match in _DIMENSION_RE.finditer(stem):
        key = match.group(1).lower()
        value = float(match.group(2))
        dimensions_cm.setdefault(key, value)
    dimensions_m = {k: v / 100.0 for k, v in dimensions_cm.items()}
    return {
        "source": "filename_hint",
        "unit": "cm",
        "centimetres": dimensions_cm,
        "metres": dimensions_m,
        "complete": all(k in dimensions_m for k in ("l", "w", "h")),
    }


def is_architecture_path(path: str) -> bool:
    p = normalize_path(path).lower()
    return "\\environment\\architecture\\" in p


def is_probable_interior(path: str) -> bool:
    p = normalize_path(path).lower()
    name = Path(p.replace("\\", "/")).stem.lower()
    if any(marker in p for marker in _INTERIOR_MARKERS):
        return True
    if "\\environment\\architecture\\" not in p:
        return False
    if any(token in name for token in ("int_", "_int", "interior", "bathroom", "kitchen", "corridor", "lobby", "apartment")):
        return True
    return "\\buildings\\" in p and "\\interior\\" in p


def _has_any(text: str, tokens: Iterable[str]) -> bool:
    return any(token in text for token in tokens)


def classify_structural_resource(path: str, roles: Iterable[str] = ()) -> tuple[str | None, list[str]]:
    """Return a structural class and explanatory signals.

    Classes are intentionally conservative. Generic props (tables, chairs, computers, etc.)
    are not structural candidates even when they happen to live under architecture folders.
    """
    p = normalize_path(path).lower()
    stem = Path(p.replace("\\", "/")).stem.lower()
    role_set = {str(x).lower() for x in roles}
    if not p.endswith(".mesh") or not is_architecture_path(p):
        return None, []

    path_tokens = set(re.split(r"[^a-z0-9]+", p))
    if path_tokens & _EXCLUDE_TOKENS:
        return None, ["excluded_non_architectural_domain"]

    signals: list[str] = []
    if "\\without_collision\\" in p or stem.endswith("_no_col"):
        signals.append("collisionless_variant")

    def hit(cls: str, *why: str) -> tuple[str, list[str]]:
        return cls, signals + list(why)

    # Filename semantics win over broad harvested roles. This prevents resources such as
    # "ceiling_tiles" from being reclassified as floor just because the generic "tile"
    # role was detected during harvest.
    if _has_any(stem, ("doorframe", "door_frame", "doorway")):
        return hit("door_frame", "doorframe_token")
    if "door" in role_set or _has_any(stem, ("door", "entrance", "entry")):
        if re.search(r"(?:^|[_-])(?!no[_-]?holes?)(?:hole|opening)(?:$|[_-])", stem):
            return hit("opening_piece", "door_opening_token")
        return hit("door_piece", "door_token")
    if _has_any(stem, ("window", "shopwindow", "skylight")):
        return hit("window_piece", "window_token")
    if _has_any(stem, ("ceiling", "roof", "soffit")):
        return hit("ceiling_piece", "ceiling_token")
    if _has_any(stem, ("floor", "ground", "walkway")):
        return hit("floor_piece", "floor_token")
    # Only fall back to role metadata when the filename itself is neutral.
    if "ceiling" in role_set:
        return hit("ceiling_piece", "harvest_ceiling_role")
    if "floor" in role_set:
        return hit("floor_piece", "harvest_floor_role")
    if _has_any(stem, ("stairs", "stair", "steps")):
        return hit("stairs_piece", "stairs_token")
    if _has_any(stem, ("pillar", "column")):
        return hit("pillar_piece", "pillar_token")
    if _has_any(stem, ("railing", "rail", "balustrade")):
        return hit("rail_piece", "rail_token")
    if _has_any(stem, ("trim", "baseboard", "molding", "moulding", "skirting")):
        return hit("trim_piece", "trim_token")
    if "wall" in role_set or _has_any(stem, ("wall", "partition", "bulkhead", "drywall")):
        if re.search(r"(?:^|[_-])(?!no[_-]?holes?)(?:hole|opening)(?:$|[_-])", stem):
            return hit("opening_piece", "wall_opening_token")
        return hit("wall_piece", "wall_token")
    return None, signals


def derive_family(path: str) -> str:
    """Derive a stable architecture family from the environment/architecture path."""
    p = normalize_path(path).strip("\\")
    parts = p.split("\\")
    lowered = [x.lower() for x in parts]
    try:
        i = lowered.index("architecture")
    except ValueError:
        return "unknown"
    tail = parts[i + 1 :]
    if not tail:
        return "architecture"

    # The final path component is the mesh filename, never part of the architecture
    # family. Keeping it here made every flat resource directory look like a different
    # family (for example common/tech_corridor/<wall>.mesh), which prevented walls,
    # doors, frames and windows from sharing a coherent kit.
    dirs = tail[:-1] if str(tail[-1]).lower().endswith(".mesh") else tail
    if not dirs:
        return "architecture"

    lowered_dirs = [x.lower() for x in dirs]
    if "interior" in lowered_dirs:
        j = lowered_dirs.index("interior")
        return "/".join(dirs[: min(len(dirs), j + 2)]).lower()
    return "/".join(dirs[: min(3, len(dirs))]).lower()


def score_structural_candidate(path: str, roles: Iterable[str], structural_class: str, dimensions: dict[str, Any]) -> tuple[int, list[str]]:
    p = normalize_path(path).lower()
    role_set = {str(x).lower() for x in roles}
    score = 0
    reasons: list[str] = []
    if is_architecture_path(p):
        score += 40
        reasons.append("architecture_path")
    if is_probable_interior(p):
        score += 25
        reasons.append("interior_path")
    if structural_class in role_set or structural_class.split("_")[0] in role_set:
        score += 50
        reasons.append("harvest_role")
    if Path(p).suffix.lower() == ".mesh":
        score += 10
        reasons.append("mesh")
    if dimensions.get("complete"):
        score += 10
        reasons.append("complete_dimension_hint")
    if "\\without_collision\\" in p or p.endswith("_no_col.mesh"):
        score -= 5
        reasons.append("collisionless_variant")
    if "_temp\\" in p or "\\_temp\\" in p:
        score -= 3
        reasons.append("temporary_content")
    if "common\\int" in p or "\\int_" in p:
        score += 8
        reasons.append("common_interior_kit")
    return score, reasons


def _resource_items(harvest: dict[str, Any]) -> Iterable[tuple[str, dict[str, Any]]]:
    resources = harvest.get("resources")
    if not isinstance(resources, dict):
        return []
    return ((str(path), meta if isinstance(meta, dict) else {}) for path, meta in resources.items())


def build_architecture_catalog(
    harvest: dict[str, Any],
    *,
    max_per_class: int = 250,
    max_total: int | None = None,
    interior_only: bool = False,
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    counts = Counter()
    families = Counter()
    all_structural = 0

    for raw_path, meta in _resource_items(harvest):
        path = normalize_path(raw_path)
        roles = meta.get("roles", []) if isinstance(meta, dict) else []
        cls, signals = classify_structural_resource(path, roles)
        if cls is None:
            continue
        if interior_only and not is_probable_interior(path):
            continue
        all_structural += 1
        dimensions = parse_dimension_hints(path)
        score, reasons = score_structural_candidate(path, roles, cls, dimensions)
        item = {
            "path": path,
            "class": cls,
            "roles": sorted({str(x) for x in roles}),
            "family": derive_family(path),
            "interior": is_probable_interior(path),
            "dimensions": dimensions,
            "collisionless_variant": "collisionless_variant" in signals,
            "score": score,
            "signals": signals + reasons,
            "sources": meta.get("sources", []) if isinstance(meta, dict) else [],
        }
        candidates.append(item)
        counts[cls] += 1
        families[item["family"]] += 1

    by_class: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in candidates:
        by_class[item["class"]].append(item)

    selected: list[dict[str, Any]] = []
    selected_counts: dict[str, int] = {}
    for cls in _STRUCTURAL_CLASSES:
        items = by_class.get(cls, [])
        # Sort by score, then family and path for deterministic output.
        items.sort(key=lambda x: (-x["score"], x["family"], x["path"]))
        limit = max(0, int(max_per_class))
        chosen: list[dict[str, Any]] = []
        # Prefer family diversity before consuming the class cap.
        seen_families: set[str] = set()
        for item in items:
            if len(chosen) >= limit:
                break
            if item["family"] not in seen_families:
                chosen.append(item)
                seen_families.add(item["family"])
        for item in items:
            if len(chosen) >= limit:
                break
            if item not in chosen:
                chosen.append(item)
        selected.extend(chosen)
        selected_counts[cls] = len(chosen)

    if max_total is not None and len(selected) > max_total:
        selected.sort(key=lambda x: (-x["score"], x["class"], x["family"], x["path"]))
        selected = selected[: max(0, int(max_total))]

    selected.sort(key=lambda x: (x["class"], -x["score"], x["family"], x["path"]))
    return {
        "format": FORMAT,
        "source_format": harvest.get("format"),
        "source_root": harvest.get("root"),
        "source_resource_count": harvest.get("resource_count"),
        "structural_candidate_count": all_structural,
        "candidate_counts": {cls: counts.get(cls, 0) for cls in _STRUCTURAL_CLASSES},
        "selected_counts": {cls: sum(1 for x in selected if x["class"] == cls) for cls in _STRUCTURAL_CLASSES},
        "family_count": len(families),
        "selected_count": len(selected),
        "max_per_class": int(max_per_class),
        "max_total": None if max_total is None else int(max_total),
        "interior_only": bool(interior_only),
        "items": selected,
    }


def architecture_catalog_report(catalog: dict[str, Any]) -> dict[str, Any]:
    items = catalog.get("items", []) if isinstance(catalog, dict) else []
    classes = Counter(x.get("class") for x in items if isinstance(x, dict))
    families = Counter(x.get("family") for x in items if isinstance(x, dict))
    complete_dims = sum(bool(x.get("dimensions", {}).get("complete")) for x in items if isinstance(x, dict))
    return {
        "format": catalog.get("format"),
        "source_resource_count": catalog.get("source_resource_count"),
        "structural_candidate_count": catalog.get("structural_candidate_count", 0),
        "selected_count": len(items),
        "classes": dict(classes),
        "families": len(families),
        "complete_dimension_hints": complete_dims,
    }
