NCIG v0.22.5 — walkable entries + geometry-aware building detection

This is a sync/repair bundle, NOT a complete repository archive.
The canonical source of truth is GitHub main: https://github.com/Guarrazo/harvest

What v0.22.5 changes
====================
1. Collision orientation fixed.
   Positive-Y rooms use the north wall as the corridor-facing doorway.
   Negative-Y rooms use the south wall as the corridor-facing doorway.
   The previous collision code opened the exterior wall instead, matching the
   user's observation of an external wall with a centered collision-free gap.

2. Doorway reduced to 1.15 m x 2.10 m.
   Door leaves are emitted only when a harvested resource is explicitly marked
   collisionless. This keeps the structural doorway traversable instead of
   allowing a static door mesh to block the player.

3. Structural wall selection hardened.
   Decorative add-ons/protectors and obvious grate/grid/bar/cage/prison pieces
   are rejected when a suitable structural alternative exists.

4. Thin wall backfaces.
   Runtime-bounded wall meshes <= 8 cm thick get a second visual face rotated
   180 degrees with a 2 cm offset. This targets the one-sided/transparency
   effect observed from inside rooms without doing it for ordinary thick walls.

5. Detected exterior entrance integration.
   Building candidates retain entry position, side, orientation, scale and
   filename dimension hints. The generated floor-0 room now creates a facade
   doorway at the detected entrance and the collision shell opens at the same
   location.

6. Geometry-aware automatic detection.
   detect-buildings now estimates building footprint/orientation from exterior
   architecture node transforms and filename l/w/h hints. Existing interior
   evidence downgrades a target to review rather than treating it as empty.
   The automatic preparation helper prefers the bounded 1,579-resource catalog
   when it already exists.

Local installation
==================
From the NCIG folder:

  cd C:\Users\Guarrazo\Desktop\NCIG
  powershell -ExecutionPolicy Bypass -File .\sync_v0225_main_canonical.ps1

Then regenerate the synthetic test building:

  $py = Get-Command py.exe | Select-Object -First 1 -ExpandProperty Source
  & $py -3 -m ncig.cli generate --input examples\buildings.json --out build\generated
  .\tools\architecture_assemble_bounded_cp2077.cmd
  .\tools\architecture_test_compose_bounded_cp2077.cmd
  .\tools\architecture_geometry_diagnostic_cp2077.cmd

The existing runtime bounds do NOT need to be harvested again. Because the
architecture family derivation changed in v0.22.4, rebuild/merge the catalog
from the existing harvest before the bounded assembly when your local helper
requires it:

  & $py -3 -m ncig.cli architecture-catalog --harvest build\remote_harvest\harvest.json --out build\real_architecture_remote\architecture_catalog.json --interior-only
  .\tools\merge_bounds_cp2077.cmd

Automatic building detection:

  .\tools\prepare_detected_buildings_remote.cmd https://github.com/Guarrazo/harvest C:\CyberpunkExports\sectors 10

This produces:
  build\auto_building_candidates.json
  build\auto_buildings.json
  build\generated_auto\layouts.json
  build\real_architecture_remote\architecture_assembly_auto.json

Expected immediate in-game difference
======================================
- Walking through the corridor doorway should no longer hit the old inverted
  collision box.
- The exterior wall should be solid except where a real detected entrance is
  intentionally opened.
- The generated doorway should be slightly smaller than v0.22.4 and should not
  contain a colliding static door leaf.
- Very thin structural walls should remain visually readable from the interior.
- A detected real building should receive its generated entrance on the facade,
  not only at a synthetic centered corridor location.

Scope / limitation
==================
The automatic detector is still conservative: exported streamingsector JSON is
needed as evidence. The next major iteration is to make the detected exterior
shell the authoritative footprint and validate every generated doorway against
actual world geometry before native composition.

Canonical commits in main (v0.22.5 work)
=========================================
cda6b3fe58ef8db924286b5eb58ef657c07e0af9
0b5c9c15b53aa087a2031e349e1e3a977c58179b2
738eae5952cde8ce6e5a794d48d5064aadcb7463
22fe5ec803eee8469d7c4fd5e024f7d777512476
5377de11a26b706cd955ddbd1371794eea6fde0c
bbdac2c296bf23f286167f876149d672027e378a
aff3b8c6b8f11a134e9bde5e08a9aa9d27f2716e
bf6770bb45d3b0ce8450af45fbb2232109ca99e5
ca9a7c61075f21e3fdd7c395b1a91bd0b024ffbf
30aa12bf8ce71c257dad634acc764d0733092151
7c4293513c2970acdc5744c24bca24ece61ee4a3
2868ea5bac734651a6fcd58a0c2d8c2f3c6ce08c
64ca5c31c8edd39bad9f79ccb2870fd4453a985c
87a94339ba0764f5e50eb4fbd1c31321b7f468f4
4e18f2589082205f1900114a6c31848f37a90338
6889d111c34817add755d4081ecca22d805d4add
5d18b4297b5533b2c54b32e0250a72efc375a7ff
3d1e08d8b901373c8f1243b2f78ed36e26ddf61e
62272a3cdebaa93cdea6a00a41770f40daff402b
8a0995976bb598ae3513c75168e6ed53233fa979
bbdac2c296bf23f286167f876149d672027e378a
