from pathlib import Path

def _ps1() -> str:
    return Path(__file__).parents[1].joinpath("tools", "harvest_cp2077.ps1").read_text(encoding="utf-8")


def test_cet_entspawner_path_is_preferred_and_legacy_path_kept():
    s = _ps1()
    cet = r"bin\x64\plugins\cyber_engine_tweaks\mods\entSpawner"
    legacy = r"bin\x64\plugins\entSpawner"
    assert cet in s
    assert legacy in s
    assert s.index(cet) < s.index(legacy)


def test_explicit_entspawner_override_exists():
    s = _ps1()
    assert "EntSpawnerRoot" in s
    assert "-EntSpawnerRoot" in s


def test_msys2_and_devkitpro_are_rejected():
    s = _ps1().lower()
    assert "msys2" in s
    assert "devkitpro" in s
    assert "cygwin" in s
    assert "mingw" in s
