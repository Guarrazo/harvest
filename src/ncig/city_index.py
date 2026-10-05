from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .city_pipeline import _records_from_json, _sector_files
from . import target_detector as td

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY,
    source_file TEXT NOT NULL,
    sector TEXT NOT NULL,
    category TEXT NOT NULL,
    type TEXT NOT NULL,
    name TEXT NOT NULL,
    resource TEXT NOT NULL,
    x REAL NOT NULL, y REAL NOT NULL, z REAL NOT NULL,
    yaw_deg REAL NOT NULL,
    sx REAL NOT NULL, sy REAL NOT NULL, sz REAL NOT NULL,
    l REAL NOT NULL, w REAL NOT NULL, h REAL NOT NULL,
    kind TEXT NOT NULL,
    interior INTEGER NOT NULL,
    architecture INTEGER NOT NULL,
    entrance INTEGER NOT NULL,
    window INTEGER NOT NULL,
    cell_x INTEGER NOT NULL, cell_y INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_flags_cells ON records(architecture, interior, entrance, cell_x, cell_y);
CREATE INDEX IF NOT EXISTS idx_entrance_cells ON records(entrance, cell_x, cell_y);
"""

CELL_SIZE_M = 16.0


def _cell(v: float) -> int:
    return int(v // CELL_SIZE_M)


def _row(record: dict[str, Any]) -> tuple[Any, ...] | None:
    kind = td._record_kind(record)
    interior = int(td._is_interior(record))
    architecture = int(td._is_architecture(record) and not interior)
    entrance = int(td._is_entrance(record) and not interior)
    window = int(td._is_window(record))
    if not any((interior, architecture, entrance)):
        return None
    scale = record.get("scale", (1.0, 1.0, 1.0))
    dims = record.get("dimensions_m") if isinstance(record.get("dimensions_m"), dict) else {}
    return (
        str(record.get("source_file", "")), str(record.get("sector", "")),
        str(record.get("category", "")), str(record.get("type", "")),
        str(record.get("name", "")), str(record.get("resource", "")),
        float(record["x"]), float(record["y"]), float(record["z"]),
        float(record.get("yaw_deg", 0.0)),
        float(scale[0]), float(scale[1]), float(scale[2]),
        float(dims.get("l", 0.0)), float(dims.get("w", 0.0)), float(dims.get("h", 0.0)),
        kind, interior, architecture, entrance, window,
        _cell(float(record["x"])), _cell(float(record["y"])),
    )


def build_city_index(input_path: str | Path, db_path: str | Path) -> dict[str, Any]:
    files = _sector_files(input_path)
    out = Path(db_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()

    conn = sqlite3.connect(out)
    parsed_records = 0
    indexed = 0
    invalid: list[dict[str, str]] = []
    try:
        conn.executescript(SCHEMA)
        insert_sql = (
            "INSERT INTO records(source_file,sector,category,type,name,resource,x,y,z,yaw_deg,"
            "sx,sy,sz,l,w,h,kind,interior,architecture,entrance,window,cell_x,cell_y) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
        )
        for path in files:
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                records = _records_from_json(raw, str(path))
            except (OSError, json.JSONDecodeError) as exc:
                invalid.append({"path": str(path), "error": type(exc).__name__, "message": str(exc)[:240]})
                continue
            rows = [row for record in records if (row := _row(record)) is not None]
            if rows:
                conn.executemany(insert_sql, rows)
                indexed += len(rows)
            parsed_records += len(records)
        conn.commit()
        counts = {
            "indexed_records": indexed,
            "entrances": int(conn.execute("SELECT COUNT(*) FROM records WHERE entrance=1").fetchone()[0]),
            "architecture": int(conn.execute("SELECT COUNT(*) FROM records WHERE architecture=1").fetchone()[0]),
            "interior": int(conn.execute("SELECT COUNT(*) FROM records WHERE interior=1").fetchone()[0]),
            "windows": int(conn.execute("SELECT COUNT(*) FROM records WHERE window=1").fetchone()[0]),
        }
        return {
            "format": "ncig-city-index-v3",
            "input": str(Path(input_path).resolve()),
            "database": str(out.resolve()),
            "cell_size_m": CELL_SIZE_M,
            "json_file_count": len(files),
            "valid_file_count": len(files) - len(invalid),
            "invalid_file_count": len(invalid),
            "invalid_files": invalid[:200],
            "parsed_records": parsed_records,
            **counts,
            "notes": [
                "The index keeps only entrance, exterior architecture and interior evidence.",
                "The source sector JSON files are not modified.",
                "The index is intended to be reused for repeated candidate-detection passes.",
            ],
        }
    finally:
        conn.close()


def _record(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "source_file": row[0], "sector": row[1], "category": row[2], "type": row[3],
        "name": row[4], "resource": row[5], "x": row[6], "y": row[7], "z": row[8],
        "yaw_deg": row[9], "scale": (row[10], row[11], row[12]),
        "dimensions_m": {"l": row[13], "w": row[14], "h": row[15]},
        "text": " ".join((str(row[4]), str(row[3]), str(row[5]), str(row[1]))).lower().replace("/", "\\"),
    }


def load_index_records(db_path: str | Path) -> list[dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT source_file,sector,category,type,name,resource,x,y,z,yaw_deg,"
            "sx,sy,sz,l,w,h FROM records"
        ).fetchall()
    finally:
        conn.close()
    return [_record(row) for row in rows]


def inspect_city_json(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    raw = json.loads(p.read_text(encoding="utf-8"))
    report: dict[str, Any] = {
        "path": str(p.resolve()),
        "top_level_keys": sorted(raw.keys()) if isinstance(raw, dict) else [],
        "top_level_type": type(raw).__name__,
    }
    if isinstance(raw, dict) and isinstance(raw.get("Data"), dict):
        data = raw["Data"]
        root = data.get("RootChunk") if isinstance(data.get("RootChunk"), dict) else None
        sector = root if root is not None else data
        report["cr2w_data_keys"] = sorted(data.keys())
        report["data_type"] = sector.get("$type") if isinstance(sector, dict) else None
        report["data_keys"] = sorted(sector.keys()) if isinstance(sector, dict) else []
        nodes = sector.get("nodes") if isinstance(sector, dict) else None
        nd = sector.get("nodeData") if isinstance(sector, dict) else None
        report["root_chunk_present"] = root is not None
        report["root_chunk_type"] = sector.get("$type") if isinstance(sector, dict) else None
        report["root_chunk_keys"] = sorted(sector.keys()) if isinstance(sector, dict) else []
        report["node_count"] = len(nodes) if isinstance(nodes, list) else 0
        report["nodeData_type"] = type(nd).__name__ if nd is not None else None
        report["nodeData_keys"] = sorted(nd.keys()) if isinstance(nd, dict) else []
        if isinstance(nd, dict):
            payload = nd.get("Data")
            report["nodeData_Data_type"] = type(payload).__name__ if payload is not None else None
            report["nodeData_Data_count"] = len(payload) if isinstance(payload, list) else None
            raw_bytes = nd.get("Bytes")
            report["nodeData_bytes_length"] = len(raw_bytes) if isinstance(raw_bytes, str) else None
        sample_types = []
        if isinstance(nodes, list):
            for node in nodes[:20]:
                if isinstance(node, dict):
                    wrapped = node.get("Data") if isinstance(node.get("Data"), dict) else node
                    value = wrapped.get("$type") or wrapped.get("type") or wrapped.get("nodeType")
                    if value:
                        sample_types.append(str(value).rsplit(".", 1)[-1].split(",")[0])
        report["sample_node_types"] = sample_types
    records = _records_from_json(raw, str(p))
    report["parsed_record_count"] = len(records)
    report["parsed_kinds"] = {
        kind: sum(1 for record in records if td._record_kind(record) == kind)
        for kind in ("door", "wall", "window", "floor", "ceiling", "other")
    }
    return report
