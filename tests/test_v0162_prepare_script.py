from pathlib import Path

def test_v0162_prepare_script_has_layout_fallbacks():
    p = Path(__file__).parents[1] / "tools" / "prepare_architecture_cp2077.ps1"
    s = p.read_text(encoding="utf-8")
    assert "build\\layouts.json" in s
    assert "build\\generated\\layouts.json" in s
    assert "examples\\buildings.json" in s
    assert "no había layouts" in s
