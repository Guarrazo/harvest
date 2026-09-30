from ncig.architecture_catalog import classify_structural_resource
from ncig.architecture_assembler import choose_architecture_family, build_architecture_assembly
from ncig.model import BuildingAnchor, Layout, Room, Sector, Socket, Vec3


def _catalog():
    dims = lambda l, w, h: {"source": "filename_hint", "metres": {"l": l, "w": w, "h": h}, "complete": True}
    rows = []
    for cls, path in [
        ("floor_piece", "base\\environment\\architecture\\common\\int\\shopkit_floor_l300_w300_h10.mesh"),
        ("wall_piece", "base\\environment\\architecture\\common\\int\\shopkit_wall_l300_w15_h300.mesh"),
        ("ceiling_piece", "base\\environment\\architecture\\common\\int\\shopkit_ceiling_l300_w300_h10.mesh"),
        ("door_frame", "base\\environment\\architecture\\common\\int\\shopkit_doorframe_l100_w20_h210.mesh"),
        ("door_piece", "base\\environment\\architecture\\common\\int\\shopkit_door_l100_w5_h210.mesh"),
        ("window_piece", "base\\environment\\architecture\\common\\int\\shopkit_window_l200_w10_h140.mesh"),
    ]:
        rows.append({"path": path, "class": cls, "family": "common/int/shopkit", "score": 100,
                     "dimensions": dims(3 if cls in {"floor_piece","wall_piece","ceiling_piece"} else 2, 3 if cls in {"floor_piece","ceiling_piece"} else .1, 3)})
    rows.append({"path": "base\\environment\\architecture\\common\\int\\other_wall_l300_w15_h300.mesh", "class": "wall_piece", "family": "common/int/other", "score": 90, "dimensions": dims(3,.1,3)})
    return {"format": "ncig-architecture-catalog-v1", "items": rows, "selected_count": len(rows)}


def test_ceiling_tiles_are_not_classified_as_floor():
    cls, _ = classify_structural_resource(
        "base\\environment\\architecture\\common\\int\\kit\\kit_ceiling_tiles_w500_l300_a_aa.mesh",
        {"floor", "ceiling", "mesh"},
    )
    assert cls == "ceiling_piece"


def test_choose_one_architecture_family_for_building():
    family, info = choose_architecture_family(_catalog(), "commercial")
    assert family == "common/int/shopkit"
    assert info["core_coverage"] == 3
    assert info["secondary_coverage"] == 3


def test_building_assembly_marks_family_coherent():
    b = BuildingAnchor("shop", "kabuki", "commercial", Vec3(0, 0, 0), 0, 8, 8, 1)
    r = Room("shop_F1_R01", "shopfloor", 0, 0, 0, 6, 6)
    s = Sector("shop_sector_F01", "shop", 0, "interior", Vec3(-4, -4, -1), Vec3(4, 4, 4), [r.id])
    layout = Layout(b, [r], [], [s], [])
    out = build_architecture_assembly([layout], _catalog())
    row = out["buildings"][0]
    assert row["selected_family"] == "common/int/shopkit"
    assert row["family_coherence"] is True
