from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CACHE_PATH = Path(__file__).resolve().parents[3] / "data" / "cache" / "etf_live_series.json"
_DEFAULT_MAX_AGE_SECONDS = 300


def _cache_metadata(
    *,
    hit: bool,
    stored_at_ts: float = 0.0,
    max_age_seconds: int = _DEFAULT_MAX_AGE_SECONDS,
    meta: dict[str, Any] | None = None,
    path: Path = _CACHE_PATH,
) -> dict[str, Any]:
    age = max(time.time() - stored_at_ts, 0.0) if stored_at_ts else None
    stale = True if age is None else age > max_age_seconds
    source = "tushare_cache" if hit else "tushare_cache_miss"
    base = dict(meta or {})
    return {
        **base,
        "data_source": base.get("data_source") or source,
        "data_mode": base.get("data_mode") or ("cache" if hit else "unavailable"),
        "as_of": base.get("as_of"),
        "cache_hit": hit,
        "cache_hit_rate": 1.0 if hit else 0.0,
        "cache_stale": stale,
        "cache_age_seconds": round(age, 3) if age is not None else None,
        "cache_path": str(path),
    }


def describe_cache(
    *,
    max_age_seconds: int = _DEFAULT_MAX_AGE_SECONDS,
    path: Path = _CACHE_PATH,
) -> dict[str, Any]:
    """Return cache metadata without loading series into feature code."""
    try:
        if not path.exists():
            return _cache_metadata(hit=False, max_age_seconds=max_age_seconds, path=path)
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("failed to describe ETF live cache: %s", exc)
        return {
            **_cache_metadata(hit=False, max_age_seconds=max_age_seconds, path=path),
            "fallback_reason": "cache_read_error",
        }

    meta = payload.get("meta") or {}
    stored_at_ts = float(payload.get("stored_at_ts") or 0.0)
    return _cache_metadata(
        hit=True,
        stored_at_ts=stored_at_ts,
        max_age_seconds=max_age_seconds,
        meta=meta if isinstance(meta, dict) else {},
        path=path,
    )


def load_cached_bundle(
    max_age_seconds: int = _DEFAULT_MAX_AGE_SECONDS,
    *,
    path: Path = _CACHE_PATH,
) -> tuple[list[dict[str, Any]], dict[str, Any], bool] | None:
    """Load cached ETF live series bundle from disk.

    Returns a tuple of (series, meta, is_fresh) when cache is available, otherwise ``None``.
    ``is_fresh`` indicates whether the cache age is within ``max_age_seconds``.
    """
    try:
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - best effort cache read
        logger.warning("failed to load ETF live cache: %s", exc)
        return None

    series = payload.get("series") or []
    meta = payload.get("meta") or {}
    stored_at_ts = float(payload.get("stored_at_ts") or 0.0)

    if not isinstance(series, list):
        logger.warning("ETF live cache corrupted: series is not list")
        return None
    if not isinstance(meta, dict):
        logger.warning("ETF live cache corrupted: meta is not dict")
        return None

    age = time.time() - stored_at_ts if stored_at_ts else float("inf")
    is_fresh = age <= max_age_seconds
    meta = _cache_metadata(
        hit=True,
        stored_at_ts=stored_at_ts,
        max_age_seconds=max_age_seconds,
        meta=meta,
        path=path,
    )
    return series, meta, is_fresh


def save_cached_bundle(
    series: list[dict[str, Any]],
    meta: dict[str, Any],
    *,
    path: Path = _CACHE_PATH,
) -> None:
    """Persist ETF live series bundle to disk for reuse."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "stored_at_ts": time.time(),
            "stored_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "series": series,
            "meta": meta,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:  # pragma: no cover - cache write failure should not break flow
        logger.warning("failed to persist ETF live cache: %s", exc)
