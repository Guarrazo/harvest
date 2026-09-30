## v0.21.1

- Architectural fit now uses complete filename dimensions as a narrowly bounded pre-runtime hint; runtime bounds remain authoritative.
- Structural class selection is family-fixed per building to avoid per-piece family roulette; incompatible global fallbacks are explicitly reported.
- Automatic building candidates preserve detected entrance coordinates in building-local space.
- Decoration selection now chooses a room-level furniture kit family before selecting individual `.ent` resources.

## v0.21.0

- Corrected CP77 `w/l/h` dimension semantics for walls, doors, windows, floors and ceilings.
- Architecture selection now falls back from exact kit family to the same family group before global candidates, reducing cross-theme mixing.
- Added conservative runtime-bound scaling: automatic mesh stretching is only enabled after actual ResourceDepot bounding boxes are harvested.
- Added native room-shell collision generation using the observed entSpawner `worldCollisionNode` serializer shape, including corridor door gaps.
- Expanded generated sector bounds with a configurable streaming margin (default 32 m) to reduce premature unloads during in-game validation.
- Added a deterministic `.ent` decoration catalog and room-grammar decoration planner.
- Added native `worldEntityNode` composition using the harvested real entity template.
- Native audit now accounts for mesh, collision and optional entity nodes.

# Changelog

## v0.19.0 — native architecture mesh export

- Added `architecture-native-export` for cloning a real harvested `worldMeshNode` into native Object Spawner output.
- Preserves exporter-specific render/enumeration fields from the real probe template.
- Adds a Windows launcher using the verified Python launcher path.
- Supports exporting one building with `--building-id` or all buildings present in layouts and assembly.
- Keeps mesh-bounds validation explicit; no automatic filename-based scaling is introduced.
- Added `architecture-native-audit` to compare emitted nodes against the harvested template and assembly.
- Added `prepare_native_architecture_remote.cmd` for one-command remote harvest + real template merge + native export + audit.

## 0.18.1
- Added Windows `native_probe_cp2077.cmd` launcher using the configured Windows Python launcher, avoiding devkitPro/MSYS2 Python resolution.
- `native-probe` can merge an extracted real template harvest with an existing `templates.json` via `--base-templates`.
- Template merge preserves exported node payloads and deduplicates identical nodes without synthesizing native fields.

## 0.17.2 — remote architecture prepare fix

- Fixed `tools/prepare_architecture_remote.cmd` creating its output directory before copying the remote architecture catalog.
- Fixed the launcher to stop when the catalog copy fails instead of continuing to `architecture-assemble` with a missing file.


## v0.19.0 — native architecture mesh export

- Added `architecture-native-export` for cloning a real harvested `worldMeshNode` into native Object Spawner output.
- Preserves exporter-specific render/enumeration fields from the real probe template.
- Adds a Windows launcher using the verified Python launcher path.
- Supports exporting one building with `--building-id` or all buildings present in layouts and assembly.
- Keeps mesh-bounds validation explicit; no automatic filename-based scaling is introduced.
- Added `architecture-native-audit` to compare emitted nodes against the harvested template and assembly.
- Added `prepare_native_architecture_remote.cmd` for one-command remote harvest + real template merge + native export + audit.

## 0.17.1
- Fixed missing `sync_github_harvest` import in `ncig.cli`.
- Added regression coverage for the `sync-harvest` CLI symbol.
- Bumped package version to 0.17.1.

# NCIG v0.16.2

- `prepare_architecture_cp2077` now resolves existing `layouts.json` from common build locations.
- When no layout exists, it generates one from `build\examples\buildings.json` (or `-Buildings`) instead of failing with FileNotFoundError.
- Adds explicit selected-layout diagnostics.

# Changelog

## v0.19.0 — native architecture mesh export

- Added `architecture-native-export` for cloning a real harvested `worldMeshNode` into native Object Spawner output.
- Preserves exporter-specific render/enumeration fields from the real probe template.
- Adds a Windows launcher using the verified Python launcher path.
- Supports exporting one building with `--building-id` or all buildings present in layouts and assembly.
- Keeps mesh-bounds validation explicit; no automatic filename-based scaling is introduced.
- Added `architecture-native-audit` to compare emitted nodes against the harvested template and assembly.
- Added `prepare_native_architecture_remote.cmd` for one-command remote harvest + real template merge + native export + audit.

## v0.16.1

- Hardened the architecture preparation launcher with the same Windows-Python discovery used by the harvest launcher.
- Preserved rejection of MSYS2/devkitPro/Cygwin/MinGW interpreters.

## v0.16.0

- Fixed architecture application to emit the quaternion `rotation` consumed by the native bridge.
- Added explicit dimensional coverage/penalty reporting for filename-hint matching.
- Added `architecture-audit` readiness report.
- Added `probe-plan` command to identify missing real World Builder node templates instead of fabricating them.
- Added Windows helpers `prepare_architecture_cp2077.ps1` / `.cmd` to build a compact real-architecture catalog and assembly from the user's harvest.

## v0.15.0

- Added deterministic architecture assembler using the real harvested architecture catalog.
- Builds floor, wall, ceiling, doorway/frame and optional window placements from real resource paths.
- Preserves native mesh scale at 1.0; filename dimensions are used only as fit hints.
- Added `architecture-assemble` CLI command.
- Added `architecture-apply` CLI command to enrich an NCIG world plan with resource-bound `worldMeshNode` intent.
- Keeps the native Object Spawner boundary explicit: emitted architecture nodes still require a verified real `worldMeshNode` template before native export.

# Changelog

## v0.19.0 — native architecture mesh export

- Added `architecture-native-export` for cloning a real harvested `worldMeshNode` into native Object Spawner output.
- Preserves exporter-specific render/enumeration fields from the real probe template.
- Adds a Windows launcher using the verified Python launcher path.
- Supports exporting one building with `--building-id` or all buildings present in layouts and assembly.
- Keeps mesh-bounds validation explicit; no automatic filename-based scaling is introduced.
- Added `architecture-native-audit` to compare emitted nodes against the harvested template and assembly.
- Added `prepare_native_architecture_remote.cmd` for one-command remote harvest + real template merge + native export + audit.

## v0.13.4

- Corrige la autodetección de entSpawner instalado como mod de Cyber Engine Tweaks en `bin\x64\plugins\cyber_engine_tweaks\mods\entSpawner`.
- Mantiene compatibilidad con la ruta alternativa `bin\x64\plugins\entSpawner`.
- Añade `-EntSpawnerRoot` para indicar explícitamente la carpeta cuando sea necesario.
- Mantiene la selección de un Python 3.11+ nativo de Windows y rechaza intérpretes MSYS2/Cygwin/MinGW/devkitPro.

# Changelog

## v0.19.0 — native architecture mesh export

- Added `architecture-native-export` for cloning a real harvested `worldMeshNode` into native Object Spawner output.
- Preserves exporter-specific render/enumeration fields from the real probe template.
- Adds a Windows launcher using the verified Python launcher path.
- Supports exporting one building with `--building-id` or all buildings present in layouts and assembly.
- Keeps mesh-bounds validation explicit; no automatic filename-based scaling is introduced.
- Added `architecture-native-audit` to compare emitted nodes against the harvested template and assembly.
- Added `prepare_native_architecture_remote.cmd` for one-command remote harvest + real template merge + native export + audit.

## v0.13.2

- Fixed `tools/harvest_cp2077.ps1` selecting MSYS2/devkitPro Python before a Windows Python.
- Added automatic Python discovery via `py.exe` and common Windows Python locations.
- Added an import probe so the launcher only accepts interpreters that can import `ncig`.
- Kept the harvest pipeline and output format unchanged.


## v0.12.0
- Added deterministic resource resolver for harvested asset catalogs.
- Added semantic aliases and node-context scoring so catalog order no longer decides assets.
- Enforced `.mesh` resources for mesh nodes and `.ent` resources for entity nodes.
- Added `resource-check` audit command with ranked alternatives and confidence.
- Added `bind-resources` command to write auditable resource assignments into a plan copy.
- Updated the native bridge to use the resolver instead of first-match-by-role selection.
- Added regression tests for resource binding and native bridge resolution.


## v0.11.0
- Added deterministic playable-shell planning with one room area per generated room.
- Fixed architectural node rotation so building yaw is applied to generated shell geometry.
- Added optional exact collision-box generation when verified preset/material values are supplied.
- Harvested mesh, light and collision templates now accept generated overrides without discarding harvested exporter-specific fields.
- Preserved pitch/roll when rotating harvested modules.
- Added regression coverage for shell composition and template overrides.

## 0.10.0

- Added explicit `floor` assignment to generated world-plan nodes.
- Fixed multi-floor native bridge composition so nodes are emitted only into their matching floor sector.
- Added logical connectivity graph with entrance, room-access and vertical-core transitions.
- Added `plan-lint` CLI command for structural pre-bridge validation.
- Added per-sector native emission diagnostics.

## 0.5.0

- Added public/reference node schema layer based on World Builder + entSpawner exporter structure.
- Added automatic asset/template harvesting from World Builder/entSpawner/mod data.
- Added `schema-report` CLI command.
- Added `harvest` CLI command.
- Added `schema-bridge` CLI command.
- Added exact-shape serializers for entity, mesh, light, collision and area nodes, with conservative fallback for unresolved runtime-sensitive enum fields.
- Kept the previous exact-template bridge unchanged for maximum compatibility.
- Added v0.5 documentation.

## 0.6.0

- Added module library built from harvested World Builder/mod templates.
- Added semantic module classification and room-kind matching.
- Added deterministic module instantiation/placement with transform preservation.
- Added `modules` CLI command.
- Added automated tests for module indexing and placement.

## 0.7.0

- Added harvested-module room decoration layer.
- Added deterministic module selection by room role/fit.
- Added transform-aware module instantiation while preserving source node payloads.
- Added `decorate` CLI command.
- Added decorator tests.

## 0.8.0

- Sanitized NCIG-only node metadata before native Object Spawner output.
- Added sector-aware composition of harvested module nodes.
- Added `--decoration` support to `schema-bridge`.
- Added regression coverage for native-shaped output and module composition.

## 0.8.1

- Fixed Object Spawner sector-name handling for NCIG world plans using `name` instead of `id`.
- Fixed native composition test expectations after NCIG metadata sanitization.

## 0.9.0

- Added clean native Object Spawner output with NCIG metadata removed.
- Added optional diagnostics sidecar via `schema-bridge --report`.
- Added regression test for metadata sanitization.

## v0.13.2

- Added `preflight` export-readiness gate.
- Added deterministic `merge-harvest` for combining multiple machine-local harvests.
- Added PowerShell helper `tools/harvest_cp2077.ps1` for the user's Cyberpunk installation.
- Added v0.13 documentation for the exact user-side harvest and preflight workflow.
### 0.13.3
- Robust Windows Python discovery for CP2077 harvest.
- Explicitly rejects MSYS2/devkitPro/Cygwin/Mingw interpreters.
- Added `tools/diagnose_environment.ps1`.
- `harvest_cp2077.cmd` now delegates to the same robust PowerShell launcher.

## 0.14.0 — real architecture catalog
- Added `ncig.architecture_catalog` for compact structural asset indexing.
- Added deterministic structural classes: floor, wall, ceiling, door frame, door, opening, window, pillar, stairs, rail and trim.
- Added conservative architecture-domain filtering and interior detection.
- Added filename dimension hints with explicit `filename_hint` provenance.
- Added family extraction and family-diverse candidate selection.
- Added `architecture-catalog` CLI command with `--interior-only`.
- Fixed `no_holes` false-positive opening classification.

## 0.14.1 — Windows launcher
- Added `architecture_catalog_cp2077.cmd` / `.ps1` so the compact catalog command uses a verified Windows Python instead of the active MSYS2/devkitPro `python.exe`.

## v0.17.0 — remote harvest cache

- Added `ncig sync-harvest` for public GitHub harvest repositories.
- Added deterministic SHA-256 manifesting and atomic downloads.
- Added optional ingestion of `architecture_catalog.json` and `architecture_assembly.json` when present.
- Added `tools/sync_harvest_github.cmd` and `tools/prepare_architecture_remote.cmd`.
- Remote sync never invents resources and keeps the original harvest files untouched.

## v0.18.0 — native mesh probe tooling

- Added `native-probe` to inspect one real World Builder/Object Spawner export and extract its real node templates without synthesizing fields.
- `architecture-audit` can now consume `templates.json` and reports the actual `worldMeshNode` template count.
- `prepare_architecture_remote.cmd` now feeds the remote template harvest into the architecture audit.
- Native mesh readiness remains gated by both real `worldMeshNode` template presence and zero unresolved architecture placements; mesh bounds still require validation.

## 0.19.1 — native remote pipeline audit fix

- Fixed `prepare_native_architecture_remote.cmd` failing at the final audit because `PYTHONEXE` was scoped inside a child `setlocal`.
- The parent script now re-discovers Windows Python before `architecture-native-audit`.
- Added a postcondition that fails if the audit command returns without creating its report.

## v0.20.0 — target detection, coherent architecture kits, runtime mesh bounds

- Added conservative `detect-buildings` analysis for exported streamingsector JSON.
- Added `candidates-to-buildings` conversion with PCA-derived building yaw.
- Architecture assembly now selects a dominant structural family per building to avoid unrelated wall/floor/ceiling kits being mixed.
- Structural classification prioritizes filename semantics, preventing ceiling tile resources from being classified as floor pieces by broad harvest roles.
- Added `bounds-targets`, `merge-bounds`, and the optional CET `NCIGBoundsHarvester` for runtime `.mesh` bounding boxes and physics presence.
- Native preparation reuses `architecture_catalog_bounded.json` automatically when present.
