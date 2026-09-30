# Roadmap

## v0.1 — procedural planning
- deterministic floor plans
- room/activity/loot sockets
- sector suggestions
- previews

## v0.2 — runtime-aware architecture
- flexible RedHotTools observation ingestion
- door candidate scanner
- deterministic building anchors
- dedicated building entry markers
- modular room floors/ceilings/walls/openings
- vertical core/circulation planning
- improved asset catalogue scoring
- World Builder node-model plan

## v0.3 — native authoring bridge
- template-driven Object Spawner export bridge
- export fingerprinting to learn the exact installed World Builder schema
- automatic nodeRef generation and transform/resource field mapping
- deterministic NCIG metadata and warnings
- WolvenKit import handoff documentation
- native `.streamingsector` / `.streamingblock` smoke-test fixture (requires one real user export)

## v0.4 — playable shell
- entrance linking
- interior trigger/ambient areas
- collision generation
- doors and lighting
- first real test building in-game

## v0.5 — population
- AISpot placement
- Community authoring
- time-of-day activity phases
- safe NPC density limits

## v0.6 — city scanner
- bulk extraction of candidate doors/entries
- existing-interior blacklist
- building footprint inference from nearby geometry
- per-district rules

## v0.10 — floor-safe composition + connectivity
- explicit node-to-floor assignment
- cross-floor duplication guard in native bridge
- logical entrance/room/vertical connectivity graph
- pre-bridge structural plan lint

## v0.11 — playable shell composition
- room area nodes generated from exact room footprints
- building-yaw-safe shell transforms
- collision shell generation when exact verified collision values are provided
- harvested-template resource/shape overrides
- first shell diagnostics bundled with world plans

## v0.12 — deterministic resource binding
- semantic/resource-role resolver
- deterministic candidate scoring using harvested metadata and node context
- mesh/entity extension enforcement
- resource-check audit command
- bind-resources plan transformation with confidence and alternatives

## v0.13 — first in-game authoring pack
- verified mesh/entity/light/marker templates from one real World Builder installation
- entrance/marker native composition
- one clean end-to-end building export for WolvenKit validation
- collision/template readiness report

## v1.0 — city-scale generation
- hundreds/thousands of candidate interiors
- deterministic seeds
- compatibility blacklist
- incremental generation by district
- regression tests for streaming, collisions and runtime entry routing

## v0.14 — real architecture catalog
- compact structural asset catalog derived from the machine-local harvest
- architecture/interior filtering and domain exclusions
- filename dimension hints marked as non-authoritative
- family-aware deterministic candidate selection
- CLI export for the next shell/module assembly stage
