# Integration contract

This project intentionally has a strict separation between **planning** and **game asset authoring**.

## Why

World Builder is excellent at placing native world nodes, but the exact resource paths and node properties depend on the assets selected and on the build of the user's tools. Hard-coding fictional resource paths would make the generator look complete while producing a broken mod.

## Stable intermediate representation

`ncig-wb-plan-v1` contains:

- building metadata
- sector extents
- room rectangles
- world transforms
- semantic prop names
- gameplay interactions
- loot sockets

A future adapter can translate this representation into actual World Builder groups.

## Runtime side

The eventual runtime mod should be kept separate from the generator:

```text
NCIG Generator        -> authoring-time assets
NCIG Runtime          -> routing / optional dynamic entities
ArchiveXL             -> custom streaming additions
World Builder         -> native world editing
NIF                   -> supported interactions
```

That keeps the runtime dependency surface small.
