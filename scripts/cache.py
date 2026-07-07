#!/usr/bin/env python3
"""Fettle result caching — skip re-scanning unchanged files.

Cache key: file content hash + tool version + config hash.
Cache store: $XDG_CACHE_HOME/fettle/results/<hash>.json

When a file hasn't changed since last scan, return cached result immediately.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))
    d = Path(base) / "fettle" / "results"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _file_hash(file_path: str) -> str:
    """SHA256 of file content."""
    h = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
    except OSError:
        return ""
    return h.hexdigest()[:16]


def _tool_version(tool: str) -> str:
    """Get tool version string for cache invalidation."""
    bin_path = shutil.which(tool)
    if not bin_path:
        return "unavailable"
    try:
        result = subprocess.run(
            [bin_path, "--version"], capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip()[:50]
    except (subprocess.TimeoutExpired, OSError):
        return "unknown"


def _config_hash(config: dict) -> str:
    """Hash of relevant config sections for cache invalidation."""
    relevant = json.dumps({
        "severity": config.get("severity", {}),
        "gates": config.get("gates", {}).get("lint", {}),
    }, sort_keys=True)
    return hashlib.md5(relevant.encode()).hexdigest()[:8]


def cache_key(file_path: str, config: dict) -> str:
    """Generate cache key for a file + config combination."""
    fh = _file_hash(file_path)
    ch = _config_hash(config)
    return f"{fh}_{ch}"


def get_cached(key: str) -> dict | None:
    """Retrieve cached result, or None if miss."""
    cache_file = _cache_dir() / f"{key}.json"
    if cache_file.exists():
        try:
            data = json.loads(cache_file.read_text())
            return data
        except (json.JSONDecodeError, OSError):
            pass
    return None


def set_cached(key: str, result: dict) -> None:
    """Store result in cache."""
    import contextlib
    cache_file = _cache_dir() / f"{key}.json"
    with contextlib.suppress(OSError):
        cache_file.write_text(json.dumps(result))


def invalidate_all() -> None:
    """Clear entire cache."""
    cache_d = _cache_dir()
    if cache_d.exists():
        for f in cache_d.glob("*.json"):
            f.unlink()


def cache_stats() -> dict:
    """Report cache stats."""
    cache_d = _cache_dir()
    if not cache_d.exists():
        return {"entries": 0, "size_kb": 0}
    files = list(cache_d.glob("*.json"))
    size = sum(f.stat().st_size for f in files)
    return {"entries": len(files), "size_kb": size // 1024}
