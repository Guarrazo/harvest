NCIG v0.22.9 — CR2W streamingsector parser fix

This is a small sync/repair bundle, NOT the full NCIG repository and NOT the 90+ GB world export.

Problem fixed:
- WolvenKit exports use Data.RootChunk for worldStreamingSector.
- Native nodes can be wrapped as nodes[*].Data.
- nodeData is a structured worldNodeDataBuffer with Data[] placements referencing NodeIndex.
- SQLite city detection previously reused an empty v2 index and then crashed because its runtime manifest lacked json_file_count.

What v0.22.9 changes:
- Parser reads Data.RootChunk.
- Native node wrappers are unwrapped.
- CName-style debugName values are resolved.
- City index format is now ncig-city-index-v3.
- prepare_detected_buildings_remote.cmd rebuilds a stale/incompatible index automatically.
- SQLite detection safely reuses the persisted city_world_index_manifest.json.
- Regression coverage added for the native CR2W layout.

Install locally:
1. Copy sync_v0229_main_canonical.ps1 to C:\Users\Guarrazo\Desktop\NCIG\
2. Run from PowerShell:
   powershell -ExecutionPolicy Bypass -File .\sync_v0229_main_canonical.ps1

Then rerun the prepare command. No world re-export is required.

The existing empty build\\city_world_index.sqlite is automatically invalidated because its manifest is v2, while v0.22.9 expects v3.
