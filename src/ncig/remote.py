from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

GITHUB_RE = re.compile(r"^https?://github\.com/([^/]+)/([^/#?]+?)(?:\.git)?/?$")
RAW_RE = re.compile(r"^https?://raw\.githubusercontent\.com/([^/]+)/([^/]+)/([^/]+)/(.+)$")
DEFAULT_FILES = ("harvest.json", "templates.json")
OPTIONAL_FILES = ("architecture_catalog.json", "architecture_assembly.json")


def parse_github_source(source: str) -> tuple[str, str]:
    source = source.strip()
    m = GITHUB_RE.match(source)
    if not m:
        raise ValueError(f"Unsupported harvest source: {source!r}. Use a public GitHub repo URL such as https://github.com/owner/repo")
    return m.group(1), m.group(2)


def github_raw_url(owner: str, repo: str, filename: str, ref: str = "main") -> str:
    return f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{filename}"


def _download(url: str, destination: Path, *, max_bytes: int = 80_000_000, timeout: int = 30) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "NCIG/0.17 harvest-sync"})
    total = 0
    digest = hashlib.sha256()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        with destination.open("wb") as fh:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError(f"Remote file exceeds NCIG safety limit ({max_bytes} bytes): {url}")
                digest.update(chunk)
                fh.write(chunk)
    return {"url": url, "bytes": total, "sha256": digest.hexdigest()}


def _atomic_download(url: str, destination: Path, **kwargs: Any) -> dict[str, Any]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=destination.name + ".", suffix=".part", dir=str(destination.parent))
    os.close(fd)
    temp = Path(temp_name)
    try:
        meta = _download(url, temp, **kwargs)
        temp.replace(destination)
        return meta
    finally:
        temp.unlink(missing_ok=True)


def sync_github_harvest(source: str, out_dir: str | Path, *, ref: str = "main", include_optional: bool = True) -> dict[str, Any]:
    owner, repo = parse_github_source(source)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    files = list(DEFAULT_FILES) + (list(OPTIONAL_FILES) if include_optional else [])
    downloaded: list[dict[str, Any]] = []
    missing: list[str] = []
    for filename in files:
        url = github_raw_url(owner, repo, filename, ref=ref)
        destination = out / filename
        try:
            meta = _atomic_download(url, destination)
            meta.update({"file": filename, "status": "downloaded"})
            downloaded.append(meta)
        except urllib.error.HTTPError as exc:
            if exc.code == 404 and filename in OPTIONAL_FILES:
                missing.append(filename)
                continue
            raise RuntimeError(f"Failed to download {url}: HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Failed to download {url}: {exc.reason}") from exc
    manifest = {
        "format": "ncig-remote-harvest-manifest-v1",
        "source": source,
        "owner": owner,
        "repo": repo,
        "ref": ref,
        "files": downloaded,
        "missing_optional": missing,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest
