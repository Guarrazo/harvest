# NCIG v0.30.1 — detector hotfix

This corrects the packaging/indentation error in v0.30.0 and keeps the intended performance changes.

Changes:
- valid Windows batch and Python files with normal line endings;
- spatial windows use the minimum cell span required by the query radius;
- exact radius filtering happens before deterministic Python sorting;
- detector heartbeat is emitted at the first processed group and every 100 groups;
- preserves v0.29 bounded LRU cache and checkpoint/resume support;
- existing SQLite indexes are reused; do not delete them.
