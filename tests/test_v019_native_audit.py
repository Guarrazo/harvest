import json
from pathlib import Path

from ncig.native_architecture_audit import audit_native_architecture
from test_v019_native_architecture import datasets
from ncig.native_architecture import build_native_architecture_export


def test_v019_native_audit_accepts_valid_export():
    layout, assembly, templates, base = datasets()
    native, _ = build_native_architecture_export(layout, assembly, templates, base)
    # build output is the native envelope already stripped of ncigSourceFile.
    report = audit_native_architecture(native, layout, assembly, templates)
    assert report["passed"] is True
    assert report["matched_placements"] == 1


def test_v019_native_audit_rejects_resource_mismatch():
    layout, assembly, templates, base = datasets()
    native, _ = build_native_architecture_export(layout, assembly, templates, base)
    native["sectors"][0]["nodes"][0]["data"]["mesh"]["DepotPath"]["$value"] = "base\\wrong\\not_the_assembly.mesh"
    report = audit_native_architecture(native, layout, assembly, templates)
    assert report["passed"] is False
    assert report["resource_errors"] >= 1
