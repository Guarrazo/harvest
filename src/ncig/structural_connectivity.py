from __future__ import annotations

import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

VERSION = "0.28.0"


def _entry_room(layout: dict[str, Any]) -> str | None:
    for socket in layout.get("sockets", []) or []:
        if isinstance(socket, dict) and socket.get("kind") == "entry" and socket.get("room_id"):
            return str(socket["room_id"])
    return None


def build_connectivity(layout: dict[str, Any]) -> dict[str, Any]:
    building = layout.get("building") or {}
    bid = str(building.get("id", "building"))
    rooms = [r for r in layout.get("rooms", []) or [] if isinstance(r, dict)]
    cores = [r for r in rooms if r.get("kind") == "stairwell"]
    graph: dict[str, set[str]] = defaultdict(set)
    corridor_by_floor: dict[int, str] = {}
    for r in rooms:
        floor = int(r.get("floor", 0))
        corridor_by_floor.setdefault(floor, f"{bid}_F{floor+1}_corridor")
        rid = str(r.get("id"))
        graph[rid].add(corridor_by_floor[floor])
        graph[corridor_by_floor[floor]].add(rid)
    for socket in layout.get("sockets", []) or []:
        if not isinstance(socket, dict) or socket.get("kind") != "vertical_link":
            continue
        rid = str(socket.get("room_id", ""))
        props = socket.get("properties") or {}
        to_floor = props.get("to_floor")
        try:
            to_floor_i = int(to_floor)
        except (TypeError, ValueError):
            continue
        target_core = next((r for r in cores if int(r.get("floor", -1)) == to_floor_i), None)
        if target_core is None:
            continue
        target_id = str(target_core.get("id"))
        graph[rid].add(target_id)
        graph[target_id].add(rid)
    start = _entry_room(layout)
    visited: set[str] = set()
    if start:
        q = deque([start])
        while q:
            cur = q.popleft()
            if cur in visited:
                continue
            visited.add(cur)
            for nxt in graph.get(cur, ()):
                if nxt not in visited:
                    q.append(nxt)
    room_ids = {str(r.get("id")) for r in rooms}
    reachable_rooms = sorted(room_ids & visited)
    unreachable_rooms = sorted(room_ids - visited)
    floor_reachability: dict[str, bool] = {}
    for floor in sorted({int(r.get("floor", 0)) for r in rooms}):
        floor_ids = {str(r.get("id")) for r in rooms if int(r.get("floor", 0)) == floor}
        floor_reachability[str(floor)] = floor_ids.issubset(visited)
    vertical_links = [s for s in layout.get("sockets", []) or [] if isinstance(s, dict) and s.get("kind") == "vertical_link"]
    expected_links = max(0, len(cores) - 1) * 2
    return {
        "format": "ncig-structural-connectivity-v1",
        "version": VERSION,
        "building_id": bid,
        "entry_room": start,
        "room_count": len(rooms),
        "stairwell_count": len(cores),
        "vertical_link_count": len(vertical_links),
        "expected_bidirectional_vertical_links": expected_links,
        "reachable_room_count": len(reachable_rooms),
        "unreachable_rooms": unreachable_rooms,
        "all_rooms_reachable": bool(start) and not unreachable_rooms,
        "floor_reachability": floor_reachability,
        "connected_floors": [int(f) for f, ok in floor_reachability.items() if ok],
        "graph_node_count": len(graph),
        "graph_edge_count": sum(len(v) for v in graph.values()) // 2,
        "assumptions": [
            "Every ordinary room has a corridor-facing doorway socket.",
            "Vertical stairwell sockets connect adjacent stairwell rooms.",
            "This validates logical routing, not physical collision/walkability; that still requires native/runtime validation.",
        ],
    }


def audit_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    rows = [build_connectivity(x) for x in bundle.get("layouts", []) or [] if isinstance(x, dict)]
    return {
        "format": "ncig-structural-connectivity-bundle-v1",
        "version": VERSION,
        "layout_count": len(rows),
        "fully_connected_buildings": sum(1 for x in rows if x["all_rooms_reachable"]),
        "audits": rows,
    }


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="NCIG structural connectivity audit")
    p.add_argument("--input", required=True); p.add_argument("--out", required=True)
    args = p.parse_args()
    bundle = json.loads(Path(args.input).read_text(encoding="utf-8"))
    out = audit_bundle(bundle)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"layout_count": out["layout_count"], "fully_connected_buildings": out["fully_connected_buildings"]}, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
