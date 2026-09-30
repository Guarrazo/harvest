from ncig.architecture_geometry import planar_dimensions, family_candidates


def test_wall_filename_uses_w_as_visible_span_when_l_is_absent():
    item = {"class": "wall_piece", "dimensions": {"metres": {"w": 3.0, "h": 3.2}}}
    span, thickness, height = planar_dimensions(item, "wall_piece")
    assert span == 3.0
    assert thickness is None
    assert height == 3.2


def test_door_uses_w_as_opening_span():
    item = {"class": "door_piece", "dimensions": {"metres": {"w": 0.9, "l": 0.2, "h": 2.1}}}
    span, thickness, height = planar_dimensions(item, "door_piece")
    assert span == 0.9
    assert thickness == 0.2
    assert height == 2.1


def test_family_candidates_falls_back_to_family_group_before_global():
    catalog = {"items": [
        {"class": "wall_piece", "family": "common/int/shopkit", "dimensions": {"metres": {"w": 3, "h": 3}}},
        {"class": "wall_piece", "family": "common/int/otherkit", "dimensions": {"metres": {"w": 3, "h": 3}}},
        {"class": "wall_piece", "family": "characters/boss", "dimensions": {"metres": {"w": 3, "h": 3}}},
    ]}
    rows = family_candidates(catalog, "wall_piece", "common/int/missing")
    assert {x["family"] for x in rows} == {"common/int/shopkit", "common/int/otherkit"}


def test_runtime_linear_fit_honors_local_span_axis_and_rotation():
    from ncig.runtime_geometry import linear_fit
    item = {"bounds": {"min": {"x": -0.1, "y": -1.5, "z": 0.0}, "max": {"x": 0.1, "y": 1.5, "z": 3.0}, "dimensions_m": {"x": 0.2, "y": 3.0, "z": 3.0}}}
    fit = linear_fit(item, span=4.5, height=3.0, desired_rotation_deg=0.0)
    assert fit["span_axis"] == "y"
    assert fit["rotation_deg"] == -90.0
    assert abs(fit["scale"]["y"] - 1.5) < 1e-6

def test_runtime_surface_fit_preserves_local_axis_mapping():
    from ncig.runtime_geometry import preferred_surface_rotation, surface_scale, surface_world_dimensions
    item = {"bounds": {"min": {"x": -5.0, "y": -1.0, "z": -0.1}, "max": {"x": 5.0, "y": 1.0, "z": 0.1}, "dimensions_m": {"x": 10.0, "y": 2.0, "z": 0.2}}}
    orientation = preferred_surface_rotation(item, 2.0, 10.0)
    assert orientation == 90.0
    assert surface_world_dimensions(item, orientation) == (2.0, 10.0)
    scale = surface_scale(item, 2.0, 10.0, orientation)
    assert abs(scale["x"] - 1.0) < 1e-6
    assert abs(scale["y"] - 1.0) < 1e-6

def test_runtime_pivot_alignment_uses_real_bbox_center():
    from ncig.runtime_geometry import align_node_local_position
    item = {"bounds": {"min": {"x": 1.0, "y": 2.0, "z": 0.0}, "max": {"x": 3.0, "y": 4.0, "z": 2.0}, "dimensions_m": {"x": 2.0, "y": 2.0, "z": 2.0}}}
    pos = align_node_local_position(item, {"x": 1.0, "y": 1.0, "z": 1.0}, 0.0, (0.0, 0.0, 1.0))
    assert pos == (-2.0, -3.0, 0.0)
