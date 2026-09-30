from ncig.architecture_geometry import dimension_hint_scale
from ncig.architecture_assembler import build_architecture_assembly
from ncig.cli import _layout_from_raw
from ncig.target_detector import candidates_to_buildings, detect_building_candidates
from ncig.model import BuildingAnchor, Layout, Room, Sector, Vec3
from ncig.decoration_catalog import build_decoration_catalog
from ncig.decoration_plan import build_decoration_plan


def test_hint_fit_allows_narrow_wall_and_floor_scaling():
    wall = {"class":"wall_piece","dimensions":{"complete":True,"metres":{"w":3.0,"l":0.2,"h":3.2}}}
    scale = dimension_hint_scale(wall, "wall_piece", {"span":2.5,"height":3.0})
    assert scale == {"x": 2.5/3.0, "y": 1.0, "z": 3.0/3.2}


def test_detector_preserves_entrance_local_coordinates():
    records=[]
    # Exterior architecture around an east-facing entrance.
    for x,y in [(0,0),(4,0),(0,4),(4,4),(2,0),(2,4)]:
        records.append({"x":x,"y":y,"z":0,"type":"worldMeshNode","name":"building wall","resource":"base\\environment\\architecture\\common\\int\\shop\\wall.mesh","sector":"s","category":"Exterior","text":"building wall"})
    records.append({"x":2,"y":4.5,"z":0,"type":"worldMeshNode","name":"shop door","resource":"base\\environment\\architecture\\common\\int\\shop\\door.mesh","sector":"s","category":"Exterior","text":"shop door entrance"})
    report=detect_building_candidates(records, cluster_radius_m=10)
    assert report["candidates"]
    c=report["candidates"][0]
    assert "entry_local_x" in c and "entry_local_y" in c
    result=candidates_to_buildings(report,min_score=0,include_review=True)
    b=result["buildings"][0]
    assert b["entry_local_x"] == c["entry_local_x"]


def test_layout_loader_roundtrips_entry_anchor():
    raw={"building":{"id":"B1","district":"d","type":"commercial","position":{"x":0,"y":0,"z":0},"yaw_deg":0,"width_m":8,"depth_m":8,"floors":1,"entry_local_x":1.25,"entry_local_y":4.0,"entry_yaw_deg":180},"rooms":[],"sockets":[],"sectors":[],"warnings":[]}
    layout=_layout_from_raw(raw)
    assert layout.building.entry_local_x == 1.25
    assert layout.building.entry_local_y == 4.0
    assert layout.building.entry_yaw_deg == 180


def test_decoration_uses_room_level_kit_family_consistently():
    harvest={"resources":{
      "base\\environment\\furniture\\shop\\shop_counter.ent":{"roles":["counter"]},
      "base\\environment\\furniture\\shop\\shop_display.ent":{"roles":["display"]},
      "base\\environment\\furniture\\shop\\shop_shelf.ent":{"roles":["shelf"]},
      "base\\environment\\furniture\\office\\office_counter.ent":{"roles":["counter"]},
      "base\\environment\\furniture\\office\\office_display.ent":{"roles":["display"]},
      "base\\environment\\furniture\\shop\\shop_light.ent":{"roles":["light"]},
    }}
    cat=build_decoration_catalog(harvest,max_per_role=20)
    b=BuildingAnchor("B","d","commercial",Vec3(0,0,0),0,8,8,1)
    r=Room("B_F1_R01","shopfloor",0,-3,-3,6,6)
    s=Sector("B_sector_F01","B",0,"interior",Vec3(-4,-4,-1),Vec3(4,4,4),[r.id])
    plan=build_decoration_plan(Layout(b,[r],[],[s],[]),cat)
    kits={p.get("decoration_kit_family") for p in plan["placements"]}
    assert len(kits)==1
