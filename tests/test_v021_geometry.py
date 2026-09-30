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
