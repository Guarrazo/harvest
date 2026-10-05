from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

from .physics_index import PhysicsIndex, load_index

VERSION = "0.24.0"
FORMAT = "ncig-world-access-audit-v1"


def _hash_int(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16)


def _world_to_local(building: dict[str, Any], x: float, y: float) -> tuple[float, float]:
    p = building.get("position") or {}
    dx = float(x) - float(p.get("x", 0.0))
    dy = float(y) - float(p.get("y", 0.0))
    a = math.radians(float(building.get("yaw_deg", 0.0)))
    return dx * math.cos(a) + dy * math.sin(a), -dx * math.sin(a) + dy * math.cos(a)


def _local_point_in_rect(lx: float, ly: float, width: float, depth: float, margin: float = 0.0) -> bool:
    return abs(lx) <= width * 0.5 + margin and abs(ly) <= depth * 0.5 + margin


def _rotate_dims(row: dict[str, Any]) -> tuple[float, float]:
    l = abs(float(row.get("l", 0.0) or 0.0) * float(row.get("sx", 1.0) or 1.0))
    w = abs(float(row.get("w", 0.0) or 0.0) * float(row.get("sy", 1.0) or 1.0))
    yaw = math.radians(float(row.get("yaw_deg", 0.0)))
    ex = abs(math.cos(yaw)) * l * 0.5 + abs(math.sin(yaw)) * w * 0.5
    ey = abs(math.sin(yaw)) * l * 0.5 + abs(math.cos(yaw)) * w * 0.5
    return 2.0 * ex, 2.0 * ey


def _row_aabb(row: dict[str, Any]) -> tuple[float, float, float, float, float, float] | None:
    dims_xy = _rotate_dims(row)
    if dims_xy[0] <= 0.01 or dims_xy[1] <= 0.01:
        return None
    h = abs(float(row.get("h", 0.0) or 0.0) * float(row.get("sz", 1.0) or 1.0))
    if h <= 0.01 and row.get("shape_x", 0.0):
        h = abs(float(row.get("shape_z", 0.0) or 0.0))
    return (
        float(row["x"]) - dims_xy[0] * 0.5, float(row["x"]) + dims_xy[0] * 0.5,
        float(row["y"]) - dims_xy[1] * 0.5, float(row["y"]) + dims_xy[1] * 0.5,
        float(row["z"]) - h * 0.5, float(row["z"]) + h * 0.5,
    )


def _distance_to_boundary(building: dict[str, Any], row: dict[str, Any]) -> tuple[float, str, float, float]:
    lx, ly = _world_to_local(building, float(row["x"]), float(row["y"]))
    hw = float(building.get("width_m", 0.0)) * 0.5
    hd = float(building.get("depth_m", 0.0)) * 0.5
    distances = {
        "north": abs(ly + hd),
        "south": abs(ly - hd),
        "west": abs(lx + hw),
        "east": abs(lx - hw),
    }
    side = min(distances, key=distances.get)
    return distances[side], side, lx, ly


def _opening_center(candidate: dict[str, Any]) -> tuple[float, float, float, str]:
    p = candidate.get("entry_world") or {}
    return float(p.get("x", 0.0)), float(p.get("y", 0.0)), float(p.get("z", 0.0)), str(candidate.get("entry_side") or "unknown")


def _overlaps_opening(row: dict[str, Any], candidate: dict[str, Any], extra_margin: float = 0.30) -> bool:
    ex, ey, ez, side = _opening_center(candidate)
    lx, ly = _world_to_local(candidate, ex, ey)
    rlx, rly = _world_to_local(candidate, float(row["x"]), float(row["y"]))
    hw = max(0.55, min(1.25, float(candidate.get("entry_width_m", 1.1)) * 0.5 + extra_margin))
    half_h = max(1.05, min(1.8, float(candidate.get("entry_height_m", 2.1)) * 0.5 + 0.25))
    row_h = abs(float(row.get("h", 0.0) or 0.0) * float(row.get("sz", 1.0) or 1.0))
    shape_h = abs(float(row.get("shape_z", 0.0) or 0.0))
    h = max(row_h, shape_h)
    row_span = max(_rotate_dims(row)) * 0.5
    # Unknown-size collision nodes are still considered doorway blockers when their center
    # is essentially at the portal; later runtime validation decides whether the node is safe.
    if row_span <= 0.01:
        if side in {"north", "south"}:
            return abs(rlx - lx) <= hw + 0.25 and abs(rly - ly) <= 0.75 and abs(float(row["z"]) - ez) <= half_h + 1.0
        return abs(rly - ly) <= hw + 0.25 and abs(rlx - lx) <= 0.75 and abs(float(row["z"]) - ez) <= half_h + 1.0
    if side in {"north", "south"}:
        along = abs(rlx - lx)
        through = abs(rly - ly)
        return along <= hw + row_span and through <= max(0.18, h * 0.15) + 0.20 and abs(float(row["z"]) - ez) <= half_h + max(0.5, h * 0.5)
    along = abs(rly - ly)
    through = abs(rlx - lx)
    return along <= hw + row_span and through <= max(0.18, h * 0.15) + 0.20 and abs(float(row["z"]) - ez) <= half_h + max(0.5, h * 0.5)


def _door_score(row: dict[str, Any], candidate: dict[str, Any]) -> tuple[int, list[str]]:
    distance, side, _, _ = _distance_to_boundary(candidate, row)
    text = (str(row.get("name", "")) + " " + str(row.get("resource", ""))).lower()
    score = 0
    reasons: list[str] = []
    if distance <= 1.5:
        score += 45
        reasons.append("near_exterior_boundary")
    elif distance <= 3.0:
        score += 20
        reasons.append("near_boundary")
    if row.get("door"):
        score += 20
        reasons.append("door_node_signal")
    if any(tok in text for tok in ("entrance", "entry", "main_door", "shopfront")):
        score += 25
        reasons.append("strong_entrance_name")
    if any(tok in text for tok in ("elevator", "bathroom", "corridor", "interior")):
        score -= 25
        reasons.append("interior_door_signal")
    return max(0, min(100, score)), reasons + [f"side_{side}"]


def _collision_size(row: dict[str, Any]) -> tuple[float, float, float] | None:
    sx = abs(float(row.get("shape_x", 0.0) or 0.0))
    sy = abs(float(row.get("shape_y", 0.0) or 0.0))
    sz = abs(float(row.get("shape_z", 0.0) or 0.0))
    if sx > 0.01 or sy > 0.01 or sz > 0.01:
        return sx, sy, sz
    aabb = _row_aabb(row)
    if aabb is None:
        return None
    return aabb[1] - aabb[0], aabb[3] - aabb[2], aabb[5] - aabb[4]


def _classify_collision(row: dict[str, Any], candidate: dict[str, Any]) -> str:
    dims = _collision_size(row)
    if dims is None:
        return "unknown_size"
    sx, sy, sz = dims
    local_x, local_y = _world_to_local(candidate, float(row["x"]), float(row["y"]))
    w = float(candidate.get("width_m", 0.0))
    d = float(candidate.get("depth_m", 0.0))
    building_span = max(w, d)
    collider_span = max(sx, sy)
    center_inside = _local_point_in_rect(local_x, local_y, w, d, margin=1.0)
    if center_inside and collider_span <= 3.8 and sz <= 4.0:
        return "small_door_blocker"
    if collider_span >= max(8.0, building_span * 0.65):
        return "large_shell_collision"
    return "localized_collision"


def _sector_path_placeholder(row: dict[str, Any]) -> str:
    # The exported file path is deliberately preserved as source evidence. Mapping it
    # to a depot path is not guessed because a flat export directory does not encode it.
    return ""


def _style_profile(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Infer a conservative architectural style signature from the building's real exterior resources.

    This is deliberately lexical rather than visual: the exported sector only gives us resource
    paths/node metadata. The profile is used to bias selection toward real sibling kits, not to
    claim semantic understanding of materials.
    """
    ignore = {
        "base", "ep1", "environment", "architecture", "common", "int", "interior", "exterior",
        "building", "buildings", "wall", "floor", "ceiling", "roof", "window", "door", "mesh",
        "solid", "panel", "frame", "asset", "variant", "a", "b", "c", "d", "aa", "ab", "ac",
    }
    token_counts: Counter[str] = Counter()
    family_counts: Counter[str] = Counter()
    known = {
        "nkt", "kts", "mlt", "ent", "jp", "arasaka", "steinbeck", "megabuilding", "dogtown",
        "industrial", "apartment", "office", "mall", "casino", "diner", "hotel", "chapel",
        "tech_corridor", "common_techpanel", "common_a", "japan_town", "watson", "westbrook",
        "pacifica", "heywood", "santo_domingo", "city_center",
    }
    for row in rows:
        if not row.get("mesh") or row.get("proxy"):
            continue
        resource = str(row.get("resource", "")).lower().replace("/", "\\")
        parts = [x for x in re.split(r"[\\_\-./]+", resource) if x]
        compact_parts: list[str] = []
        for part in parts:
            if part in ignore or part.isdigit() or re.fullmatch(r"[a-z]?\d+", part):
                continue
            compact_parts.append(part)
            if part in known:
                token_counts[part] += 1
        # Prefer the distinctive family-bearing path segment immediately after common/int/buildings.
        for i, part in enumerate(parts):
            if part in {"int", "buildings", "building"} and i + 1 < len(parts):
                nxt = parts[i + 1]
                if nxt not in ignore:
                    family_counts[nxt] += 1
        stem = Path(resource).stem
        for token in known:
            if token in stem:
                token_counts[token] += 0.5
    tokens = [t for t, _ in token_counts.most_common(8)]
    families = [f for f, _ in family_counts.most_common(6)]
    # Family names themselves are valuable because the architecture assembler compares path-derived families.
    for family in families:
        short = family.replace("int_", "")
        if short and short not in tokens and short not in ignore:
            tokens.append(short)
    return {
        "version": VERSION,
        "style_tokens": tokens[:12],
        "dominant_resource_families": families,
        "sample_count": sum(1 for r in rows if r.get("mesh") and not r.get("proxy")),
        "method": "exterior_worldMeshNode_resource_path_family_and_semantic_tokens",
    }


def _candidate_audit(candidate: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    width = float(candidate.get("width_m", 0.0) or 0.0)
    depth = float(candidate.get("depth_m", 0.0) or 0.0)
    height = float(candidate.get("height_m", 0.0) or 0.0)
    radius = max(10.0, math.hypot(width, depth) * 0.60 + 4.0)
    selected: list[dict[str, Any]] = []
    for row in rows:
        lx, ly = _world_to_local(candidate, float(row["x"]), float(row["y"]))
        if _local_point_in_rect(lx, ly, width, depth, margin=3.0) or row.get("door"):
            selected.append(row)
    proxies = [r for r in selected if r.get("proxy")]
    collisions = [r for r in selected if r.get("collision")]
    doors = [r for r in selected if r.get("door")]
    meshes = [r for r in selected if r.get("mesh") and not r.get("proxy")]
    door_rows = []
    for row in doors:
        distance, side, lx, ly = _distance_to_boundary(candidate, row)
        score, reasons = _door_score(row, candidate)
        door_rows.append({
            "source_file": row.get("source_file"), "sector": row.get("sector"),
            "type": row.get("type"), "name": row.get("name"), "resource": row.get("resource"),
            "node_index": row.get("node_index"), "position": {"x": row.get("x"), "y": row.get("y"), "z": row.get("z")},
            "local": {"x": round(lx, 3), "y": round(ly, 3)}, "boundary_distance_m": round(distance, 3),
            "side": side, "score": score, "reasons": reasons,
        })
    door_rows.sort(key=lambda d: (-int(d["score"]), float(d["boundary_distance_m"]), str(d["name"])))
    best_door = door_rows[0] if door_rows else None

    blockers = []
    for row in collisions:
        if best_door and _overlaps_opening(row, candidate):
            cls = _classify_collision(row, candidate)
            blockers.append({
                "source_file": row.get("source_file"), "sector": row.get("sector"),
                "type": row.get("type"), "node_index": row.get("node_index"),
                "name": row.get("name"), "resource": row.get("resource"),
                "expectedNodes": row.get("source_node_count"), "classification": cls,
                "shape_kind": row.get("shape_kind"),
                "shape_dimensions_m": {"x": row.get("shape_x"), "y": row.get("shape_y"), "z": row.get("shape_z")},
            })

    proxy_only = bool(proxies) and not meshes and not collisions
    if proxy_only:
        collision_status = "proxy_only_no_explicit_collision"
    elif collisions:
        collision_status = "explicit_collision_present"
    else:
        collision_status = "no_explicit_collision_evidence"

    if best_door is None:
        door_status = "no_confident_exterior_door"
    elif best_door["score"] >= 70:
        door_status = "confident_exterior_door"
    elif best_door["score"] >= 45:
        door_status = "probable_exterior_door"
    else:
        door_status = "weak_door_evidence"

    if blockers and any(b["classification"] == "large_shell_collision" for b in blockers):
        access_action = "requires_collision_mesh_replacement_or_runtime_validation"
    elif blockers and any(b["classification"] in {"small_door_blocker", "localized_collision"} for b in blockers):
        access_action = "candidate_for_archive_xl_collision_node_removal"
    elif best_door and collision_status == "no_explicit_collision_evidence":
        access_action = "runtime_probe_for_embedded_collision"
    elif proxy_only:
        access_action = "runtime_probe_proxy_only"
    elif not best_door:
        access_action = "manual_review_no_portal"
    else:
        access_action = "runtime_probe_required"

    removal_candidates = []
    for blocker in blockers:
        if blocker["classification"] in {"small_door_blocker", "localized_collision"} and blocker.get("node_index") is not None:
            removal_candidates.append({
                "source_file": blocker.get("source_file"), "sector": blocker.get("sector"),
                "node_type": blocker.get("type"), "node_index": blocker.get("node_index"),
                "expectedNodes": blocker.get("expectedNodes"),
                "archive_xl_sector_path": _sector_path_placeholder(blocker),
                "reason": "explicit_collision_overlaps_detected_exterior_door",
                "safe_to_auto_remove": blocker["classification"] == "small_door_blocker",
            })

    if proxy_only:
        proxy_state = "proxy_only"
    elif proxies:
        proxy_state = "proxy_plus_runtime_or_collision_geometry"
    else:
        proxy_state = "no_proxy_evidence"

    style = _style_profile(selected)

    return {
        "building_id": candidate.get("id"),
        "collision_status": collision_status,
        "proxy_status": proxy_state,
        "door_status": door_status,
        "recommended_access_action": access_action,
        "selected_physics_records": len(selected),
        "proxy_node_count": len(proxies),
        "explicit_collision_node_count": len(collisions),
        "visible_mesh_node_count": len(meshes),
        "door_node_count": len(doors),
        "style_profile": style,
        "doors": door_rows[:12],
        "best_exterior_door": best_door,
        "door_collision_blockers": blockers,
        "removal_candidates": removal_candidates,
        "runtime_validation": {
            "required": access_action.startswith("runtime_probe") or "runtime_validation" in access_action,
            "reason": "Missing explicit collision can still mean embedded collision in the mesh; only runtime inspection can distinguish these cases.",
        },
        "geometry": {"width_m": width, "depth_m": depth, "height_m": height, "query_radius_m": radius},
    }


def annotate_candidates(candidate_report: dict[str, Any], db_path: str | Path) -> dict[str, Any]:
    idx = load_index(db_path)
    try:
        out_candidates = []
        counts = Counter()
        for candidate in candidate_report.get("candidates", []) or []:
            if not isinstance(candidate, dict):
                continue
            p = candidate.get("position") or {}
            width = float(candidate.get("width_m", 10.0) or 10.0)
            depth = float(candidate.get("depth_m", 10.0) or 10.0)
            radius = max(12.0, math.hypot(width, depth) * 0.65 + 5.0)
            rows = idx.query(float(p.get("x", 0.0)), float(p.get("y", 0.0)), radius)
            audit = _candidate_audit(candidate, rows)
            c = dict(candidate)
            evidence = dict(c.get("evidence") or {})
            evidence["physics"] = audit
            c["evidence"] = evidence
            q = dict(c.get("quality") or {})
            action = str(c.get("suggested_action") or "review")
            if audit["recommended_access_action"] == "requires_collision_mesh_replacement_or_runtime_validation":
                action = "review"
                q.setdefault("reasons", []).append("large_collision_blocks_entry")
            elif audit["door_status"] == "no_confident_exterior_door":
                action = "review"
                q.setdefault("reasons", []).append("no_confident_exterior_door")
            elif audit["proxy_status"] == "proxy_only" and audit["visible_mesh_node_count"] == 0:
                action = "review"
                q.setdefault("reasons", []).append("proxy_only_no_visible_mesh")
            c["suggested_action"] = action
            q["access_audit_version"] = VERSION
            q["access_action"] = audit["recommended_access_action"]
            q["collision_status"] = audit["collision_status"]
            q["door_status"] = audit["door_status"]
            c["style_profile"] = audit.get("style_profile", {})
            c["style_tokens"] = list(audit.get("style_profile", {}).get("style_tokens", []))
            c["quality"] = q
            out_candidates.append(c)
            counts[audit["recommended_access_action"]] += 1
        out_candidates.sort(key=lambda c: (-int(c.get("score", 0)), str(c.get("id", ""))))
        return {
            "format": FORMAT,
            "version": VERSION,
            "source_format": candidate_report.get("format"),
            "input_candidate_count": len(candidate_report.get("candidates", []) or []),
            "output_candidate_count": len(out_candidates),
            "access_action_counts": dict(sorted(counts.items())),
            "physics_index": idx.manifest(),
            "candidates": out_candidates,
            "notes": [
                "Proxy meshes are evidence for distant exterior geometry only; they never count as collision.",
                "Explicit worldCollisionNode overlap is used to locate likely door blockers.",
                "Large collision shells are never auto-deleted; they require collision-mesh replacement or in-game validation.",
                "A missing worldCollisionNode does not prove a mesh is non-collidable because embedded mesh collision may exist.",
            ],
        }
    finally:
        idx.close()


def write_removal_manifest(candidate_report: dict[str, Any], out_path: str | Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for c in candidate_report.get("candidates", []) or []:
        physics = (c.get("evidence") or {}).get("physics") or {}
        for item in physics.get("removal_candidates", []) or []:
            rows.append({"building_id": c.get("id"), **item})
    data = {
        "format": "ncig-collision-removal-manifest-v1",
        "version": VERSION,
        "candidate_count": len(candidate_report.get("candidates", []) or []),
        "removal_target_count": len(rows),
        "targets": rows,
        "notes": [
            "This is an evidence manifest, not a guessed ArchiveXL .xl file.",
            "The depot sector path is intentionally left blank when the export directory does not preserve it.",
            "Only small/localized worldCollisionNode targets are marked safe_to_auto_remove; a large shell collider requires a custom collision mesh replacement or explicit runtime test.",
        ],
    }
    p = Path(out_path); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return data


def main() -> int:
    p = argparse.ArgumentParser(description="NCIG 0.24.0 world collision/proxy/door audit")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("annotate-candidates")
    a.add_argument("--input", required=True)
    a.add_argument("--physics-index", required=True)
    a.add_argument("--out", required=True)
    a.add_argument("--removal-manifest")
    args = p.parse_args()
    report = json.loads(Path(args.input).read_text(encoding="utf-8"))
    out = annotate_candidates(report, args.physics_index)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.removal_manifest:
        write_removal_manifest(out, args.removal_manifest)
    print(json.dumps({"output_candidate_count": out["output_candidate_count"], "access_action_counts": out["access_action_counts"]}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
