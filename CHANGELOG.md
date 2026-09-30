- Backwards-compatible room-rule dimension filtering, partial filename-hint fitting, normalized common interior family identities, and room-aware door candidate filtering.
- Exterior perimeter collision now preserves a detected ground-floor entrance opening.
## v0.23.0

- Add style-aware interior asset quality filtering for walls and doors, including explicit penalties/blocks for grille, railing, prison/cell and other non-partition semantics.
- Add deterministic variety selection among near-equivalent architectural candidates instead of always selecting the same first-ranked mesh.
- Increase generated door clear-width targeting to human-scale openings and report clear-width/height diagnostics.
- Add an explicit exterior perimeter collision shell on every generated floor, independent of room-shell coverage.
- Keep collision door openings synchronized with the visual door clear-width policy.
- Preserve a last-resort catalog fallback when semantic filtering exhausts all candidates, with the mismatch recorded in selection metadata.

## v0.22.3

- Keep generated room bays flush with the building footprint so structural walls meet instead of leaving artificial offsets.
- Generate the render floor/ceiling and continuous floor collision against the full building footprint rather than the shrunken room envelope.
- Restore the `assemble_room` function required by the runtime-bounds assembly pipeline.

## v0.22.2

- Report the continuous per-floor collision policy accurately in native composition metadata.

## v0.22.1

- Restore the runtime-aware ceiling surface function required by the 0.22.x architecture pipeline.
- Use valid entSpawner collision defaults: `Simple Environment Collision` and `concrete.physmat`.
- Keep the continuous per-floor collision envelope across generated corridors.

## v0.22.0

- Use runtime mesh bounds without collapsing local X/Y axis identity: wall-like pieces now scale along their actual structural span axis and rotate that axis onto the requested wall run.
- Align emitted meshes by their harvested bounding-box center, preventing non-centered mesh pivots from shifting walls, doors, windows, floors and ceilings.
- Generate one continuous floor and ceiling surface per generated floor envelope so the central corridor is no longer left without render geometry.
- Extend generated floor collision to the same continuous per-floor envelope and route those collision nodes to the correct floor sector.
- Keep corridor-facing wall pieces on the selected wall class family instead of falling back to the primary building family.