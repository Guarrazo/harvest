# NCIG v0.29.0 UNIFIED — missing patches

This package combines the two overlays that were still unapplied in the current workflow:

- **v0.28.0 Structural Upgrade**
  - explicit corridor / entry lobby / stairwell structural zones
  - continuous vertical stair core metadata
  - bidirectional vertical sockets
  - real `stairs_piece` architectural placements
  - logical connectivity audit
  - footprint profile metadata for compact / elongated / long-strip plans

- **v0.29.0 Detector**
  - bounded LRU SQL-window cache
  - read-only SQLite connection
  - deterministic Python-side ordering
  - checkpoint/resume support
  - no SQLite `ORDER BY id` temporary-sort dependency

## Install

From the extracted package, run:

`tools\\install_missing_v028_v029.cmd C:\\Users\\Guarrazo\\Desktop\\NCIG`

The installer creates backups under:

`build\\patch_backups\\v028_v029_unified`

It performs a Python syntax check, installs the v0.28 runner into the target repo, but **does not execute the long detector** and **does not run the v0.28 structural post-process**.

## After install

Re-run your existing detection command:

`prepare_detected_buildings_remote.cmd https://github.com/Guarrazo/harvest C:\\CyberpunkExports\\sectors 10`

The detector can resume from:

`build\\auto_building_candidates.json.partial.json`

Once the normal pipeline has produced:

`build\\generated_auto\\layouts.json`

run:

`tools\\apply_v028_structural.cmd`

## Deliberately not included

The still-unfinished **physical stair collision integration / floor-hole collision** is not included in this package. The current v0.28 stair upgrade is structural + visual + logical connectivity; physical stair traversal still requires the dedicated collision stage and runtime validation.

Native `worldMeshNode` export also remains blocked until a real World Builder/entSpawner `worldMeshNode` template is supplied.
