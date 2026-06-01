"""D-series — dense, gap-filled DAILY time-series builder over real voc360 data.

This is the input layer for `forecaster.forecast_series` (see
`FORECASTING_RECIPE.md`) and the `/api/forecast*` endpoints. It turns the raw
signal layer `the_data` into an evenly-spaced daily grid (TimesFM and
Holt-Winters both need that) for a service, a root-cause cluster, or the whole
nation, on one of three metrics: volume / negativity / severity.

Design notes
------------
* DB access goes through the existing read-only `db` helper (psycopg, named
  `%(name)s` params), exactly like `api_kpis` / `rootcause` / `cluster_link`.
* Real voc360 columns only:
    - daily key  `date_trunc('day', nullif(date::text, '')::timestamp)::date`
      (`observed_at` primary, `date` fallback) — the established expression from
      api_kpis / the forecasting recipe.
    - negativity = `lower(sentiment_label) like 'negative%%' or like 'high_severity%%'`
      (identical to api_kpis Q_KPIS), averaged only over non-null sentiment.
    - severity   low/medium/high/critical -> 1/2/3/4, averaged only over non-null
      severity (NULL for app_reviews — excluded, NOT counted as 0).
* Clusters do NOT join `the_data` by id (the RIL pipeline ran on a separate
  snapshot). A cluster is expanded to its service set via
  `cluster_link.cluster_services(cluster_id)` and aggregated over those services.
* Import-safe: importing this module never touches the network. Every query is
  wrapped so a DB outage / unknown key yields a graceful, well-typed fallback
  (empty frame, zeroed stats) instead of a 500 — mirrors api_kpis' degrade
  pattern. `build_series` never raises.
* No hard dependency on pandas / numpy / torch / timesfm / llm. Gap-filling is a
  pure-Python `datetime.timedelta` loop (series <= ~3200 points — trivial).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

try:
    from . import db
except Exception:  # pragma: no cover - allows standalone import for tooling
    db = None  # type: ignore

try:
    from . import cluster_link
except Exception:  # pragma: no cover - cluster expansion degrades to no services
    cluster_link = None  # type: ignore


# --- contract literals ------------------------------------------------------
# (kept as plain strings so this module imports on any Python without typing
# extras; the values below mirror the D-series Metric / Entity unions.)
METRICS = ("volume", "negativity", "severity")
ENTITIES = ("service", "cluster", "all")
DEFAULT_METRIC = "volume"
DEFAULT_FREQ = "D"


# --- SQL (raw daily aggregate, pre-densify) --------------------------------
# One query computes all three metrics; we pick `y` per the requested metric in
# Python. `{entity_clause}` is one of the constants below (no user text is ever
# interpolated — only these fixed clauses — and the entity key/services bind via
# named `%(key)s` / `%(services)s` params).
Q_DAILY = """
  select nullif("date", '')::date                                        as ds,
         count(*)                                                         as volume,
         avg( (lower(sentiment_label) like 'negative%%'
               or lower(sentiment_label) like 'high_severity%%')::int )
           filter (where sentiment_label is not null)                    as negativity,
         avg( case severity when 'low' then 1 when 'medium' then 2
                            when 'high' then 3 when 'critical' then 4 end )
           filter (where severity is not null)                           as severity
  from the_data
  where nullif("date", '') is not null
    {entity_clause}
  group by 1
  order by 1
"""

_CLAUSE_SERVICE = "and service_id = %(key)s"
_CLAUSE_CLUSTER = "and service_id = any(%(services)s)"
_CLAUSE_ALL = ""


# --- helpers ----------------------------------------------------------------

def _fetchall(sql: str, params: dict | None = None) -> list[dict[str, Any]]:
    if db is None:
        return []
    return db.fetchall(sql, params or {})


def _as_date(d: Any) -> date | None:
    """Coerce a DB `ds` value (date / datetime / ISO str) to a plain `date`."""
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, date):
        return d
    if isinstance(d, str):
        try:
            return date.fromisoformat(d[:10])
        except Exception:
            return None
    return None


def _to_float(v: Any) -> float:
    if v is None:
        return 0.0
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _mean(xs: list[float]) -> float:
    return round(sum(xs) / len(xs), 4) if xs else 0.0


def _zero_stats() -> dict[str, float]:
    return {
        "mean": 0.0,
        "mean_7": 0.0,
        "mean_14": 0.0,
        "mean_30": 0.0,
        "last": 0.0,
        "nonzero_days": 0,
    }


def _empty(
    entity_type: str,
    key: str | None,
    metric: str,
    freq: str,
    services: list[str],
    error: str | None,
) -> dict[str, Any]:
    """The well-typed degrade shape: valid result with an empty dense frame."""
    return {
        "entity_type": entity_type,
        "key": key,
        "metric": metric,
        "freq": freq,
        "frame": [],
        "values": [],
        "start": None,
        "end": None,
        "n_points": 0,
        "n_observed": 0,
        "stats": _zero_stats(),
        "services": services,
        "ok": error is None,
        "error": error,
    }


def _resolve_services(entity_type: str, key: str | None) -> tuple[str, dict, list[str]]:
    """Pick the WHERE clause + params + the actual aggregated service set.

    Returns (entity_clause_sql, sql_params, services_list).
    For clusters the service set is recovered via `cluster_link` (text-match
    chain) since cluster ids do not join `the_data`.
    """
    if entity_type == "service":
        return _CLAUSE_SERVICE, {"key": key}, ([key] if key else [])
    if entity_type == "cluster":
        services: list[str] = []
        if cluster_link is not None and key:
            try:
                services = [s for s, _ in cluster_link.cluster_services(key) if s]
            except Exception:
                services = []
        return _CLAUSE_CLUSTER, {"services": services}, services
    # "all" (national) — no entity filter
    return _CLAUSE_ALL, {}, []


def _densify(
    rows: list[dict[str, Any]], metric: str
) -> tuple[list[dict[str, Any]], int, date | None, date | None]:
    """Reindex raw daily rows onto an inclusive min..max calendar.

    * volume   : missing days -> 0.0 (no signals == zero volume).
    * negativity / severity : forward-fill (a rate carries until new evidence);
      a leading gap (before any observation) -> 0.0. A day that HAS signals but a
      NULL aggregate (e.g. app-review volume with no labelled sentiment/severity)
      is treated as "no new rate evidence" and also carries the prior value —
      not reset to 0 — since the metric is genuinely unmeasured that day.
    Returns (dense_frame, n_observed, start_date, end_date).

    `n_observed` counts calendar days with >=1 real signal (any metric), so it is
    consistent across metrics and matches the "days with data" notion.
    """
    is_rate = metric in ("negativity", "severity")

    # Index observed rows by their (clean) date. For rate metrics keep the value
    # OR None (NULL aggregate) so we can carry-forward across unmeasured days.
    observed: dict[date, float | None] = {}
    for r in rows:
        d = _as_date(r.get("ds"))
        if d is None:
            continue
        raw = r.get(metric)
        if is_rate:
            observed[d] = None if raw is None else _to_float(raw)
        else:
            observed[d] = _to_float(raw)

    if not observed:
        return [], 0, None, None

    start = min(observed)
    end = max(observed)
    n_observed = len(observed)  # days with a real signal row (pre-fill)

    frame: list[dict[str, Any]] = []
    carry = 0.0  # forward-fill accumulator for rate metrics (0.0 until first obs)
    cur = start
    one = timedelta(days=1)
    while cur <= end:
        val = observed.get(cur, None) if cur in observed else (None if is_rate else 0.0)
        if is_rate:
            # carry forward across both missing days and NULL-aggregate days
            if val is not None:
                carry = val
            y = carry
        else:
            # volume: present day uses its count, missing day -> 0
            y = val if cur in observed else 0.0
        frame.append({"ds": cur.isoformat(), "y": float(y)})
        cur += one

    return frame, n_observed, start, end


def _recent_stats(values: list[float]) -> dict[str, Any]:
    if not values:
        return _zero_stats()
    return {
        "mean": _mean(values),
        "mean_7": _mean(values[-7:]),
        "mean_14": _mean(values[-14:]),
        "mean_30": _mean(values[-30:]),
        "last": round(float(values[-1]), 4),
        "nonzero_days": int(sum(1 for v in values if v > 0)),
    }


# --- public API -------------------------------------------------------------

def build_series(
    entity_type: str = "all",
    key: str | None = None,
    metric: str = DEFAULT_METRIC,
    freq: str = DEFAULT_FREQ,
) -> dict[str, Any]:
    """Build a dense, gap-filled DAILY series for a service / cluster / nation.

    Parameters
    ----------
    entity_type : "service" | "cluster" | "all"
        What to aggregate. "service" filters `the_data.service_id`; "cluster"
        expands the cluster to its service set via `cluster_link` and aggregates
        over them; "all" is the national series.
    key : str | None
        The `service_id` (entity_type="service") or `cluster_id`
        (entity_type="cluster"). Ignored for "all".
    metric : "volume" | "negativity" | "severity"
        Daily count, daily negative-sentiment share (0..1), or daily mean
        severity (1..4). Defaults to "volume".
    freq : str
        Reserved for future weekly/monthly resampling; only "D" (daily) is wired.

    Returns
    -------
    A `SeriesResult` dict (see D-series). `frame` is dense oldest->newest with
    ISO date strings; `values = [r["y"] for r in frame]` feeds
    `forecaster.forecast_series(values, horizon)` directly. Never raises — any
    failure degrades to an empty frame with `ok=False` and `error` set, like
    `api_kpis`.
    """
    # Normalise inputs against the contract (be lenient, never raise).
    entity_type = entity_type if entity_type in ENTITIES else "all"
    metric = metric if metric in METRICS else DEFAULT_METRIC
    freq = freq or DEFAULT_FREQ

    if db is None:
        return _empty(entity_type, key, metric, freq, [], "db module unavailable")

    # service/cluster require a key; without one return a valid empty result.
    if entity_type in ("service", "cluster") and not key:
        return _empty(entity_type, key, metric, freq, [], f"{entity_type} requires a key")

    try:
        entity_clause, params, services = _resolve_services(entity_type, key)

        # A cluster that maps to no services has no signals: valid empty result.
        if entity_type == "cluster" and not services:
            return _empty(entity_type, key, metric, freq, services, None)

        sql = Q_DAILY.format(entity_clause=entity_clause)
        rows = _fetchall(sql, params)

        frame, n_observed, start, end = _densify(rows, metric)
        values = [r["y"] for r in frame]

        return {
            "entity_type": entity_type,
            "key": key,
            "metric": metric,
            "freq": freq,
            "frame": frame,
            "values": values,
            "start": start.isoformat() if start else None,
            "end": end.isoformat() if end else None,
            "n_points": len(frame),
            "n_observed": n_observed,
            "stats": _recent_stats(values),
            "services": services,
            "ok": True,
            "error": None,
        }
    except Exception as e:  # surface the reason, keep the shape
        return _empty(entity_type, key, metric, freq, [], str(e))


def recent_stats(
    entity_type: str = "all",
    key: str | None = None,
    metric: str = DEFAULT_METRIC,
) -> dict[str, Any]:
    """Convenience accessor: just the recent-window stats for an entity/metric.

    Builds the series and returns its `stats` block (mean / mean_7 / mean_14 /
    mean_30 / last / nonzero_days). Used for escalation grounding
    (`forecast_mean` vs `mean_14`) and Q&A windows. Never raises.
    """
    return build_series(entity_type, key, metric).get("stats", _zero_stats())
