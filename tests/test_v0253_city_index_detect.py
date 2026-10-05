from __future__ import annotations

import sqlite3
from pathlib import Path

from ncig.city_index_detect import _clusters_spatial


def _r(x: float, y: float) -> dict:
    return {"x": x, "y": y, "z": 0.0}


def test_spatial_clusters_are_deterministic_and_chain_connected() -> None:
    rows = [_r(0, 0), _r(7, 0), _r(14, 0), _r(100, 0)]
    groups = _clusters_spatial(rows, 8.0)
    assert [len(g) for g in groups] == [3, 1]
    assert groups[0][0]["x"] == 0
    assert groups[0][-1]["x"] == 14


def test_sqlite_schema_supports_flag_cell_query(tmp_path: Path) -> None:
    db = tmp_path / "city.sqlite"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE records (id INTEGER PRIMARY KEY, architecture INTEGER, interior INTEGER, entrance INTEGER, cell_x INTEGER, cell_y INTEGER)")
    conn.execute("CREATE INDEX idx_flags_cells ON records(architecture, interior, entrance, cell_x, cell_y)")
    conn.execute("INSERT INTO records(id,architecture,interior,entrance,cell_x,cell_y) VALUES(1,1,0,0,5,5)")
    conn.commit()
    row = conn.execute("SELECT id FROM records WHERE architecture=1 AND cell_x BETWEEN 4 AND 6 AND cell_y BETWEEN 4 AND 6").fetchone()
    conn.close()
    assert row == (1,)
