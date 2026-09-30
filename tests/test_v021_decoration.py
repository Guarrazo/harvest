from ncig.decoration_catalog import build_decoration_catalog
from ncig.decoration_plan import build_decoration_plan
from ncig.model import BuildingAnchor, Layout, Room, Sector, Vec3


def _harvest():
    def meta(path_roles):
        return {"roles": path_roles, "sources": ["fixture.json"]}
    return {"format": "ncig-harvest-v1", "resources": {
        "base\\environment\\furniture\\shop\\shop_counter.ent": meta(["counter"]),
        "base\\environment\\furniture\\shop\\shop_shelf.ent": meta(["shelf"]),
        "base\\environment\\furniture\\shop\\shop_display.ent": meta(["display"]),
        "base\\environment\\furniture\\shop\\shop_light.ent": meta(["light"]),
        "base\\environment\\furniture\\office\\desk.ent": meta(["desk"]),
    }}


def _layout():
    b = BuildingAnchor("shop", "kabuki", "commercial", Vec3(0,0,0), 0, 8, 8, 1)
    r = Room("shop_F1_R01", "shopfloor", 0, -3, -3, 6, 6)
    s = Sector("shop_sector_F01", "shop", 0, "interior", Vec3(-4,-4,-1), Vec3(4,4,4), [r.id])
    return Layout(b, [r], [], [s], [])


def test_decoration_catalog_collects_only_ent_resources():
    c = build_decoration_catalog(_harvest(), max_per_role=10)
    assert c["selected_count"] >= 4
    assert all(x["path"].endswith(".ent") for x in c["items"])


def test_shop_decoration_plan_is_rule_driven_and_deterministic():
    c = build_decoration_catalog(_harvest(), max_per_role=10)
    a = _layout()
    p1 = build_decoration_plan(a, c, architecture_family="common/int/shopkit")
    p2 = build_decoration_plan(a, c, architecture_family="common/int/shopkit")
    assert p1["placements"] == p2["placements"]
    roles = {x["role"] for x in p1["placements"]}
    assert "counter" in roles
    assert "shelf" in roles
    assert "display" in roles
