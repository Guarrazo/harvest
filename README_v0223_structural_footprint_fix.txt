NCIG v0.22.3 — structural footprint patch

Purpose:
- Make generated room bays flush with the detected/building footprint.
- Generate render floor and ceiling against the full building footprint.
- Generate continuous floor collision against the full building footprint.
- Restore assemble_room locally if it is missing.

This is a LOCAL PATCH, not a complete repository ZIP.

Run from:
C:\Users\Guarrazo\Desktop\NCIG

Command:
powershell -ExecutionPolicy Bypass -File .\apply_v0223_structural_footprint_fix.ps1

The script creates .bak_v0223 backups before changing files.
Then regenerate:
.\tools\architecture_test_compose_bounded_cp2077.cmd
