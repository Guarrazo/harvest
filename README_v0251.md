# NCIG v0.25.1 — pipeline hotfix

v0.25.1 fixes the v0.25.0 pipeline failure caused by calling the non-existent `ncig.cli detect-city-buildings` command.

Instead, the persistent `build\city_world_index.sqlite` is consumed by the dedicated `ncig.city_index_detect` module. This preserves the intended no-rescan behavior and keeps the change isolated from `cli.py`.

After installing over v0.25.0, rerun the normal prepare command. The existing city and physics indexes are reused. The pipeline can then produce the v0.25 collision probe outputs:

- `build\collision_probe_first_safe.json`
- `build\collision_probe_first_safe.archive.xl` when the sector path is recoverable
