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

def test_v023_weighted_rule_filters_by_room_dimensions():
    import random
    from ncig.generator import weighted_rule
    from ncig.templates import RoomRule
    rules = [
        RoomRule("large", 4.0, 8.0, 4.0, 8.0, 10),
        RoomRule("small", 1.0, 2.0, 1.0, 2.0, 10),
    ]
    assert weighted_rule(random.Random(1), rules, set(), width=1.5, depth=1.5).kind == "small"


def test_v023_partial_filename_hint_can_fit():
    from ncig.architecture_geometry import dimension_hint_scale
    item = {
        "class": "door_piece",
        "dimensions": {
            "source": "filename_hint",
            "metres": {"w": 1.0, "h": 2.0},
            "complete": False,
        },
    }
    scale = dimension_hint_scale(item, "door_piece", {"span": 1.1, "height": 2.1})
    assert scale is not None
    assert scale["x"] == 1.1
    assert scale["z"] == 1.05


def test_v023_door_pool_rejects_gross_oversize_and_security_for_normal_room():
    from ncig.architecture_assembler import _door_candidate_pool
    rows = [
        {"class": "door_piece", "path": "base/security/security_gate.mesh", "dimensions": {"metres": {"w": 1.0, "h": 2.0}}},
        {"class": "door_piece", "path": "base/interior/huge_door_l300_w300_h300.mesh", "dimensions": {"metres": {"l": 3.0, "w": 3.0, "h": 3.0}}},
        {"class": "door_piece", "path": "base/interior/normal_door_l20_w100_h210.mesh", "dimensions": {"metres": {"l": 0.2, "w": 1.0, "h": 2.1}}},
    ]
    pool = _door_candidate_pool(rows, cls="door_piece", room_kind="living", target_width=1.2, target_height=2.1)
    assert [row["path"] for row in pool] == ["base/interior/normal_door_l20_w100_h210.mesh"]


def test_v023_security_room_keeps_security_door_eligible():
    from ncig.architecture_assembler import _door_candidate_pool
    row = {"class": "door_piece", "path": "base/security/security_gate.mesh", "dimensions": {"metres": {"w": 1.0, "h": 2.0}}}
    pool = _door_candidate_pool([row], cls="door_piece", room_kind="security", target_width=1.2, target_height=2.1)
    assert pool == [row]


def test_v023_district_is_recorded_in_architecture_assembly():
    import inspect
    from ncig import architecture_assembler
    assert 'district=getattr(layout.building, "district", "unknown")' in inspect.getsource(
        architecture_assembler.build_architecture_assembly
    )
