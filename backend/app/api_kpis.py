"""Dashboard KPIs + signal-volume timeseries — real voc360 numbers.

This is the Track-2 data layer behind the Console Dashboard. Every figure is
pulled live from `the_data` (the SIGNAL / data-source layer of voc360); there
are NO demo fixtures here. Two public entry points, matching the agreed
contract:

  kpis()                  -> {total, negative_pct, critical, top_service, ...}
  signal_volume(range)    -> [{t, v}, ...]   (grouped over observed_at)

Design notes
------------
* DB access goes through the existing read-only `db` helper (psycopg, named
  `%(name)s` params), exactly like `graph_builder`/`rootcause`.
* Real voc360 columns only: observed_at, date, hour, severity, sentiment_label,
  service_id, source_type. `severity` is NULL for app_reviews; `governorate` is
  mostly NULL — both handled.
* Import-safe: importing this module never touches the network. Every query is
  wrapped so a DB outage yields a graceful, well-typed fallback instead of a
  500 — the console still renders, just with zeros and an `ok: False` flag.
* AEGIS tone tokens (alert / warn / calm / neutral) accompany the headline
  numbers so the frontend KpiCard can colour them with the shared Tailwind
  palette without re-deriving thresholds.
"""
from __future__ import annotations

from typing import Any

try:
    from . import db
except Exception:  # pragma: no cover - allows standalone import for tooling
    db = None  # type: ignore


# --- AEGIS severity tones --------------------------------------------------
# Mirrors graph_builder's _tone_from_ratio semantics so KPI cards and graph
# nodes agree on what "alert" vs "warn" vs "calm" means.

def _tone_from_ratio(part: float, whole: float) -> str:
    if not whole:
        return "neutral"
    r = part / whole
    return "alert" if r >= 0.30 else "warn" if r >= 0.10 else "calm"


def _pct(part: float, whole: float) -> float:
    return round(100.0 * part / whole, 1) if whole else 0.0


# --- time-range presets for the volume chart -------------------------------
# Each range picks a bucket granularity that keeps the series readable.
#   key      window                  bucket     ~points
RANGES: dict[str, dict[str, Any]] = {
    "24h": {"interval": "24 hours", "trunc": "hour", "label": "Last 24h"},
    "7d":  {"interval": "7 days",   "trunc": "day",  "label": "Last 7 days"},
    "30d": {"interval": "30 days",  "trunc": "day",  "label": "Last 30 days"},
    "90d": {"interval": "90 days",  "trunc": "week", "label": "Last 90 days"},
    "all": {"interval": None,       "trunc": "week", "label": "All time"},
}
DEFAULT_RANGE = "30d"


# --- SQL (read-only; %(name)s params) --------------------------------------

# Headline counters in a single round-trip. We treat sentiment as negative when
# the label literally starts with "negative" OR is the high-severity complaint
# bucket; severity 'high'/'critical' drives the critical counter (NULL-safe).
Q_KPIS = """
  select
    count(*)                                                            as total,
    count(*) filter (
      where sentiment_label is not null
        and (lower(sentiment_label) like 'negative%%'
             or lower(sentiment_label) like 'high_severity%%')
    )                                                                   as negative,
    count(*) filter (where sentiment_label is not null)                 as sentiment_known,
    count(*) filter (where severity in ('high', 'critical'))            as critical,
    count(*) filter (where severity is not null)                       as severity_known,
    count(distinct service_id) filter (where service_id is not null)    as services,
    count(distinct source_type) filter (where source_type is not null)  as sources
  from the_data
"""

# Busiest service by raw signal volume, with its own negativity read so the
# card can show *which* service is hurting and how badly.
Q_TOP_SERVICE = """
  select service_id as id,
         count(*)   as signals,
         count(*) filter (where severity in ('high','critical')) as critical,
         count(*) filter (
           where sentiment_label is not null
             and (lower(sentiment_label) like 'negative%%'
                  or lower(sentiment_label) like 'high_severity%%')
         ) as negative
  from the_data
  where service_id is not null
  group by 1
  order by signals desc
  limit 1
"""

# Time bucket over observed_at. date_trunc keeps it to real Postgres; the
# optional rolling window is applied relative to the freshest signal we have
# (max(observed_at)) rather than now(), because the snapshot may be historical.
Q_VOLUME_WINDOWED = """
  with bounds as (select max(observed_at) as hi from the_data where observed_at is not null)
  select date_trunc(%(trunc)s, observed_at) as t, count(*) as v
  from the_data, bounds
  where observed_at is not null
    and observed_at >= bounds.hi - (%(interval)s)::interval
  group by 1
  order by 1
"""
Q_VOLUME_ALL = """
  select date_trunc(%(trunc)s, observed_at) as t, count(*) as v
  from the_data
  where observed_at is not null
  group by 1
  order by 1
"""


# --- helpers ---------------------------------------------------------------

def _fetchone(sql: str, params: dict | None = None) -> dict[str, Any] | None:
    if db is None:
        return None
    return db.fetchone(sql, params)


def _fetchall(sql: str, params: dict | None = None) -> list[dict[str, Any]]:
    if db is None:
        return []
    return db.fetchall(sql, params)


def _isoformat(t: Any) -> Any:
    # observed_at buckets come back as datetime/date; hand the frontend an ISO
    # string it can feed straight into recharts. Anything else passes through.
    try:
        return t.isoformat()
    except AttributeError:
        return t


# --- public API ------------------------------------------------------------

def kpis() -> dict[str, Any]:
    """Headline KPIs for the Console Dashboard, computed live from voc360.

    Returns a flat, frontend-friendly dict::

        {
          "ok": True,
          "total": 22882,                # total citizen signals
          "negative": 1234,              # negative + high-severity signals
          "negative_pct": 41.2,          # of signals with a known sentiment
          "negative_tone": "alert",
          "critical": 395,               # severity in (high, critical)
          "critical_pct": 10.6,          # of signals with a known severity
          "critical_tone": "warn",
          "services": 14,
          "sources": 9,
          "top_service": {               # busiest service, with its own reads
            "id": "Sanad", "signals": 15800,
            "critical": 120, "negative_pct": 33.1, "tone": "alert"
          }
        }

    On any DB error this returns the same shape with zeros and ``ok: False`` so
    the dashboard degrades instead of 500-ing.
    """
    try:
        row = _fetchone(Q_KPIS) or {}
        total = int(row.get("total") or 0)
        negative = int(row.get("negative") or 0)
        sentiment_known = int(row.get("sentiment_known") or 0)
        critical = int(row.get("critical") or 0)
        severity_known = int(row.get("severity_known") or 0)

        top = _fetchone(Q_TOP_SERVICE) or {}
        top_service = None
        if top.get("id") is not None:
            ts_signals = int(top.get("signals") or 0)
            ts_negative = int(top.get("negative") or 0)
            top_service = {
                "id": top["id"],
                "signals": ts_signals,
                "critical": int(top.get("critical") or 0),
                "negative_pct": _pct(ts_negative, ts_signals),
                "tone": _tone_from_ratio(ts_negative, ts_signals),
            }

        return {
            "ok": True,
            "total": total,
            "negative": negative,
            "negative_pct": _pct(negative, sentiment_known),
            "negative_tone": _tone_from_ratio(negative, sentiment_known),
            "critical": critical,
            "critical_pct": _pct(critical, severity_known),
            "critical_tone": _tone_from_ratio(critical, severity_known),
            "services": int(row.get("services") or 0),
            "sources": int(row.get("sources") or 0),
            "top_service": top_service,
        }
    except Exception as e:  # surface the reason, keep the shape
        return {
            "ok": False,
            "error": str(e),
            "total": 0,
            "negative": 0,
            "negative_pct": 0.0,
            "negative_tone": "neutral",
            "critical": 0,
            "critical_pct": 0.0,
            "critical_tone": "neutral",
            "services": 0,
            "sources": 0,
            "top_service": None,
        }


def signal_volume(range: str = DEFAULT_RANGE) -> list[dict[str, Any]]:
    """Signal-volume timeseries for the SignalVolume chart, from `the_data`.

    Groups citizen signals by a time bucket over ``observed_at``. ``range`` is
    one of ``24h | 7d | 30d | 90d | all`` (unknown values fall back to the
    default 30-day window). Each point is ``{"t": <iso>, "v": <count>}`` ordered
    oldest→newest. Returns ``[]`` on DB error so the chart renders empty rather
    than crashing.
    """
    cfg = RANGES.get(range, RANGES[DEFAULT_RANGE])
    trunc = cfg["trunc"]
    interval = cfg["interval"]
    try:
        if interval is None:
            rows = _fetchall(Q_VOLUME_ALL, {"trunc": trunc})
        else:
            rows = _fetchall(Q_VOLUME_WINDOWED, {"trunc": trunc, "interval": interval})
        return [{"t": _isoformat(r["t"]), "v": int(r["v"] or 0)} for r in rows]
    except Exception:
        return []
