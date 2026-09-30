from ncig.architecture_bounds import merge_bounds_into_catalog


def test_merge_runtime_bounds_overrides_filename_hint():
    catalog = {"items": [{
        "path": "base\\environment\\architecture\\kit\\wall.mesh",
        "class": "wall_piece",
        "family": "kit",
        "dimensions": {"source": "filename_hint", "metres": {"l": 3, "w": 0.1, "h": 3}},
    }]}
    bounds = {"format": "ncig-architecture-bounds-v1", "bounds": {
        "base\\environment\\architecture\\kit\\wall.mesh": {
            "min": {"x": -1.25, "y": -0.05, "z": 0},
            "max": {"x": 1.25, "y": 0.05, "z": 3.0},
            "has_physics": True,
        }
    }}
    merged, report = merge_bounds_into_catalog(catalog, bounds)
    assert report["matched"] == 1
    assert merged["items"][0]["bounds"]["dimensions_m"]["x"] == 2.5
