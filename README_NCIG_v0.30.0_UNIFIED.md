# NCIG v0.30.0 — performance hotfix over unified v0.28/v0.29

Use this after installing the unified v0.28/v0.29 package, or use the included installer to replace the detector file only.

Changes:
- tighter spatial cell window (10 m queries no longer scan 5x5 cells);
- filter exact-radius results before deterministic Python sorting;
- progress heartbeat starts immediately and reports every 100 groups;
- preserves bounded cache and checkpoint/resume from v0.29.

This does not invalidate the existing SQLite indexes. Do not delete them.
