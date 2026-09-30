# NCIG architecture

```text
             +---------------------------+
             |   Anchor acquisition      |
             |  RHT / curated dataset    |
             +-------------+-------------+
                           |
                           v
                    BuildingAnchor
                           |
                           v
             +---------------------------+
             | Procedural planner        |
             | templates + seeded RNG    |
             +-------------+-------------+
                           |
          +----------------+----------------+
          |                |                |
          v                v                v
        rooms           sectors          sockets
          |                |                |
          +----------------+----------------+
                           |
                           v
                    ncig-wb-plan-v1
                           |
                           v
              +---------------------------+
              | World Builder adapter     |
              | actual native world nodes |
              +-------------+-------------+
                            |
                            v
                       WolvenKit
                            |
                            v
              streamingsector/block files
                            |
                            v
                        ArchiveXL
```

## v0.2 data layers

```text
RHT observation
   |
   +--> entry candidate ----> BuildingAnchor
   |                              |
   |                              +--> room plan
   |                              +--> shell plan
   |                              +--> gameplay sockets
   |                              +--> sector plan
   |
   +--> existing-interior evidence / blacklist input
```

The scanner intentionally keeps uncertain measurements out of the generator core. A runtime observation can identify an entry very reliably while width, depth and floor count may still need a curated override.

## Runtime split

The authoring tool should generate static geometry and most world nodes. A small runtime mod should handle only what genuinely needs scripting: entry routing, state, optional dynamic population, and compatibility switches.

This prevents a city-scale mod from becoming a giant runtime object-spawner.

## Gameplay socket contract

Every generated room can expose:

- `door` — where the room connects to circulation.
- `activity` — primary player/NPC interaction candidate.
- `prop` — semantic asset socket.
- `loot` — optional item container socket.

The resource catalog resolves semantic names into real game resource paths.
