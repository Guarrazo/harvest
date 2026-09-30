NCIG v0.22.4 — architecture coherence fix

Run:
powershell -ExecutionPolicy Bypass -File .\sync_v0224_main_canonical.ps1

Then rebuild the architecture catalog because family IDs changed:
$py = Get-Command py.exe | Select-Object -First 1 -ExpandProperty Source
& $py -3 -m ncig.cli architecture-catalog --harvest build\remote_harvest\harvest.json --out build\real_architecture_remote\architecture_catalog.json --interior-only

After rebuilding the catalog, merge the already-harvested runtime bounds using your existing merge-bounds command, then:
.\tools\architecture_assemble_bounded_cp2077.cmd
.\tools\architecture_test_compose_bounded_cp2077.cmd

v0.22.4 fixes:
- family derivation excludes mesh filenames
- shared vertical partitions emitted once
- doors widened to 1.30 m and 2.20 m high
- door/frame/window selection avoids obvious staircase/cage/prison styles and prefers the wall family
- collision doorway width matches visual doorway

This is a sync/repair bundle, not a complete repository ZIP.