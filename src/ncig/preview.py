from __future__ import annotations

from pathlib import Path
from html import escape

from .model import Layout


def make_svg(layout: Layout, floor: int) -> str:
    rooms = [r for r in layout.rooms if r.floor == floor]
    if not rooms:
        return "<svg xmlns='http://www.w3.org/2000/svg' width='800' height='500'><text x='20' y='30'>No rooms</text></svg>"

    min_x = min(r.x for r in rooms) - 0.8
    min_y = min(r.y for r in rooms) - 0.8
    max_x = max(r.x + r.width for r in rooms) + 0.8
    max_y = max(r.y + r.depth for r in rooms) + 0.8
    scale = min(760 / (max_x - min_x), 420 / (max_y - min_y))

    def sx(v: float) -> float: return 20 + (v - min_x) * scale
    def sy(v: float) -> float: return 60 + (v - min_y) * scale

    parts = [
        "<svg xmlns='http://www.w3.org/2000/svg' width='800' height='520' viewBox='0 0 800 520'>",
        f"<text x='20' y='25' font-family='Arial' font-size='18'>{escape(layout.building.id)} — floor {floor+1}</text>",
        f"<text x='20' y='45' font-family='Arial' font-size='11'>template={escape(layout.building.type)} size={layout.building.width_m:.1f}m×{layout.building.depth_m:.1f}m</text>",
    ]
    for r in rooms:
        x, y = sx(r.x), sy(r.y)
        w, h = r.width * scale, r.depth * scale
        parts.append(f"<rect x='{x:.1f}' y='{y:.1f}' width='{w:.1f}' height='{h:.1f}' fill='none' stroke='black' stroke-width='1'/>")
        parts.append(f"<text x='{x+4:.1f}' y='{y+16:.1f}' font-family='Arial' font-size='10'>{escape(r.kind)}</text>")
    parts.append("</svg>")
    return "".join(parts)


def write_previews(layout: Layout, out_dir: str | Path) -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for floor in range(max(1, layout.building.floors)):
        path = out / f"{layout.building.id}_F{floor+1:02d}.svg"
        path.write_text(make_svg(layout, floor), encoding="utf-8")
        paths.append(path)
    return paths
