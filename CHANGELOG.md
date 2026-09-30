## v0.22.7

- Add a city-scale world-data pipeline for large `.streamingsector` exports, using an XY spatial grid for proximity queries instead of full pairwise scans.
- Accept both World Builder/Object Spawner JSON envelopes and direct single-sector JSON files, including `nodes` + `nodeData` placement exports.
- Add `detect-city-buildings` and automatically write a compact `build\\world_manifest.json` beside the candidate report.
- Restrict existing-interior evidence checks to the estimated building footprint (with a small margin), reducing false rejection from neighboring interiors.
- Add city-pipeline tests for direct sector parsing, spatial indexing and world manifests.

## v0.22.6

- Correct the corridor/exterior collision orientation and add a solid collision header above 2.20 m door openings.
- Set the default doorway to 1.25 m × 2.20 m and avoid emitting door leaves unless a collisionless variant is known.
- Remove arbitrary generated facade windows; detected exterior windows are retained as evidence and are not rendered until NCIG can cut a proper wall opening around them.
- Carry detected facade openings and district information into building anchors.
- Add district-aware, deterministic variation between compatible architecture kits.
- Require multi-side architectural evidence and a sane geometry range before an automatic building candidate is marked fillable.
- Improve exterior footprint estimation for wall/door/window meshes by treating filename dimensions according to structural semantics.
## v0.22.5

- Fix collision doorway orientation: corridor-facing walls keep the walkable opening; exterior walls no longer get an accidental centered gap.
- Reduce default generated doorway opening to 1.15 m × 2.10 m and omit door leaves unless a harvested collisionless variant exists, keeping entrances traversable.
- Prefer full structural wall modules and reject decorative/add-on/protector/grate/bar pieces for the main shell when suitable alternatives exist.
- Add mirrored visual faces for very thin runtime wall meshes to reduce one-sided/backface transparency when viewed from inside.
- Carry detected exterior entrance position, orientation, scale and filename dimensions into building candidates and open the generated exterior wall at that entry.
- Make automatic building detection more geometry-aware and prefer the bounded runtime architecture catalog when it is available.

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
