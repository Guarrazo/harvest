from __future__ import annotations

from pathlib import Path
from html import escape


def build_viewer(preview_dir: str | Path, out: str | Path) -> Path:
    preview_dir = Path(preview_dir)
    files = sorted(preview_dir.glob("*.svg"))
    rows = []
    for f in files:
        rows.append(f"<article><h3>{escape(f.name)}</h3><img src='{escape(f.name)}' loading='lazy'></article>")
    html = "<!doctype html><html><head><meta charset='utf-8'><title>NCIG Preview</title><style>body{font-family:Arial,sans-serif}article{display:inline-block;vertical-align:top;width:800px;margin:12px}img{width:100%;border:1px solid #aaa}</style></head><body><h1>Night City Interior Generator — previews</h1>" + "".join(rows) + "</body></html>"
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out
