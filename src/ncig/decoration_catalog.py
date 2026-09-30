from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

FORMAT = "ncig-decoration-catalog-v1"

ROLE_TOKENS: dict[str, tuple[str, ...]] = {
    "bed": ("bed", "mattress"),
    "sofa": ("sofa", "couch"),
    "wardrobe": ("wardrobe", "closet"),
    "nightstand": ("nightstand", "bedside"),
    "table": ("table", "coffee_table"),
    "desk": ("desk", "workstation"),
    "chair": ("chair", "stool", "seat"),
    "computer": ("computer", "terminal", "pc", "laptop"),
    "tv": ("tv", "television"),
    "fridge": ("fridge", "refrigerator"),
    "sink": ("sink", "washbasin", "lavatory"),
    "toilet": ("toilet", "wc"),
    "shower": ("shower", "bathtub"),
    "counter": ("counter", "checkout"),
    "display": ("display", "showcase"),
    "shelf": ("shelf", "shelving"),
    "crate": ("crate", "box", "container"),
    "workbench": ("workbench", "work_bench"),
    "tool_rack": ("tool", "pegboard"),
    "server_rack": ("server", "rack"),
    "washer": ("washer", "washing_machine"),
    "light": ("lamp", "ceiling_light", "fixture", "light"),
    "plant": ("plant", "flowerpot", "planter"),
    "trash": ("trash", "bin", "garbage"),
}

STYLE_TOKENS: dict[str, tuple[str, ...]] = {
    "commercial": ("shop", "store", "retail", "market", "bar", "restaurant", "mall"),
    "residential": ("apartment", "residential", "home", "flat", "housing"),
    "office": ("office", "corp", "corporate", "executive", "business"),
    "industrial": ("industrial", "factory", "warehouse", "workshop", "garage"),
    "mixed": ("common\\int", "interior", "int_"),
}


def _has_token(text: str, token: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(token.lower())}(?![a-z0-9])", text) is not None


def roles_for(path: str, harvested_roles: list[str] | tuple[str, ...] = ()) -> list[str]:
    p = path.replace("/", "\\").lower()
    stem = Path(p.replace("\\", "/")).stem.lower()
    roles = set(str(x).lower() for x in harvested_roles)
    out: set[str] = set()
    combined = f"{stem} {p}"
    for role, tokens in ROLE_TOKENS.items():
        if any(_has_token(stem, t) for t in tokens):
            out.add(role)
    # Avoid treating every generic rack as a server rack unless server/terminal tokens exist.
    if "server" not in stem and "server" in out:
        out.discard("server_rack")
    if roles & {"bed", "sofa", "chair", "table", "desk", "computer", "tv", "fridge", "sink", "toilet", "counter", "display", "shelf", "crate", "workbench", "washer"}:
        out.update(roles & {"bed", "sofa", "chair", "table", "desk", "computer", "tv", "fridge", "sink", "toilet", "counter", "display", "shelf", "crate", "workbench", "washer"})
    return sorted(out)


def style_for(path: str, building_type: str | None = None) -> list[str]:
    p = path.replace("/", "\\").lower()
    stem = Path(p.replace("\\", "/")).stem.lower()
    hits: list[str] = []
    for style, tokens in STYLE_TOKENS.items():
        if any(token in p or _has_token(stem, token) for token in tokens):
            hits.append(style)
    return sorted(set(hits)) or ([building_type] if building_type else ["generic"])


def _family(path: str) -> str:
    p = path.replace("/", "\\").strip("\\")
    parts = p.split("\\")
    lowered = [x.lower() for x in parts]
    if "architecture" in lowered:
        i = lowered.index("architecture")
        tail = parts[i + 1 :]
        return "/".join(tail[:3]).lower() if tail else "architecture"
    if len(parts) >= 5:
        return "/".join(parts[:4]).lower()
    if len(parts) >= 4:
        return "/".join(parts[:3]).lower()
    return "/".join(parts[:-1]).lower() or "generic"


def _score(path: str, role: str, building_type: str | None, meta: dict[str, Any], roles: list[str]) -> float:
    p = path.lower()
    stem = Path(p.replace("\\", "/")).stem
    score = 0.0
    if role in roles:
        score += 100
    if p.endswith(".ent"):
        score += 10
    for token in STYLE_TOKENS.get(building_type or "mixed", ()):  # shared style signal
        if token in p or token in stem:
            score += 15
    # Paths explicitly sourced from an Object Spawner/template/export are more useful than
    # arbitrary mentions because they are known to be spawnable resources.
    score += min(12.0, len(meta.get("sources", []) or []) * 1.5)
    return score


def build_decoration_catalog(harvest: dict[str, Any], *, max_per_role: int = 80) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for raw_path, meta in (harvest.get("resources") or {}).items():
        path = str(raw_path).replace("/", "\\")
        if not path.lower().endswith(".ent"):
            continue
        meta = meta if isinstance(meta, dict) else {}
        roles = roles_for(path, meta.get("roles", []))
        if not roles:
            continue
        family = _family(path)
        styles = style_for(path)
        for role in roles:
            candidates.append({
                "path": path,
                "role": role,
                "family": family,
                "styles": styles,
                "score": _score(path, role, None, meta, roles),
                "sources": meta.get("sources", []),
            })
    by_role: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in candidates:
        by_role[item["role"]].append(item)
    selected: list[dict[str, Any]] = []
    for role, rows in sorted(by_role.items()):
        rows.sort(key=lambda x: (-x["score"], x["family"], x["path"]))
        # Keep style/family diversity, then fill the cap with the strongest candidates.
        chosen: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in rows:
            key = row["family"]
            if key not in seen:
                chosen.append(row)
                seen.add(key)
            if len(chosen) >= max_per_role:
                break
        if len(chosen) < max_per_role:
            for row in rows:
                if row not in chosen:
                    chosen.append(row)
                if len(chosen) >= max_per_role:
                    break
        selected.extend(chosen)
    return {
        "format": FORMAT,
        "role_counts": dict(sorted(Counter(x["role"] for x in selected).items())),
        "selected_count": len(selected),
        "items": selected,
        "notes": [
            "Decoration candidates are .ent resources only; mesh props are not emitted as worldEntityNode without a corresponding entity template.",
            "Selection is deterministic and style-aware; it does not invent resource paths.",
        ],
    }
