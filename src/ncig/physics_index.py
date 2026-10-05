from __future__ import annotations

import argparse
import json
import math
import sqlite3
from pathlib import Path
from typing import Any, Iterable

VERSION = "0.24.0"
FORMAT = "ncig-world-physics-index-v1"
CELL_SIZE_M = 16.0


def _vec3(value: Any) -> tuple[float, float, float] | None:
    if isinstance(value, dict):
        out = []
        for aliases in (("x", "X", "XCoord"), ("y", "Y", "YCoord"), ("z", "Z", "ZCoord")):
            value2 = next((value[k] for k in aliases if value.get(k) is not None), None)
            if value2 is None:
                return None
            try:
                out.append(float(value2))
            except (TypeError, ValueError):
                return None
        return tuple(out)  # type: ignore[return-value]
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        try:
            return float(value[0]), float(value[1]), float(value[2])
        except (TypeError, ValueError):
            return None
    return None


def _depot_path(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("DepotPath") or value.get("depotPath") or value.get("path")
        if isinstance(value, dict):
            value = value.get("$value")
    return value.replace("/", "\\") if isinstance(value, str) else ""


def _resource_path(node: dict[str, Any]) -> str:
    pools = [node]
    for key in ("Data", "data"):
        if isinstance(node.get(key), dict):
            pools.append(node[key])
    for pool in pools:
        for key in ("mesh", "Mesh", "entityTemplate", "EntityTemplate", "resource", "Resource", "meshResource", "MeshResource"):
            path = _depot_path(pool.get(key))
            if path:
                return path
    return ""


def _node_type(node: dict[str, Any]) -> str:
    for pool in ([node.get("Data"), node] if isinstance(node.get("Data"), dict) else [node]):
        for key in ("type", "nodeType", "Type", "NodeType", "$type"):
            val = pool.get(key)
            if isinstance(val, str) and val:
                return val.rsplit(".", 1)[-1].split(",")[0]
    return ""


def _node_name(node: dict[str, Any]) -> str:
    for pool in ([node.get("Data"), node] if isinstance(node.get("Data"), dict) else [node]):
        for key in ("name", "nodeName", "Name", "NodeName", "debugName", "DebugName"):
            val = pool.get(key)
            if isinstance(val, str):
                return val
            if isinstance(val, dict) and isinstance(val.get("$value"), str):
                return val["$value"]
    return ""


def _node_position(obj: dict[str, Any]) -> tuple[float, float, float] | None:
    pools = [obj]
    for key in ("Data", "data", "transform", "Transform"):
        if isinstance(obj.get(key), dict):
            pools.append(obj[key])
    for pool in pools:
        for key in ("position", "worldPosition", "nodePosition", "Position", "WorldPosition", "NodePosition", "pos", "Pivot"):
            pos = _vec3(pool.get(key))
            if pos is not None:
                return pos
    return None


def _node_yaw(obj: dict[str, Any]) -> float:
    pools = [obj]
    for key in ("Data", "data", "transform", "Transform"):
        if isinstance(obj.get(key), dict):
            pools.append(obj[key])
    for pool in pools:
        for key in ("yaw_deg", "yaw", "Yaw", "YawDeg"):
            if pool.get(key) is not None:
                try:
                    return float(pool[key])
                except (TypeError, ValueError):
                    pass
        rot = next((pool.get(k) for k in ("rotation", "Rotation", "rot", "Rot", "Orientation") if isinstance(pool.get(k), dict)), None)
        if isinstance(rot, dict):
            try:
                x = float(rot.get("i", rot.get("x", 0.0)))
                y = float(rot.get("j", rot.get("y", 0.0)))
                z = float(rot.get("k", rot.get("z", 0.0)))
                w = float(rot.get("r", rot.get("w", 1.0)))
                return math.degrees(math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z)))
            except (TypeError, ValueError):
                pass
    return 0.0


def _node_scale(obj: dict[str, Any]) -> tuple[float, float, float]:
    pools = [obj]
    for key in ("Data", "data", "transform", "Transform"):
        if isinstance(obj.get(key), dict):
            pools.append(obj[key])
    for pool in pools:
        val = pool.get("scale", pool.get("Scale"))
        if isinstance(val, dict):
            try:
                return abs(float(val.get("x", val.get("X", 1.0)))), abs(float(val.get("y", val.get("Y", 1.0)))), abs(float(val.get("z", val.get("Z", 1.0))))
            except (TypeError, ValueError):
                pass
    return 1.0, 1.0, 1.0


def _node_index(value: Any) -> int | None:
    if isinstance(value, dict):
        value = value.get("$value", value.get("value"))
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _unwrap_sector(raw: dict[str, Any]) -> dict[str, Any] | None:
    if isinstance(raw.get("sector"), dict):
        return raw["sector"]
    if isinstance(raw.get("sectors"), list) and raw["sectors"] and isinstance(raw["sectors"][0], dict):
        return raw["sectors"][0]
    data = raw.get("Data")
    if isinstance(data, dict):
        root = data.get("RootChunk")
        if isinstance(root, dict):
            return root
        return data if isinstance(data.get("nodes"), list) else None
    return raw if isinstance(raw.get("nodes"), list) else None


def _flatten_nodes(sector: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = sector.get("nodes")
    if not isinstance(nodes, list):
        return []
    out = []
    for item in nodes:
        if not isinstance(item, dict):
            continue
        data = item.get("Data")
        out.append(dict(data) if isinstance(data, dict) else dict(item))
    return out


def _node_data_entries(sector: dict[str, Any]) -> list[dict[str, Any]]:
    raw = sector.get("nodeData") or sector.get("NodeData")
    if isinstance(raw, list):
        return [dict(x) for x in raw if isinstance(x, dict)]
    if isinstance(raw, dict):
        data = raw.get("Data")
        if isinstance(data, list):
            return [dict(x) for x in data if isinstance(x, dict)]
    return []


def _records_from_sector(raw: dict[str, Any], source_file: str) -> Iterable[dict[str, Any]]:
    sector = _unwrap_sector(raw)
    if not sector:
        return []
    nodes = _flatten_nodes(sector)
    by_index = {i: node for i, node in enumerate(nodes)}
    placements = _node_data_entries(sector)
    out = []
    if placements:
        for placement in placements:
            idx = _node_index(placement.get("NodeIndex", placement.get("nodeIndex", placement.get("node_index"))))
            node = by_index.get(idx) if idx is not None else None
            if not isinstance(node, dict):
                continue
            pos = _node_position(placement)
            if pos is None:
                continue
            out.append({
                "source_file": source_file,
                "sector": str(sector.get("name") or sector.get("sectorName") or Path(source_file).stem),
                "type": _node_type(node), "name": _node_name(node), "resource": _resource_path(node),
                "x": pos[0], "y": pos[1], "z": pos[2], "yaw_deg": _node_yaw(placement), "scale": _node_scale(placement),
                "node_index": idx,
                "node": node, "placement": placement,
            })
    else:
        for i, node in enumerate(nodes):
            pos = _node_position(node)
            if pos is None:
                continue
            out.append({
                "source_file": source_file,
                "sector": str(sector.get("name") or sector.get("sectorName") or Path(source_file).stem),
                "type": _node_type(node), "name": _node_name(node), "resource": _resource_path(node),
                "x": pos[0], "y": pos[1], "z": pos[2], "yaw_deg": _node_yaw(node), "scale": _node_scale(node),
                "node_index": i, "node": node, "placement": node,
            })
    return out


def _walk_size(obj: Any, path: str = "") -> list[tuple[tuple[float, float, float], str]]:
    found = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            child = f"{path}.{key}" if path else str(key)
            key_l = str(key).lower()
            if any(token in key_l for token in ("size", "extent", "halfext", "halfdimension", "boxsize", "collisionbounds")):
                vec = _vec3(value)
                if vec and all(0.001 < x < 100.0 for x in vec):
                    found.append((vec, child))
                elif isinstance(value, dict):
                    vals = []
                    for aliases in (("width", "Width"), ("depth", "Depth", "length", "Length"), ("height", "Height")):
                        raw = next((value[k] for k in aliases if value.get(k) is not None), None)
                        try:
                            vals.append(abs(float(raw)))
                        except (TypeError, ValueError):
                            vals = []
                            break
                    if len(vals) == 3 and all(0.001 < x < 100.0 for x in vals):
                        found.append((tuple(vals), child))
            found.extend(_walk_size(value, child))
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            found.extend(_walk_size(value, f"{path}[{i}]"))
    return found


def _shape_info(record: dict[str, Any]) -> tuple[str, tuple[float, float, float] | None, str | None]:
    typ = str(record.get("type", "")).lower()
    if typ != "worldcollisionnode":
        return "unknown", None, None
    candidates = _walk_size({"node": record.get("node"), "placement": record.get("placement")})
    if candidates:
        vec, path = max(candidates, key=lambda x: max(x[0]))
        return "native_shape", vec, path
    return "unknown", None, None


def _flags(record: dict[str, Any]) -> tuple[int, int, int, int]:
    typ = str(record.get("type", "")).lower()
    text = (str(record.get("name", "")) + " " + str(record.get("resource", ""))).lower()
    collision = int(typ == "worldcollisionnode")
    proxy = int(typ == "worldbuildingproxymeshnode" or "buildingproxymesh" in typ or "proxymesh" in typ)
    mesh = int(typ in {"worldmeshnode", "worldrotatingmeshnode", "worlddynamicmeshnode", "worldbuildingproxymeshnode"})
    door = int((not collision) and any(token in text for token in ("door", "doorway", "entrance", "shopfront", "entry")))
    return collision, proxy, mesh, door


def _cell(v: float) -> int:
    return math.floor(float(v) / CELL_SIZE_M)


SCHEMA = """
CREATE TABLE IF NOT EXISTS physics_records (
    id INTEGER PRIMARY KEY,
    source_file TEXT NOT NULL, sector TEXT NOT NULL, type TEXT NOT NULL, name TEXT NOT NULL, resource TEXT NOT NULL,
    x REAL NOT NULL, y REAL NOT NULL, z REAL NOT NULL, yaw_deg REAL NOT NULL,
    sx REAL NOT NULL, sy REAL NOT NULL, sz REAL NOT NULL, l REAL NOT NULL, w REAL NOT NULL, h REAL NOT NULL,
    node_index INTEGER, source_node_count INTEGER NOT NULL,
    collision INTEGER NOT NULL, proxy INTEGER NOT NULL, mesh INTEGER NOT NULL, door INTEGER NOT NULL,
    cell_x INTEGER NOT NULL, cell_y INTEGER NOT NULL,
    shape_kind TEXT NOT NULL, shape_x REAL NOT NULL, shape_y REAL NOT NULL, shape_z REAL NOT NULL, shape_source TEXT
);
CREATE INDEX IF NOT EXISTS idx_physics_cell ON physics_records(cell_x, cell_y);
CREATE INDEX IF NOT EXISTS idx_physics_flags ON physics_records(collision, proxy, mesh, door, cell_x, cell_y);
"""


def build_physics_index(input_path: str | Path, db_path: str | Path) -> dict[str, Any]:
    root = Path(input_path)
    files = [root] if root.is_file() else sorted(root.rglob("*.streamingsector.json"))
    if not files and root.is_dir():
        files = sorted(x for x in root.rglob("*.json") if "streamingsector" in x.name.lower())
    out = Path(db_path); out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists(): out.unlink()
    conn = sqlite3.connect(out)
    parsed = indexed = invalid = 0
    try:
        conn.executescript(SCHEMA)
        sql = "INSERT INTO physics_records(source_file,sector,type,name,resource,x,y,z,yaw_deg,sx,sy,sz,l,w,h,node_index,source_node_count,collision,proxy,mesh,door,cell_x,cell_y,shape_kind,shape_x,shape_y,shape_z,shape_source) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
        for path in files:
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                sector = _unwrap_sector(raw)
                node_count = len(sector.get("nodes", [])) if isinstance(sector, dict) and isinstance(sector.get("nodes"), list) else 0
                records = list(_records_from_sector(raw, str(path)))
            except (OSError, json.JSONDecodeError):
                invalid += 1; continue
            parsed += len(records)
            rows = []
            for rec in records:
                collision, proxy, mesh, door = _flags(rec)
                if not any((collision, proxy, door)):
                    continue
                shape_kind, shape, shape_source = _shape_info(rec)
                dims = shape or (0.0, 0.0, 0.0)
                # The l/w/h fields are filename hints only; native shape dims are separately retained.
                row = (
                    rec["source_file"], rec["sector"], rec["type"], rec["name"], rec["resource"], rec["x"], rec["y"], rec["z"], rec["yaw_deg"],
                    rec["scale"][0], rec["scale"][1], rec["scale"][2], 0.0, 0.0, 0.0, rec["node_index"], node_count,
                    collision, proxy, mesh, door, _cell(rec["x"]), _cell(rec["y"]), shape_kind, dims[0], dims[1], dims[2], shape_source,
                )
                rows.append(row)
            if rows:
                conn.executemany(sql, rows); indexed += len(rows)
        conn.commit()
        counts = {f: int(conn.execute(f"SELECT COUNT(*) FROM physics_records WHERE {f}=1").fetchone()[0]) for f in ("collision", "proxy", "door")}
        return {"format": FORMAT, "version": VERSION, "input": str(root.resolve()), "database": str(out.resolve()), "cell_size_m": CELL_SIZE_M, "json_file_count": len(files), "invalid_file_count": invalid, "parsed_records": parsed, "indexed_records": indexed, **counts}
    finally:
        conn.close()


class PhysicsIndex:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row

    def close(self) -> None:
        self.conn.close()

    def query(self, x: float, y: float, radius_m: float) -> list[dict[str, Any]]:
        radius = max(0.0, float(radius_m))
        lo_x, hi_x = _cell(x - radius), _cell(x + radius)
        lo_y, hi_y = _cell(y - radius), _cell(y + radius)
        rows = self.conn.execute("SELECT * FROM physics_records WHERE cell_x BETWEEN ? AND ? AND cell_y BETWEEN ? AND ?", (lo_x, hi_x, lo_y, hi_y)).fetchall()
        rsq = radius * radius
        return [dict(r) for r in rows if (float(r["x"]) - x) ** 2 + (float(r["y"]) - y) ** 2 <= rsq]

    def manifest(self) -> dict[str, Any]:
        count = self.conn.execute("SELECT COUNT(*) FROM physics_records").fetchone()[0]
        return {"format": FORMAT, "version": VERSION, "database": self.db_path, "indexed_records": int(count)}


def load_index(path: str | Path) -> PhysicsIndex:
    return PhysicsIndex(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="NCIG world physics/proxy/door index")
    parser.add_argument("command", choices=["build"])
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--manifest-out", required=True)
    args = parser.parse_args()
    report = build_physics_index(args.input, args.out)
    p = Path(args.manifest_out); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("database", "indexed_records", "collision", "proxy", "door")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
