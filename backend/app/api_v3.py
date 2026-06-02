"""AEGIS v3 — DEEP grounded reasoning API (api_v3 APIRouter).

A single FastAPI ``APIRouter`` that exposes the v3 "deep reasoning" surface on
top of the real **voc360** Voice-of-Customer database. Every number, label and
citizen quote it returns is RETRIEVED from real rows (``the_data``,
``ril_problem_clusters``, ``ril_text_segments``, ``ril_cluster_members``) or
from the existing deterministic engines (``rootcause``, ``cluster_link``,
``graph_builder``, ``mesa_sim``). The local LLM (``llm.narrate``) is used ONLY
to *phrase* facts that were already retrieved — it never invents counts,
services, clusters or causes. If the model is down the deterministic
``llm.grounded_summary`` / inline templates ARE the answer.

Endpoints (all wrapped → grounded fallback, never 500):
  GET  /api/forecast        ?entity=service|cluster&key=&metric=volume|sentiment&horizon=30
  GET  /api/forecast/escalations   ?horizon=14
  GET  /api/forecast/status
  POST /api/whys            body {type:"service"|"cluster"|"all", key?, max_depth?}
  GET  /api/rootcause-graph ?type=&key=&depth=5
  GET  /api/validate        ?cluster_id=&service=    (or ?case=)
  GET  /api/validate/rank   ?limit=8
  POST /api/ask             body {question, case?}
  GET  /api/suggest         ?type=&key=&limit=8

Optional v3 helper modules (``whys``, ``validate``, ``suggest``, ``qa``,
``forecaster``) are imported with graceful fallback: if a module is absent or
errors, this router falls back to an inline grounded implementation built from
the SAME real engines, so the surface is always live.

``main.py`` includes this with the same ``try/except include_router`` pattern it
already uses for ``main_v2.router``::

    try:
        from . import api_v3
        app.include_router(api_v3.router)
    except Exception:
        pass
"""
from __future__ import annotations

import datetime as _dt
import math
import re
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Body, Query

# --------------------------------------------------------------------------- #
# Hard dependencies that are always present in the backend (import-safe).      #
# --------------------------------------------------------------------------- #
from . import db  # read-only voc360 access: db.fetchall / db.fetchone / db.health

# Real deterministic engines — import each defensively so one missing module
# never takes the whole router down on import.
try:
    from . import rootcause
except Exception:  # pragma: no cover
    rootcause = None  # type: ignore

try:
    from . import cluster_link
except Exception:  # pragma: no cover
    cluster_link = None  # type: ignore

try:
    from . import graph_builder
except Exception:  # pragma: no cover
    graph_builder = None  # type: ignore

try:
    from . import mesa_sim
except Exception:  # pragma: no cover
    mesa_sim = None  # type: ignore

try:
    from . import llm
except Exception:  # pragma: no cover
    llm = None  # type: ignore

try:
    from . import main_v2  # for translate_label
except Exception:  # pragma: no cover
    main_v2 = None  # type: ignore

# --------------------------------------------------------------------------- #
# OPTIONAL v3 helper modules — graceful fallback to inline implementations.    #
# Never hard-depend on torch / timesfm: forecaster lazy-loads behind an env.   #
# --------------------------------------------------------------------------- #
try:
    from . import forecaster  # forecast_series / escalation / scan_escalations
    _HAS_FORECASTER = True
except Exception:  # pragma: no cover
    forecaster = None  # type: ignore
    _HAS_FORECASTER = False

try:
    from . import whys  # ask_whys
    _HAS_WHYS = True
except Exception:  # pragma: no cover
    whys = None  # type: ignore
    _HAS_WHYS = False

try:
    from . import validate as _validate_mod  # validate_case
    _HAS_VALIDATE = True
except Exception:  # pragma: no cover
    _validate_mod = None  # type: ignore
    _HAS_VALIDATE = False

try:
    from . import suggest as _suggest_mod  # suggest
    _HAS_SUGGEST = True
except Exception:  # pragma: no cover
    _suggest_mod = None  # type: ignore
    _HAS_SUGGEST = False

try:
    from . import qa as _qa_mod  # ask
    _HAS_QA = True
except Exception:  # pragma: no cover
    _qa_mod = None  # type: ignore
    _HAS_QA = False


router = APIRouter()

# --------------------------------------------------------------------------- #
# AEGIS palette (frontend tokens) — surfaced so clients can theme consistently #
# --------------------------------------------------------------------------- #
AEGIS_TOKENS = {
    "bg": "#0A0A0B", "sidebar": "#0B0B0D", "card": "#131417", "cardhi": "#181A1E",
    "border": "#212228", "soft": "#1A1B20", "txt": "#ECEDEE", "muted": "#8B8D96",
    "faint": "#62646D", "blue": "#3B82F6", "danger": "#F04359", "good": "#34D399",
    "warn": "#FBBF24",
}

# Negativity predicate matches api_kpis convention exactly.
_NEG_SQL = (
    "(lower(sentiment_label) like 'negative%%' "
    "or lower(sentiment_label) like 'high_severity%%')"
)


# =========================================================================== #
# Small grounded helpers (all read-only, all degrade to safe values).         #
# =========================================================================== #
def _translate(label_ar: Optional[str], label_en: Optional[str] = None) -> str:
    """English gloss for a cluster/service label, via main_v2 when available."""
    if main_v2 is not None:
        try:
            return main_v2.translate_label(label_ar, label_en)
        except Exception:
            pass
    if label_en and str(label_en).strip():
        return str(label_en).strip()
    return (str(label_ar).strip() if label_ar else "") or "Unlabelled cluster"


def _safe_narrate(prompt: str, context: Dict[str, Any]) -> str:
    """Phrase retrieved facts via the local LLM; never raise, never invent.

    Falls back to llm.grounded_summary, then to the caller-provided summary in
    ``context['summary']``. The LLM is bound to narrate ONLY the given facts.
    """
    if llm is not None:
        try:
            txt = llm.narrate(prompt, context)
            if txt and str(txt).strip():
                return str(txt).strip()
        except Exception:
            pass
        try:
            txt = llm.grounded_summary(context)
            if txt and str(txt).strip():
                return str(txt).strip()
        except Exception:
            pass
    return str(context.get("summary") or "").strip()


def _service_exists(service: str) -> int:
    """Real signal count for a service_id (0 if unknown). Read-only."""
    try:
        row = db.fetchone(
            "select count(*) c from the_data where service_id = %(svc)s",
            ({"svc": service}),
        )
        return int(row["c"]) if row else 0
    except Exception:
        return 0


def _cluster_row(cluster_id: str) -> Optional[Dict[str, Any]]:
    """Fetch the real ril_problem_clusters row for a cluster_id."""
    try:
        return db.fetchone(
            """
            select cluster_id, canonical_label_ar, canonical_label_en, service_id,
                   coalesce(member_count,0) member_count,
                   coalesce(severity_avg,0) severity_avg,
                   first_seen, last_seen, status
            from ril_problem_clusters where cluster_id = %(cid)s
            """,
            ({"cid": cluster_id}),
        )
    except Exception:
        return None


def _cluster_services(cluster_id: str) -> List[Tuple[str, int]]:
    if cluster_link is not None:
        try:
            return cluster_link.cluster_services(cluster_id)
        except Exception:
            pass
    return []


def _cluster_signals(cluster_id: str) -> int:
    if cluster_link is not None:
        try:
            return int(cluster_link.cluster_signals(cluster_id))
        except Exception:
            pass
    return 0


def _cluster_segments(cluster_id: str, limit: int = 60) -> List[str]:
    """Member problem-segments for a cluster, most-representative first."""
    try:
        rows = db.fetchall(
            """
            select s.segment_text
            from ril_cluster_members m
            join ril_text_segments s on s.segment_id = m.segment_id
            where m.cluster_id = %(cid)s and length(s.segment_text) > 8
            order by m.distance_to_centroid asc nulls last
            limit %(lim)s
            """,
            ({"cid": cluster_id, "lim": limit}),
        )
        return [r["segment_text"] for r in rows if r.get("segment_text")]
    except Exception:
        return []


def _resolve_case_to_cluster(case: str) -> Optional[str]:
    """Resolve a free-text/case key to a cluster_id (cluster-first, else service
    → dominant cluster). Mirrors graph_builder/whys resolution. Read-only."""
    if not case:
        return None
    # direct cluster id?
    row = _cluster_row(case)
    if row:
        return row["cluster_id"]
    # fuzzy cluster-label match
    try:
        r = db.fetchone(
            """
            select cluster_id
            from ril_problem_clusters
            where coalesce(member_count,0) > 1
              and (canonical_label_ar ilike %(q)s or canonical_label_en ilike %(q)s
                   or description ilike %(q)s)
            order by coalesce(member_count,0) * (0.5 + coalesce(severity_avg,0)) desc
            limit 1
            """,
            ({"q": f"%{case}%"}),
        )
        if r:
            return r["cluster_id"]
    except Exception:
        pass
    # service → dominant cluster via recovered text edges
    if cluster_link is not None and _service_exists(case) > 0:
        try:
            edges = [e for e in cluster_link.service_cluster_edges() if e[0] == case]
            if edges:
                edges.sort(key=lambda e: e[2], reverse=True)
                return edges[0][1]
        except Exception:
            pass
    return None


# =========================================================================== #
# Inline forecasting fallback (used only if forecaster module is absent).      #
# Pure-numpy seasonal-naive + EWMA drift — zero heavy deps, always available.  #
# =========================================================================== #
def _inline_forecast_series(y: List[float], horizon: int = 30, season: int = 7) -> Dict[str, Any]:
    try:
        import numpy as np  # numpy is already installed in the backend
    except Exception:
        # last-ditch pure-python: flat last value
        last = float(y[-1]) if y else 0.0
        z = [max(0.0, last)] * horizon
        return {"source": "flat", "mean": z, "lo": z, "hi": z}

    hist = np.asarray(y, dtype=float)
    n = len(hist)
    if n == 0:
        z = [0.0] * horizon
        return {"source": "empty", "mean": z, "lo": z, "hi": z}
    s = min(season, n)
    last = hist[-s:]

    def ewma(a, al):
        o = a[0]
        for v in a[1:]:
            o = al * v + (1 - al) * o
        return o

    drift = (ewma(hist, 0.5) - ewma(hist, 0.1)) / max(s, 1)
    sd = float(np.std(hist[-min(n, 4 * s):])) or 1.0
    mean = np.asarray([max(0.0, last[h % s] + drift * (h + 1)) for h in range(horizon)])
    return {
        "source": "seasonal-naive",
        "mean": mean.tolist(),
        "lo": np.clip(mean - 1.28 * sd, 0, None).tolist(),
        "hi": (mean + 1.28 * sd).tolist(),
    }


def _forecast_series(y: List[float], horizon: int = 30, season: int = 7) -> Dict[str, Any]:
    """Forecast via the real forecaster module if present, else inline."""
    if _HAS_FORECASTER and forecaster is not None:
        try:
            out = forecaster.forecast_series(y, horizon=horizon, season=season)
            if isinstance(out, dict) and "mean" in out:
                return out
        except Exception:
            pass
    return _inline_forecast_series(y, horizon=horizon, season=season)


def _escalation(history: List[float], fc_mean: List[float], window: int = 14) -> Dict[str, Any]:
    if _HAS_FORECASTER and forecaster is not None and hasattr(forecaster, "escalation"):
        try:
            return forecaster.escalation(history, fc_mean, window=window)
        except Exception:
            pass
    recent = sum(history[-window:]) / max(1, len(history[-window:])) if history else 0.0
    fut = sum(fc_mean) / max(1, len(fc_mean)) if fc_mean else 0.0
    ratio = (fut / recent) if recent > 0 else (2.0 if fut > 0 else 1.0)
    return {
        "recent_mean": round(float(recent), 3),
        "forecast_mean": round(float(fut), 3),
        "ratio": round(float(ratio), 3),
        "escalating": bool(ratio >= 1.2),
    }


def _daily_series(entity: str, key: Optional[str], metric: str) -> Dict[str, Any]:
    """Dense, gap-filled daily series for a service / cluster / all.

    metric: 'volume' (count) or 'sentiment' (daily negative share).
    For a cluster, aggregates over its recovered service set (record_id does NOT
    join the_data — same parallel-layer rule the graph uses).
    Returns {frame:[{t,v}], values:[float], services:[...], n_points}.
    """
    params: Dict[str, Any] = {}
    clause = ""
    services_used: List[str] = []

    if entity == "service" and key:
        clause = "and service_id = %(key)s"
        params["key"] = key
        services_used = [key]
    elif entity == "cluster" and key:
        svcs = [s for s, _ in _cluster_services(key)][:6]
        services_used = svcs
        if svcs:
            clause = "and service_id = any(%(svcs)s)"
            params["svcs"] = svcs
        else:
            # no recovered services — empty series
            return {"frame": [], "values": [], "services": [], "n_points": 0}

    if metric == "sentiment":
        agg = (
            "avg(case when " + _NEG_SQL.replace("%%", "%") + " then 1.0 else 0.0 end) "
            "filter (where sentiment_label is not null)"
        )
    else:
        agg = "count(*)"

    sql = (
        "select date_trunc('day', nullif(date::text, '')::timestamp)::date ds, "
        f"{agg} v "
        "from the_data "
        "where nullif(date::text, '')::timestamp is not null " + clause + " "
        "group by 1 order by 1"
    )
    try:
        rows = db.fetchall(sql, params or None)
    except Exception:
        rows = []
    if not rows:
        return {"frame": [], "values": [], "services": services_used, "n_points": 0}

    by_day = {r["ds"]: (float(r["v"]) if r["v"] is not None else 0.0) for r in rows}
    d0, d1 = min(by_day), max(by_day)
    frame: List[Dict[str, Any]] = []
    values: List[float] = []
    cur = d0
    carry = 0.0
    one = _dt.timedelta(days=1)
    while cur <= d1:
        if cur in by_day:
            v = by_day[cur]
            carry = v
        else:
            v = 0.0 if metric == "volume" else carry  # fwd-fill rates, 0-fill volume
        frame.append({"t": cur.isoformat(), "v": v})
        values.append(v)
        cur += one
    return {"frame": frame, "values": values, "services": services_used, "n_points": len(values)}


# =========================================================================== #
# 1) FORECAST                                                                  #
# =========================================================================== #
@router.on_event("startup")
def _warm_forecaster() -> None:
    """Warm the (optional) TimesFM model once at boot, off the request hot path."""
    if _HAS_FORECASTER and forecaster is not None and hasattr(forecaster, "_try_load"):
        try:
            forecaster._try_load()
        except Exception:
            pass


@router.get("/api/forecast")
def forecast(
    entity: str = Query("service", pattern="^(service|cluster|all)$"),
    key: Optional[str] = Query(default=None),
    metric: str = Query("volume", pattern="^(volume|sentiment)$"),
    horizon: int = Query(30, ge=1, le=120),
) -> Dict[str, Any]:
    """Per-service/cluster volume or sentiment forecast with escalation verdict.

    Grounded on the real ``the_data`` daily series; TimesFM if ``TIMESFM_MODEL``
    is set, else statistical fallback. ``source`` is the honesty flag.
    """
    try:
        ser = _daily_series(entity, key, metric)
        y = ser["values"]
        if not y:
            return {
                "ok": False, "entity": entity, "key": key, "metric": metric,
                "history": [], "forecast": [], "source": "empty",
                "escalation": {"escalating": False, "ratio": 1.0},
                "narration": f"No {metric} series available for {entity} {key or ''}.".strip(),
                "engine": "forecast",
            }
        fc = _forecast_series(y, horizon=horizon)
        esc = _escalation(y, fc.get("mean", []))

        # future date axis continues the history
        last_day = _dt.date.fromisoformat(ser["frame"][-1]["t"])
        fmean = fc.get("mean", [])
        flo = fc.get("lo", fmean)
        fhi = fc.get("hi", fmean)
        forecast_pts = []
        for i in range(len(fmean)):
            d = (last_day + _dt.timedelta(days=i + 1)).isoformat()
            forecast_pts.append({
                "t": d,
                "mean": round(float(fmean[i]), 3),
                "lo": round(float(flo[i]) if i < len(flo) else fmean[i], 3),
                "hi": round(float(fhi[i]) if i < len(fhi) else fmean[i], 3),
            })

        label = key or ("all services" if entity == "all" else entity)
        verdict = "escalating" if esc["escalating"] else "stable"
        summary = (
            f"{label}: {metric} is {verdict} — recent mean {esc['recent_mean']} "
            f"vs forecast mean {esc['forecast_mean']} ({esc['ratio']}x) over {horizon} days "
            f"[{fc.get('source')}]."
        )
        narration = _safe_narrate(
            "Use ONLY these forecast facts; do not invent numbers.",
            {
                "case": label,
                "stats": {"signals": int(sum(y)) if metric == "volume" else len(y)},
                "summary": summary,
            },
        ) or summary
        return {
            "ok": True, "entity": entity, "key": key, "metric": metric, "horizon": horizon,
            "history": ser["frame"], "forecast": forecast_pts,
            "source": fc.get("source"), "escalation": esc,
            "services": ser["services"], "n_points": ser["n_points"],
            "narration": narration, "engine": "forecast",
        }
    except Exception as e:  # never 500
        return {"ok": False, "entity": entity, "key": key, "metric": metric,
                "history": [], "forecast": [], "source": "error",
                "escalation": {"escalating": False, "ratio": 1.0},
                "error": str(e), "engine": "forecast"}


@router.get("/api/forecast/escalations")
def forecast_escalations(horizon: int = Query(14, ge=1, le=60), top: int = Query(12, ge=1, le=40)) -> Dict[str, Any]:
    """Rank services (and top clusters) by projected near-term volume growth."""
    if _HAS_FORECASTER and forecaster is not None and hasattr(forecaster, "scan_escalations"):
        try:
            ranked = forecaster.scan_escalations(horizon=horizon)
            return {"ok": True, "horizon": horizon, "escalations": ranked, "engine": "forecast"}
        except Exception:
            pass
    out: List[Dict[str, Any]] = []
    # services
    try:
        svc_rows = db.fetchall(
            """
            select service_id, count(*) n
            from the_data
            where service_id is not null
              and nullif(date::text, '')::timestamp is not null
            group by 1 having count(distinct date_trunc('day', nullif(date::text, '')::timestamp)) >= 28
            order by n desc limit %(top)s
            """,
            ({"top": top}),
        )
    except Exception:
        svc_rows = []
    for r in svc_rows:
        svc = r["service_id"]
        ser = _daily_series("service", svc, "volume")
        y = ser["values"]
        if not y:
            continue
        fc = _forecast_series(y, horizon=horizon)
        esc = _escalation(y, fc.get("mean", []))
        if esc["escalating"]:
            out.append({
                "level": "service", "key": svc, "ratio": esc["ratio"],
                "recent_mean": esc["recent_mean"], "forecast_mean": esc["forecast_mean"],
                "source": fc.get("source"),
            })
    # top clusters
    if rootcause is not None:
        try:
            for rc in rootcause.rank_root_causes(8):
                cid = rc["cluster_id"]
                ser = _daily_series("cluster", cid, "volume")
                y = ser["values"]
                if not y:
                    continue
                fc = _forecast_series(y, horizon=horizon)
                esc = _escalation(y, fc.get("mean", []))
                if esc["escalating"]:
                    out.append({
                        "level": "cluster", "key": cid,
                        "label": rc.get("label_en") or rc.get("label_ar"),
                        "ratio": esc["ratio"], "recent_mean": esc["recent_mean"],
                        "forecast_mean": esc["forecast_mean"], "source": fc.get("source"),
                    })
        except Exception:
            pass
    out.sort(key=lambda d: d["ratio"], reverse=True)
    return {"ok": True, "horizon": horizon, "escalations": out[:top], "engine": "forecast"}


@router.get("/api/forecast/status")
def forecast_status() -> Dict[str, Any]:
    """Honest report of which forecasting backend is active."""
    if _HAS_FORECASTER and forecaster is not None:
        try:
            if hasattr(forecaster, "_try_load"):
                forecaster._try_load()
            return {
                "ok": True,
                "backend": getattr(forecaster, "_BACKEND", "stat"),
                "model_loaded": getattr(forecaster, "_MODEL", None) is not None,
                "load_error": getattr(forecaster, "_LOAD_ERR", None),
            }
        except Exception as e:
            return {"ok": True, "backend": "stat", "model_loaded": False, "load_error": str(e)}
    return {"ok": True, "backend": "inline-stat", "model_loaded": False,
            "load_error": "forecaster module not present (using inline seasonal-naive)"}


# =========================================================================== #
# 2) WHYS — 5-whys chain + root-cause graph                                   #
# =========================================================================== #
def _inline_extract_subthemes(segments: List[str], n: int = 6) -> List[Dict[str, Any]]:
    """Arabic-aware keyword frequency over problem-segments (no external deps)."""
    tashkeel = re.compile(r"[ؗ-ًؚ-ْٰـ]")
    stop = {
        "في", "من", "على", "الى", "إلى", "عن", "مع", "هذا", "هذه", "ذلك", "التي",
        "الذي", "كان", "قد", "ما", "لا", "ان", "أن", "إن", "هو", "هي", "كل",
        "the", "and", "for", "with", "this", "that", "are", "was", "not",
    }
    counts: Dict[str, int] = {}
    samples: Dict[str, List[str]] = {}
    total = 0
    for seg in segments:
        norm = tashkeel.sub("", seg or "")
        norm = norm.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ى", "ي").replace("ة", "ه")
        toks = [t for t in re.split(r"[^\w؀-ۿ]+", norm) if len(t) >= 3 and t.lower() not in stop]
        for t in set(toks):
            counts[t] = counts.get(t, 0) + 1
            if t not in samples and seg:
                samples[t] = [seg[:140]]
            elif len(samples.get(t, [])) < 2 and seg and seg[:140] not in samples.get(t, []):
                samples.setdefault(t, []).append(seg[:140])
        total += 1
    items = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    out = []
    for term, c in items[:n]:
        if c < 2:
            continue
        out.append({
            "term": term, "count": c,
            "share": round(c / max(1, total), 3),
            "samples": samples.get(term, []),
        })
    return out


def _inline_whys(start: Dict[str, Any], max_depth: int = 5) -> Dict[str, Any]:
    """Grounded 5-whys fallback when the whys module is absent.

    service → dominant cluster → sub-themes → specific phrase, each step grounded
    in real counts + evidence; emits a reactflow-shaped root-cause graph.
    """
    etype = (start.get("type") or "all").lower()
    key = start.get("key")
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    chain: List[Dict[str, Any]] = []

    # depth 0 — the symptom (service or national)
    cluster_id: Optional[str] = None
    if etype == "cluster" and key:
        cluster_id = key
        root_id = f"cl::{key[:8]}"
    elif etype == "service" and key:
        root_id = f"svc::{key}"
        nodes.append({"id": root_id, "type": "service", "label": key, "value": _service_exists(key),
                      "severity": "warn", "depth": 0})
        cluster_id = _resolve_case_to_cluster(key)
    else:
        # national — take the top root cause
        if rootcause is not None:
            try:
                top = rootcause.rank_root_causes(1)
                if top:
                    cluster_id = top[0]["cluster_id"]
            except Exception:
                pass
        root_id = "case::all"
        nodes.append({"id": root_id, "type": "service", "label": "VOC 360 · National",
                      "value": 0, "severity": "alert", "depth": 0})

    if not cluster_id:
        return {
            "start": start, "chain": [], "root": None,
            "graph": {"nodes": nodes, "edges": edges, "stats": {"depth": 0}},
            "narration": f"No dominant cluster could be grounded for {etype} {key or ''}.".strip(),
            "method": "inline",
        }

    crow = _cluster_row(cluster_id) or {}
    label_ar = crow.get("canonical_label_ar") or ""
    label_en = _translate(label_ar, crow.get("canonical_label_en"))
    members = int(crow.get("member_count") or 0)
    sev = round(float(crow.get("severity_avg") or 0.0), 2)
    signals = _cluster_signals(cluster_id)
    cid_node = f"cl::{cluster_id[:8]}"
    nodes.append({"id": cid_node, "type": "cluster", "label": label_en[:46], "label_ar": label_ar[:80],
                  "value": members, "severity": "alert" if sev >= 0.5 else "warn", "depth": 1,
                  "signals": signals, "members": members, "severity_avg": sev})
    edges.append({"source": root_id, "target": cid_node, "weight": members or 1, "kind": "dominant_cluster"})

    segs = _cluster_segments(cluster_id)
    evidence1 = [s[:140] for s in segs[:3]]
    conf1 = max(0.0, min(1.0, 0.45 * min(1, signals / 60.0) + 0.35 + 0.20 * sev))
    chain.append({
        "depth": 1, "node_id": cid_node, "kind": "dominant_cluster",
        "question": f"Why does {key or 'this service'} generate the most negative signals?",
        "answer": f"The dominant problem cluster is '{label_en}'.",
        "because": label_ar, "because_en": label_en,
        "evidence": evidence1, "signals": signals, "members": members, "severity_avg": sev,
        "confidence": round(conf1, 2),
    })

    # depth 2 — sub-themes
    subs = _inline_extract_subthemes(segs, n=6)
    root_step = chain[-1]
    if subs and max_depth >= 2:
        top = subs[0]
        sub_node = f"sub::{cluster_id[:8]}::{top['term']}"
        nodes.append({"id": sub_node, "type": "subtheme", "label": top["term"],
                      "value": top["count"], "severity": "warn", "depth": 2,
                      "signals": top["count"]})
        edges.append({"source": cid_node, "target": sub_node, "weight": top["count"], "kind": "subtheme"})
        # sibling sub-themes as side branches
        for s in subs[1:4]:
            sib = f"sub::{cluster_id[:8]}::{s['term']}"
            nodes.append({"id": sib, "type": "subtheme", "label": s["term"], "value": s["count"],
                          "severity": "calm", "depth": 2, "signals": s["count"]})
            edges.append({"source": cid_node, "target": sib, "weight": s["count"], "kind": "subtheme"})
        conf2 = max(0.0, min(1.0, 0.45 * min(1, top["count"] / 60.0) + 0.35 * top["share"] + 0.20 * sev))
        chain.append({
            "depth": 2, "node_id": sub_node, "kind": "subtheme",
            "question": f"Why is '{label_en}' the dominant cluster?",
            "answer": f"The leading sub-theme is «{top['term']}» ({top['count']} segments).",
            "because": top["term"], "because_en": top["term"],
            "evidence": top.get("samples", []), "signals": top["count"],
            "subthemes": subs, "confidence": round(conf2, 2),
        })
        root_step = chain[-1]

        # depth 3 — specific phrase via bigram over filtered segments
        if max_depth >= 3:
            filtered = [s for s in segs if top["term"] in s]
            if filtered:
                phrases = _inline_extract_subthemes(filtered, n=4)
                if phrases:
                    p = phrases[0]
                    p_node = f"ph::{cluster_id[:8]}::{p['term']}"
                    nodes.append({"id": p_node, "type": "phrase", "label": p["term"],
                                  "value": p["count"], "severity": "warn", "depth": 3,
                                  "signals": p["count"]})
                    edges.append({"source": sub_node, "target": p_node, "weight": p["count"], "kind": "root_phrase"})
                    conf3 = max(0.0, min(1.0, 0.45 * min(1, p["count"] / 60.0) + 0.35 * p["share"] + 0.20 * sev))
                    chain.append({
                        "depth": 3, "node_id": p_node, "kind": "root_phrase",
                        "question": f"Why does «{top['term']}» recur?",
                        "answer": f"It concentrates on «{p['term']}» ({p['count']} segments).",
                        "because": p["term"], "because_en": p["term"],
                        "evidence": p.get("samples", []), "signals": p["count"],
                        "confidence": round(conf3, 2),
                    })
                    root_step = chain[-1]

    stats = {"depth": len(chain), "nodes": len(nodes), "edges": len(edges),
             "signals": signals, "members": members}
    summary = (
        f"Why-chain for {key or 'the national VOC graph'}: dominant cluster '{label_en}' "
        f"({members} reports, severity {sev}, {signals} recovered signals)"
        + (f"; leading sub-theme «{root_step.get('because')}»." if len(chain) > 1 else ".")
    )
    narration = _safe_narrate(
        "Rephrase ONLY these why-steps; cite counts exactly; add no new cause.",
        {"case": key, "summary": summary,
         "root_causes": [{"label_ar": label_ar, "label_en": label_en, "members": members,
                          "severity_avg": sev, "signal_count": signals, "evidence": evidence1}]},
    ) or summary
    return {
        "start": start, "chain": chain, "root": root_step,
        "graph": {"nodes": nodes, "edges": edges, "stats": stats},
        "narration": narration, "method": "inline",
    }


def _run_whys(start: Dict[str, Any], max_depth: int) -> Dict[str, Any]:
    if _HAS_WHYS and whys is not None:
        try:
            out = whys.ask_whys(start, max_depth=max_depth)
            if isinstance(out, dict) and "chain" in out:
                out.setdefault("method", "whys")
                return out
        except Exception:
            pass
    return _inline_whys(start, max_depth=max_depth)


@router.post("/api/whys")
def whys_endpoint(body: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    """5-whys chain (symptom → dominant cluster → sub-themes → root) + graph.

    Body: ``{type:"service"|"cluster"|"all", key?, max_depth?}``.
    Also accepts ``{case, cluster_id, max_depth}`` (D-api shape).
    """
    try:
        etype = body.get("type")
        key = body.get("key")
        if not etype:
            if body.get("cluster_id"):
                etype, key = "cluster", body.get("cluster_id")
            elif body.get("case"):
                etype, key = "service", body.get("case")
            else:
                etype = "all"
        max_depth = int(body.get("max_depth") or 5)
        max_depth = max(1, min(5, max_depth))
        start = {"type": etype, "key": key}
        return {"ok": True, **_run_whys(start, max_depth)}
    except Exception as e:  # never 500
        return {"ok": False, "error": str(e), "chain": [], "root": None,
                "graph": {"nodes": [], "edges": [], "stats": {}}, "method": "error"}


@router.get("/api/rootcause-graph")
def rootcause_graph(
    type: str = Query("all", pattern="^(service|cluster|all)$"),
    key: Optional[str] = Query(default=None),
    depth: int = Query(5, ge=1, le=5),
) -> Dict[str, Any]:
    """The why-chain graph alone (reactflow), reusing the whys builder."""
    try:
        out = _run_whys({"type": type, "key": key}, depth)
        return {"ok": True, "type": type, "key": key,
                "graph": out.get("graph", {"nodes": [], "edges": [], "stats": {}}),
                "root": out.get("root"), "method": out.get("method")}
    except Exception as e:
        # last resort: the existing VOC dependency graph
        if graph_builder is not None and type != "cluster":
            try:
                g = graph_builder.build_graph(key)
                return {"ok": True, "type": type, "key": key, "graph": g, "method": "graph_builder"}
            except Exception:
                pass
        return {"ok": False, "error": str(e),
                "graph": {"nodes": [], "edges": [], "stats": {}}, "method": "error"}


# =========================================================================== #
# 3) VALIDATE — is the root cause real?                                        #
# =========================================================================== #
def _inline_validate(cluster_id: str, service: Optional[str] = None) -> Dict[str, Any]:
    """Five grounded checks → verdict valid|weak|insufficient + confidence.

    Used when the validate module is absent. Every detail is a retrieved fact.
    """
    checks: List[Dict[str, Any]] = []
    crow = _cluster_row(cluster_id)
    if not crow:
        return {"ok": False, "verdict": "insufficient", "confidence": 0.0, "score": 0,
                "target": cluster_id, "checks": [],
                "summary": f"No cluster '{cluster_id}' in ril_problem_clusters.",
                "engine": "validate"}

    label_en = _translate(crow.get("canonical_label_ar"), crow.get("canonical_label_en"))
    members = int(crow.get("member_count") or 0)
    sev = round(float(crow.get("severity_avg") or 0.0), 2)
    signals = _cluster_signals(cluster_id)
    svcs = _cluster_services(cluster_id)
    owner = service or (svcs[0][0] if svcs else None)

    # (1) coverage 0.30
    owner_total = _service_exists(owner) if owner else 0
    coverage = (signals / owner_total) if owner_total else 0.0
    cov_pass = (signals >= 20) or (coverage >= 0.05)
    checks.append({"name": "coverage", "weight": 0.30, "pass": cov_pass,
                   "score": min(1.0, signals / 60.0),
                   "detail": f"{signals} recovered signals ≈ {round(coverage*100,1)}% of {owner or 'owner'}'s {owner_total} reports",
                   "value": signals})

    # (2) evidence sufficiency 0.20
    try:
        erow = db.fetchone(
            """
            select count(*) m, count(distinct left(s.segment_text,60)) d
            from ril_cluster_members m2
            join ril_text_segments s on s.segment_id = m2.segment_id
            where m2.cluster_id = %(cid)s
            """,
            ({"cid": cluster_id}),
        ) or {}
    except Exception:
        erow = {}
    mcount = int(erow.get("m") or 0)
    distinct = int(erow.get("d") or 0)
    ev_pass = (mcount >= 5) and (distinct >= 3)
    samples = _cluster_segments(cluster_id, limit=3)
    checks.append({"name": "evidence_sufficiency", "weight": 0.20, "pass": ev_pass,
                   "score": min(1.0, mcount / 12.0),
                   "detail": f"{mcount} clustered segments, {distinct} distinct texts",
                   "value": mcount, "evidence": samples})

    # (3) temporal trend 0.20
    ser = _daily_series("cluster", cluster_id, "volume")
    y = ser["values"]
    esc = {"escalating": False, "ratio": 1.0, "recent_mean": 0.0, "forecast_mean": 0.0}
    if y:
        fc = _forecast_series(y, horizon=14)
        esc = _escalation(y, fc.get("mean", []))
    checks.append({"name": "temporal_trend", "weight": 0.20, "pass": bool(esc["escalating"]),
                   "score": min(1.0, max(0.0, (esc["ratio"] - 0.8))),
                   "detail": f"forecast {esc['forecast_mean']} vs recent {esc['recent_mean']} ({esc['ratio']}x)",
                   "value": esc["ratio"]})

    # (4) sim impact 0.20
    sim_delta = 0.0
    if mesa_sim is not None and owner:
        try:
            sim = mesa_sim.simulate(case=owner, intervene=True,
                                    intervention_node=f"cluster:{cluster_id}")
            sim_delta = float((sim.get("delta") or {}).get("mean_negativity_final") or 0.0)
        except Exception:
            sim_delta = 0.0
    sim_pass = sim_delta > 0.002
    checks.append({"name": "sim_impact", "weight": 0.20, "pass": sim_pass,
                   "score": min(1.0, max(0.0, sim_delta * 50)),
                   "detail": f"Δ mean-negativity after intervening = {round(sim_delta,4)}",
                   "value": round(sim_delta, 4)})

    # (5) symptom vs cause 0.10 — Arabic specificity heuristic
    cause_kw = ("تأخير", "رسوم", "نظام", "خطأ", "حفر", "منصة", "تطبيق", "رد", "صرف", "إصدار")
    text = (crow.get("canonical_label_ar") or "") + " " + " ".join(samples)
    specific = any(k in text for k in cause_kw)
    checks.append({"name": "symptom_vs_cause", "weight": 0.10, "pass": specific,
                   "score": 1.0 if specific else 0.3,
                   "detail": "label/evidence names a specific mechanism" if specific else "reads as a generic symptom",
                   "value": specific})

    confidence = sum(c["score"] * c["weight"] for c in checks)
    score100 = round(100 * confidence)
    n_pass = sum(1 for c in checks if c["pass"])
    if score100 >= 65 and cov_pass and ev_pass and n_pass >= 3:
        verdict = "valid"
    elif score100 >= 40 and n_pass >= 2:
        verdict = "weak"
    else:
        verdict = "insufficient"

    summary = (
        f"Verdict: {verdict} — '{label_en}' (cluster {cluster_id[:8]}) "
        f"confidence {round(confidence*100)}%. {signals} signals, {members} segments, "
        f"trend {('rising' if esc['escalating'] else 'flat')}, sim Δ {round(sim_delta,4)}."
    )
    narration = _safe_narrate(
        "Use ONLY these validation facts; if a number is missing say unknown.",
        {"case": owner, "summary": summary,
         "root_causes": [{"label_ar": crow.get("canonical_label_ar"), "label_en": label_en,
                          "members": members, "severity_avg": sev, "signal_count": signals,
                          "evidence": samples}]},
    ) or summary
    return {
        "ok": True, "verdict": verdict, "confidence": round(confidence, 3), "score": score100,
        "target": {"cluster_id": cluster_id, "label_en": label_en, "service": owner,
                   "members": members, "severity_avg": sev},
        "checks": checks, "summary": narration, "engine": "validate",
    }


def _run_validate(cluster_id: str, service: Optional[str]) -> Dict[str, Any]:
    if _HAS_VALIDATE and _validate_mod is not None:
        try:
            out = _validate_mod.validate_case(cluster_id, service=service)
            if isinstance(out, dict) and "verdict" in out:
                out.setdefault("engine", "validate")
                out.setdefault("ok", True)
                return out
        except Exception:
            pass
    return _inline_validate(cluster_id, service)


@router.get("/api/validate")
def validate_endpoint(
    cluster_id: Optional[str] = Query(default=None),
    service: Optional[str] = Query(default=None),
    case: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    """Validate a root cause: coverage, evidence, trend, sim-impact, specificity."""
    try:
        cid = cluster_id
        if not cid and case:
            cid = _resolve_case_to_cluster(case)
        if not cid and service:
            cid = _resolve_case_to_cluster(service)
        if not cid:
            return {"ok": False, "verdict": "insufficient", "confidence": 0.0, "score": 0,
                    "summary": "No cluster_id resolved — pass cluster_id, service, or case.",
                    "checks": [], "engine": "validate"}
        return _run_validate(cid, service)
    except Exception as e:
        return {"ok": False, "verdict": "insufficient", "confidence": 0.0, "score": 0,
                "error": str(e), "checks": [], "engine": "validate"}


@router.get("/api/validate/rank")
def validate_rank(limit: int = Query(8, ge=1, le=20)) -> Dict[str, Any]:
    """Validate the top ranked root causes — which are 'valid' vs 'weak'."""
    out: List[Dict[str, Any]] = []
    if rootcause is not None:
        try:
            for rc in rootcause.rank_root_causes(limit):
                try:
                    v = _run_validate(rc["cluster_id"], None)
                except Exception:
                    v = {"verdict": "insufficient", "confidence": 0.0, "score": 0}
                out.append({
                    "cluster_id": rc["cluster_id"],
                    "label_en": rc.get("label_en") or rc.get("label_ar"),
                    "members": rc.get("members"), "severity_avg": rc.get("severity_avg"),
                    "verdict": v.get("verdict"), "confidence": v.get("confidence"),
                    "score": v.get("score"),
                })
        except Exception:
            pass
    return {"ok": True, "ranked": out, "engine": "validate"}


# =========================================================================== #
# 4) ASK — grounded Q&A                                                        #
# =========================================================================== #
def _inline_ask(question: str, case: Optional[str] = None) -> Dict[str, Any]:
    """Minimal grounded Q&A fallback when the qa module is absent.

    Retrieves real national root-cause facts and lets the LLM phrase ONLY those
    facts; no facts ⇒ grounded:false + fixed answer. Never fabricates.
    """
    facts: List[Dict[str, Any]] = []
    citations: List[Dict[str, Any]] = []
    root_causes: List[Dict[str, Any]] = []

    # resolve a case to a cluster if possible (grounds "why is X…")
    resolved = _resolve_case_to_cluster(case) if case else None
    if resolved and rootcause is not None:
        crow = _cluster_row(resolved) or {}
        label_en = _translate(crow.get("canonical_label_ar"), crow.get("canonical_label_en"))
        members = int(crow.get("member_count") or 0)
        sev = round(float(crow.get("severity_avg") or 0.0), 2)
        signals = _cluster_signals(resolved)
        samples = _cluster_segments(resolved, limit=3)
        facts += [
            {"label": "dominant cluster", "value": label_en},
            {"label": "member reports", "value": members},
            {"label": "severity", "value": sev},
            {"label": "recovered signals", "value": signals},
        ]
        citations.append({"type": "cluster", "id": resolved, "label": label_en})
        for s in samples:
            citations.append({"type": "segment", "id": resolved, "text": s[:140]})
        root_causes = [{"label_ar": crow.get("canonical_label_ar"), "label_en": label_en,
                        "members": members, "severity_avg": sev, "signal_count": signals,
                        "evidence": samples}]
    elif rootcause is not None:
        try:
            ranked = rootcause.rank_root_causes(5)
        except Exception:
            ranked = []
        root_causes = ranked
        for rc in ranked[:3]:
            facts.append({"label": rc.get("label_en") or rc.get("label_ar"),
                          "value": f"{rc.get('members')} reports, severity {rc.get('severity_avg')}"})
            citations.append({"type": "cluster", "id": rc["cluster_id"],
                              "label": rc.get("label_en") or rc.get("label_ar")})

    grounded = bool(facts)
    if not grounded:
        return {"question": question, "intent": "overview", "grounded": False,
                "answer": "I don't have voc360 data to answer that.",
                "facts": [], "citations": [], "engine": "fallback", "followups": []}

    summary_bits = "; ".join(f"{f['label']}: {f['value']}" for f in facts[:4])
    summary = f"Grounded facts for '{case or 'national'}': {summary_bits}."
    answer = _safe_narrate(
        "Answer ONLY from these FACTS; add no value not present; if unanswerable "
        "reply exactly \"I don't have voc360 data to answer that.\"",
        {"case": case, "question": question, "summary": summary, "root_causes": root_causes},
    ) or summary
    return {
        "question": question, "intent": "root_cause" if resolved else "overview",
        "grounded": True, "answer": answer, "facts": facts, "citations": citations,
        "engine": "llm" if (llm is not None and llm.available()) else "fallback",
        "followups": [
            f"What are the dominant sub-themes inside {case or 'the top cluster'}?",
            f"Is {case or 'the top root cause'} forecast to escalate?",
            f"Validate: is {case or 'the top cluster'} really the root cause?",
        ],
    }


@router.post("/api/ask")
def ask_endpoint(body: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    """Grounded Q&A: parse intent → retrieve real voc360 facts → phrase them."""
    try:
        question = str(body.get("question") or "").strip()
        case = body.get("case")
        if not question:
            return {"ok": False, "grounded": False,
                    "answer": "Ask a question about voc360 services, clusters or forecasts.",
                    "facts": [], "citations": [], "engine": "fallback", "followups": []}
        if _HAS_QA and _qa_mod is not None:
            try:
                out = _qa_mod.ask(question, case=case)
                if isinstance(out, dict) and "answer" in out:
                    out.setdefault("ok", True)
                    return out
            except Exception:
                pass
        return {"ok": True, **_inline_ask(question, case)}
    except Exception as e:
        return {"ok": False, "grounded": False, "answer": "I don't have voc360 data to answer that.",
                "error": str(e), "facts": [], "citations": [], "engine": "error", "followups": []}


# =========================================================================== #
# 5) SUGGEST — high-value questions per scope                                  #
# =========================================================================== #
def _inline_suggest(ctx_type: str, key: Optional[str], limit: int) -> List[Dict[str, Any]]:
    """Templated, grounded suggestions (gated on real counts). Never LLM-made."""
    out: List[Dict[str, Any]] = []

    def add(q: str, intent: str, params: Dict[str, Any], why: str, score: float, needs=None):
        sid = abs(hash((q, intent))) % (10 ** 9)
        out.append({"id": str(sid), "q": q, "intent": intent, "params": params,
                    "why_useful": why, "score": round(score, 2), "needs": needs or []})

    if ctx_type == "service" and key:
        n = _service_exists(key)
        if n >= 20:
            score = math.log1p(n)
            add(f"Which root-cause cluster drives the most negative signals for {key}?",
                "why_chain", {"type": "service", "key": key},
                "grounds the service to its dominant cluster", score)
            add(f"How has {key}'s daily signal volume trended — is it escalating?",
                "forecast_volume", {"entity": "service", "key": key, "metric": "volume"},
                "forward-looking escalation check", score)
            add(f"What is the negative-vs-positive sentiment split for {key}?",
                "metric_breakdown", {"service": key, "dim": "sentiment"},
                "sentiment composition", score * 0.9)
            add(f"What share of {key}'s complaints are high or critical severity?",
                "metric_breakdown", {"service": key, "dim": "severity"},
                "severity profile", score * 0.85)
            add(f"If {key}'s top root cause were fixed, how much would negativity drop?",
                "sim_impact", {"service": key},
                "intervention payoff via simulation", score * 0.8)
    elif ctx_type in ("cluster", "case") and key:
        cid = key if _cluster_row(key) else _resolve_case_to_cluster(key)
        if cid:
            crow = _cluster_row(cid) or {}
            members = int(crow.get("member_count") or 0)
            sev = float(crow.get("severity_avg") or 0.0)
            if members >= 3:
                score = math.log1p(members) * (0.5 + sev)
                lbl = _translate(crow.get("canonical_label_ar"), crow.get("canonical_label_en"))
                add(f"Explain the full why-chain for '{lbl}'.",
                    "why_chain", {"type": "cluster", "key": cid}, "5-whys decomposition", score)
                add(f"What are the dominant sub-themes inside '{lbl}'?",
                    "cluster_subthemes", {"cluster_id": cid}, "citizens' own words", score)
                add(f"Validate: is '{lbl}' really a distinct root cause?",
                    "case_validation", {"cluster_id": cid}, "coverage + evidence + trend", score)
                add(f"Which services own '{lbl}', and what evidence backs it?",
                    "cluster_services", {"cluster_id": cid}, "ownership + signal count", score * 0.9)
                add(f"Is '{lbl}' forecast to escalate over the next 30 days?",
                    "forecast_volume", {"entity": "cluster", "key": cid, "metric": "volume"},
                    "temporal escalation", score * 0.8)
    else:  # national
        if rootcause is not None:
            try:
                ranked = rootcause.rank_root_causes(2)
            except Exception:
                ranked = []
            if ranked:
                base = math.log1p(ranked[0].get("members") or 1)
                add("What are the top root-cause clusters nationwide right now?",
                    "root_cause_rank", {"limit": 5}, "national ranking", base + 2)
                add("Which service or problem is forecast to escalate next?",
                    "escalation_scan", {"horizon": 14}, "forward watchlist", base + 1.5)
                add("Which services have the most negative citizen sentiment right now?",
                    "metric_breakdown", {"dim": "sentiment"}, "national sentiment", base + 1)
                top = ranked[0]
                lbl = top.get("label_en") or top.get("label_ar")
                add(f"Explain the why-chain for the top cause '{lbl}'.",
                    "why_chain", {"type": "cluster", "key": top["cluster_id"]},
                    "drill into #1", base + 1.2)
                if len(ranked) > 1:
                    add(f"Compare '{lbl}' against '{ranked[1].get('label_en') or ranked[1].get('label_ar')}'.",
                        "compare_services", {"a": top["cluster_id"], "b": ranked[1]["cluster_id"]},
                        "prioritisation", base)
    out.sort(key=lambda d: d["score"], reverse=True)
    return out[:limit]


@router.get("/api/suggest")
def suggest_endpoint(
    type: str = Query("national", pattern="^(national|service|cluster|case)$"),
    key: Optional[str] = Query(default=None),
    limit: int = Query(8, ge=1, le=20),
) -> Dict[str, Any]:
    """High-value, grounded suggested questions for a scope → drill-down."""
    try:
        if _HAS_SUGGEST and _suggest_mod is not None:
            try:
                ctx = {"type": type, "key": key}
                sugg = _suggest_mod.suggest(ctx, limit=limit)
                if isinstance(sugg, list):
                    return {"ok": True, "context": ctx, "suggestions": sugg,
                            "grounded": True, "engine": "suggest"}
            except Exception:
                pass
        sugg = _inline_suggest(type, key, limit)
        return {"ok": True, "context": {"type": type, "key": key},
                "suggestions": sugg, "grounded": bool(sugg), "engine": "suggest-inline"}
    except Exception as e:
        return {"ok": False, "context": {"type": type, "key": key},
                "suggestions": [], "grounded": False, "error": str(e), "engine": "suggest"}


# =========================================================================== #
# Meta                                                                         #
# =========================================================================== #
@router.get("/api/v3/health")
def v3_health() -> Dict[str, Any]:
    """v3 surface health + which optional engines are live."""
    try:
        dbh = db.health()
        db_ok = True
    except Exception as e:
        dbh = {"error": str(e)}
        db_ok = False
    return {
        "ok": True, "db_ok": db_ok, "db": dbh,
        "engines": {
            "forecaster": _HAS_FORECASTER, "whys": _HAS_WHYS, "validate": _HAS_VALIDATE,
            "suggest": _HAS_SUGGEST, "qa": _HAS_QA,
            "rootcause": rootcause is not None, "cluster_link": cluster_link is not None,
            "mesa_sim": mesa_sim is not None,
            "llm": (llm is not None and llm.available()) if llm is not None else False,
        },
        "tokens": AEGIS_TOKENS,
    }


__all__ = ["router"]
