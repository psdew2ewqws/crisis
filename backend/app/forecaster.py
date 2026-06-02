"""D-forecast — per-service / per-cluster volume & sentiment forecasting on real
voc360 `the_data`.

GOAL #5. TimesFM is **optional + env-gated** (`TIMESFM_MODEL`); it is loaded once,
lazily, and cached. When it is unavailable (the common case — torch/timesfm are NOT
in requirements.txt) the engine degrades to a statistical fallback:
statsmodels Holt-Winters when present, else a pure-numpy seasonal-naive + EWMA-drift
forecaster, else a flat pure-python path. The module is therefore **import-safe** on a
box with neither torch, timesfm, statsmodels, nor numpy — exactly the graceful-degrade
pattern `main.py:24-35` uses for deer_flow / mesa_sim.

The daily series is built from real `the_data` rows via `db.fetchall`, dense-filled to a
gap-free calendar (TimesFM and Holt-Winters both need an evenly-spaced grid). For a
cluster, `ril_text_segments.record_id` does NOT join `the_data`, so the series is
aggregated over the cluster's mapped service set from
`cluster_link.cluster_services(cluster_id)` (the same parallel-layer rule the graph uses).

If `series.build_series` (D-series) is available it is preferred for the series build;
otherwise an inline SQL builder applying the identical D-series gap-fill rules is used.

Public contract (uniform across ALL engines):

    forecast_series(y, horizon=30, season=7) -> {source, mean[h], lo[h], hi[h]}
    forecast(entity='service'|'cluster', key=..., metric='volume'|'sentiment',
             horizon=30) -> {entity, id, metric, horizon, history, forecast, source,
                             escalation, history_points}
    escalation(history, fc_mean, window=14) -> {recent_mean, forecast_mean, ratio,
                                                escalating}
    scan_escalations(horizon=14, metric='volume') -> {horizon, ranked[...]}

LLM trust boundary: forecast numbers are RETRIEVED facts; the local model only phrases
them (see D-forecast §5). This module never invents a trend.
"""
from __future__ import annotations

import datetime as _dt
import os
from typing import Any

# numpy is the only light dependency for the fallback; guard it so the module still
# imports on a box without it (degrades to a flat pure-python path).
try:
    import numpy as np  # noqa: F401

    _HAS_NUMPY = True
except Exception:  # pragma: no cover - numpy is normally present
    np = None  # type: ignore
    _HAS_NUMPY = False

from . import db

# cluster_link maps a cluster -> its real service set (cluster ids don't join the_data).
try:
    from . import cluster_link
except Exception:  # pragma: no cover
    cluster_link = None  # type: ignore

# Prefer the D-series builder when it lands; fall back to the inline builder below.
try:
    from . import series as _series  # type: ignore
except Exception:
    _series = None  # type: ignore


# ---------------------------------------------------------------------------
# Engine state — TimesFM is loaded at most once per process (env-gated).
# ---------------------------------------------------------------------------
_MODEL: Any = None              # TimesFM model handle, or None
_BACKEND: str | None = None     # '2.5' | '2.0' | 'stat'  (None until first _try_load)
_LOAD_ERR: str | None = None


def _try_load() -> None:
    """Load TimesFM ONCE, lazily, only if `TIMESFM_MODEL` is set. Never hard-depends on
    torch/timesfm — any failure pins the backend to the statistical fallback. Idempotent;
    safe to call from a startup hook to warm the (potentially 2GB) checkpoint off the
    request hot path."""
    global _MODEL, _BACKEND, _LOAD_ERR
    if _MODEL is not None or _BACKEND == "stat":
        return
    ckpt = os.environ.get("TIMESFM_MODEL")  # e.g. google/timesfm-2.5-200m-pytorch
    if not ckpt:
        _BACKEND = "stat"
        return
    try:
        import timesfm  # lazy: torch is heavy/optional, imported only when env-opted-in

        if "TimesFM_2p5_200M_torch" in dir(timesfm) and "2.5" in ckpt:
            m = timesfm.TimesFM_2p5_200M_torch.from_pretrained(ckpt)
            m.compile(
                timesfm.ForecastConfig(
                    max_context=1024,
                    max_horizon=256,
                    normalize_inputs=True,
                    use_continuous_quantile_head=True,
                    force_flip_invariance=True,
                    infer_is_positive=True,
                    fix_quantile_crossing=True,
                )
            )
            _MODEL, _BACKEND = m, "2.5"
        else:  # legacy 2.0 / 1.x checkpoints (have a freq arg + fixed hparams)
            m = timesfm.TimesFm(
                hparams=timesfm.TimesFmHparams(
                    backend="cpu",
                    per_core_batch_size=32,
                    horizon_len=int(os.environ.get("TIMESFM_HORIZON", 128)),
                    context_len=512,  # must be a multiple of input_patch_len (32)
                    input_patch_len=32,
                    output_patch_len=128,
                    num_layers=50,
                    model_dims=1280,
                    use_positional_embedding=False,
                ),
                checkpoint=timesfm.TimesFmCheckpoint(huggingface_repo_id=ckpt),
            )
            _MODEL, _BACKEND = m, "2.0"
    except Exception as e:  # torch/timesfm/checkpoint missing -> degrade silently
        _MODEL, _BACKEND, _LOAD_ERR = None, "stat", str(e)


def status() -> dict[str, Any]:
    """Honest backend flag for `/api/forecast/status` and `/api/health`."""
    _try_load()
    return {
        "backend": _BACKEND,
        "model_loaded": _MODEL is not None,
        "load_error": _LOAD_ERR,
    }


# ---------------------------------------------------------------------------
# forecast_series — the uniform-shape engine entry point.
# ---------------------------------------------------------------------------
def forecast_series(y: list[float], horizon: int = 30, season: int = 7) -> dict:
    """Forecast ONE chronological daily series (volume or sentiment) for a single
    service/cluster. Returns the same shape regardless of which engine ran so the
    frontend ForecastPanel/recharts is engine-agnostic:

        {"source": "timesfm-2.5"|"timesfm-2.0"|"holt-winters"|"seasonal-naive"|"empty",
         "mean": [float x horizon], "lo": [...], "hi": [...]}

    `lo`/`hi` approximate the 10th/90th percentile band; volume is clamped >= 0.
    """
    horizon = max(1, int(horizon))
    _try_load()
    hist = list(y or [])

    if _BACKEND in ("2.5", "2.0") and _MODEL is not None and _HAS_NUMPY and hist:
        try:
            arr = np.asarray(hist, dtype=np.float32)
            if _BACKEND == "2.5":
                pt, q = _MODEL.forecast(horizon=horizon, inputs=[arr])
                mean = np.asarray(pt[0], dtype=float)[:horizon]
                qa = np.asarray(q[0], dtype=float)  # (horizon, 10) = mean, q10..q90
                lo = qa[:horizon, 1]   # 10th decile
                hi = qa[:horizon, 9]   # 90th decile
                src = "timesfm-2.5"
            else:  # 2.0
                pt, q = _MODEL.forecast([arr], freq=[0])  # 0 = daily / high-freq
                mean = np.asarray(pt[0], dtype=float)[:horizon]
                qa = np.asarray(q[0], dtype=float)
                lo = qa[:horizon, 0]
                hi = qa[:horizon, -1]
                src = "timesfm-2.0"
            mean = np.clip(mean, 0.0, None)
            lo = np.clip(lo, 0.0, None)
            hi = np.clip(hi, 0.0, None)
            # pad if the model returned fewer than `horizon` points
            mean, lo, hi = _pad(mean, horizon), _pad(lo, horizon), _pad(hi, horizon)
            return {"source": src, "mean": mean, "lo": lo, "hi": hi}
        except Exception:
            pass  # any inference error -> statistical fallback

    return _stat_forecast(hist, horizon, season)


def _pad(a, horizon: int) -> list[float]:
    """Coerce a numpy/list to a length-`horizon` python float list (pad with last value)."""
    vals = [float(x) for x in list(a)]
    if not vals:
        return [0.0] * horizon
    if len(vals) < horizon:
        vals = vals + [vals[-1]] * (horizon - len(vals))
    return vals[:horizon]


# ---------------------------------------------------------------------------
# Statistical fallback: Holt-Winters (statsmodels, if present) -> seasonal-naive.
# ---------------------------------------------------------------------------
def _stat_forecast(hist: list[float], horizon: int, season: int) -> dict:
    """Holt-Winters additive (weekly season) via statsmodels when it is installed AND
    there are >= 2 full seasons; otherwise the pure-numpy seasonal-naive path. statsmodels
    is NOT a hard dependency, so the import is guarded."""
    if _HAS_NUMPY and len(hist) >= 2 * season:
        try:
            from statsmodels.tsa.holtwinters import ExponentialSmoothing

            arr = np.asarray(hist, dtype=float)
            fit = ExponentialSmoothing(
                arr,
                trend="add",
                seasonal="add",
                seasonal_periods=season,
                initialization_method="estimated",
            ).fit()
            mean = np.clip(np.asarray(fit.forecast(horizon), dtype=float), 0.0, None)
            resid = arr - np.asarray(fit.fittedvalues, dtype=float)
            sd = float(np.nanstd(resid)) or 1.0
            band = 1.28 * sd  # ~80% band (p10/p90)
            return {
                "source": "holt-winters",
                "mean": mean.tolist(),
                "lo": np.clip(mean - band, 0.0, None).tolist(),
                "hi": (mean + band).tolist(),
            }
        except Exception:
            pass  # statsmodels missing or fit failed -> seasonal-naive
    return _seasonal_naive(hist, horizon, season)


def _seasonal_naive(hist: list[float], horizon: int, season: int) -> dict:
    """Zero-dependency safety net: weekly seasonal-naive + EWMA drift + widening naive CI.
    Uses numpy when available, else a pure-python implementation so the module still
    forecasts on a box without numpy."""
    n = len(hist)
    if n == 0:
        z = [0.0] * horizon
        return {"source": "empty", "mean": z, "lo": z, "hi": z}

    season = min(season, n)
    last = hist[-season:]

    def _ewma(a: list[float], al: float) -> float:
        o = a[0]
        for v in a[1:]:
            o = al * v + (1 - al) * o
        return o

    # drift = short-window EWMA minus long-window EWMA (recent trend), per step
    drift = (_ewma(hist, 0.5) - _ewma(hist, 0.1)) / max(season, 1)

    if _HAS_NUMPY:
        tail = hist[-min(n, 4 * season):]
        sd = float(np.std(np.asarray(tail, dtype=float))) or 1.0
    else:  # pure-python std
        tail = hist[-min(n, 4 * season):]
        mu = sum(tail) / len(tail)
        sd = (sum((v - mu) ** 2 for v in tail) / len(tail)) ** 0.5 or 1.0

    mean: list[float] = []
    lo: list[float] = []
    hi: list[float] = []
    for h in range(horizon):
        pt = max(0.0, last[h % season] + drift * (h + 1))
        band = 1.28 * sd * ((h + 1) ** 0.5)  # widening band with horizon
        mean.append(pt)
        lo.append(max(0.0, pt - band))
        hi.append(pt + band)
    return {"source": "seasonal-naive", "mean": mean, "lo": lo, "hi": hi}


# ---------------------------------------------------------------------------
# Series builders — real voc360 `the_data`, dense-filled (D-series rules).
# ---------------------------------------------------------------------------
_DAILY_KEY = "nullif(\"date\", '')::date"


def _raw_daily(metric: str, services: list[str] | None) -> list[dict]:
    """Raw daily aggregate from `the_data` (pre-densify). `services=None` => national.
    Negativity convention matches api_kpis (`like 'negative%%'`/`'high_severity%%'`)."""
    if metric == "sentiment":
        y_expr = (
            "avg((lower(sentiment_label) like 'negative%%' "
            "or lower(sentiment_label) like 'high_severity%%')::int) "
            "filter (where sentiment_label is not null)"
        )
    else:  # volume
        y_expr = "count(*)::float"

    where = "nullif(\"date\", '') is not null"
    params: tuple
    if services is None:
        params = ()
    elif len(services) == 0:
        return []  # cluster maps to no services -> empty (valid)
    else:
        where += " and service_id = any(%s)"
        params = (list(services),)

    sql = (
        f"select {_DAILY_KEY} as ds, {y_expr} as y "
        f"from the_data where {where} group by 1 order by 1"
    )
    return db.fetchall(sql, params)


def _densify(rows: list[dict], metric: str) -> tuple[list[str], list[float]]:
    """Reindex onto an inclusive day calendar. volume -> fill 0; sentiment -> forward-fill
    (a rate carries until new evidence), leading gap -> 0.0. Returns (iso_dates, values),
    oldest -> newest. Pure-python; series <= ~3200 points."""
    obs: dict[_dt.date, float] = {}
    for r in rows:
        ds = r["ds"]
        if isinstance(ds, _dt.datetime):
            ds = ds.date()
        v = r["y"]
        obs[ds] = float(v) if v is not None else None  # type: ignore[assignment]
    if not obs:
        return [], []

    start, end = min(obs), max(obs)
    dates: list[str] = []
    values: list[float] = []
    carry = 0.0  # last seen sentiment rate (leading gap -> 0.0)
    day = start
    one = _dt.timedelta(days=1)
    while day <= end:
        raw = obs.get(day)
        if metric == "sentiment":
            if raw is None:
                val = carry  # forward-fill the rate
            else:
                val = raw
                carry = raw
        else:  # volume
            val = 0.0 if raw is None else raw
        dates.append(day.isoformat())
        values.append(float(val))
        day += one
    return dates, values


def _cluster_services(cluster_id: str) -> list[str]:
    """The cluster's mapped service set (cluster ids don't join the_data)."""
    if cluster_link is None:
        return []
    try:
        return [svc for svc, _w in cluster_link.cluster_services(cluster_id)]
    except Exception:
        return []


def build_series(
    entity: str, key: str | None, metric: str = "volume"
) -> dict:
    """Dense daily series for a service/cluster. Prefers the D-series builder when present,
    else builds inline from `the_data` with the identical gap-fill rules. Never raises.

    Returns {dates: [iso], values: [float], services: [str]}."""
    # Prefer the dedicated D-series module if it is wired up.
    if _series is not None and hasattr(_series, "build_series"):
        try:
            s_metric = "negativity" if metric == "sentiment" else metric
            res = _series.build_series(entity, key, metric=s_metric)
            if res and res.get("ok", True):
                frame = res.get("frame") or []
                dates = [r["ds"] for r in frame]
                values = res.get("values") or [float(r["y"]) for r in frame]
                return {
                    "dates": dates,
                    "values": [float(v) for v in values],
                    "services": res.get("services") or ([key] if key else []),
                }
        except Exception:
            pass  # fall through to inline builder

    # Inline builder.
    try:
        if entity == "cluster":
            svcs = _cluster_services(key) if key else []
            rows = _raw_daily(metric, svcs)
            used = svcs
        elif entity == "all":
            rows = _raw_daily(metric, None)
            used = []
        else:  # service
            rows = _raw_daily(metric, [key]) if key else []
            used = [key] if key else []
        dates, values = _densify(rows, metric)
        return {"dates": dates, "values": values, "services": used}
    except Exception:
        return {"dates": [], "values": [], "services": []}


# ---------------------------------------------------------------------------
# Escalation — "which problem grows" (powers GOAL #5 + the root-cause graph).
# ---------------------------------------------------------------------------
def escalation(
    history: list[float], fc_mean: list[float], window: int = 14
) -> dict:
    """Compare the forecast-window mean vs the recent-history mean. `escalating` when the
    ratio >= 1.2 — this surfaces the growing service/cluster."""
    h = list(history or [])
    f = list(fc_mean or [])
    recent = (sum(h[-window:]) / len(h[-window:])) if h else 0.0
    fut = (sum(f) / len(f)) if f else 0.0
    if recent > 0:
        ratio = fut / recent
    else:
        ratio = 2.0 if fut > 0 else 1.0
    return {
        "recent_mean": round(float(recent), 3),
        "forecast_mean": round(float(fut), 3),
        "ratio": round(float(ratio), 3),
        "escalating": bool(ratio >= 1.2),
    }


def _future_dates(history_dates: list[str], horizon: int) -> list[str]:
    """Future ISO dates = last history date + 1..horizon (fallback to a synthetic span)."""
    if history_dates:
        try:
            last = _dt.date.fromisoformat(history_dates[-1])
        except Exception:
            last = _dt.date.today()
    else:
        last = _dt.date.today()
    one = _dt.timedelta(days=1)
    out: list[str] = []
    d = last
    for _ in range(horizon):
        d = d + one
        out.append(d.isoformat())
    return out


def forecast(
    entity: str = "service",
    key: str | None = None,
    metric: str = "volume",
    horizon: int = 30,
) -> dict:
    """End-to-end grounded forecast for one entity. Builds the real dense series, forecasts
    it, and attaches the escalation verdict. Degrades to an empty-but-valid result rather
    than raising. The `source` field is the honesty flag (timesfm-* vs holt-winters /
    seasonal-naive)."""
    horizon = max(1, min(int(horizon), 120))
    entity = entity if entity in ("service", "cluster", "all") else "service"
    metric = metric if metric in ("volume", "sentiment") else "volume"

    s = build_series(entity, key, metric=metric)
    dates, values = s["dates"], s["values"]

    if not values:
        return {
            "entity": entity,
            "id": key,
            "metric": metric,
            "horizon": horizon,
            "history": [],
            "forecast": [],
            "source": "empty",
            "escalation": escalation([], []),
            "history_points": 0,
            "services": s.get("services", []),
        }

    fc = forecast_series(values, horizon=horizon)
    f_dates = _future_dates(dates, horizon)
    forecast_points = [
        {"t": f_dates[i], "mean": round(fc["mean"][i], 3),
         "lo": round(fc["lo"][i], 3), "hi": round(fc["hi"][i], 3)}
        for i in range(horizon)
    ]
    history_points = [{"t": dates[i], "v": round(values[i], 3)} for i in range(len(values))]

    return {
        "entity": entity,
        "id": key,
        "metric": metric,
        "horizon": horizon,
        "history": history_points,
        "forecast": forecast_points,
        "source": fc["source"],
        "escalation": escalation(values, fc["mean"]),
        "history_points": len(values),
        "services": s.get("services", []),
    }


# ---------------------------------------------------------------------------
# scan_escalations — rank services + clusters by projected near-term growth.
# ---------------------------------------------------------------------------
def _top_services(limit: int = 12) -> list[str]:
    try:
        rows = db.fetchall(
            """
            select service_id from the_data
            where service_id is not null
            group by 1 order by count(*) desc limit %s
            """,
            (limit,),
        )
        return [r["service_id"] for r in rows]
    except Exception:
        return []


def _top_clusters(limit: int = 8) -> list[str]:
    # Prefer rootcause ranking; fall back to the cluster table directly.
    try:
        from . import rootcause

        ranked = rootcause.rank_root_causes(limit)
        return [r["cluster_id"] for r in ranked if r.get("cluster_id")]
    except Exception:
        pass
    try:
        rows = db.fetchall(
            """
            select cluster_id from ril_problem_clusters
            where coalesce(member_count,0) > 1
            order by member_count desc limit %s
            """,
            (limit,),
        )
        return [r["cluster_id"] for r in rows]
    except Exception:
        return []


def scan_escalations(horizon: int = 14, metric: str = "volume") -> dict:
    """Forecast the top services + clusters and rank them by escalation ratio (desc).
    Surfaces the fastest-growing problem for the watchlist / root-cause graph. Never raises;
    entities that error or have no series are skipped."""
    horizon = max(1, min(int(horizon), 120))
    ranked: list[dict] = []

    for svc in _top_services(12):
        try:
            r = forecast("service", svc, metric=metric, horizon=horizon)
            if r["history_points"] == 0:
                continue
            esc = r["escalation"]
            ranked.append({
                "entity": "service", "id": svc,
                "ratio": esc["ratio"], "escalating": esc["escalating"],
                "recent_mean": esc["recent_mean"], "forecast_mean": esc["forecast_mean"],
                "source": r["source"],
            })
        except Exception:
            continue

    for cid in _top_clusters(8):
        try:
            r = forecast("cluster", cid, metric=metric, horizon=horizon)
            if r["history_points"] == 0:
                continue
            esc = r["escalation"]
            ranked.append({
                "entity": "cluster", "id": cid,
                "ratio": esc["ratio"], "escalating": esc["escalating"],
                "recent_mean": esc["recent_mean"], "forecast_mean": esc["forecast_mean"],
                "source": r["source"],
            })
        except Exception:
            continue

    ranked.sort(key=lambda x: x["ratio"], reverse=True)
    return {"horizon": horizon, "metric": metric, "ranked": ranked}
