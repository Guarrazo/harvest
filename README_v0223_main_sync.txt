NCIG v0.22.3 — canonical main sync repair

Run from C:\Users\Guarrazo\Desktop\NCIG:
powershell -ExecutionPolicy Bypass -File .\sync_v0223_main_canonical.ps1

The script downloads the canonical v0.22.3 files from Guarrazo/harvest main, validates them, backs up the current local copies as .bak_v0223_sync, and replaces them.

Then run:
.\tools\architecture_assemble_bounded_cp2077.cmd
.\tools\architecture_test_compose_bounded_cp2077.cmd

This is a repair/sync ZIP, not a complete repository ZIP.
