# NCIG v0.22.6


Esta iteración corrige un problema físico importante detectado en la prueba de `demo_shop_001`: los nombres de meshes CP77 usan `w/l/h` con semánticas distintas según la clase. Los muros y puertas ya no interpretan un `_w300` como 30 cm de tramo.

La arquitectura se mantiene en un kit familiar y, cuando faltan piezas de la familia exacta, NCIG prefiere familias del mismo grupo (`common/int`, etc.) antes de caer a recursos globales. La deformación automática queda desactivada hasta disponer de bounding boxes reales del ResourceDepot.

También se añade un shell de colisión por habitación con hueco de puerta y dintel sólido, selección de kits sensible al distrito, variación determinista entre familias compatibles y detección de ventanas/entradas basada en evidencia exterior. Las ventanas ya no se inventan en edificios sintéticos.

La detección automática de edificios usa exports reales de `streamingsector`, agrupa alrededor de entradas, estima el footprint exterior orientado, conserva puertas/ventanas detectadas, filtra carretera/terreno y evidencia de interior existente, y solo marca como rellenables los candidatos con geometría estructural suficiente.
# Night City Interior Generator (NCIG)

Procedural interior-generation toolkit for Cyberpunk 2077.

NCIG is designed around one goal: make a large portion of Night City's otherwise fake/closed spaces explorable without hand-authoring every building.


### Harvest desde entSpawner instalado como mod CET

El launcher detecta automáticamente la instalación habitual:
`bin\x64\plugins\cyber_engine_tweaks\mods\entSpawner`. También acepta la ruta alternativa `bin\x64\plugins\entSpawner`.

Desde PowerShell:

```powershell
.\tools\harvest_cp2077.cmd
```

Para forzar otra ruta:

```powershell
.\tools\harvest_cp2077.cmd -EntSpawnerRoot "C:\ruta\a\entSpawner"
```


## Current status

NCIG v0.14 adds a compact, deterministic architecture catalog on top of the v0.13 harvest/preflight pipeline. NCIG v0.13 adds a deterministic export preflight gate on top of resource binding. v0.12 introduced deterministic resource binding: a generated plan can now be matched against a harvested asset catalog without relying on catalog order. Every binding is scored and recorded, and unresolved resources remain unresolved rather than being fabricated.

The project now has a runtime-aware authoring pipeline:

```text
RedHotTools observations
          |
          v
      NCIG scanner
          |
          v
   building anchors
          |
          v
 procedural generator
    /      |       \
   v       v        v
shell    gameplay   sectors
   |       |        |
   +-------+--------+
           v
    World Builder plan
           |
           v
 World Builder / WolvenKit
           |
           v
 ArchiveXL streaming additions
```

The official World Editing documentation describes Night City as nodes grouped into `streamingsector`s and identifies RedHotTools, World Builder, WolvenKit and ArchiveXL as the relevant toolchain. World Builder's current export workflow turns saved root groups into sectors and exports Object Spawner JSON for WolvenKit import. citeturn755193view0turn788982search0

## v0.13 — export preflight and user harvest

Before producing a native Object Spawner file, NCIG can now verify that every generated node has the runtime-sensitive template/resource information required by its node class.

```powershell
python -m ncig.cli preflight --plan build/generated/wb_plans/demo_shop_001_world_plan_v2.json --assets build/user_harvest/harvest.json --templates build/user_harvest/templates.json --base examples/ncig_probe_exported.json --out build/preflight.json
```

Run `tools/harvest_cp2077.ps1` first on the target installation to collect the machine-local resources and node templates. `preflight` is a gate, not a guarantee of in-game acceptance.

## Commands

### Scan runtime observations

```powershell
$env:PYTHONPATH="$PWD/src"
python -m ncig.cli scan --input examples/runtime_observations.example.json --out build/scan_report.json --anchors-out build/scanned_buildings.json --district watson
```

### Generate interiors

```powershell
python -m ncig.cli generate --input build/scanned_buildings.json --out build/generated
```

### Build an asset catalog from a WolvenKit depot

```powershell
python -m ncig.cli catalog --root C:\CyberpunkAssets\Depot --out build/resource_catalog.json
```

### Prepare architecture from a real harvest

`tools\prepare_architecture_cp2077.cmd` first reuses an existing layout from `build\layouts.json`, `build\generated\layouts.json` or the demo bundle. If none exists, it generates a layout from `examples\buildings.json` automatically. Pass `-Layouts` or `-Buildings` to override this behavior.

### Build a compact architecture catalog from the real harvest

The full `harvest.json` is a resource-path catalogue. v0.14 turns it into a small deterministic index of real architectural `.mesh` candidates, separated into floors, walls, ceilings, doors, openings, windows, pillars, stairs, rails and trim. Dimensions parsed from filenames are explicitly marked as `filename_hint`; NCIG does not treat them as authoritative mesh bounds.

```powershell
.\tools\architecture_catalog_cp2077.cmd -InteriorOnly
```

Equivalent direct command:

```powershell
python -m ncig.cli architecture-catalog --harvest build/user_harvest/harvest.json --out build/architecture_catalog.json --interior-only
```

Use `--max-per-class` to change the number of candidates retained per structural class.

### Detectar edificios vacíos automáticamente

Exporta desde la herramienta de edición de mundo los `.streamingsector` del área que quieras analizar y colócalos, por ejemplo, en `C:\CyberpunkExports\sectors`.

Después ejecuta:

```powershell
.\tools\prepare_detected_buildings_remote.cmd https://github.com/Guarrazo/harvest C:\CyberpunkExports\sectors 10
```

El pipeline genera:

- `build\auto_building_candidates.json`: todos los candidatos con evidencia y puntuación.
- `build\auto_buildings.json`: solo candidatos suficientemente respaldados para generar.
- `build\generated_auto\layouts.json`: interiores calculados desde el footprint detectado.
- `build\real_architecture_remote\architecture_assembly_auto.json`: ensamblaje con assets reales.

La detección todavía necesita un export del mundo. No se añaden datos del mapa del juego al repositorio; el objetivo es que, dado el export, la detección, clasificación, cálculo y generación sean automáticos.
### Match scanned entries to generated anchors

```powershell
python -m ncig.cli routes --buildings build/scanned_buildings.json --scan examples/runtime_observations.example.json --out build/routes.json
```

### Validate

```powershell
python -m ncig.cli validate --layout build/generated/layouts.json
```

## Important boundary

`ncig-world-plan-v3.json` is intentionally **not** claimed to be a native CR2W or native World Builder project file. It uses World Builder's documented node vocabulary and export concepts, while preserving NCIG's deterministic procedural data. The native export adapter is the next milestone because the exact resource/node fields should be verified against the user's installed World Builder build rather than guessed.

World Builder currently supports static meshes, entity nodes, collision, lights, AI spots, communities, interior/ambient areas and static markers. Collision meshes in custom streaming sectors have an extra dependency on UnlimitedGeometryCacheStreaming. citeturn755193view1

## Why this architecture scales

The generator only needs a compact building anchor and a seed. A single building can expand into many rooms using reusable templates and resource semantics. A change to a template can therefore affect hundreds of generated interiors without opening each location manually.

## Next technical target

The next concrete target is **v0.3: exact Object Spawner/WolvenKit native export**. World Builder's current exporter already writes the high-level sector/node structure, streaming extents, NodeRefs and community metadata; NCIG should reproduce that mapping only after verifying the exact node/resource payloads in the user's toolchain. citeturn937975view0turn937975view1

## Native bridge

The project now contains a template-driven bridge for real World Builder/Object Spawner exports. Because the exact exported JSON envelope depends on the installed World Builder build, NCIG first fingerprints one real export and then uses that export as the schema template. See `docs/V0.3_BRIDGE.md`.

## Exact Object Spawner envelope

NCIG now understands the real export supplied from the user's World Builder build:

```json
{
  "xlFormat": 0,
  "sectors": [...],
  "version": "1.0.4",
  "name": "...",
  "devices": [],
  "psEntries": []
}
```

The command `exact-fingerprint` reports the exact node types present in a real export. `exact-bridge` then creates sectors and nodes using only payload templates that actually exist in that export. Unsupported node classes are reported in `ncig.skipped` instead of being fabricated.

### First concrete probe

`examples/ncig_probe_exported.json` is the exact user-supplied export containing one `worldEntityNode`. `build/ncig_probe_relocated.json` is a generated verification artifact using that exact node shape.

### What is needed for native interior geometry

The supplied probe contains only `worldEntityNode`, so NCIG can currently reproduce/relocate real entity nodes but cannot truthfully synthesize real mesh, collision, light, marker, area or community payloads. For the first complete procedural room, the minimum additional World Builder probe pack is:

- one Static Mesh (`worldMeshNode`)
- one Collision Shape (`worldCollisionNode`)
- one Static Light (`worldStaticLightNode`)
- one Static Marker (`worldStaticMarkerNode`)

A later pass can add Interior Area and Community nodes for AI/gameplay. World Builder documents these as distinct node types, so NCIG keeps them as separate template classes. citeturn227614search0

## v0.5 — public schema + automatic harvest

The manual probe-pack workflow is no longer required for the common node classes. NCIG now includes reference serializers derived from the public World Builder/entSpawner exporter structure and can automatically harvest real node payloads and resource paths from existing `entSpawner`/World Builder/mod JSON, Lua and text files. This is especially useful for mesh/light/collision nodes whose runtime-sensitive enum fields are safer to clone from a real exported node than to guess.

Use:

```powershell
python -m ncig.cli harvest --root "C:\Cyberpunk 2077\bin\x64\plugins\entSpawner" --out build/harvest.json --templates-out build/templates.json
python -m ncig.cli schema-bridge --plan build/generated/wb_plans/demo_shop_001_world_plan_v2.json --base examples/ncig_probe_exported.json --assets build/harvest.json --templates build/templates.json --out build/demo_shop_001_schema_object_spawner.json
```

The reference layer is based on the public World Builder supported-node documentation and the open-source entSpawner exporter implementations. It does **not** redistribute game assets; it only captures schemas and can discover resource paths in files already present on the user's machine.

## v0.6 — automatic module library

NCIG can now group harvested World Builder/mod JSON by source file and treat each file as a reusable module. The module library computes bounds, semantic roles and node-type composition, then can place a module around a room anchor with deterministic transforms. This means existing World Builder favorites/prefabs can become an automatically discovered decoration/room-module pool without recreating them manually in World Builder.

```powershell
python -m ncig.cli modules --harvest build/harvest_templates.json --out build/module_library.json
```

The module system deliberately preserves each real node payload. It changes placement and generated NodeRefs, not the underlying game resource payload.

## v0.7 — module decoration

Generated rooms can now be decorated from harvested World Builder/mod modules. NCIG selects a compatible module by room role and dimensions, places it around the room center with a deterministic transform, and preserves the real node payloads from the source module.

```powershell
python -m ncig.cli decorate --layout build/generated/layouts.json --library build/module_library.json --out build/decorated.json --density 0.65
```

This is intentionally an additional layer rather than replacing the procedural shell: a harvested furniture/room cluster can be reused across hundreds of procedurally generated rooms without manually recreating it.


## v0.8 — native composition / metadata sanitization

The final Object Spawner bridge strips NCIG-only annotations from individual nodes before writing the JSON consumed by WolvenKit. Harvested module nodes can be composed into the same sector as procedural content using `--decoration` on `schema-bridge`.

```powershell
python -m ncig.cli schema-bridge `
  --plan build/generated/wb_plans/demo_shop_001_world_plan_v2.json `
  --base examples/ncig_probe_exported.json `
  --templates build/templates.json `
  --decoration build/decorated.json `
  --out build/demo_shop_001_object_spawner.json
```


### v0.8.1 bugfix

The native bridge now accepts both `sector.id` and the World Plan v3 `sector.name` form, preventing generated content from being assigned to a differently named sector.


## v0.9 — clean native output

The `schema-bridge` writer now produces a clean Object Spawner JSON and removes NCIG-only metadata from the native payload. Diagnostics can be written separately with `--report`. This keeps the artifact handed to WolvenKit focused on the World Builder/Object Spawner schema.


## v0.10 — floor-aware native composition + connectivity

NCIG world plans now assign every generated node to an explicit floor. The native schema bridge uses those floor assignments to place nodes only in their correct streaming sector, preventing cross-floor duplication in multi-storey buildings.

A logical `ncig-connectivity-v1` graph is also emitted with room-access, entrance-access and vertical-core transitions. This is planner/runtime metadata, not a claim that NCIG has generated a native navigation mesh.

Before native composition, a plan can be structurally linted with:

```powershell
python -m ncig.cli plan-lint --plan build/generated/wb_plans/demo_megabuilding_001_world_plan_v2.json --out build/plan_lint.json
```

The lint checks unique `nodeRef`s, explicit floor assignments, sector uniqueness/extents and orphan floor references.


## v0.12 — deterministic resource binding

Resource selection is now an explicit, auditable step between procedural planning and native export. This prevents a valid layout from being accidentally paired with an unrelated asset simply because it appeared first in a catalog.


### Windows harvest launcher

If PowerShell resolves `python.exe` to MSYS2/devkitPro, use `tools\harvest_cp2077.cmd` or the v0.13.2 PowerShell launcher. NCIG requires a Windows Python 3.11+ interpreter that can import the project package.

## Windows harvest quick start

From PowerShell, after changing into the NCIG directory, run **only**:

```powershell
.\tools\harvest_cp2077.ps1
```

Do **not** paste the `PS F:\Games\NCIG>` prompt itself into the command.

The launcher deliberately avoids the MSYS2/devkitPro `python.exe` when selecting Python for NCIG. For diagnostics:

```powershell
.\tools\test_python.ps1
.\tools\diagnose_environment.ps1
```

## v0.14 — real architecture catalog

v0.14 separates the large machine-local resource harvest from the small structural catalog consumed by layout/module generation. The catalog is deterministic, conservative and family-aware. It never invents resource paths or runtime enum payloads.

The current user harvest was observed to contain 39,623 resource paths, including 27,301 `.mesh`, 11,229 `.ent` and 1,093 `.mi` entries. It also contains node-type mentions, but only one actual node template in the companion `templates.json`; therefore the architecture catalog can select real mesh paths while the native Object Spawner bridge still remains template-gated.


## v0.15 — architecture assembly

NCIG can now take the compact real architecture catalog and assemble deterministic floor/wall/ceiling/door/window placements around generated rooms. The output is deliberately an intermediate architecture assembly: it uses real harvested resource paths but does not invent runtime-sensitive World Builder node payload fields.

```powershell
python -m ncig.cli architecture-assemble --layouts build/generated/layouts.json --catalog build/architecture_catalog.json --out build/architecture_assembly.json
python -m ncig.cli architecture-apply --plan build/generated/wb_plans/demo_shop_001_world_plan_v2.json --assembly build/architecture_assembly.json --out build/generated/wb_plans/demo_shop_001_world_plan_v3_arch.json
```

Every selected placement is marked `requires_bounds_validation=true` because filename dimensions are hints, not authoritative mesh bounds. Automatic mesh scaling is disabled.


## v0.16.1 — native readiness launcher hardening

The architecture preparation helper uses the same verified Windows-Python selection as the harvest helper and rejects MSYS2/devkitPro/Cygwin/MinGW interpreters.

## v0.16 — native readiness and architecture audit

The architecture stage now writes both `rotation` (yaw quaternion) and a human-readable `rotation_deg`, so native bridging preserves building orientation.

Use the Windows helper:

```powershell
.\tools\prepare_architecture_cp2077.cmd
```

It builds `build\real_architecture\architecture_catalog.json` and `architecture_assembly.json` from the local harvest.

To identify missing real World Builder templates:

```powershell
python -m ncig.cli probe-plan --plan build/real_architecture/../generated/wb_plans/demo_shop_001_world_plan_v3_arch.json --templates build/user_harvest/templates.json --out build/real_architecture/probe_plan.json
```

`architecture-audit` reports catalog coverage and keeps native mesh export explicitly blocked until a real `worldMeshNode` template is available.

## v0.17 — GitHub harvest cache

A large machine-local harvest can be kept in a public GitHub repository and synchronized directly from the target PC:

```powershell
.\tools\sync_harvest_github.cmd https://github.com/Guarrazo/harvest
```

For an end-to-end architecture preparation flow:

```powershell
.\tools\prepare_architecture_remote.cmd https://github.com/Guarrazo/harvest
```

See `docs/V0.17_REMOTE_HARVEST.md` for the cache and manifest format.


## v0.18 — native mesh probe tooling

When you have a single real World Builder/Object Spawner export containing a mesh, NCIG can inspect it directly and extract the real `worldMeshNode` template:

```powershell
python -m ncig.cli native-probe --input build\mesh_probe.json --out build\mesh_probe_report.json --templates-out build\mesh_probe_templates.json
```

The generated `mesh_probe_templates.json` is compatible with the existing `schema-bridge` and native readiness pipeline. The architecture audit now also accepts `--templates` and reports the actual number of harvested `worldMeshNode` templates.

The native mesh gate opens only when a real `worldMeshNode` template is present and the architecture assembly has zero unresolved placements. Mesh bounds remain a separate validation step.

## v0.19 — native architecture mesh export

Once a real `worldMeshNode` has been harvested, NCIG can clone that native node shape into the architecture assembly:

```powershell
.\tools\architecture_native_export_cp2077.cmd `
  build\generated\layouts.json `
  build\real_architecture_remote\architecture_assembly.json `
  build\mesh_probe_templates.json `
  C:\Users\Guarrazo\Desktop\mesh_probe.json `
  build\real_architecture_remote\ncig_architecture_demo.json `
  build\real_architecture_remote\ncig_architecture_demo.report.json `
  demo_shop_001
```

See `docs/V0.19_NATIVE_ARCHITECTURE.md`.

For the complete remote workflow, including merging your real mesh probe and validating the generated native JSON:

```powershell
.\tools\prepare_native_architecture_remote.cmd `
  https://github.com/Guarrazo/harvest `
  C:\Users\Guarrazo\Desktop\mesh_probe.json `
  C:\Users\Guarrazo\Desktop\mesh_probe.json `
  demo_shop_001
```

This produces a native Object Spawner JSON plus an integrity audit.

## v0.20 — target detection, coherent kits and runtime bounds

NCIG now has a conservative building-target detection path for exported base-game `.streamingsector` JSONs:

```powershell
python -m ncig.cli detect-buildings --input C:\CyberpunkExports\sectors --out build\auto_building_candidates.json
python -m ncig.cli candidates-to-buildings --input build\auto_building_candidates.json --out build\auto_buildings.json --min-score 75 --max-count 10
```

Architecture assembly now selects a dominant structural family per building instead of mixing unrelated families piece-by-piece. The detector and assembler remain deliberately conservative because identifying a missing interior requires evidence from the actual world data.

For physical mesh fitting, v0.20 also includes a CET runtime bounding-box harvester. Install it with:

```powershell
.\tools\install_bounds_harvester.cmd
```

and merge the resulting runtime measurements with:

```powershell
.\tools\merge_bounds_cp2077.cmd
```

See `docs/V0.20_DETECTION_KITS_BOUNDS.md`.