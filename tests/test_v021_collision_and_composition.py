from ncig.native_collision import build_room_collisions
from ncig.reference_nodes import entity_node
from ncig.native_composition import build_native_composition


def _layout():
    return {"format":"ncig-layout-v1","layouts":[{
        "building":{"id":"B1","district":"Watson","type":"commercial","position":{"x":0,"y":0,"z":0},"yaw_deg":0,"width_m":6,"depth_m":6,"floors":1},
        "rooms":[{"id":"B1_F1_R01","kind":"shopfloor","floor":0,"x":-2.5,"y":-2.5,"width":5,"depth":5,"rotation_deg":0,"is_start":True,"is_exit":False}],
        "sockets":[],
        "sectors":[{"id":"B1_sector_F01","building_id":"B1","floor":0,"category":"interior","min_xyz":{"x":-3,"y":-3,"z":-0.2},"max_xyz":{"x":3,"y":3,"z":3.5},"rooms":["B1_F1_R01"]}]
    }]}


def _assembly():
    return {"buildings":[{"id":"B1","floors":1,"rooms":1,"placements":[
        {"id":"B1_F1_R01_floor","class":"floor_piece","resource":"base\\env\\floor.mesh","floor":0,"position":{"x":0,"y":0,"z":0},"rotation_deg":0,"scale":{"x":1,"y":1,"z":1}}
    ],"placement_count":1,"unresolved_count":0}]}


def _templates():
    mesh={"type":"worldMeshNode","uk10":1040,"uk11":512,"name":"mesh","position":{"x":0,"y":0,"z":0,"w":0},"rotation":{"i":0,"j":0,"k":0,"r":1},"scale":{"x":1,"y":1,"z":1},"primaryRange":100,"secondaryRange":120,"streamingRefPoint":{"x":0,"y":0,"z":0,"w":0},"nodeRef":"","data":{"mesh":{"DepotPath":{"$value":"base\\env\\probe.mesh"}},"meshAppearance":{"$storage":"string","$value":"default"},"castShadows":"Default","castLocalShadows":"Default","castRayTracedGlobalShadows":"Default","castRayTracedLocalShadows":"Default","occluderType":"Default","windImpulseEnabled":1}}
    col=build_room_collisions(_layout()["layouts"][0])[0][0]
    ent=entity_node(name="probe",node_ref="",position={"x":0,"y":0,"z":0},entity_path="base\\env\\probe.ent")
    return {"templates":{"worldMeshNode":[mesh],"worldCollisionNode":[col],"worldEntityNode":[ent]},"counts":{"worldMeshNode":1,"worldCollisionNode":1,"worldEntityNode":1}}


def _base():
    return {"xlFormat":0,"sectors":[{"name":"probe","prefabRef":"","min":{"x":-5,"y":-5,"z":-1},"max":{"x":5,"y":5,"z":5},"variants":[],"variantIndices":[0],"category":"Exterior","nodes":[],"level":1}],"name":"probe","version":"1.0.4","devices":[],"psEntries":[]}


def test_collision_generator_creates_floor_and_walls_with_door_gap():
    nodes, report = build_room_collisions(_layout()["layouts"][0])
    assert report["node_count"] >= 5
    assert any("_floor" in n["name"] for n in nodes)
    assert all(n["type"] == "worldCollisionNode" for n in nodes)


def test_native_composition_expands_streaming_bounds_and_adds_collisions():
    result, report = build_native_composition(_layout(), _assembly(), _templates(), _base(), include_collisions=True, streaming_margin_m=32)
    sector = result["sectors"][0]
    assert report["collision_nodes"] > 0
    assert sector["min"]["x"] < -30
    assert any(n["type"] == "worldCollisionNode" for n in sector["nodes"])


def test_native_composition_can_emit_real_world_entity_decoration():
    layout_data = _layout()
    templates = _templates()
    # _templates contains an entity template; the decoration plan supplies only a real .ent path.
    decoration = {
        "format": "ncig-decoration-plan-v2",
        "building_id": "B1",
        "placements": [{
            "id": "B1_F1_R01_DEC_counter_01",
            "resource": "base\\env\\shop\\counter.ent",
            "role": "counter",
            "room_id": "B1_F1_R01",
            "floor": 0,
            "position": {"x": 1, "y": 1, "z": 0},
            "rotation_deg": 0,
            "scale": {"x": 1, "y": 1, "z": 1},
        }],
    }
    result, report = build_native_composition(layout_data, _assembly(), templates, _base(), decoration=decoration, include_collisions=False)
    assert report["decoration_nodes"] == 1
    entities = [n for n in result["sectors"][0]["nodes"] if n["type"] == "worldEntityNode"]
    assert len(entities) == 1
    assert entities[0]["data"]["entityTemplate"]["DepotPath"]["$value"].endswith("counter.ent")


def test_collision_node_uses_valid_entspawner_defaults():
    from ncig.reference_nodes import collision_node
    node = collision_node(
        name="c",
        node_ref="$/#c",
        position={"x": 0, "y": 0, "z": 0},
        size={"x": 1, "y": 1, "z": 0.1},
    )
    shape = node["data"]["compiledData"]["Data"]["Actors"][0]["Shapes"][0]
    assert shape["Preset"]["$value"] == "Simple Environment Collision"
    assert shape["Materials"][0]["$value"] == "concrete.physmat"


def test_collision_generator_has_continuous_floor():
    nodes, report = build_room_collisions({
        "building": {"id": "B", "position": {"x": 0, "y": 0, "z": 0}, "yaw_deg": 0},
        "rooms": [
            {"id": "B_F1_R01", "floor": 0, "x": -3, "y": -3, "width": 2, "depth": 2},
            {"id": "B_F1_R02", "floor": 0, "x": 1, "y": 1, "width": 2, "depth": 2},
        ],
    })
    assert report["floor_node_count"] == 1
    assert any(str(n.get("nodeRef", "")).endswith("F01_COLL_floor") for n in nodes)
