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
