from __future__ import annotations

from collections import defaultdict
import re
from typing import Any, Iterable


_STRUCTURAL_WITH_WIDTH = {
    'wall_piece', 'door_frame', 'door_piece', 'window_piece', 'opening_piece',
    'pillar_piece', 'rail_piece', 'trim_piece',
}


def family_group(family: str | None) -> str | None:
    if not family or family == "unknown":
        return None
    parts = [p for p in str(family).replace('\\', '/').split('/') if p]
    if len(parts) >= 2:
        return '/'.join(parts[:2]).lower()
    return parts[0].lower() if parts else None


def family_tokens(family: str | None) -> set[str]:
    if not family:
        return set()
    return {t for t in re.split(r'[^a-z0-9]+', str(family).lower()) if t and t not in {'common', 'int', 'environment', 'architecture'}}


def _dims(item: dict[str, Any]) -> dict[str, float]:
    bounds = item.get('bounds') if isinstance(item.get('bounds'), dict) else None
    if bounds and isinstance(bounds.get('dimensions_m'), dict):
        d = bounds['dimensions_m']
        return {k: float(d.get(k, 0.0)) for k in ('x', 'y', 'z')}
    d = (item.get('dimensions') or {}).get('metres') or {}
    return {k: float(d.get(k, 0.0)) for k in ('l', 'w', 'h', 'x', 'y', 'z') if isinstance(d.get(k), (int, float))}


def planar_dimensions(item: dict[str, Any], cls: str | None = None) -> tuple[float | None, float | None, float | None]:
    """Return visible span, secondary planar dimension and height.

    Runtime resource bounds win. Filename hints use CP77's common w/l/h convention:
    for walls/doors/windows, `w` is generally the visible span and `l` is thickness
    when both are present; floors/ceilings use l/w as their planar dimensions.
    """
    d = _dims(item)
    runtime = isinstance(item.get('bounds'), dict)
    if runtime:
        x, y, z = d.get('x', 0.0), d.get('y', 0.0), d.get('z', 0.0)
        if cls in _STRUCTURAL_WITH_WIDTH:
            return (max(x, y) or None, min(x, y) or None, z or None)
        return (x or None, y or None, z or None)

    l, w, h = d.get('l', 0.0), d.get('w', 0.0), d.get('h', 0.0)
    if cls in _STRUCTURAL_WITH_WIDTH:
        span = w or l
        thickness = l if w else w
        if span and thickness and thickness > span:
            span, thickness = thickness, span
        return (span or None, thickness or None, h or None)
    return (l or w or None, w or l or None, h or None)


def sane_dimensions(item: dict[str, Any], cls: str) -> bool:
    span, secondary, height = planar_dimensions(item, cls)
    if cls in {'floor_piece', 'ceiling_piece'}:
        return bool(span and secondary and 0.25 <= span <= 12 and 0.25 <= secondary <= 12 and (not height or height <= 1.5))
    if cls == 'wall_piece':
        return bool(span and height and 0.5 <= span <= 12 and 1.8 <= height <= 6.0)
    if cls in {'door_frame', 'door_piece'}:
        return bool(span and height and 0.5 <= span <= 2.5 and 1.6 <= height <= 3.5)
    if cls == 'window_piece':
        return bool(span and height and 0.4 <= span <= 5.0 and 0.5 <= height <= 3.0)
    return True


def dimension_hint_scale(item: dict[str, Any], cls: str, target: dict[str, float]) -> dict[str, float] | None:
    """Return a bounded scale inferred from complete filename dimensions.

    This is intentionally more conservative than runtime bounds: it only applies
    directional fitting when all required dimensions are present and the requested
    deformation stays within a narrow range. Runtime bounds remain authoritative.
    """
    if isinstance(item.get('bounds'), dict):
        if cls in {'wall_piece', 'door_frame', 'door_piece', 'window_piece'}:
            span = planar_dimensions(item, cls)[0]
            height = planar_dimensions(item, cls)[2]
            desired_span = float(target.get('span', span or 0.0))
            desired_height = float(target.get('height', height or 0.0))
            if not span or not height or desired_span <= 0 or desired_height <= 0:
                return None
            return {'x': desired_span / span, 'y': 1.0, 'z': desired_height / height}
        span, secondary, _ = planar_dimensions(item, cls)
        desired_x = float(target.get('x', span or 0.0))
        desired_y = float(target.get('y', secondary or 0.0))
        if not span or not secondary or desired_x <= 0 or desired_y <= 0:
            return None
        return {'x': desired_x / span, 'y': desired_y / secondary, 'z': 1.0}
    dims = item.get('dimensions') or {}
    if not bool(dims.get('complete')):
        return None
    span, secondary, height = planar_dimensions(item, cls)
    if cls in {'wall_piece', 'door_frame', 'door_piece', 'window_piece'}:
        desired_span = float(target.get('span', span or 0.0))
        desired_height = float(target.get('height', height or 0.0))
        if not span or not height or desired_span <= 0 or desired_height <= 0:
            return None
        sx = desired_span / span
        sz = desired_height / height
        if not (0.72 <= sx <= 1.28 and 0.80 <= sz <= 1.20):
            return None
        return {'x': sx, 'y': 1.0, 'z': sz}
    desired_x = float(target.get('x', span or 0.0))
    desired_y = float(target.get('y', secondary or 0.0))
    if not span or not secondary or desired_x <= 0 or desired_y <= 0:
        return None
    sx = desired_x / span
    sy = desired_y / secondary
    if not (0.72 <= sx <= 1.28 and 0.72 <= sy <= 1.28):
        return None
    return {'x': sx, 'y': sy, 'z': 1.0}


def _family_score(target_family: str, candidate_family: str, building_tokens: Iterable[str] = ()) -> float:
    ta = family_tokens(target_family)
    cb = family_tokens(candidate_family)
    if not cb:
        return -100.0
    common = len(ta & cb)
    union = len(ta | cb)
    score = common * 80.0 + (common / union * 40.0 if union else 0.0)
    if family_group(target_family) == family_group(candidate_family):
        score += 20.0
    bt = {x.lower() for x in building_tokens}
    score += len(cb & bt) * 35.0
    return score


def compatible_family_candidates(
    catalog: dict[str, Any],
    cls: str,
    family: str | None,
    *,
    building_tokens: Iterable[str] = (),
    min_compatibility: float = 20.0,
) -> list[dict[str, Any]]:
    """Select a coherent family pool for one structural class.

    Exact family wins. When a class is absent from that family, only families that
    share meaningful identity/style signals are accepted; arbitrary global fallback
    is retained solely when no compatible family exists and is deliberately appended
    after compatible candidates.
    """
    items = [x for x in catalog.get('items', []) if isinstance(x, dict) and x.get('class') == cls]
    sane = [x for x in items if sane_dimensions(x, cls)] or items
    if not family:
        return sane
    exact = [x for x in sane if str(x.get('family')) == family]
    if exact:
        return exact

    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for x in sane:
        fam = str(x.get('family') or 'unknown')
        if fam != 'unknown':
            by_family[fam].append(x)
    ranked: list[tuple[float, str]] = []
    for fam, rows in by_family.items():
        score = _family_score(family, fam, building_tokens)
        complete = sum(bool((r.get('dimensions') or {}).get('complete')) for r in rows)
        score += min(20.0, complete) * 1.5
        if score >= min_compatibility:
            ranked.append((score, fam))
    ranked.sort(key=lambda row: (-row[0], row[1]))
    if ranked:
        top = ranked[0][0]
        keep = {fam for score, fam in ranked if score >= top - 18.0}
        return [x for x in sane if str(x.get('family')) in keep]
    return sane



def rank_family_options(
    catalog: dict[str, Any],
    cls: str,
    primary_family: str | None,
    *,
    building_tokens: Iterable[str] = (),
) -> list[tuple[float, str, str]]:
    """Rank whole resource families for one structural class.

    The result is `(score, family, mode)` and is stable. Exact primary family wins;
    compatible sibling families are preferred over unrelated global fallbacks.
    """
    items = [x for x in catalog.get('items', []) if isinstance(x, dict) and x.get('class') == cls]
    items = [x for x in items if sane_dimensions(x, cls)] or items
    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        fam = str(item.get('family') or 'unknown')
        if fam != 'unknown':
            by_family[fam].append(item)
    out: list[tuple[float, str, str]] = []
    for fam, rows in by_family.items():
        fam_score = _family_score(primary_family or '', fam, building_tokens) if primary_family else 0.0
        avg_score = sum(float(r.get('score', 0.0)) for r in rows) / max(1, len(rows))
        complete = sum(bool((r.get('dimensions') or {}).get('complete')) for r in rows)
        sane = sum(1 for r in rows if sane_dimensions(r, cls))
        exact = primary_family is not None and fam == primary_family
        mode = 'exact' if exact else ('compatible' if fam_score >= 20.0 else 'global_fallback')
        score = avg_score + min(25.0, complete) * 2.0 + sane * 0.5
        score += fam_score
        if exact:
            score += 10000.0
        out.append((score, fam, mode))
    out.sort(key=lambda x: (-x[0], x[1]))
    return out

def family_candidates(catalog: dict[str, Any], cls: str, family: str | None, *, building_tokens: Iterable[str] = ()) -> list[dict[str, Any]]:
    return compatible_family_candidates(catalog, cls, family, building_tokens=building_tokens)


def family_class_matrix(catalog: dict[str, Any]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for item in catalog.get('items', []) or []:
        if not isinstance(item, dict):
            continue
        fam = str(item.get('family') or 'unknown')
        cls = str(item.get('class') or '')
        if fam != 'unknown' and cls:
            out[fam][cls] += 1
    return {f: dict(c) for f, c in sorted(out.items())}
