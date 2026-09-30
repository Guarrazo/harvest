from ncig.architecture_catalog import (
    build_architecture_catalog,
    classify_structural_resource,
    derive_family,
    is_probable_interior,
    parse_dimension_hints,
)


def test_dimension_parser_cm_to_m():
    d = parse_dimension_hints(r"base\environment\architecture\common\int\kit\wall_l600_w300_h300.mesh")
    assert d["source"] == "filename_hint"
    assert d["unit"] == "cm"
    assert d["metres"] == {"l": 6.0, "w": 3.0, "h": 3.0}
    assert d["complete"] is True


def test_dimension_parser_does_not_consume_c_rotation_token():
    d = parse_dimension_hints(r"base\environment\architecture\common\int\kit\wall_l600_c90.mesh")
    assert d["metres"] == {"l": 6.0}


def test_architecture_filter():
    assert is_probable_interior(r"base\environment\architecture\common\int\kit\floor_l600_w300.mesh")
    assert not is_probable_interior(r"base\environment\decoration\street\sign.mesh")


def test_family_common_int_preserves_set():
    p = r"base\environment\architecture\common\int\int_ent_apartment_a\int_ent_apartment_a_bathroom_wall_w300_b_hole.mesh"
    assert derive_family(p) == "common/int/int_ent_apartment_a"


def test_family_interior_building_preserves_interior_marker():
    p = r"base\environment\architecture\common\buildings\steinbeck\interior\kit\wall_l600.mesh"
    assert derive_family(p) == "common/buildings/steinbeck/interior"


def test_structural_classes_use_specific_precedence():
    door, _ = classify_structural_resource(
        r"base\environment\architecture\common\int\corridor\corridor_doorframe_a.mesh",
        ["door", "geometry", "mesh"],
    )
    window, _ = classify_structural_resource(
        r"base\environment\architecture\common\int\kit\wall_window_l300.mesh",
        ["wall", "geometry", "mesh"],
    )
    assert door == "door_frame"
    assert window == "window_piece"


def test_character_domain_is_excluded_even_under_architecture_path():
    cls, signals = classify_structural_resource(
        r"base\environment\architecture\characters\props\wall.mesh", ["wall", "mesh"]
    )
    assert cls is None
    assert "excluded_non_architectural_domain" in signals


def test_non_mesh_door_entity_is_not_structural_geometry():
    cls, _ = classify_structural_resource(
        r"base\environment\architecture\common\int\kit\doorbase.ent", ["door", "entity"]
    )
    assert cls is None


def test_build_catalog_deterministic_and_family_diverse():
    harvest = {
        "format": "ncig-harvest-v1",
        "root": "X",
        "resource_count": 4,
        "resources": {
            r"base\environment\architecture\common\int\a\floor_l600_w300_h10_a.mesh": {
                "roles": ["floor", "mesh"], "sources": ["a"]
            },
            r"base\environment\architecture\common\int\b\floor_l500_w300_h10_a.mesh": {
                "roles": ["floor", "mesh"], "sources": ["a"]
            },
            r"base\environment\architecture\common\int\b\wall_l600_w300_h300_a.mesh": {
                "roles": ["wall", "mesh"], "sources": ["a"]
            },
            r"base\characters\foo\wall_l600_w300_h300.mesh": {
                "roles": ["wall", "mesh"], "sources": ["a"]
            },
        },
    }
    a = build_architecture_catalog(harvest, max_per_class=10)
    b = build_architecture_catalog(harvest, max_per_class=10)
    assert a == b
    assert a["candidate_counts"]["floor_piece"] == 2
    assert a["candidate_counts"]["wall_piece"] == 1
    assert a["selected_counts"]["floor_piece"] == 2
    assert a["items"][0]["dimensions"]["complete"] is True


def test_no_holes_is_not_opening():
    cls, _ = classify_structural_resource(
        r"base\environment\architecture\city_center\arasaka_tower\interior\lobby\int_arasaka_tower_lobby_a_wall_glass_addon_a_no_holes.mesh",
        ["geometry", "mesh", "wall"],
    )
    assert cls == "wall_piece"


def test_architecture_catalog_windows_launcher_exists_and_rejects_msys2():
    from pathlib import Path
    root = Path(__file__).parents[1]
    ps1 = (root / "tools" / "architecture_catalog_cp2077.ps1").read_text(encoding="utf-8").lower()
    cmd = root / "tools" / "architecture_catalog_cp2077.cmd"
    assert cmd.exists()
    assert "msys2" in ps1 and "devkitpro" in ps1 and "cygwin" in ps1 and "mingw" in ps1
    assert "architecture-catalog" in ps1
