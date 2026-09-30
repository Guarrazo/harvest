# Technical sources used for NCIG v0.2

These are the current public references checked while designing the v0.2 pipeline:

- CDPR Modding Documentation — World Editing: world nodes are grouped into streaming sectors; ArchiveXL supports non-destructive sector additions; RedHotTools can inspect runtime nodes; World Builder is the main native world-editing tool.
- Redmodding Wiki — Exporting from Object Spawner: World Builder saves root groups as sectors and exports an Object Spawner JSON which WolvenKit imports to create native `.streamingsector` and `.streamingblock` files.
- Redmodding Wiki — Object Spawner project structure: separate root groups can keep distant parts in separate streaming sectors.
- CDPR Modding Documentation — Supported World Builder Nodes: static mesh, entity, collision, light, AI spot, community, interior/ambient areas and static marker nodes are available.
- ArchiveXL repository: current compatibility information includes Cyberpunk 2077 2.31.
- Codeware repository: current compatibility information includes Cyberpunk 2077 2.31 and exposes a DynamicEntitySystem for runtime-managed entities.

NCIG does not copy proprietary game assets. It expects paths from the user's own WolvenKit-extracted depot.
