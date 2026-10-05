# NCIG v0.25.3 — fast city detection + exact collision probe

v0.25.3 addresses two v0.25.x issues:

1. Candidate detection no longer materializes the entire ~2.8M-record city index into Python and no longer performs quadratic entrance grouping. It loads the entrance rows from SQLite, clusters them spatially, and fetches local architecture/interior rows through the existing cell indexes.
2. The exact collision probe is now included. It reads the `node_index` from `collision_removal_manifest.json`, opens the matching local `.streamingsector.json`, validates `expectedNodes`, extracts the exact `worldCollisionNode`, its placement/nodeData, shape information when available, and nearby nodes.

The probe never edits the source sector. It only emits diagnostic JSON. An ArchiveXL `.xl` draft is emitted **only** when a verified depot sector path is supplied; the pipeline does not invent an installable path from a flat export directory.

Expected output after existing indexes are reused:

- `NCIG 0.25.3: loaded N entrance records from SQLite (no full-city load)`
- `NCIG 0.25.3: entrance groups=...`
- progress every 500 groups
- `build\collision_probe_first_safe.json` at the end of the collision-probe stage
