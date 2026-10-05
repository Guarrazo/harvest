NCIG v0.22.8 — city-scale sync

This is a sync/diagnostic bundle, not a complete repository archive.

1. Copy sync_v0228_main_canonical.ps1 to C:\Users\Guarrazo\Desktop\NCIG.
2. Run it from the NCIG directory.
3. Use tools\inspect_city_json_cp2077.cmd to inspect one exported sector without manually setting PYTHONPATH.

The city pipeline now parses WolvenKit's native worldStreamingSector/Data/nodeData format and can build a persistent SQLite evidence index before automatic detection.
