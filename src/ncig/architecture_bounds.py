from __future__ import annotations

import json
from pathlib import Path
from typing import Any

FORMAT = "ncig-architecture-bounds-v1"


def _load(path: str | Path) -> dict[str, Any]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected JSON object")
    return raw


def _valid_box(value: Any) -> bool:
    return isinstance(value, dict) and all(k in value for k in ("x", "y", "z"))


def merge_bounds_into_catalog(catalog: dict[str, Any], bounds: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    records = bounds.get("bounds", {})
    if not isinstance(records, dict):
        raise ValueError("bounds file must contain a 'bounds' object")
    out = json.loads(json.dumps(catalog))
    matched = 0
    missing = 0
    invalid = 0
    for item in out.get("items", []) or []:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", "")).replace("/", "\\")
        rec = records.get(path) or records.get(path.replace("\\", "/"))
        if not isinstance(rec, dict):
            missing += 1
            continue
        min_v, max_v = rec.get("min"), rec.get("max")
        if not (_valid_box(min_v) and _valid_box(max_v)):
            invalid += 1
            continue
        dims = {
            "x": abs(float(max_v["x"]) - float(min_v["x"])),
            "y": abs(float(max_v["y"]) - float(min_v["y"])),
            "z": abs(float(max_v["z"]) - float(min_v["z"])),
        }
        item["bounds"] = {
            "source": "runtime_mesh_resource",
            "min": {k: float(min_v[k]) for k in ("x", "y", "z")},
            "max": {k: float(max_v[k]) for k in ("x", "y", "z")},
            "dimensions_m": dims,
            "has_physics": bool(rec.get("has_physics")),
        }
        matched += 1
    out["bounds_enriched"] = True
    out["bounds_source_format"] = bounds.get("format", FORMAT)
    report = {
        "format": FORMAT,
        "catalog_items": len(out.get("items", []) or []),
        "matched": matched,
        "missing": missing,
        "invalid": invalid,
        "coverage": round(matched / max(1, len(out.get("items", []) or [])), 4),
        "runtime_dimensions_available": matched > 0,
    }
    return out, report


def merge_bounds_file(catalog_path: str | Path, bounds_path: str | Path, out_path: str | Path, report_path: str | Path | None = None) -> dict[str, Any]:
    catalog = _load(catalog_path)
    bounds = _load(bounds_path)
    merged, report = merge_bounds_into_catalog(catalog, bounds)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if report_path:
        Path(report_path).parent.mkdir(parents=True, exist_ok=True)
        Path(report_path).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def build_bounds_targets(catalog: dict[str, Any], out_path: str | Path) -> dict[str, Any]:
    targets = []
    seen: set[str] = set()
    for item in catalog.get("items", []) or []:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", "")).replace("/", "\\")
        if not path.lower().endswith(".mesh") or path in seen:
            continue
        seen.add(path)
        targets.append(path)
    payload = {
        "format": "ncig-architecture-bounds-targets-v1",
        "count": len(targets),
        "targets": targets,
    }
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"written": str(out_path), "count": len(targets), "format": payload["format"]}
