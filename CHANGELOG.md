## v0.22.4

- Fix architecture family derivation so mesh filenames are not treated as family names.
- Prevent duplicate shared room partitions that caused coplanar wall overlap and apparent transparency between rooms.
- Prefer door/frame assets compatible with the selected wall kit and reject obvious staircase/cage/prison styles for structural doors/walls.
- Increase generated door opening width/height to 1.30 m × 2.20 m and match collision doorway width.

## v0.22.3

- Keep generated room bays flush with the building footprint so structural walls meet instead of leaving artificial offsets.
- Generate the render floor/ceiling and continuous floor collision against the full building footprint rather than the shrunken room envelope.
- Restore the `assemble_room` function required by the runtime-bounds assembly pipeline.

## v0.22.2

- Report the continuous per-floor collision policy accurately in native composition metadata.

## v0.22.1
