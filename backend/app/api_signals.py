"""AEGIS Deer Graph — Signals API (the_data → paginated signal feed).

This module backs the console's **Signals** page (Track 2): a filterable,
paginated view over the voc360 SIGNAL / data-source layer, ``the_data``
(22,882 rows of app reviews, social sentiment, surveys, and Arabic complaint
types).  It is the raw evidence layer that sits *upstream* of the
Segment → Cluster → Service root-cause chain the rest of the backend builds.

Grounded in the REAL voc360 schema via the project's read-only data layer:

  * ``db`` — psycopg READ-ONLY session against voc360 (DSN from env ``VOC_DSN``).

Only columns that actually exist on ``the_data`` are selected/filtered:
``record_id, source_type, service_id, governorate, text_clean,
sentiment_label, severity, observed_at, rating``.

Public surface (consumed by ``main.py`` / the frontend ``lib/voc.ts`` client):

    signals(page, size, service, severity, source, sentiment, q)
        -> {rows, total, page, size, pages, filters}

All parameters bind through psycopg's named-parameter substitution
(``%(name)s``) — never string-formatted into SQL — so the endpoint is safe to
expose to arbitrary client filters.  Arabic ``text_clean`` / Arabic service and
source types flow through untouched (serialize with ``ensure_ascii=False``).

Import-safe: if the data layer can't be imported or the DB is unreachable, the
module still imports and ``signals(...)`` returns an empty, well-formed page
with an ``error`` field rather than raising — so FastAPI startup never breaks.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# --- ground in the real voc360 data layer ---------------------------------
# Support both "package" execution (app.api_signals) and flat imports so the
# module is import-safe in either layout (mirrors deer_flow's import shim).
try:  # pragma: no cover - import shim
    from . import db
except Exception:  # pragma: no cover
    try:
        import db  # type: ignore
    except Exception:  # pragma: no cover - keep the module importable
        db = None  # type: ignore


# ---------------------------------------------------------------------------
# Bounds / defaults.
# ---------------------------------------------------------------------------
DEFAULT_PAGE = 1
DEFAULT_SIZE = 25
MIN_SIZE = 1
MAX_SIZE = 200  # cap the page window so a client can't pull the whole table

# The exact, REAL the_data columns this feed exposes (no invented columns).
COLUMNS: List[str] = [
    "record_id",
    "source_type",
    "service_id",
    "governorate",
    "text_clean",
    "sentiment_label",
    "severity",
    "observed_at",
    "rating",
]
_SELECT_COLS = ",\n         ".join(COLUMNS)


def _clamp_int(value: Any, lo: int, hi: int, default: int) -> int:
    """Coerce ``value`` to an int clamped to ``[lo, hi]`` (default on junk)."""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, n))


def _clean_str(value: Any) -> Optional[str]:
    """Trim a filter value to a non-empty string, else ``None`` (no filter)."""
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _build_where(params: Dict[str, Any]) -> str:
    """Assemble the WHERE clause from whichever filters are present.

    Every predicate references a NAMED bind parameter (``%(name)s``); column
    names are fixed literals from ``COLUMNS`` — never client-controlled — so
    there is no SQL-injection surface here.  Equality filters match exact
    service/severity/source/sentiment values; ``q`` is a case-insensitive
    substring search over the Arabic ``text_clean`` body.
    """
    clauses: List[str] = []
    if params.get("service") is not None:
        clauses.append("service_id = %(service)s")
    if params.get("severity") is not None:
        clauses.append("severity = %(severity)s")
    if params.get("source") is not None:
        clauses.append("source_type = %(source)s")
    if params.get("sentiment") is not None:
        clauses.append("sentiment_label = %(sentiment)s")
    if params.get("q") is not None:
        clauses.append("text_clean ILIKE %(q_like)s")
    return ("where " + " and ".join(clauses)) if clauses else ""


def _empty_page(page: int, size: int, error: Optional[str] = None,
                filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """A well-formed empty page (used for graceful DB/import fallbacks)."""
    out: Dict[str, Any] = {
        "rows": [],
        "total": 0,
        "page": page,
        "size": size,
        "pages": 0,
        "filters": filters or {},
    }
    if error is not None:
        out["error"] = error
    return out


def signals(
    page: int = DEFAULT_PAGE,
    size: int = DEFAULT_SIZE,
    service: Optional[str] = None,
    severity: Optional[str] = None,
    source: Optional[str] = None,
    sentiment: Optional[str] = None,
    q: Optional[str] = None,
) -> Dict[str, Any]:
    """Return a filtered, paginated page of voc360 citizen signals.

    Queries ``the_data`` ordered by ``observed_at desc`` (newest first), with
    optional equality filters on ``service_id`` / ``severity`` / ``source_type``
    / ``sentiment_label`` and a free-text ILIKE search ``q`` over ``text_clean``.

    Args:
        page: 1-based page number (clamped to >= 1).
        size: rows per page (clamped to ``[1, 200]``).
        service: exact ``service_id`` to filter on (e.g. ``"Sanad"``).
        severity: exact ``severity`` (``low``/``medium``/``high``/``critical``).
        source: exact ``source_type`` (e.g. ``"app_review"``).
        sentiment: exact ``sentiment_label`` (e.g. ``"negative"``).
        q: case-insensitive substring matched against Arabic ``text_clean``.

    Returns:
        ``{rows, total, page, size, pages, filters}`` where ``rows`` is a list
        of dicts over :data:`COLUMNS`, ``total`` is the unpaginated match count,
        and ``pages`` is ``ceil(total/size)``.  On DB/import failure returns the
        same shape with empty ``rows`` and an ``error`` string (never raises).

    Example::

        page = signals(page=1, size=25, service="Sanad", severity="high")
        for r in page["rows"]:
            print(r["record_id"], r["sentiment_label"], r["text_clean"])
    """
    page = _clamp_int(page, 1, 10_000_000, DEFAULT_PAGE)
    size = _clamp_int(size, MIN_SIZE, MAX_SIZE, DEFAULT_SIZE)

    f_service = _clean_str(service)
    f_severity = _clean_str(severity)
    f_source = _clean_str(source)
    f_sentiment = _clean_str(sentiment)
    f_q = _clean_str(q)

    filters: Dict[str, Any] = {
        "service": f_service,
        "severity": f_severity,
        "source": f_source,
        "sentiment": f_sentiment,
        "q": f_q,
    }

    if db is None:  # data layer unavailable — keep the API import-safe.
        return _empty_page(page, size, error="data layer unavailable", filters=filters)

    # Named bind params shared by the COUNT and the page query.
    bind: Dict[str, Any] = {
        "service": f_service,
        "severity": f_severity,
        "source": f_source,
        "sentiment": f_sentiment,
        "q": f_q,
        "q_like": f"%{f_q}%" if f_q is not None else None,
        "limit": size,
        "offset": (page - 1) * size,
    }
    where = _build_where(filters)

    count_sql = f"select count(*) as n from the_data {where}".strip()
    # Stable, deterministic ordering: newest first, record_id as a tiebreaker so
    # pagination never drops/duplicates rows that share an observed_at.
    page_sql = (
        f"select {_SELECT_COLS}\n"
        f"  from the_data\n"
        f"  {where}\n"
        f"  order by observed_at desc nulls last, record_id desc\n"
        f"  limit %(limit)s offset %(offset)s"
    ).strip()

    try:
        total_row = db.fetchone(count_sql, bind)
        total = int(total_row["n"]) if total_row and total_row.get("n") is not None else 0
        rows = db.fetchall(page_sql, bind) if total else []
    except Exception as e:  # surface the failure, keep the shape stable.
        return _empty_page(page, size, error=str(e), filters=filters)

    pages = (total + size - 1) // size if size else 0
    return {
        "rows": rows,
        "total": total,
        "page": page,
        "size": size,
        "pages": pages,
        "filters": filters,
    }


__all__ = ["signals", "COLUMNS", "DEFAULT_PAGE", "DEFAULT_SIZE", "MAX_SIZE"]


# ===========================================================================
# Manual smoke test (won't touch the DB unless VOC_DSN is set & reachable).
# ===========================================================================
if __name__ == "__main__":  # pragma: no cover
    import json

    res = signals(page=1, size=5)
    print(json.dumps(
        {k: (v if k != "rows" else f"<{len(v)} rows>") for k, v in res.items()},
        ensure_ascii=False,
        default=str,
    ))
    for row in res.get("rows", [])[:3]:
        print(row.get("record_id"), row.get("source_type"),
              row.get("service_id"), row.get("severity"))
