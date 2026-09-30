from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RoomRule:
    kind: str
    min_w: float
    max_w: float
    min_d: float
    max_d: float
    weight: int


TEMPLATES: dict[str, list[RoomRule]] = {
    "residential": [
        RoomRule("living", 3.0, 5.5, 3.0, 5.0, 8),
        RoomRule("bedroom", 2.8, 4.2, 2.8, 4.2, 8),
        RoomRule("kitchen", 2.0, 3.6, 2.0, 3.5, 6),
        RoomRule("bathroom", 1.6, 2.5, 1.8, 3.0, 4),
        RoomRule("utility", 1.4, 2.5, 1.4, 2.5, 2),
    ],
    "commercial": [
        RoomRule("shopfloor", 4.0, 7.5, 3.5, 7.0, 10),
        RoomRule("stockroom", 2.5, 5.0, 2.5, 5.0, 7),
        RoomRule("office", 2.2, 4.0, 2.2, 4.0, 4),
        RoomRule("bathroom", 1.6, 2.4, 1.8, 3.0, 3),
    ],
    "office": [
        RoomRule("open_office", 5.0, 9.0, 4.0, 8.0, 10),
        RoomRule("meeting", 3.0, 5.5, 2.8, 5.0, 5),
        RoomRule("private_office", 2.8, 4.0, 2.8, 4.2, 5),
        RoomRule("server", 2.0, 3.5, 2.0, 3.5, 2),
        RoomRule("bathroom", 1.6, 2.4, 1.8, 3.0, 3),
    ],
    "industrial": [
        RoomRule("workshop", 5.0, 10.0, 4.0, 10.0, 10),
        RoomRule("storage", 4.0, 8.0, 3.5, 8.0, 9),
        RoomRule("office", 2.5, 4.0, 2.5, 4.0, 3),
        RoomRule("utility", 2.0, 4.0, 2.0, 4.0, 4),
        RoomRule("bathroom", 1.6, 2.4, 1.8, 3.0, 2),
    ],
}

ALIASES = {
    "mixed": "commercial",
}


FURNITURE_BY_ROOM = {
    "living": ["sofa", "tv", "table", "light"],
    "bedroom": ["bed", "wardrobe", "nightstand", "light"],
    "kitchen": ["counter", "fridge", "sink", "light"],
    "bathroom": ["toilet", "sink", "mirror", "light"],
    "utility": ["washer", "shelf", "light"],
    "shopfloor": ["counter", "display", "shelf", "light"],
    "stockroom": ["shelf", "crate", "light"],
    "office": ["desk", "chair", "computer", "light"],
    "open_office": ["desk", "chair", "computer", "light"],
    "meeting": ["meeting_table", "chair", "screen", "light"],
    "private_office": ["desk", "chair", "computer", "light"],
    "server": ["server_rack", "terminal", "light"],
    "workshop": ["workbench", "tool_rack", "crate", "light"],
    "storage": ["shelf", "crate", "light"],
}


INTERACTION_BY_ROOM = {
    "living": ["sit", "watch_tv", "loot_drawer"],
    "bedroom": ["sleep", "open_wardrobe", "loot_nightstand"],
    "kitchen": ["use_sink", "open_fridge", "loot_cupboard"],
    "bathroom": ["use_sink", "open_cabinet"],
    "utility": ["use_washer", "loot_shelf"],
    "shopfloor": ["browse_counter", "talk_to_vendor", "loot_display"],
    "stockroom": ["loot_crate", "loot_shelf"],
    "office": ["use_computer", "loot_desk"],
    "open_office": ["use_computer", "read_terminal", "loot_desk"],
    "meeting": ["use_screen", "loot_table"],
    "private_office": ["use_computer", "loot_desk"],
    "server": ["use_terminal", "loot_rack"],
    "workshop": ["use_workbench", "loot_tool_rack", "loot_crate"],
    "storage": ["loot_shelf", "loot_crate"],
}
