from __future__ import annotations

import re
from pathlib import Path
from typing import Any

TOKEN_RULES = {
    "bed": ["bed", "mattress", "sleep"],
    "wardrobe": ["wardrobe", "closet", "cabinet"],
    "sofa": ["sofa", "couch"],
    "chair": ["chair", "stool", "seat"],
    "table": ["table", "desk"],
    "desk": ["desk", "workstation"],
    "computer": ["computer", "pc", "terminal", "laptop"],
    "tv": ["tv", "television", "screen"],
    "fridge": ["fridge", "refrigerator"],
    "sink": ["sink", "washbasin", "lavatory"],
    "toilet": ["toilet", "wc", "toilette"],
    "shelf": ["shelf", "shelving", "rack"],
    "crate": ["crate", "box", "container"],
    "counter": ["counter", "checkout"],
    "display": ["display", "showcase"],
    "workbench": ["workbench", "work_bench", "bench"],
    "tool_rack": ["tool", "rack", "pegboard"],
    "server_rack": ["server", "rack"],
    "washer": ["washer", "washing_machine"],
    "light": ["light", "lamp", "ceiling", "fixture"],
    "floor": ["floor", "ground", "plank", "tile"],
    "ceiling": ["ceiling", "roof", "panel"],
    "wall": ["wall", "partition", "panel", "concrete"],
    "opening": ["doorframe", "door_frame", "archway", "opening"],
    "door": ["door", "door_frame", "doorframe"],
}

_ASSET_SUFFIXES = {".ent", ".mesh", ".mi", ".mat", ".xbm"}


def classify(path: str) -> list[str]:
    name = path.lower().replace("\\", "/")
    stem = Path(name).stem
    hits: list[str] = []
    for semantic, tokens in TOKEN_RULES.items():
        if any(re.search(rf"(?<![a-z0-9]){re.escape(t)}(?![a-z0-9])", stem) for t in tokens):
            hits.append(semantic)
    return hits


def score_candidate(rel: str, semantic: str) -> int:
    stem = Path(rel).stem.lower()
    tokens = TOKEN_RULES.get(semantic, [semantic])
    score = sum(3 for token in tokens if token in stem)
    ext = Path(rel).suffix.lower()
    if semantic in {"bed", "wardrobe", "sofa", "computer", "fridge", "toilet", "sink", "counter"} and ext == ".ent":
        score += 5
    if semantic in {"wall", "floor", "ceiling"} and ext == ".mesh":
        score += 4
    if semantic == "light" and ext == ".ent":
        score += 2
    return score


def build_catalog(root: str | Path) -> dict[str, list[str]]:
    root = Path(root)
    catalog: dict[str, list[str]] = {k: [] for k in TOKEN_RULES}
    for path in root.rglob("*"):
        if path.suffix.lower() not in _ASSET_SUFFIXES:
            continue
        rel = str(path.relative_to(root)).replace("\\", "/")
        for semantic in classify(rel):
            catalog[semantic].append(rel)
    for key in catalog:
        catalog[key] = sorted(set(catalog[key]), key=lambda p: (-score_candidate(p, key), p))
    return catalog


def choose_assets(catalog: dict[str, list[str]], semantics: list[str], max_per_semantic: int = 3) -> dict[str, list[str]]:
    return {s: catalog.get(s, [])[:max_per_semantic] for s in semantics}


def catalog_report(catalog: dict[str, list[str]]) -> dict[str, Any]:
    return {
        "format": "ncig-resource-catalog-v2",
        "semantics": len(catalog),
        "assets": sum(len(v) for v in catalog.values()),
        "empty_semantics": [k for k, v in catalog.items() if not v],
        "counts": {k: len(v) for k, v in catalog.items()},
    }
