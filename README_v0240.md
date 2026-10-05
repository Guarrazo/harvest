# NCIG v0.24.0 — world physics / proxy / door audit

This overlay extends the v0.23.0 pipeline with a dedicated lightweight physics index and access audit.

## Why this exists

A `.streamingsector` export can expose several different facts that must not be conflated:

- `worldBuildingProxyMeshNode` is distant proxy geometry. It is indexed as proxy evidence, never as collision.
- `worldCollisionNode` is explicit world collision. Its node index and source node count are preserved so a later ArchiveXL removal step can be generated from evidence rather than guessed.
- A missing `worldCollisionNode` does **not** prove that a visible `worldMeshNode` is walk-through, because embedded mesh collision can exist.
- A door-looking mesh is not automatically a real exterior portal. Door candidates are scored by their proximity to the detected exterior boundary and by semantic resource/name signals.

## New outputs

`build/world_physics_index.sqlite` is a persistent physics/proxy/door index. It is expensive to build once, then cheap to reuse.

`build/auto_building_candidates_access.json` adds per-building:

- proxy status
- explicit collision status
- probable exterior doors
- collision nodes overlapping the doorway
- safe/unsafe collision-removal candidates
- an exterior style profile derived from real resource-family paths

`build/collision_removal_manifest.json` is an evidence file, not a guessed `.xl` file. It records source sector, node index and expected node count for small/localized collision blockers. The actual ArchiveXL sector depot path is intentionally left blank unless the export preserves that mapping.

## Collision policy

1. Small/localized `worldCollisionNode` overlapping a high-confidence exterior door: candidate for node removal.
2. Large shell collision overlapping the entry: never auto-delete. It must be replaced by a collision mesh with the doorway cut out, or explicitly validated in-game.
3. No explicit collision: runtime probe required, because embedded collision may still exist.
4. Proxy-only evidence: runtime probe required; proxy nodes are never treated as a physical barrier.

## Style policy

The audit extracts distinctive tokens and family-bearing path segments from the building's actual exterior `worldMeshNode` resources. The style-aware assembler temporarily uses these tokens to bias the architectural kit toward compatible interior families. It does not claim to infer material colors or fine visual details from sector metadata alone.

## In-game validation

The first runtime validation should be a single selected building with `runtime_probe_required`, `runtime_probe_proxy_only`, or `requires_collision_mesh_replacement_or_runtime_validation` in the access audit.

Use RedHotTools World Inspector around the entrance and record:

- the exterior door node type/name
- any `worldCollisionNode` at the doorway
- whether the visible facade itself has embedded collision
- whether the player can physically pass the doorway after temporarily removing the identified collision blocker

Do not mass-test the whole city yet. One or two representative buildings are enough to calibrate the rules before scaling up.
