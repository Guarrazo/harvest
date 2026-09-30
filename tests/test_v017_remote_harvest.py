import json
from pathlib import Path

from ncig.remote import github_raw_url, parse_github_source


def test_v017_parse_public_github_repo():
    assert parse_github_source("https://github.com/Guarrazo/harvest") == ("Guarrazo", "harvest")
    assert parse_github_source("https://github.com/Guarrazo/harvest.git/") == ("Guarrazo", "harvest")


def test_v017_reject_non_github_source():
    try:
        parse_github_source("https://example.com/harvest")
    except ValueError as exc:
        assert "public GitHub repo URL" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_v017_raw_url_is_deterministic():
    assert github_raw_url("Guarrazo", "harvest", "harvest.json") == "https://raw.githubusercontent.com/Guarrazo/harvest/main/harvest.json"


def test_v017_manifest_format_example(tmp_path):
    manifest = {
        "format": "ncig-remote-harvest-manifest-v1",
        "source": "https://github.com/Guarrazo/harvest",
        "files": [{"file": "harvest.json", "bytes": 10, "sha256": "abc", "status": "downloaded"}],
        "missing_optional": [],
    }
    p = tmp_path / "manifest.json"
    p.write_text(json.dumps(manifest), encoding="utf-8")
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["format"] == "ncig-remote-harvest-manifest-v1"
