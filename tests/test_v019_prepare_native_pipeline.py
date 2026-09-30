from pathlib import Path


def test_v019_prepare_native_pipeline_wires_probe_export_and_audit():
    text = (Path(__file__).parents[1] / "tools" / "prepare_native_architecture_remote.cmd").read_text(encoding="utf-8")
    assert "prepare_architecture_remote.cmd" in text
    assert "native_probe_cp2077.cmd" in text
    assert "architecture-native-compose" in text
    assert 'architecture-native-audit' in text
    assert '"%PYTHONEXE%" -m ncig.cli architecture-native-audit' in text
    assert 'set "TEMPLATES=build\\native_templates.json"' in text
    assert 'set "BUILDING=demo_shop_001"' in text
    assert "native audit command returned without creating" in text
