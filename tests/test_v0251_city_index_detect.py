from __future__ import annotations

import sqlite3
from pathlib import Path

from ncig.city_index_detect import run


def _db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript("""
    CREATE TABLE records (
      id INTEGER PRIMARY KEY, source_file TEXT NOT NULL, sector TEXT NOT NULL, category TEXT NOT NULL,
      type TEXT NOT NULL, name TEXT NOT NULL, resource TEXT NOT NULL, x REAL NOT NULL, y REAL NOT NULL, z REAL NOT NULL,
      yaw_deg REAL NOT NULL, sx REAL NOT NULL, sy REAL NOT NULL, sz REAL NOT NULL, l REAL NOT NULL, w REAL NOT NULL, h REAL NOT NULL,
      kind TEXT NOT NULL, interior INTEGER NOT NULL, architecture INTEGER NOT NULL, entrance INTEGER NOT NULL, window INTEGER NOT NULL,
      cell_x INTEGER NOT NULL, cell_y INTEGER NOT NULL
    );
    """)
    rows = [
      (1, r"C:\sector.json", "sector", "", "worldMeshNode", "wall_a", r"base\environment\architecture\common\building_wall.mesh", 0,0,0,0,1,1,1,6,0.2,3, "wall",0,1,0,0,0,0),
      (2, r"C:\sector.json", "sector", "", "worldMeshNode", "wall_b", r"base\environment\architecture\common\building_wall.mesh", 6,0,0,0,1,1,1,6,0.2,3, "wall",0,1,0,0,0,0),
      (3, r"C:\sector.json", "sector", "", "worldMeshNode", "wall_c", r"base\environment\architecture\common\building_wall.mesh", 0,6,0,0,1,1,1,6,0.2,3, "wall",0,1,0,0,0,0),
      (4, r"C:\sector.json", "sector", "", "worldMeshNode", "entry_door", r"base\environment\architecture\common\building_door.mesh", 0,-2,0,0,1,1,1,1.2,0.2,2.1, "door",0,0,1,0,0,0),
    ]
    conn.executemany("INSERT INTO records VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    conn.commit(); conn.close()


def test_city_index_detector_reads_sqlite(tmp_path: Path) -> None:
    db=tmp_path/'city.sqlite'; out=tmp_path/'candidates.json'; _db(db)
    report=run(db,out)
    assert report['index_source'].endswith('city.sqlite')
    assert out.exists()
    assert report['detector_version'] == '0.25.1'
