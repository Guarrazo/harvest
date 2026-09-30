# Anchor schema

An anchor is the minimum information the generator needs about a real-world entrance/building. Coordinates must come from the game/modding tools; NCIG never guesses them.

```json
{
  "id": "unique-stable-id",
  "district": "watson",
  "type": "residential",
  "position": {"x": -1200.0, "y": 860.0, "z": 15.0},
  "yaw_deg": 35.0,
  "width_m": 18.0,
  "depth_m": 15.0,
  "floors": 4,
  "entry_width_m": 1.0,
  "entry_height_m": 2.1,
  "tags": ["residential", "vertical"]
}
```

The production scanner will eventually populate these records from inspected game nodes. Until then, sample data is intentionally fictional and must not be pasted into the real game.
