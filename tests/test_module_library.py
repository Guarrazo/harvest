from ncig.module_library import build_module_library, choose_module, instantiate_module


def _harvest():
    return {
        "format": "ncig-template-harvest-v1",
        "templates": {
            "worldMeshNode": [
                {"ncigSourceFile": "favorites/kitchen.json", "type":"worldMeshNode", "name":"counter", "position":{"x":0,"y":0,"z":0}, "rotation":{"i":0,"j":0,"k":0,"r":1}},
                {"ncigSourceFile": "favorites/kitchen.json", "type":"worldMeshNode", "name":"fridge", "position":{"x":2,"y":0,"z":0}, "rotation":{"i":0,"j":0,"k":0,"r":1}},
            ],
            "worldEntityNode": [
                {"ncigSourceFile": "favorites/bedroom.json", "type":"worldEntityNode", "name":"bed", "position":{"x":0,"y":0,"z":0}, "rotation":{"i":0,"j":0,"k":0,"r":1}},
            ],
        },
    }


def test_library_and_instantiation():
    lib = build_module_library(_harvest())
    assert lib["module_count"] == 2
    kitchen = choose_module(lib, "kitchen", 5, 5)
    assert kitchen["source_file"].endswith("kitchen.json")
    placed = instantiate_module(kitchen, anchor=(100,200,10), yaw_deg=90, prefix="r01_kitchen")
    assert len(placed) == 2
    assert all(n["position"]["z"] == 10 for n in placed)
    assert placed[0]["name"].startswith("[NCIG MODULE]")


def test_instantiation_preserves_non_yaw_rotation_components():
    from ncig.module_library import instantiate_module
    module = {
        "min_xyz": [0, 0, 0], "max_xyz": [1, 1, 1],
        "nodes": [{"name": "tilted", "type": "worldEntityNode", "position": {"x": 0, "y": 0, "z": 0},
                   "rotation": {"i": 0.2, "j": 0.1, "k": 0.3, "r": 0.9}}]
    }
    out = instantiate_module(module, anchor=(0,0,0), yaw_deg=45)
    q = out[0]["rotation"]
    assert abs(q["i"]) > 0.0
    assert abs(q["j"]) > 0.0
