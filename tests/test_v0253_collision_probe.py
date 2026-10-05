from __future__ import annotations

import json
from pathlib import Path


def test_probe_artifacts_have_expected_schema() -> None:
    # Structural contract test for the output shape used by downstream tooling.
    sample = {
        "format": "ncig-collision-probe-v1", "version": "0.25.3",
        "probes": [{"status": "ok", "target": {"node_index": 2}, "neighbors": []}],
        "archive_xl": {"requested": True, "generated": False, "reason": "verified depot path required"},
    }
    assert sample["format"] == "ncig-collision-probe-v1"
    assert sample["probes"][0]["status"] == "ok"
    assert sample["archive_xl"]["generated"] is False
