"""AEGIS Deer Graph — v2 console router (Tracks 2 & 3 on REAL voc360 data).

This module is an ``APIRouter`` that ``main.py`` includes with
``app.include_router(main_v2.router)``. It adds the remaining console-page
endpoints on top of the existing v1 API (``/api/health``, ``/api/stats``,
``/api/graph``, ``/api/rootcause``, ``/api/flow/run``, ``/api/simulate``) without
touching them, so v1 keeps working unchanged. CORS is already configured in
``main.py``; this router adds no middleware.

Endpoints added here
--------------------
  GET  /api/signals          paginated citizen-signal feed (the_data)        [T2]
  GET  /api/kpis             dashboard KPIs from real voc360 aggregates      [T2]
  GET  /api/signal-volume    time-bucketed signal volume for the chart       [T2]
  GET  /api/solutions        cause→countermeasure 'valid solution' engine    [T3]
  GET  /api/decisions        decision log (read)                              [T2]
  POST /api/decisions        append a decision                                [T2]
  POST /api/narrate          optional LLM narration w/ grounded fallback      [T3]
  GET  /api/graph2           v1 graph + real text-recovered root-cause edges  [T1]

Design stance
-------------
* **Real voc360 columns only.** Every figure traces to ``the_data`` /
  ``ril_problem_clusters`` / ``ril_text_segments`` via the existing read-only
  ``db`` layer and the sibling modules (``api_signals``, ``api_kpis``,
  ``rootcause``, ``cluster_link``/``linker``). No Zarqa demo fixtures.
* **Import-safe with graceful fallbacks.** Every sibling module is imported
  defensively; if one is missing or its DB is unreachable, the corresponding
  endpoint returns a well-formed, grounded fallback (matching the frontend
  ``lib/voc2.ts`` fallback shapes) instead of 500-ing. The router therefore
  imports cleanly even on a machine with no DB and no local LLM.
* **AEGIS tone tokens** (``danger`` / ``good`` / ``warn`` / ``neutral``) and the
  ``source: 'voc360' | 'engine' | 'fallback'`` honesty flags are emitted exactly
  as ``lib/voc2.ts`` expects, so the UI can badge provenance truthfully.
* **Frontend contract adaptation.** The page modules expose Python-native
  signatures (``api_signals.signals(page,size,...)``, ``api_kpis.signal_volume(range)``);
  this router adapts them to the wire contract the frontend client speaks
  (``/api/signals?limit&offset&service_id``, ``/api/signal-volume?bucket`` →
  ``{signals,total,filters}`` / ``{series,bucket,source}``).

Track 3 — Arabic→English label translation is performed at BUILD time (the
``_AR_EN`` map below; no LLM key in env) and used to ground both the solutions
engine and the narration fallback. The optional LLM narration node calls a local
OpenAI-compatible / Ollama server (``LLM_BASE_URL`` default
``http://localhost:11434``, ``LLM_MODEL``) and degrades to a deterministic,
voc360-grounded summary when that server is unreachable.
"""
from __future__ import annotations

import json
import os
import re
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

# ===========================================================================
# Defensive imports — every sibling is optional. The router must import on a
# bare machine (no DB, no LLM, modules built by sibling agents not yet present).
# We try the package form first (app.<mod>) then a flat import, mirroring the
# shim used by deer_flow / api_signals.
# ===========================================================================

def _opt_import(name: str):
    try:
        return __import__(f"{__package__}.{name}", fromlist=[name]) if __package__ \
            else __import__(name)
    except Exception:
        try:
            return __import__(name)
        except Exception:
            return None


db = _opt_import("db")
rootcause = _opt_import("rootcause")
graph_builder = _opt_import("graph_builder")
api_signals = _opt_import("api_signals")
api_kpis = _opt_import("api_kpis")
graph_real = _opt_import("graph_real")
# T1 linker backend: canonical name is ``linker`` (D-pipeline); some build
# branches ship it as ``cluster_link``. Bind to whichever exists.
linker = _opt_import("linker") or _opt_import("cluster_link")
# T3 sibling modules (built by other agents). If absent we fall back to the
# grounded implementations at the bottom of this file.
solutions_mod = _opt_import("solutions")
decisions_mod = _opt_import("decisions")
llm_mod = _opt_import("llm")


router = APIRouter()


# ===========================================================================
# AEGIS tone helpers (mirror api_kpis / graph_builder / voc2.ts semantics).
# ===========================================================================
def _tone_from_ratio(part: float, whole: float) -> str:
    if not whole:
        return "neutral"
    r = part / whole
    return "alert" if r >= 0.30 else "warn" if r >= 0.10 else "calm"


def _ui_tone(part: float, whole: float) -> str:
    """voc2.ts Tone: 'danger' | 'good' | 'warn' | 'neutral'."""
    if not whole:
        return "neutral"
    r = part / whole
    return "danger" if r >= 0.30 else "warn" if r >= 0.10 else "good"


def _pct(part: float, whole: float) -> float:
    return round(100.0 * part / whole, 1) if whole else 0.0


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ===========================================================================
# Track 3 — build-time Arabic → English cluster/service label translations.
# No LLM key in env, so the agents translate the real voc360 Arabic labels now.
# Keyed by NORMALISED Arabic (diacritics/tatweel stripped, alef/yaa/taa unified)
# so lookups are robust to spelling variants; we also keep raw-substring hints.
# ===========================================================================
# Combining Arabic marks only (harakat, superscript alef, etc.). The naive class
# "[ؐ-ًؚ-ٰ…]" is WRONG: ؚ-ٰ (U+061A–U+0670) spans the Arabic letters themselves and
# would wipe every word. These ranges are restricted to the diacritic code points.
_DIAC = re.compile("[ً-ٰٟۖ-ۜ۟-ۤۧ-ۭ]")
_TAT = re.compile("ـ")  # tatweel/kashida
_WS = re.compile(r"\s+")


def _norm_ar(s: Optional[str]) -> str:
    if not s:
        return ""
    t = _DIAC.sub("", str(s))
    t = _TAT.sub("", t)
    t = (t.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
           .replace("ى", "ي").replace("ة", "ه"))
    return _WS.sub(" ", t).strip().lower()


# Substring → English. Matched against the normalised Arabic label; first hit
# wins. Covers the real cluster labels and service_ids named in the schema.
_AR_EN: List[tuple[str, str]] = [
    ("تاخير دعم صندوق المعونه", "National Aid Fund support delays"),
    ("صندوق المعونه", "National Aid Fund"),
    ("المعونه", "National Aid Fund"),
    ("الباص السريع", "Bus Rapid Transit (BRT)"),
    ("الباص", "Amman Bus service"),
    ("باص", "bus service"),
    ("رسوم الخدمه المستعجله", "urgent-service fees"),
    ("الخدمه المستعجله", "urgent / expedited service"),
    ("منصه تكافل", "Takaful platform"),
    ("تكافل", "Takaful platform"),
    ("منصه", "online platform"),
    ("الكترون", "e-services"),
    ("الالكترونيه", "e-services"),
    ("تطبيق", "mobile app"),
    ("سند", "Sanad app"),
    ("جواز", "passports service"),
    ("جوازات السفر", "passports service"),
    ("نقل عام", "public transit"),
    ("نقل", "transport"),
    ("طرق وبنيه تحتيه", "roads & infrastructure"),
    ("طريق", "roads"),
    ("شارع", "street / roads"),
    ("بنيه تحتيه", "infrastructure"),
    ("حفر", "potholes / road damage"),
    ("مراكز الخدمه", "service centres"),
    ("فساد اداري", "administrative corruption"),
    ("سوء الخدمه", "poor service quality"),
    ("عدم الرد", "no-response / unanswered requests"),
    ("تاخير", "delays"),
    ("رسوم", "fees"),
    ("دعم", "support"),
]


def translate_label(label_ar: Optional[str], label_en: Optional[str] = None) -> str:
    """English label for a cluster/service. Prefer a real ``canonical_label_en``;
    otherwise map the Arabic via the build-time table; otherwise return the raw
    Arabic so the UI is never blank."""
    if label_en and str(label_en).strip():
        return str(label_en).strip()
    norm = _norm_ar(label_ar)
    if norm:
        for needle, en in _AR_EN:
            if needle in norm:
                return en
    return (str(label_ar).strip() if label_ar else "") or "Unlabelled problem cluster"


# ===========================================================================
# T2 — SIGNALS  (GET /api/signals)
# Adapts api_signals.signals(page,size,...) ⇄ the frontend's limit/offset +
# service_id/source_type wire contract → {signals, total, filters}.
# ===========================================================================
@router.get("/api/signals")
def signals(
    service_id: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    source_type: Optional[str] = Query(default=None),
    governorate: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
    limit: int = Query(default=25, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> Dict[str, Any]:
    """Filtered, paginated feed over the_data — the SIGNAL/data-source layer."""
    filters = {
        "service_id": service_id,
        "severity": severity,
        "source_type": source_type,
        "governorate": governorate,
        "q": q,
    }
    # Translate offset/limit → api_signals' 1-based page/size.
    size = max(1, min(200, int(limit)))
    page = (int(offset) // size) + 1

    if api_signals is None or not hasattr(api_signals, "signals"):
        return _signals_fallback(filters, limit, offset)

    try:
        res = api_signals.signals(
            page=page, size=size,
            service=service_id, severity=severity,
            source=source_type, sentiment=None, q=q,
        )
    except Exception as e:
        out = _signals_fallback(filters, limit, offset)
        out["error"] = str(e)
        return out

    rows = res.get("rows", []) if isinstance(res, dict) else []
    total = _safe_int(res.get("total")) if isinstance(res, dict) else 0
    # Optional governorate filter is not part of api_signals' signature; apply it
    # here so the wire contract still honours it (post-filter on the page).
    if governorate:
        rows = [r for r in rows if (r.get("governorate") == governorate)]
    out: Dict[str, Any] = {"signals": rows, "total": total, "filters": filters}
    if isinstance(res, dict) and res.get("error"):
        out["error"] = res["error"]
    return out


def _signals_fallback(filters: Dict[str, Any], limit: int, offset: int) -> Dict[str, Any]:
    # Try a direct DB read so the page still works if api_signals is missing.
    if db is not None:
        clauses, bind = [], {"lim": max(1, min(200, int(limit))), "off": max(0, int(offset))}
        if filters.get("service_id"):
            clauses.append("service_id = %(service_id)s"); bind["service_id"] = filters["service_id"]
        if filters.get("severity"):
            clauses.append("severity = %(severity)s"); bind["severity"] = filters["severity"]
        if filters.get("source_type"):
            clauses.append("source_type = %(source_type)s"); bind["source_type"] = filters["source_type"]
        if filters.get("governorate"):
            clauses.append("governorate = %(governorate)s"); bind["governorate"] = filters["governorate"]
        if filters.get("q"):
            clauses.append("(text ilike %(q)s or text_clean ilike %(q)s)"); bind["q"] = f"%{filters['q']}%"
        where = ("where " + " and ".join(clauses)) if clauses else ""
        try:
            total_row = db.fetchone(f"select count(*) n from the_data {where}", bind)
            total = _safe_int(total_row.get("n")) if total_row else 0
            rows = db.fetchall(
                f"""select record_id, source_type, source_platform, source_channel,
                           service_id, governorate, district, text, text_clean,
                           observed_at, rating, severity, sentiment_label, confidence
                    from the_data {where}
                    order by observed_at desc nulls last, record_id desc
                    limit %(lim)s offset %(off)s""",
                bind,
            )
            return {"signals": rows, "total": total, "filters": filters}
        except Exception as e:
            return {"signals": [], "total": 0, "filters": filters, "error": str(e)}
    return {"signals": [], "total": 0, "filters": filters, "error": "data layer unavailable"}


# ===========================================================================
# T2 — KPIS  (GET /api/kpis)
# Wraps api_kpis.kpis() into the frontend's card-array contract.
# ===========================================================================
@router.get("/api/kpis")
def kpis(case: Optional[str] = Query(default=None)) -> Dict[str, Any]:
    """Dashboard KPI cards from real voc360 aggregates (the_data + RIL clusters)."""
    raw: Dict[str, Any] = {}
    if api_kpis is not None and hasattr(api_kpis, "kpis"):
        try:
            raw = api_kpis.kpis() or {}
        except Exception:
            raw = {}

    ok = bool(raw.get("ok"))
    if not ok:
        # last-ditch direct aggregate so the dashboard still shows real numbers
        raw = _kpis_direct() or raw
        ok = bool(raw.get("ok"))

    total = _safe_int(raw.get("total"))
    critical = _safe_int(raw.get("critical"))
    services = _safe_int(raw.get("services"))
    negative_pct = float(raw.get("negative_pct") or 0.0)
    crit_pct = float(raw.get("critical_pct") or 0.0)
    top = raw.get("top_service") or {}

    clusters = _cluster_count()

    cards: List[Dict[str, Any]] = [
        {
            "key": "signals",
            "title": "Citizen Signals",
            "value": f"{total:,}" if total else "—",
            "badge": {"text": "voc360", "tone": "neutral"},
            "trend": {"text": f"{negative_pct}% negative", "dir": "up",
                      "tone": "danger" if negative_pct >= 30 else "warn" if negative_pct >= 10 else "good"},
            "sub": "the_data rows",
        },
        {
            "key": "critical",
            "title": "High / Critical",
            "value": f"{critical:,}" if critical else "—",
            "badge": {"text": "severity", "tone": "danger"},
            "trend": {"text": f"{crit_pct}% of rated", "dir": "up",
                      "tone": "danger" if crit_pct >= 30 else "warn" if crit_pct >= 10 else "good"},
            "sub": "high + critical complaints",
        },
        {
            "key": "clusters",
            "title": "Root-Cause Clusters",
            "value": f"{clusters:,}" if clusters else "—",
            "badge": {"text": "RIL", "tone": "neutral"},
            "trend": {"text": "ril_problem_clusters", "dir": "up", "tone": "neutral"},
            "sub": "active problem clusters",
        },
        {
            "key": "services",
            "title": "Services Affected",
            "value": f"{services:,}" if services else "—",
            "badge": {"text": "distinct", "tone": "neutral"},
            "trend": {
                "text": (f"top: {top.get('id')}" if top.get("id") else "distinct service_id"),
                "dir": "up",
                "tone": top.get("tone_ui", "neutral") if isinstance(top, dict) else "neutral",
            },
            "sub": "distinct service_id",
        },
    ]
    return {
        "kpis": cards,
        "generated_at": _now_iso(),
        "source": "voc360" if ok else "fallback",
    }


def _kpis_direct() -> Dict[str, Any]:
    """Minimal direct aggregate fallback if api_kpis is unavailable."""
    if db is None:
        return {"ok": False}
    try:
        row = db.fetchone("""
          select count(*) total,
                 count(*) filter (where severity in ('high','critical')) critical,
                 count(*) filter (where severity is not null) severity_known,
                 count(*) filter (where sentiment_label is not null
                    and (lower(sentiment_label) like 'negative%%'
                      or lower(sentiment_label) like 'high_severity%%')) negative,
                 count(*) filter (where sentiment_label is not null) sentiment_known,
                 count(distinct service_id) filter (where service_id is not null) services
          from the_data
        """) or {}
        total = _safe_int(row.get("total"))
        return {
            "ok": True,
            "total": total,
            "critical": _safe_int(row.get("critical")),
            "critical_pct": _pct(_safe_int(row.get("critical")), _safe_int(row.get("severity_known"))),
            "negative_pct": _pct(_safe_int(row.get("negative")), _safe_int(row.get("sentiment_known"))),
            "services": _safe_int(row.get("services")),
            "top_service": None,
        }
    except Exception:
        return {"ok": False}


def _cluster_count() -> int:
    if db is None:
        return 0
    try:
        row = db.fetchone(
            "select count(*) n from ril_problem_clusters where coalesce(member_count,0) > 1"
        )
        return _safe_int(row.get("n")) if row else 0
    except Exception:
        return 0


# ===========================================================================
# T2 — SIGNAL VOLUME  (GET /api/signal-volume)
# Adapts api_kpis.signal_volume(range) and adds an optional service filter +
# severity/negative split for the stacked recharts series the frontend wants.
# ===========================================================================
_BUCKET_TO_RANGE = {"hour": "24h", "day": "30d", "date": "30d", "dow": "all"}
_BUCKET_TRUNC = {"hour": "hour", "day": "day", "date": "day"}


@router.get("/api/signal-volume")
def signal_volume(
    case: Optional[str] = Query(default=None),
    service_id: Optional[str] = Query(default=None),
    bucket: str = Query(default="day"),
) -> Dict[str, Any]:
    """Time-bucketed signal volume for the SignalVolume chart, from the_data."""
    svc = service_id or (case if case and case != "all" else None)
    bucket = bucket if bucket in ("hour", "day", "date", "dow") else "day"

    # When a service filter or a split is needed we query directly (api_kpis'
    # signal_volume has no service param); otherwise we can reuse it.
    series = _volume_direct(svc, bucket)
    if series:  # non-empty real series
        return {"series": series, "bucket": bucket, "source": "voc360"}

    if api_kpis is not None and hasattr(api_kpis, "signal_volume") and not svc:
        try:
            rng = _BUCKET_TO_RANGE.get(bucket, "30d")
            pts = api_kpis.signal_volume(rng) or []
            if pts:
                return {
                    "series": [{"t": p.get("t"), "v": _safe_int(p.get("v"))} for p in pts],
                    "bucket": bucket,
                    "source": "voc360",
                }
        except Exception:
            pass

    # Time bucketing yielded nothing (e.g. unparseable observed_at). Fall back to
    # the always-available day-of-week distribution so the chart is never blank.
    if bucket != "dow":
        dow = _volume_direct(svc, "dow")
        if dow:
            return {"series": dow, "bucket": "dow", "source": "voc360"}

    return {"series": [], "bucket": bucket, "source": "fallback"}


def _volume_direct(service_id: Optional[str], bucket: str) -> Optional[List[Dict[str, Any]]]:
    """Direct, service-aware, severity-split volume query. None on failure."""
    if db is None:
        return None
    if bucket == "dow":
        sql = """
          select day_of_week as t, count(*) v,
                 count(*) filter (where severity in ('high','critical')) critical,
                 count(*) filter (where severity = 'high') high,
                 count(*) filter (where sentiment_label is not null
                    and (lower(sentiment_label) like 'negative%%'
                      or lower(sentiment_label) like 'high_severity%%')) negative
          from the_data
          where day_of_week is not null
            and (%(svc)s::text is null or service_id = %(svc)s::text)
          group by 1 order by 1
        """
        bind = {"svc": service_id}
    else:
        trunc = _BUCKET_TRUNC.get(bucket, "day")
        # NOTE: in voc360 `observed_at` is stored as TEXT, so date_trunc/max must
        # operate on an explicit ::timestamptz cast (date_trunc(text,text) errors).
        sql = f"""
          select date_trunc('{trunc}', observed_at::timestamptz) as t, count(*) v,
                 count(*) filter (where severity in ('high','critical')) critical,
                 count(*) filter (where severity = 'high') high,
                 count(*) filter (where sentiment_label is not null
                    and (lower(sentiment_label) like 'negative%%'
                      or lower(sentiment_label) like 'high_severity%%')) negative
          from the_data
          where observed_at is not null
            and (%(svc)s::text is null or service_id = %(svc)s::text)
          group by 1 order by 1
        """
        bind = {"svc": service_id}
    try:
        rows = db.fetchall(sql, bind)
    except Exception:
        return None
    out: List[Dict[str, Any]] = []
    for r in rows:
        t = r.get("t")
        try:
            t = t.isoformat()
        except AttributeError:
            t = str(t) if t is not None else None
        out.append({
            "t": t,
            "v": _safe_int(r.get("v")),
            "critical": _safe_int(r.get("critical")),
            "high": _safe_int(r.get("high")),
            "negative": _safe_int(r.get("negative")),
        })
    return out


# ===========================================================================
# T3 — SOLUTIONS  (GET /api/solutions)  — cause → countermeasure engine.
# Prefers a sibling ``solutions`` module; else builds grounded solutions here
# from rootcause.rank_root_causes() + the recovered cluster→service links.
# ===========================================================================
@router.get("/api/solutions")
def solutions(limit: int = Query(default=8, ge=1, le=20)) -> Dict[str, Any]:
    """'Valid solution' engine: each top root-cause cluster → a concrete
    countermeasure with feasibility + expected impact, grounded in real
    evidence (segment_text) and the recovered owning service."""
    if solutions_mod is not None:
        for fn_name in ("solutions", "recommend_solutions", "build_solutions"):
            fn = getattr(solutions_mod, fn_name, None)
            if callable(fn):
                try:
                    res = fn(limit)
                    if isinstance(res, dict) and "solutions" in res:
                        return res
                    if isinstance(res, list):
                        return {"solutions": res, "recommendation": _headline(res), "source": "engine"}
                except Exception:
                    break
    return _solutions_engine(limit)


# countermeasure templates keyed by an English-label keyword → (action, feasibility)
_COUNTERMEASURES: List[tuple[tuple[str, ...], str, float]] = [
    (("national aid", "takaful", "support", "delay"),
     "Stand up a dedicated National-Aid escalation queue with an SLA on disbursement; "
     "publish status tracking so applicants stop re-filing.", 0.7),
    (("brt", "bus", "transit", "transport"),
     "Increase BRT/feeder frequency on the complained corridors and fix real-time "
     "arrival data; add capacity at peak hours.", 0.55),
    (("fee", "urgent", "expedited"),
     "Review the urgent-service fee schedule and waive/refund where SLA was missed; "
     "make the fee and turnaround explicit before payment.", 0.65),
    (("platform", "e-services", "app", "sanad", "online"),
     "Fix the failing e-service flow (auth/upload/submit), add a fallback channel, "
     "and instrument errors so regressions surface fast.", 0.6),
    (("road", "street", "infrastructure", "pothole"),
     "Route to the municipality works queue, batch repairs by district, and close the "
     "loop with the reporting citizens.", 0.5),
    (("corruption", "no-response", "poor service"),
     "Open a supervised review of the flagged cases, enforce response SLAs, and audit "
     "the handling team.", 0.45),
]


def _countermeasure_for(label_en: str) -> tuple[str, float]:
    low = (label_en or "").lower()
    for kws, action, feas in _COUNTERMEASURES:
        if any(k in low for k in kws):
            return action, feas
    return (
        "Assign the owning agency, brief the service team, and track whether complaint "
        "volume on this cluster falls after the intervention.",
        0.5,
    )


def _label3(x: float) -> str:
    return "high" if x >= 0.66 else "medium" if x >= 0.33 else "low"


def _solutions_engine(limit: int) -> Dict[str, Any]:
    if rootcause is None or not hasattr(rootcause, "rank_root_causes"):
        return {"solutions": [], "recommendation": None, "source": "fallback"}
    try:
        ranked = rootcause.rank_root_causes(limit) or []
    except Exception:
        return {"solutions": [], "recommendation": None, "source": "fallback"}

    # Recovered cluster → owning service + signal counts (T1 links).
    svc_by_cluster: Dict[str, str] = {}
    counts: Dict[str, int] = {}
    links = _load_links()
    if links:
        for e in (links.get("cluster_service") or []):
            cid, svc = e.get("cluster_id"), e.get("service_id")
            if cid and svc and cid not in svc_by_cluster:
                svc_by_cluster[cid] = svc
        cc = links.get("cluster_counts")
        if isinstance(cc, dict):
            counts = {str(k): _safe_int(v) for k, v in cc.items()}

    out: List[Dict[str, Any]] = []
    for r in ranked:
        cid = r.get("cluster_id")
        label_en = translate_label(r.get("label_ar"), r.get("label_en"))
        action, feasibility = _countermeasure_for(label_en)
        sev = float(r.get("severity_avg") or 0.0)
        members = _safe_int(r.get("members"))
        affected = counts.get(str(cid), members)
        # Expected impact: higher when severity is high and the action is feasible.
        impact = round(min(0.9, 0.25 + 0.5 * sev + 0.15 * feasibility), 2)
        out.append({
            "cluster_id": cid,
            "label_ar": r.get("label_ar"),
            "label_en": label_en,
            "cause": f"{label_en} — {members} citizen reports, severity {round(sev, 2)}.",
            "countermeasure": action,
            "owning_service": svc_by_cluster.get(cid),
            "feasibility": round(feasibility, 2),
            "feasibility_label": _label3(feasibility),
            "expected_impact": impact,
            "impact_label": _label3(impact),
            "affected_signals": affected,
            "severity_avg": round(sev, 2),
            "evidence": list(r.get("evidence") or [])[:3],
            "rationale": (
                f"Prioritised by score {r.get('score')}: {members} reports × severity "
                f"{round(sev, 2)}. Action routes to "
                f"{svc_by_cluster.get(cid) or 'the owning agency'}."
            ),
        })
    return {"solutions": out, "recommendation": _headline(out), "source": "engine"}


def _headline(sols: List[Dict[str, Any]]) -> Optional[str]:
    if not sols:
        return None
    s = sols[0]
    return (
        f"Top priority: {s.get('label_en')} ({s.get('affected_signals')} signals, severity "
        f"{s.get('severity_avg')}). {s.get('countermeasure')}"
    )


# ===========================================================================
# T2 — DECISIONS  (GET + POST /api/decisions)  — append-only decision log.
# Prefers a sibling ``decisions`` module (persistent store); else uses a small
# in-process JSON store under backend/data/ so the page is functional.
# ===========================================================================
_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_DECISIONS_PATH = os.path.join(_DATA_DIR, "decisions.json")
_VALID_STATUS = {"proposed", "approved", "rejected", "in_progress", "done"}


class DecisionIn(BaseModel):
    cluster_id: Optional[str] = None
    title: str
    action: str
    status: Optional[str] = "proposed"
    owner: Optional[str] = None
    rationale: Optional[str] = None


@router.get("/api/decisions")
def get_decisions() -> Dict[str, Any]:
    if decisions_mod is not None:
        for fn_name in ("list_decisions", "decisions", "get_decisions"):
            fn = getattr(decisions_mod, fn_name, None)
            if callable(fn):
                try:
                    res = fn()
                    if isinstance(res, dict) and "decisions" in res:
                        return res
                    if isinstance(res, list):
                        return {"decisions": res, "source": "store"}
                except Exception:
                    break
    return {"decisions": _read_decisions(), "source": "store"}


@router.post("/api/decisions")
def post_decision(payload: DecisionIn) -> Dict[str, Any]:
    if decisions_mod is not None:
        for fn_name in ("create_decision", "add_decision", "append_decision"):
            fn = getattr(decisions_mod, fn_name, None)
            if callable(fn):
                try:
                    res = fn(payload.model_dump())
                    if isinstance(res, dict):
                        return res
                except Exception:
                    break
    status = payload.status if payload.status in _VALID_STATUS else "proposed"
    decision = {
        "id": uuid.uuid4().hex[:12],
        "cluster_id": payload.cluster_id,
        "title": payload.title.strip(),
        "action": payload.action.strip(),
        "status": status,
        "owner": payload.owner,
        "rationale": payload.rationale,
        "created_at": _now_iso(),
    }
    try:
        store = _read_decisions()
        store.insert(0, decision)
        _write_decisions(store)
        return {"ok": True, "decision": decision}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _read_decisions() -> List[Dict[str, Any]]:
    try:
        with open(_DECISIONS_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _write_decisions(store: List[Dict[str, Any]]) -> None:
    os.makedirs(_DATA_DIR, exist_ok=True)
    with open(_DECISIONS_PATH, "w", encoding="utf-8") as fh:
        json.dump(store, fh, ensure_ascii=False, indent=2, default=str)


# ===========================================================================
# T3 — NARRATE  (POST /api/narrate)  — optional local-LLM narration node.
# Tries the sibling ``llm`` module first; else calls a local OpenAI-compatible /
# Ollama server (LLM_BASE_URL / LLM_MODEL); else a grounded deterministic summary.
# NEVER raises — the Deer Graph flow must stay green even with no model.
# ===========================================================================
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://localhost:11434")
LLM_MODEL = os.environ.get("LLM_MODEL", "llama3.1")


class NarrateIn(BaseModel):
    case: Optional[str] = None
    cluster_id: Optional[str] = None
    topic: Optional[str] = "root_cause"


@router.post("/api/narrate")
def narrate(payload: NarrateIn) -> Dict[str, Any]:
    # 1) sibling llm module, if present.
    if llm_mod is not None:
        for fn_name in ("narrate", "generate", "run"):
            fn = getattr(llm_mod, fn_name, None)
            if callable(fn):
                try:
                    res = fn(payload.model_dump())
                    if isinstance(res, dict) and "narration" in res:
                        return res
                except Exception:
                    break

    facts = _narration_facts(payload)
    prompt = _narration_prompt(payload, facts)

    # 2) local LLM (best-effort, short timeout).
    text = _call_local_llm(prompt)
    if text:
        return {
            "narration": text.strip(),
            "engine": "llm",
            "model": LLM_MODEL,
            "grounded_on": facts.get("grounded_on", []),
        }

    # 3) grounded deterministic fallback.
    return {
        "narration": facts["summary"],
        "engine": "fallback",
        "model": None,
        "grounded_on": facts.get("grounded_on", []),
    }


def _narration_facts(payload: NarrateIn) -> Dict[str, Any]:
    """Pull real voc360 facts to ground (and, on fallback, to *be*) the narration."""
    grounded_on: List[str] = []
    summary = "No grounded voc360 evidence was available to narrate."
    if rootcause is None or not hasattr(rootcause, "rank_root_causes"):
        return {"summary": summary, "grounded_on": grounded_on, "ranked": []}
    try:
        ranked = rootcause.rank_root_causes(5) or []
    except Exception:
        ranked = []
    if not ranked:
        return {"summary": summary, "grounded_on": grounded_on, "ranked": []}

    chosen = None
    if payload.cluster_id:
        chosen = next((r for r in ranked if r.get("cluster_id") == payload.cluster_id), None)
    chosen = chosen or ranked[0]
    grounded_on = [chosen.get("cluster_id")] if chosen.get("cluster_id") else []
    label = translate_label(chosen.get("label_ar"), chosen.get("label_en"))
    members = _safe_int(chosen.get("members"))
    sev = round(float(chosen.get("severity_avg") or 0.0), 2)
    ev = (chosen.get("evidence") or [])
    ev_line = f' Sample citizen report: "{ev[0][:160]}".' if ev else ""

    topic = (payload.topic or "root_cause")
    scope = payload.case or "VOC 360 · Jordan public services"
    if topic == "solution":
        action, _ = _countermeasure_for(label)
        summary = (
            f"For {scope}, the leading root cause is {label} ({members} citizen reports, "
            f"severity {sev}). Recommended countermeasure: {action}{ev_line}"
        )
    elif topic == "simulation":
        summary = (
            f"Simulating {scope}: if {label} ({members} reports, severity {sev}) is left "
            f"unaddressed, complaint pressure on the owning service keeps rising; resolving "
            f"this root cause is projected to bend the curve down.{ev_line}"
        )
    elif topic == "graph":
        summary = (
            f"The dependency graph for {scope} traces citizen signals through services to "
            f"the RIL root-cause clusters. The dominant cluster is {label} with {members} "
            f"linked reports (severity {sev}).{ev_line}"
        )
    else:  # root_cause
        others = ", ".join(
            translate_label(r.get("label_ar"), r.get("label_en")) for r in ranked[1:3]
        )
        summary = (
            f"Across {scope}, the top root cause is {label} — {members} citizen reports at "
            f"severity {sev}." + (f" Secondary causes: {others}." if others else "") + ev_line
        )
    return {"summary": summary, "grounded_on": grounded_on, "ranked": ranked, "chosen": chosen}


def _narration_prompt(payload: NarrateIn, facts: Dict[str, Any]) -> str:
    ranked = facts.get("ranked") or []
    lines = []
    for r in ranked[:5]:
        lines.append(
            f"- {translate_label(r.get('label_ar'), r.get('label_en'))}: "
            f"{_safe_int(r.get('members'))} reports, severity "
            f"{round(float(r.get('severity_avg') or 0.0), 2)}"
        )
    facts_block = "\n".join(lines) or "(no clusters available)"
    return (
        "You are an analyst for a Jordanian Voice-of-Customer platform. Using ONLY the "
        "facts below, write 2-3 sentences of plain-English narration for an operator "
        f"about the '{payload.topic or 'root_cause'}'. Do not invent numbers.\n\n"
        f"Scope: {payload.case or 'all services'}\n"
        f"Top root-cause clusters (real voc360 data):\n{facts_block}\n\nNarration:"
    )


def _call_local_llm(prompt: str) -> Optional[str]:
    """Best-effort call to a local OpenAI-compatible or Ollama server. Returns
    the text, or None if anything fails (no model, timeout, bad response). Never
    raises and never blocks for long."""
    try:
        import urllib.request

        base = LLM_BASE_URL.rstrip("/")
        # Prefer the OpenAI-compatible chat endpoint; fall back to Ollama native.
        attempts = [
            (
                f"{base}/v1/chat/completions",
                {"model": LLM_MODEL,
                 "messages": [{"role": "user", "content": prompt}],
                 "temperature": 0.2, "stream": False},
                lambda d: d["choices"][0]["message"]["content"],
            ),
            (
                f"{base}/api/generate",
                {"model": LLM_MODEL, "prompt": prompt, "stream": False},
                lambda d: d.get("response"),
            ),
        ]
        for url, body, extract in attempts:
            try:
                req = urllib.request.Request(
                    url, data=json.dumps(body).encode("utf-8"),
                    headers={"Content-Type": "application/json"}, method="POST",
                )
                with urllib.request.urlopen(req, timeout=6) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                text = extract(data)
                if text and str(text).strip():
                    return str(text)
            except Exception:
                continue
    except Exception:
        return None
    return None


# ===========================================================================
# T1 — GRAPH (real augmentation)  (GET /api/graph2)
# v1 /api/graph stays untouched in main.py. This sibling endpoint returns the
# same graph with the text-recovered root_cause_real edges + cluster signal
# counts layered on (via graph_real.augment_graph_real).
# ===========================================================================
@router.get("/api/graph2")
def graph_real_endpoint(case: Optional[str] = Query(default=None)) -> Dict[str, Any]:
    """The live graph with REAL recovered Service→Cluster edges (T1)."""
    if graph_builder is None or not hasattr(graph_builder, "build_graph"):
        return {"case": case or "all", "nodes": [], "edges": [],
                "stats": {"real_source": "none"}, "error": "graph_builder unavailable"}
    try:
        g = graph_builder.build_graph(case)
    except Exception as e:
        return {"case": case or "all", "nodes": [], "edges": [],
                "stats": {"real_source": "none"}, "error": str(e)}
    if graph_real is not None and hasattr(graph_real, "augment_graph_real"):
        try:
            g = graph_real.augment_graph_real(g, case)
        except Exception:
            g.setdefault("stats", {})["real_source"] = "error"
    return g


# ===========================================================================
# links.json loader (shared by solutions). Prefers the linker's cached loader.
# ===========================================================================
def _load_links() -> Optional[Dict[str, Any]]:
    if linker is not None and hasattr(linker, "load_links"):
        try:
            res = linker.load_links()
            if isinstance(res, dict):
                return res
        except Exception:
            pass
    try:
        with open(os.path.join(_DATA_DIR, "links.json"), "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


__all__ = ["router", "translate_label"]
