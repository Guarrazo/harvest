from pathlib import Path

from ncig import __version__


def test_v017_package_version_is_current():
    assert __version__ == "0.21.1"


def test_v017_layout_bundle_uses_package_version():
    for rel in ("src/ncig/io.py", "src/ncig/worldplan.py"):
        text = (Path(__file__).parents[1] / rel).read_text(encoding="utf-8")
        assert '"generator_version": __version__' in text


def test_v017_remote_prepare_reuses_remote_catalog():
    text = (Path(__file__).parents[1] / "tools" / "prepare_architecture_remote.cmd").read_text(encoding="utf-8")
    assert "architecture_catalog.json" in text
    assert "reusing remote architecture catalog" in text
    assert "rebuild-catalog" in text
    assert 'if not exist "%OUT%" mkdir "%OUT%"' in text
    assert "if errorlevel 1" in text
