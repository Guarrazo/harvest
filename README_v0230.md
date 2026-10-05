# NCIG v0.23.0 — candidate/buildability + topology refinement

This overlay adds three deterministic pre/post-processing stages without changing the public `ncig.cli` interface:

- `ncig.refine_pipeline candidates`: strengthens the distinction between fillable facade shells, existing interiors and false positives; also suppresses overlapping doorway detections for the same physical shell.
- `ncig.refine_pipeline layouts`: replaces the uniform room grid with several deterministic bilateral/topology variants while keeping the complete exterior footprint closed.
- `ncig.refine_pipeline catalog`: removes obviously unsuitable base structural meshes such as triangles, corners, wall/ceiling frames, stairs, beams and pillars from floor/ceiling/wall selection.

The supplied `prepare_detected_buildings_remote.cmd` inserts these stages into the existing city pipeline and continues to use the same output filenames downstream. It also preserves `layouts_pre_v0230.json` before replacement.

`tools/apply_v0230_native_collision_fix.ps1` fixes a latent keyword mismatch in `native_collision.py` for lateral exterior-entry headers. It is independent of the main pipeline and safe to run once.

The changes are intentionally limited to deterministic procedural selection/geometry policy. The native `worldMeshNode` template requirement and final in-game fit/collision validation remain unchanged.
