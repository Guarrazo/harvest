from __future__ import annotations
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from ncig.physics_index import build_physics_index, load_index


def test_physics_index_reads_proxy_collision_and_door(tmp_path: Path):
    sector = {
        'Data': {'RootChunk': {
            '$type': 'worldStreamingSector',
            'nodes': [
                {'Data': {'$type':'worldBuildingProxyMeshNode','name':'HouseProxy','mesh':{'DepotPath':{'$value':'base\\environment\\architecture\\proxy.mesh'}}}},
                {'Data': {'$type':'worldCollisionNode','name':'DoorBlock','data':{'shape':{'size':{'x':1.2,'y':0.5,'z':2.2}}}}},
                {'Data': {'$type':'worldMeshNode','name':'MainEntranceDoor','mesh':{'DepotPath':{'$value':'base\\environment\\architecture\\common\\int\\door.mesh'}}}},
            ],
            'nodeData': [
                {'NodeIndex':0,'Position':{'x':0,'y':0,'z':1.5}},
                {'NodeIndex':1,'Position':{'x':0,'y':-4,'z':1.1}},
                {'NodeIndex':2,'Position':{'x':0,'y':-4,'z':1.0}},
            ]
        }}
    }
    src=tmp_path/'test.streamingsector.json'; src.write_text(json.dumps(sector),encoding='utf-8')
    db=tmp_path/'physics.sqlite'
    report=build_physics_index(tmp_path, db)
    assert report['collision']==1
    assert report['proxy']==1
    assert report['door']==1
    idx=load_index(db)
    try:
        rows=idx.query(0,-4,6)
        assert any(r['proxy']==1 for r in rows)
        col=next(r for r in rows if r['collision']==1)
        assert abs(col['shape_x']-1.2)<1e-6
        assert col['node_index']==1
        assert col['source_node_count']==3
    finally:
        idx.close()
