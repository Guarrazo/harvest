from pathlib import Path


def test_v021_native_pipeline_uses_composition_and_supports_decoration():
    text = (Path(__file__).parents[1] / "tools" / "prepare_native_architecture_remote.cmd").read_text(encoding="utf-8")
    assert "architecture-native-compose" in text
    assert "with-decoration" in text
    assert "--streaming-margin 32" in text
    assert "architecture-native-audit" in text


def test_v021_decoration_prepare_script_exists():
    p = Path(__file__).parents[1] / "tools" / "prepare_decoration_remote.cmd"
    text = p.read_text(encoding="utf-8")
    assert "decoration-catalog" in text
    assert "decoration-plan" in text
