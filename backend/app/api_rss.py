"""Live RSS crisis-signal API — Middle East-wide feed served from memory.

A thin ``APIRouter`` over :mod:`news_rss` (the in-memory aggregator). ``main.py``
includes it with ``app.include_router(api_rss.router)`` and starts the background
fetcher in its lifespan. Every endpoint degrades gracefully if the aggregator
module is unavailable, so the router imports cleanly on a bare machine.

Endpoints
---------
  GET /api/rss/signals   filtered crisis-signal feed (country/category/severity)
  GET /api/rss/sources   per-feed fetch status
  GET /api/rss/stats     aggregate counts by country/category/severity
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Query

try:
    from . import news_rss
except Exception:  # pragma: no cover - stay import-safe
    news_rss = None  # type: ignore

router = APIRouter()


@router.get("/api/rss/signals")
def rss_signals(
    country: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> Dict[str, Any]:
    """Recent geolocated crisis signals, newest first, with optional filters."""
    if news_rss is None:
        return {"signals": [], "last_fetch": None, "source_count": 0, "total_count": 0,
                "error": "rss module unavailable"}
    try:
        return news_rss.get_signals(country=country, category=category,
                                    severity=severity, limit=limit)
    except Exception as e:
        return {"signals": [], "last_fetch": None, "source_count": 0, "total_count": 0,
                "error": str(e)}


@router.get("/api/rss/sources")
def rss_sources() -> Dict[str, Any]:
    """Per-feed status: ok / error / pending, last fetch time, item count."""
    if news_rss is None:
        return {"sources": [], "error": "rss module unavailable"}
    try:
        return news_rss.get_sources()
    except Exception as e:
        return {"sources": [], "error": str(e)}


@router.get("/api/rss/stats")
def rss_stats() -> Dict[str, Any]:
    """Aggregate signal counts grouped by country, category and severity."""
    if news_rss is None:
        return {"total_signals": 0, "by_country": {}, "by_category": {}, "by_severity": {},
                "error": "rss module unavailable"}
    try:
        return news_rss.get_stats()
    except Exception as e:
        return {"total_signals": 0, "by_country": {}, "by_category": {}, "by_severity": {},
                "error": str(e)}
