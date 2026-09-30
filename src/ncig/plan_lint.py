from __future__ import annotations

from collections import defaultdict
from typing import Any


def lint_world_plan(plan: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate structural invariants before handing a world plan to the native bridge."""
    findings: list[dict[str, Any]] = []
    sectors = plan.get("sectors") or []
    nodes = plan.get("nodes") or []
    if not sectors:
        findings.append({"severity": "error", "code": "NO_SECTORS", "message": "World plan has no sectors."})
    if not nodes:
        findings.append({"severity": "error", "code": "NO_NODES", "message": "World plan has no nodes."})

    refs = defaultdict(list)
    for n in nodes:
        ref = str(n.get("nodeRef") or "")
        if not ref:
            findings.append({"severity": "error", "code": "MISSING_NODE_REF", "message": f"Node {n.get('name', '?')} has no nodeRef."})
        else:
            refs[ref].append(str(n.get("name") or "?"))
        if "floor" not in n:
            findings.append({"severity": "error", "code": "MISSING_FLOOR", "message": f"Node {n.get('name', '?')} has no floor assignment."})

    for ref, names in refs.items():
        if len(names) > 1:
            findings.append({"severity": "error", "code": "DUPLICATE_NODE_REF", "message": f"nodeRef {ref} is shared by: {', '.join(names)}"})

    sector_names = []
    for s in sectors:
        sid = str(s.get("name") or s.get("id") or "")
        sector_names.append(sid)
        if not sid:
            findings.append({"severity": "error", "code": "MISSING_SECTOR_NAME", "message": "A sector has no name/id."})
        if not (s.get("min") or (s.get("extents") or {}).get("min")) or not (s.get("max") or (s.get("extents") or {}).get("max")):
            findings.append({"severity": "error", "code": "MISSING_SECTOR_EXTENTS", "message": f"Sector {sid or '?'} has incomplete extents."})

    if len(set(sector_names)) != len(sector_names):
        findings.append({"severity": "error", "code": "DUPLICATE_SECTOR_NAME", "message": "Sector names are not unique."})

    floor_set = {int(s.get("floor", 0)) for s in sectors}
    for n in nodes:
        try:
            floor = int(n.get("floor"))
        except (TypeError, ValueError):
            continue
        if floor not in floor_set:
            findings.append({"severity": "error", "code": "ORPHAN_NODE_FLOOR", "message": f"Node {n.get('name', '?')} targets floor {floor}, but no sector exists for that floor."})

    refs_by_floor: dict[int, int] = defaultdict(int)
    for n in nodes:
        try:
            refs_by_floor[int(n.get("floor"))] += 1
        except (TypeError, ValueError):
            pass
    for floor in sorted(floor_set):
        if refs_by_floor[floor] == 0:
            findings.append({"severity": "warning", "code": "EMPTY_FLOOR", "message": f"Floor {floor} has a sector but no nodes."})

    return findings


def lint_report(plan: dict[str, Any]) -> dict[str, Any]:
    findings = lint_world_plan(plan)
    errors = sum(1 for x in findings if x["severity"] == "error")
    warnings = sum(1 for x in findings if x["severity"] == "warning")
    return {
        "format": "ncig-world-plan-lint-v1",
        "valid": errors == 0,
        "errors": errors,
        "warnings": warnings,
        "findings": findings,
    }
