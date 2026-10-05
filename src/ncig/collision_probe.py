from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from . import physics_index as pi

VERSION = "0.25.3"
FORMAT = "ncig-collision-probe-v1"


def _load(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _unwrap_sector(raw: dict[str, Any]) -> dict[str, Any] | None:
    if isinstance(raw.get("sector"), dict):
        return raw["sector"]
    if isinstance(raw.get("sectors"), list):
        for item in raw["sectors"]:
            if isinstance(item, dict) and isinstance(item.get("nodes"), list):
                return item
    data = raw.get("Data")
    if isinstance(data, dict):
        root = data.get("RootChunk")
        if isinstance(root, dict) and isinstance(root.get("nodes"), list):
            return root
        if isinstance(data.get("nodes"), list):
            return data
    if isinstance(raw.get("nodes"), list):
        return raw
    return None


def _resolve_sector_file(source_file: str, sectors_root: Path) -> Path | None:
    direct = Path(source_file)
    if direct.exists():
        return direct
    candidate = sectors_root / direct.name
    if candidate.exists():
        return candidate
    matches = list(sectors_root.rglob(direct.name))
    return matches[0] if matches else None


def _archive_xl_text(target: dict[str, Any], sector_path: str) -> str:
    expected = int(target["expectedNodes"])
    idx = int(target["node_index"])
    typ = str(target["node_type"])
    comment = str(target.get("name") or target.get("resource") or "NCIG collision target")
    return (
        "streaming:\n"
        "  sectors:\n"
        f"    - path: {sector_path}\n"
        f"      expectedNodes: {expected}\n"
        "      nodeDeletions:\n"
        f"        # REVIEW: {comment}\n"
        f"        - index: {idx}\n"
        f"          type: {typ}\n"
    )


def probe_manifest(
    manifest_path: str | Path,
    sectors_root: str | Path,
    *,
    out_path: str | Path,
    limit: int = 1,
    safe_only: bool = True,
    xl_out: str | Path | None = None,
    depot_sector_path: str | None = None,
    neighbor_radius: int = 3,
) -> dict[str, Any]:
    manifest = _load(manifest_path)
    targets = [x for x in manifest.get("targets", []) if isinstance(x, dict)]
    if safe_only:
        targets = [x for x in targets if bool(x.get("safe_to_auto_remove"))]
    targets = targets[: max(1, int(limit))]
    root = Path(sectors_root)
    probes: list[dict[str, Any]] = []
    generated_xl = False
    xl_reason = ""

    for target in targets:
        source = str(target.get("source_file", ""))
        sector_file = _resolve_sector_file(source, root)
        if sector_file is None:
            probes.append({"status": "missing_sector_file", "target": target})
            continue
        raw = _load(sector_file)
        sector = _unwrap_sector(raw)
        if not sector:
            probes.append({"status": "unrecognized_sector_envelope", "sector_file": str(sector_file), "target": target})
            continue
        nodes = pi._flatten_nodes(sector)
        placements = pi._node_data_entries(sector)
        by_index = {i: n for i, n in enumerate(nodes)}
        placement_by_index: dict[int, dict[str, Any]] = {}
        for placement in placements:
            idx = pi._node_index(placement.get("NodeIndex", placement.get("nodeIndex", placement.get("node_index"))))
            if idx is not None and idx not in placement_by_index:
                placement_by_index[idx] = placement
        idx = int(target["node_index"])
        node = by_index.get(idx)
        if node is None:
            probes.append({
                "status": "node_index_out_of_range",
                "sector_file": str(sector_file),
                "target": target,
                "actual_node_count": len(nodes),
            })
            continue
        actual_type = pi._node_type(node)
        placement = placement_by_index.get(idx, {})
        record = {
            "source_file": str(sector_file), "sector": str(sector.get("name") or sector.get("sectorName") or sector_file.stem),
            "type": actual_type, "name": pi._node_name(node), "resource": pi._resource_path(node),
            "x": pi._node_position(placement or node)[0] if pi._node_position(placement or node) else 0.0,
            "y": pi._node_position(placement or node)[1] if pi._node_position(placement or node) else 0.0,
            "z": pi._node_position(placement or node)[2] if pi._node_position(placement or node) else 0.0,
            "yaw_deg": pi._node_yaw(placement or node), "scale": pi._node_scale(placement or node),
            "node": node, "placement": placement,
        }
        shape_kind, shape_dims, shape_source = pi._shape_info(record)
        neighbors = []
        lo = max(0, idx - int(neighbor_radius)); hi = min(len(nodes), idx + int(neighbor_radius) + 1)
        for nidx in range(lo, hi):
            n = nodes[nidx]
            neighbors.append({
                "node_index": nidx,
                "type": pi._node_type(n),
                "name": pi._node_name(n),
                "resource": pi._resource_path(n),
                "placement": placement_by_index.get(nidx),
                "node": n,
            })
        expected = int(target.get("expectedNodes", -1))
        result = {
            "status": "ok",
            "building_id": target.get("building_id"),
            "sector_file": str(sector_file.resolve()),
            "sector": str(sector.get("name") or sector.get("sectorName") or sector_file.stem),
            "target": target,
            "validation": {
                "actual_node_count": len(nodes),
                "expectedNodes_matches": expected == len(nodes),
                "node_index_exists": True,
                "node_type_matches_manifest": actual_type == str(target.get("node_type")),
                "shape_kind": shape_kind,
                "shape_dimensions": shape_dims,
                "shape_source": shape_source,
            },
            "node": node,
            "node_data_placement": placement,
            "neighbors": neighbors,
        }
        probes.append(result)

        if xl_out and depot_sector_path and len(probes) == 1 and result["status"] == "ok":
            Path(xl_out).parent.mkdir(parents=True, exist_ok=True)
            Path(xl_out).write_text(_archive_xl_text({**target, "name": result["node"].get("name", "")}, depot_sector_path), encoding="utf-8")
            generated_xl = True
    if xl_out and not generated_xl:
        xl_reason = "No verified depot sector path supplied; probe JSON is generated but no installable ArchiveXL file is fabricated."

    report = {
        "format": FORMAT,
        "version": VERSION,
        "manifest": str(Path(manifest_path).resolve()),
        "sectors_root": str(root.resolve()),
        "safe_only": bool(safe_only),
        "probes": probes,
        "archive_xl": {
            "requested": bool(xl_out),
            "generated": generated_xl,
            "path": str(Path(xl_out).resolve()) if generated_xl and xl_out else "",
            "reason": xl_reason,
            "verified_depot_path_required": True,
        },
        "note": "This probe extracts the exact exported node and neighboring node payloads. It does not modify the source sector.",
    }
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> int:
    p = argparse.ArgumentParser(description="Extract exact collision nodes from exported Cyberpunk streaming sectors")
    p.add_argument("--manifest", required=True)
    p.add_argument("--sectors", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--limit", type=int, default=1)
    p.add_argument("--safe-only", action="store_true")
    p.add_argument("--xl-out")
    p.add_argument("--depot-sector-path", help="Verified ArchiveXL sector path; without this no .xl file is emitted")
    p.add_argument("--neighbor-radius", type=int, default=3)
    args = p.parse_args()
    report = probe_manifest(
        args.manifest, args.sectors, out_path=args.out, limit=args.limit, safe_only=args.safe_only,
        xl_out=args.xl_out, depot_sector_path=args.depot_sector_path, neighbor_radius=args.neighbor_radius,
    )
    print(json.dumps({
        "written": args.out,
        "probes": len(report["probes"]),
        "ok": sum(1 for x in report["probes"] if x.get("status") == "ok"),
        "archive_xl_generated": report["archive_xl"]["generated"],
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
