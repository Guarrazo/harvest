NCIG v0.22.3 geometry diagnostic

Purpose:
Analyze the freshly generated bounded architecture assembly for demo_shop_001.
It maps each resource to its runtime mesh bounds and computes the actual transformed
2D bounding box of every wall, door, frame, floor and ceiling placement.

Default inputs:
build\generated\layouts.json
build\real_architecture_remote\architecture_assembly_bounded.json
build\real_architecture_remote\architecture_catalog_bounded.json

Run:
.\tools\architecture_geometry_diagnostic_cp2077.cmd

Output:
build\real_architecture_remote\geometry_diagnostic_demo_shop_001.json

Important values:
- runtime_bounds_missing_count
- scale_non_identity_count
- wall expected line errors
- door expected center errors

This is a diagnostic ZIP, not a complete repository ZIP.
