"""
Lightweight disk + memory caching so repeated renders (previews, re-exports
with only a text tweak) are fast.

We hash the *inputs* that determine a rendered artifact (a scene's config +
content) and reuse the cached PNG/MP4 clip if nothing changed.
"""
from __future__ import annotations

import hashlib
import json
import pickle
from pathlib import Path
from typing import Any, Callable, Optional

from cachetools import LRUCache

from config import settings

_memory_cache: LRUCache = LRUCache(maxsize=256)


def make_key(*parts: Any) -> str:
    """Deterministic hash key from arbitrary JSON-serializable parts."""
    blob = json.dumps(parts, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:24]


def cache_dir() -> Path:
    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    return settings.cache_dir


def get_or_compute(key: str, compute_fn: Callable[[], Any], persist: bool = False,
                    ext: str = "pkl") -> Any:
    """Return cached value for `key`, computing + storing it if missing.

    persist=True also writes to disk (survives process restarts), useful for
    expensive PIL frame renders; persist=False keeps it memory-only (fast,
    good for objects that can't be pickled cleanly, e.g. MoviePy clips).
    """
    if key in _memory_cache:
        return _memory_cache[key]

    if persist:
        disk_path = cache_dir() / f"{key}.{ext}"
        if disk_path.exists():
            with open(disk_path, "rb") as f:
                value = pickle.load(f)
            _memory_cache[key] = value
            return value

    value = compute_fn()
    _memory_cache[key] = value

    if persist:
        try:
            disk_path = cache_dir() / f"{key}.{ext}"
            with open(disk_path, "wb") as f:
                pickle.dump(value, f)
        except Exception:
            pass  # non-fatal: memory cache still holds it

    return value


def clear_cache() -> int:
    """Wipe both memory and disk caches. Returns number of disk files removed."""
    _memory_cache.clear()
    removed = 0
    for f in cache_dir().glob("*"):
        try:
            f.unlink()
            removed += 1
        except Exception:
            pass
    return removed
