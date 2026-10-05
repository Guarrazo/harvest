from __future__ import annotations

import argparse
import json
import math
import re
import sqlite3
import time
from collections import OrderedDict, defaultdict
from pathlib import Path
from typing import Any

from . import city_index as ci
from . import target_detector as td
from .io import write_json

VERSION = "0.30.1"
DEFAULT_CACHE_WINDOWS = 256
CHECKPOINT_EVERY = 500
HEARTBEAT_EVERY = 100
CELL_SIZE_M = 16.0


def _distance(a: dict[str, Any], b: dict[str, Any]) -> float:
    return math.sqrt(
        (float(a["x"]) - float(b["x"])) ** 2
        + (float(a["y"]) - float(b["y"])) ** 2
        + (float(a["z"]) - float(b["z"])) ** 2
    )


def _cell(x: float, y: float) -> tuple[int, int]:
    return math.floor(float(x) / CELL_SIZE_M), math.floor(float(y) / CELL_SIZE_M)


def _clusters_spatial(records: list[dict[str, Any]], radius_m: float) -> list[list[dict[str, Any]]]:
    """Exact legacy clustering semantics with spatial hashing and deterministic seed order."""
    if not records:
        return []
    buckets: dict[tuple[int, int], list[int]] = defaultdict(list)
    for i, r in enumerate(records):
        buckets[_cell(r["x"], r["y"])].append(i)
    visited = [False] * len(records)
    out: list[list[dict[str, Any]]] = []
    for seed_idx in range(len(records)):
        if visited[seed_idx]:
            continue
        visited[seed_idx] = True
        queue = [seed_idx]
        indices = [seed_idx]
        while queue:
            current = records[queue.pop()]
            cx, cy = _cell(current["x"], current["y"])
            span = max(1, int(math.ceil(radius_m / CELL_SIZE_M)))
            for gx in range(cx - span, cx + span + 1):
                for gy in range(cy - span, cy + span + 1):
                    for idx in buckets.get((gx, gy), ()):
                        if visited[idx]:
                            continue
                        if _distance(current, records[idx]) <= radius_m:
                            visited[idx] = True
                            indices.append(idx)
                            queue.append(idx)
        out.append([records[i] for i in indices])
    return out


class SQLiteSpatialSource:
    def __init__(self, db_path: str | Path, *, max_cache_windows: int = DEFAULT_CACHE_WINDOWS) -> None:
        self.db_path = str(db_path)
        self.conn = sqlite3.connect(self.db_path)
        # Read-mostly detector connection: keep SQLite from creating a large
        # rollback/WAL footprint and avoid persistent writes during detection.
        self.conn.execute("PRAGMA query_only = ON")
        self.conn.execute("PRAGMA busy_timeout = 5000")
        self.max_cache_windows = max(0, int(max_cache_windows))
        self.cache: OrderedDict[tuple[str, int, int, int, int], list[dict[str, Any]]] = OrderedDict()
        self.cache_hits = 0
        self.cache_misses = 0

    def close(self) -> None:
        self.conn.close()

    @staticmethod
    def _select_sql(flag: str, xmin: int, xmax: int, ymin: int, ymax: int) -> str:
        # Do not ORDER BY id here. The flag+cell predicate is index-friendly,
        # while ordering by id can force SQLite to materialize a temporary B-tree
        # on disk for a large spatial window. Deterministic ordering is restored
        # in Python below.
        return (
            "SELECT source_file,sector,category,type,name,resource,x,y,z,yaw_deg,"
            "sx,sy,sz,l,w,h FROM records "
            f"WHERE {flag}=1 AND cell_x BETWEEN ? AND ? AND cell_y BETWEEN ? AND ?"
        )

    def _query(self, flag: str, x: float, y: float, radius: float) -> list[dict[str, Any]]:
        # For a given center cell the SQL window is identical. Use a bounded LRU
        # cache so a city-wide scan cannot grow Python memory/pagefile without limit.
        cx, cy = _cell(x, y)
        span = max(1, int(math.ceil(radius / CELL_SIZE_M)))
        key = (flag, cx - span, cx + span, cy - span, cy + span)
        rows = self.cache.get(key)
        if rows is not None:
            self.cache_hits += 1
            self.cache.move_to_end(key)
        else:
            self.cache_misses += 1
            cur = self.conn.execute(
                self._select_sql(flag, key[1], key[2], key[3], key[4]),
                (key[1], key[2], key[3], key[4]),
            )
            rows = [ci._record(row) for row in cur.fetchall()]
            if self.max_cache_windows:
                self.cache[key] = rows
                self.cache.move_to_end(key)
                while len(self.cache) > self.max_cache_windows:
                    self.cache.popitem(last=False)
        rr = float(radius) * float(radius)
        # First apply the exact-radius test; only the surviving rows are sorted.
        # This avoids Python sorting the much larger bounding-cell result set.
        filtered = [
            r for r in rows
            if (float(r["x"]) - x) ** 2 + (float(r["y"]) - y) ** 2 <= rr
        ]
        filtered.sort(key=lambda r: (
            str(r.get("source_file", "")), str(r.get("sector", "")),
            str(r.get("resource", "")), float(r.get("x", 0.0)),
            float(r.get("y", 0.0)), float(r.get("z", 0.0)),
        ))
        return filtered

    def entrances(self) -> list[dict[str, Any]]:
        cur = self.conn.execute(
            "SELECT source_file,sector,category,type,name,resource,x,y,z,yaw_deg,sx,sy,sz,l,w,h "
            "FROM records WHERE entrance=1 ORDER BY id"
        )
        return [ci._record(row) for row in cur.fetchall()]

    def architecture_near(self, x: float, y: float, radius: float) -> list[dict[str, Any]]:
        return self._query("architecture", x, y, radius)

    def interiors_near(self, x: float, y: float, radius: float) -> list[dict[str, Any]]:
        return self._query("interior", x, y, radius)


def _checkpoint_path(out_path: str | Path) -> Path:
    return Path(str(out_path) + ".partial.json")


def _atomic_write_json(path: str | Path, payload: dict[str, Any]) -> None:
    dst = Path(path)
    tmp = dst.with_name(dst.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(dst)


def detect_building_candidates_indexed(
    db_path: str | Path,
    *,
    cluster_radius_m: float = 18.0,
    checkpoint_out: str | Path | None = None,
    resume: bool = True,
    cache_windows: int = DEFAULT_CACHE_WINDOWS,
) -> dict[str, Any]:
    started = time.monotonic()
    source = SQLiteSpatialSource(db_path, max_cache_windows=cache_windows)
    try:
        entrances = source.entrances()
        print(f"NCIG {VERSION}: loaded {len(entrances)} entrance records from SQLite (no full-city load)", flush=True)
        group_radius = min(8.0, cluster_radius_m * 0.5)
        print("NCIG 0.30.1: spatial-clustering entrance groups", flush=True)
        entrance_groups = _clusters_spatial(entrances, group_radius)
        print(f"NCIG {VERSION}: entrance groups={len(entrance_groups)}", flush=True)

        candidates: list[dict[str, Any]] = []
        arch_cache_hits = arch_cache_misses = int_cache_hits = int_cache_misses = 0
        start_group = 1
        cp_path = Path(checkpoint_out) if checkpoint_out else None
        if resume and cp_path and cp_path.exists():
            try:
                cp = json.loads(cp_path.read_text(encoding="utf-8"))
                db_stat = Path(db_path).stat()
                valid = (
                    cp.get("format") == "ncig-city-detect-checkpoint-v1"
                    and cp.get("detector_version") == VERSION
                    and float(cp.get("cluster_radius_m", -1)) == float(cluster_radius_m)
                    and int(cp.get("entrance_record_count", -1)) == len(entrances)
                    and int(cp.get("group_count", -1)) == len(entrance_groups)
                    and int(cp.get("db_size", -1)) == int(db_stat.st_size)
                    and int(cp.get("db_mtime_ns", -1)) == int(db_stat.st_mtime_ns)
                )
                next_group = int(cp.get("next_group", 1))
                if valid and 1 <= next_group <= len(entrance_groups) + 1:
                    candidates = list(cp.get("candidates", []))
                    arch_cache_hits = int(cp.get("arch_cache_hits", 0))
                    arch_cache_misses = int(cp.get("arch_cache_misses", 0))
                    int_cache_hits = int(cp.get("int_cache_hits", 0))
                    int_cache_misses = int(cp.get("int_cache_misses", 0))
                    start_group = next_group
                    print(f"NCIG {VERSION}: resuming from entrance group {start_group}/{len(entrance_groups)}", flush=True)
            except Exception as exc:
                print(f"NCIG {VERSION}: ignoring invalid checkpoint: {exc}", flush=True)

        def checkpoint(group_index: int) -> None:
            if not cp_path:
                return
            db_stat = Path(db_path).stat()
            _atomic_write_json(cp_path, {
                "format": "ncig-city-detect-checkpoint-v1",
                "detector_version": VERSION,
                "cluster_radius_m": cluster_radius_m,
                "db_size": db_stat.st_size,
                "db_mtime_ns": db_stat.st_mtime_ns,
                "entrance_record_count": len(entrances),
                "group_count": len(entrance_groups),
                "next_group": group_index + 1,
                "candidates": candidates,
                "arch_cache_hits": arch_cache_hits,
                "arch_cache_misses": arch_cache_misses,
                "int_cache_hits": int_cache_hits,
                "int_cache_misses": int_cache_misses,
            })

        for group_index, entrance_group in enumerate(entrance_groups, start=1):
            if group_index < start_group:
                continue
            if group_index == start_group or group_index % HEARTBEAT_EVERY == 0:
                print(
                    f"NCIG {VERSION}: detector heartbeat {group_index}/{len(entrance_groups)}; LRU cache={len(source.cache)}/{cache_windows}",
                    flush=True,
                )
            ex = sum(float(r["x"]) for r in entrance_group) / len(entrance_group)
            ey = sum(float(r["y"]) for r in entrance_group) / len(entrance_group)
            ez = sum(float(r["z"]) for r in entrance_group) / len(entrance_group)
            before = len(source.cache)
            nearby = source.architecture_near(ex, ey, cluster_radius_m)
            after = len(source.cache)
            if after == before:
                arch_cache_hits += 1
            else:
                arch_cache_misses += 1
            if len(nearby) < 3:
                if group_index % CHECKPOINT_EVERY == 0 or group_index == len(entrance_groups):
                    checkpoint(group_index)
                    print(
                        f"NCIG {VERSION}: detector progress {group_index}/{len(entrance_groups)} groups; LRU cache={len(source.cache)}/{cache_windows}; hits={source.cache_hits}; misses={source.cache_misses}",
                        flush=True,
                    )
                continue
            before = len(source.cache)
            local_interiors = source.interiors_near(ex, ey, min(20.0, cluster_radius_m + 2.0))
            after = len(source.cache)
            if after == before:
                int_cache_hits += 1
            else:
                int_cache_misses += 1

            group = nearby + entrance_group
            building_text = " ".join(str(r.get("text", "")) for r in group)
            btype = td._building_type(building_text)
            district = td._district_from_text(building_text)
            center_x, center_y, u_min, u_max, v_min, v_max, yaw_deg = td._oriented_bounds(nearby)
            width = max(4.5, (u_max - u_min) + 0.80)
            depth = max(4.5, (v_max - v_min) + 0.80)
            z_values = [float(r["z"]) for r in nearby]
            min_z, max_z = min(z_values), max(z_values)
            for r in nearby:
                bounds = td._record_footprint(r)
                if bounds is not None:
                    min_z = min(min_z, bounds[4])
                    max_z = max(max_z, bounds[5])
            height = max(3.2, (max_z - min_z) + 0.5)
            floors = max(1, min(20, int(round(height / 3.2))))

            theta = math.radians(yaw_deg)
            ct, st = math.cos(theta), math.sin(theta)
            entry_local_x = (ex - center_x) * ct + (ey - center_y) * st
            entry_local_y = -(ex - center_x) * st + (ey - center_y) * ct
            half_w, half_d = width * 0.5, depth * 0.5
            entry_local_x = max(-half_w, min(half_w, entry_local_x))
            entry_local_y = max(-half_d, min(half_d, entry_local_y))
            side_dist = {
                "north": abs(entry_local_y + half_d), "south": abs(entry_local_y - half_d),
                "west": abs(entry_local_x + half_w), "east": abs(entry_local_x - half_w),
            }
            entry_side = min(side_dist, key=side_dist.get)
            entry_facing_deg = math.degrees(math.atan2(ey - center_y, ex - center_x))

            token_counts = td.Counter()
            for r in group:
                token_text = str(r.get("text", "")).lower()
                for token in td._BUILDING_TOKENS + td._ENTRANCE_TOKENS:
                    if token in token_text:
                        token_counts[token] += 1

            wall_records = [r for r in nearby if td._record_kind(r) == "wall"]
            wall_sides: set[str] = set()
            for wr in wall_records:
                wx, wy = float(wr["x"]), float(wr["y"])
                local_x = (wx - center_x) * ct + (wy - center_y) * st
                local_y = -(wx - center_x) * st + (wy - center_y) * ct
                dists = {
                    "north": abs(local_y + half_d), "south": abs(local_y - half_d),
                    "west": abs(local_x + half_w), "east": abs(local_x - half_w),
                }
                wall_sides.add(min(dists, key=dists.get))
            wall_count = len(wall_records)
            geometry_ready = (
                wall_count >= 2 and len(wall_sides) >= 2 and
                4.5 <= width <= 32.0 and 4.5 <= depth <= 32.0 and
                3.2 <= height <= 64.0 and floors <= 20
            )

            detected_openings: list[dict[str, Any]] = []
            for wr in (r for r in nearby if td._is_window(r)):
                wx, wy = float(wr["x"]), float(wr["y"])
                local_x = (wx - center_x) * ct + (wy - center_y) * st
                local_y = -(wx - center_x) * st + (wy - center_y) * ct
                dists = {
                    "north": abs(local_y + half_d), "south": abs(local_y - half_d),
                    "west": abs(local_x + half_w), "east": abs(local_x - half_w),
                }
                side = min(dists, key=dists.get)
                dims_w = td._resource_dimensions(str(wr.get("resource", "")))
                span = max(dims_w.get("l", 0.0), dims_w.get("w", 0.0))
                height_w = dims_w.get("h", 0.0)
                detected_openings.append({
                    "kind": "window", "side": side,
                    "local_x": round(local_x, 3), "local_y": round(local_y, 3),
                    "width_m": round(max(0.6, min(6.0, span or 1.5)), 3),
                    "height_m": round(max(0.8, min(3.0, height_w or 1.4)), 3),
                    "yaw_deg": round(float(wr.get("yaw_deg", yaw_deg)), 3),
                    "resource": str(wr.get("resource", "")),
                })

            entry_dims = [td._resource_dimensions(str(r.get("resource", ""))) for r in entrance_group]
            entry_spans = [max(d.get("l", 0.0), d.get("w", 0.0)) for d in entry_dims]
            entry_heights = [d.get("h", 0.0) for d in entry_dims]
            entry_width = max(0.8, min(2.5, max(entry_spans, default=1.1)))
            entry_height = max(1.8, min(3.0, max(entry_heights, default=2.1)))

            score = min(42, len(nearby) * 1.8)
            score += min(30, len(entrance_group) * 12)
            score += 18 if not local_interiors else 5
            score -= min(18, len(local_interiors) * 3)
            if any(t in token_counts for t in ("building", "tower", "shop", "store", "apartment", "office", "factory")):
                score += 8
            negative = sum(1 for r in nearby if td._has_token(str(r.get("text", "")).lower(), td._EXTERIOR_NEGATIVE))
            score -= min(10, negative * 2)
            score = max(0, min(100, int(round(score))))

            confidence = "high" if score >= 80 else "medium" if score >= 60 else "low"
            candidate_id = f"auto_{group_index:04d}_{re.sub(r'[^a-z0-9]+', '_', btype.lower()).strip('_') or 'mixed'}"
            candidates.append({
                "id": candidate_id, "confidence": confidence, "score": score, "type": btype, "district": district,
                "position": {"x": round(center_x, 3), "y": round(center_y, 3), "z": round(min_z, 3)},
                "yaw_deg": round(yaw_deg, 3), "width_m": round(width, 3), "depth_m": round(depth, 3),
                "height_m": round(height, 3), "floors": floors, "entry_side": entry_side,
                "entry_local_x": round(entry_local_x, 3), "entry_local_y": round(entry_local_y, 3),
                "entry_world": {"x": round(ex, 3), "y": round(ey, 3), "z": round(ez, 3)},
                "entry_facing_deg": round(entry_facing_deg, 3), "entry_yaw_deg": round(entry_facing_deg, 3),
                "entry_width_m": round(entry_width, 3), "entry_height_m": round(entry_height, 3),
                "detected_openings": detected_openings[:24],
                "exterior_bounds": {"width_m": round(width, 3), "depth_m": round(depth, 3), "z_min": round(min_z, 3), "z_max": round(max_z, 3)},
                "evidence": {
                    "architecture_nodes": len(nearby), "entrance_nodes": len(entrance_group),
                    "wall_nodes": wall_count, "wall_sides": sorted(wall_sides), "geometry_ready": geometry_ready,
                    "interior_nodes": len(local_interiors), "sectors": sorted({str(r.get("sector")) for r in group}),
                    "source_files": sorted({str(r.get("source_file")) for r in group}),
                    "token_counts": dict(sorted(token_counts.items())), "negative_exterior_signals": negative,
                    "geometry_estimated_from": "node_position_plus_filename_lwh_hints_when_available",
                },
                "suggested_action": "fill" if confidence in {"high", "medium"} and geometry_ready and not local_interiors else "review",
            })

            if group_index % CHECKPOINT_EVERY == 0 or group_index == len(entrance_groups):
                checkpoint(group_index)
                print(
                    f"NCIG {VERSION}: detector progress {group_index}/{len(entrance_groups)} groups; LRU cache={len(source.cache)}/{cache_windows}; hits={source.cache_hits}; misses={source.cache_misses}",
                    flush=True,
                )

        candidates.sort(key=lambda c: (-int(c["score"]), c["id"]))
        return {
            "format": td.FORMAT,
            "input_record_count": None,
            "architecture_record_count": None,
            "entrance_record_count": len(entrances),
            "cluster_radius_m": cluster_radius_m,
            "candidate_count": len(candidates),
            "candidates": candidates,
            "detector_engine": "sqlite_spatial_v2",
            "notes": [
                "Only entrance rows are loaded globally; architecture and interior rows are queried by indexed spatial cells on demand.",
                "Entrance clustering preserves deterministic input order while using spatial hashing instead of O(N²) scanning.",
                "Candidate schema remains ncig-building-candidates-v1 for compatibility with existing refinement and access-audit stages.",
            ],
            "performance": {
                "sql_window_cache_entries": len(source.cache),
                "sql_window_cache_limit": cache_windows,
                "sql_window_cache_hits": source.cache_hits,
                "sql_window_cache_misses": source.cache_misses,
                "architecture_window_cache_hits": arch_cache_hits,
                "architecture_window_cache_misses": arch_cache_misses,
                "interior_window_cache_hits": int_cache_hits,
                "interior_window_cache_misses": int_cache_misses,
            },
        }
    finally:
        source.close()


def run(
    input_path: str | Path,
    out_path: str | Path,
    *,
    radius: float = 18.0,
    resume: bool = True,
    cache_windows: int = DEFAULT_CACHE_WINDOWS,
) -> dict[str, Any]:
    started = time.monotonic()
    checkpoint = _checkpoint_path(out_path)
    report = detect_building_candidates_indexed(
        input_path,
        cluster_radius_m=float(radius),
        checkpoint_out=checkpoint,
        resume=resume,
        cache_windows=cache_windows,
    )
    report["index_source"] = str(Path(input_path).resolve())
    report["detector_version"] = VERSION
    report["elapsed_seconds"] = round(time.monotonic() - started, 3)
    write_json(out_path, report)
    checkpoint = _checkpoint_path(out_path)
    if checkpoint.exists():
        checkpoint.unlink()
    return report


def main() -> int:
    p = argparse.ArgumentParser(description="Detect NCIG building candidates directly from the persistent city SQLite index")
    p.add_argument("--input", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--radius", type=float, default=18.0)
    p.add_argument("--cache-windows", type=int, default=DEFAULT_CACHE_WINDOWS)
    p.add_argument("--no-resume", action="store_true")
    args = p.parse_args()
    report = run(
        args.input, args.out, radius=args.radius,
        resume=not args.no_resume, cache_windows=max(0, args.cache_windows),
    )
    print(json.dumps({
        "written": args.out,
        "entrance_records": report.get("entrance_record_count", 0),
        "candidate_count": report.get("candidate_count", 0),
        "detector_version": VERSION,
        "elapsed_seconds": report.get("elapsed_seconds"),
        "sql_window_cache_entries": (report.get("performance") or {}).get("sql_window_cache_entries", 0),
        "sql_window_cache_limit": (report.get("performance") or {}).get("sql_window_cache_limit", 0),
        "checkpoint": str(_checkpoint_path(args.out)),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
