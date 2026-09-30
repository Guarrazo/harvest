from ncig.interior_quality import asset_quality, door_clearance_report, door_opening_width, filter_asset_candidates, choose_variety_index


def test_residential_wall_rejects_grille_and_prison_semantics():
    rows = [
        {"class": "wall_piece", "family": "common/int", "path": "base/environment/architecture/common/int/grille_wall.mesh", "score": 100},
        {"class": "wall_piece", "family": "common/int", "path": "base/environment/architecture/common/int/wall_partition.mesh", "score": 80},
    ]
    selected = filter_asset_candidates(rows, cls="wall_piece", building_type="residential")
    assert [x["path"] for x in selected] == [rows[1]["path"]]


def test_door_quality_penalizes_barred_style_without_blocking_valid_fallback():
    barred = {"class": "door_piece", "path": "base/environment/architecture/common/int/barred_gate.mesh", "score": 100}
    normal = {"class": "door_piece", "path": "base/environment/architecture/common/int/interior_door.mesh", "score": 60}
    quality = asset_quality(barred, "door_piece", "residential")
    assert quality["adjustment"] < 0
    selected = filter_asset_candidates([barred, normal], cls="door_piece", building_type="residential")
    assert selected[0]["path"] == normal["path"]


def test_door_opening_meets_human_scale_target():
    width = door_opening_width(3.0)
    report = door_clearance_report(width)
    assert width >= 1.0
    assert report["usable_for_standard_character"]


def test_variety_selection_is_deterministic():
    assert choose_variety_index("B1:F1:R1", 7) == choose_variety_index("B1:F1:R1", 7)
