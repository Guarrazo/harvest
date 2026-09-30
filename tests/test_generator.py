import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / 'src'))

from ncig.generator import generate_layout, stable_seed, validate_layout
from ncig.model import BuildingAnchor, Vec3


def building(seed=None):
    return BuildingAnchor(
        id="test_001", district="watson", type="residential",
        position=Vec3(10, 20, 0), yaw_deg=30, width_m=16, depth_m=14,
        floors=3, seed=seed
    )


def test_deterministic():
    a = generate_layout(building())
    b = generate_layout(building())
    assert a.to_dict() == b.to_dict()


def test_valid():
    layout = generate_layout(building(123))
    assert validate_layout(layout) == []
    assert len(layout.sectors) == 3
    assert any(s.semantic == "sit" for s in layout.sockets if s.kind == "activity")


def test_seed_changes_layout():
    a = generate_layout(building(1)).to_dict()
    b = generate_layout(building(2)).to_dict()
    assert a != b
