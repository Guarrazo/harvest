NCIG v0.22.3 — canonical main sync repair

The previous local patch stopped because architecture_assembler.py used a different line-ending/layout variant than the patch expected.

This repair downloads the canonical v0.22.3 files from Guarrazo/harvest main, validates them, backs up the current local copies as .bak_v0223_sync, and replaces them.

Run from C:\Users\Guarrazo\Desktop\NCIG:
powershell -ExecutionPolicy Bypass -File .\sync_v0223_main_canonical.ps1

Then regenerate:
.\tools\architecture_assemble_bounded_cp2077.cmd
.\tools\architecture_test_compose_bounded_cp2077.cmd

This is a repair/sync ZIP, not a complete repository ZIP.