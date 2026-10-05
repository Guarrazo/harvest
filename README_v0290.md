# NCIG v0.29.0 — disk-safe/resumable city detector

This overlay updates only `city_index_detect.py`.

Changes:
- bounded LRU SQL-window cache (default 256 instead of unbounded growth);
- read-only SQLite connection;
- no SQLite `ORDER BY id` in the spatial window query, avoiding a possible temporary on-disk sort;
- deterministic Python-side ordering;
- checkpoint every 500 entrance groups;
- automatic resume after interruption/crash when the SQLite file has not changed;
- progress reports cache hits/misses and bounded cache size.

Run from the NCIG repo root after installing the file:
`py -3 -m ncig.city_index_detect --input build\\city_world_index.sqlite --out build\\auto_building_candidates.json --cache-windows 256`

Checkpoint:
`build\\auto_building_candidates.json.partial.json`

The patch does not delete or rebuild the existing city index.
