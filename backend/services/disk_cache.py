"""
Nivesh Disk Cache
-----------------
Persistent filesystem-backed cache for market data responses.
Uses ~/Library/Caches/nivesh/ on macOS, /var/cache/nivesh/ on Linux.
Survives service restarts. Complements (does not replace) the in-memory TTL dict.

Cache hierarchy:
  yfinance/        — yfinance ticker responses (6-hour TTL)
  bhavcopy/        — NSE Bhavcopy daily files (24-hour TTL)
  options/         — NSE option chain snapshots (15-minute TTL)
  news_processed/  — Processed FinBERT results (12-hour TTL)
"""
import gzip
import json
import hashlib
import logging
import os
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _default_cache_root() -> Path:
    if os.path.exists("/var/cache"):
        return Path("/var/cache/nivesh")
    return Path.home() / "Library" / "Caches" / "nivesh"


CACHE_ROOT = Path(os.environ.get("NIVESH_CACHE_DIR", str(_default_cache_root())))

TTL_SECONDS = {
    "yfinance":        6 * 3600,
    "bhavcopy":        24 * 3600,
    "options":         15 * 60,
    "news_processed":  12 * 3600,
}


def _cache_path(namespace: str, key: str) -> Path:
    safe_key = hashlib.sha256(key.encode()).hexdigest()[:16]
    readable = key.replace("/", "_").replace(".", "_")[:24]
    filename = f"{readable}_{safe_key}.json.gz"
    return CACHE_ROOT / namespace / filename


def get(namespace: str, key: str) -> Optional[Any]:
    """Retrieve a cached value. Returns None on miss, expiry, or read error."""
    path = _cache_path(namespace, key)
    ttl = TTL_SECONDS.get(namespace, 3600)
    try:
        if not path.exists():
            return None
        age = time.time() - path.stat().st_mtime
        if age > ttl:
            path.unlink(missing_ok=True)
            return None
        with gzip.open(path, "rt", encoding="utf-8") as f:
            data = json.load(f)
        logger.debug(f"[disk_cache] HIT {namespace}/{key[:30]} (age={age:.0f}s)")
        return data
    except Exception as e:
        logger.warning(f"[disk_cache] READ ERROR {namespace}/{key[:30]}: {e}")
        return None


def set(namespace: str, key: str, value: Any) -> bool:
    """Write a value to the disk cache. Returns True on success. Never raises."""
    path = _cache_path(namespace, key)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(path, "wt", encoding="utf-8") as f:
            json.dump(value, f, default=str)
        logger.debug(f"[disk_cache] WRITE {namespace}/{key[:30]}")
        return True
    except Exception as e:
        logger.warning(f"[disk_cache] WRITE ERROR {namespace}/{key[:30]}: {e}")
        return False


def invalidate(namespace: str, key: str) -> None:
    """Explicitly remove a cache entry."""
    path = _cache_path(namespace, key)
    path.unlink(missing_ok=True)


def stats() -> dict:
    """Return cache utilization stats for the /health endpoint."""
    result = {}
    for namespace in TTL_SECONDS:
        ns_path = CACHE_ROOT / namespace
        if ns_path.exists():
            files = list(ns_path.glob("*.json.gz"))
            total_bytes = sum(f.stat().st_size for f in files)
            result[namespace] = {"count": len(files), "size_mb": round(total_bytes / 1e6, 2)}
        else:
            result[namespace] = {"count": 0, "size_mb": 0}
    import shutil
    try:
        disk = shutil.disk_usage(str(CACHE_ROOT.parent))
        result["_disk"] = {
            "used_gb": round(disk.used / 1e9, 2),
            "free_gb": round(disk.free / 1e9, 2),
            "total_gb": round(disk.total / 1e9, 2),
        }
    except Exception:
        result["_disk"] = {}
    return result
