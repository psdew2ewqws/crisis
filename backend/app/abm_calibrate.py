"""Ground the ABM's intervention in REAL voc360 history instead of a guessed 0.60.

The agent-based model needs three numbers it should not invent:
  • effect_size  — how much an intervention actually relieves a crisis,
  • spread_rate  — how fast grievance propagates,
  • decay        — how fast it subsides on its own.

This module fits all three from the_data and returns them with an honest
confidence band and provenance. It is ALWAYS available (scipy/pandas/numpy/db
are installed). DoWhy is an OPTIONAL robustness layer on top: when present
(``causal_validate.available()``), a refutation battery only *adjusts the
confidence* of the data-fit effect — it never overrides the headline number.

Honesty contract (mirrors cascade_sim / causal_validate):
  - source: 'data'  → effect fit from observed post-peak decline,
            'dowhy' → data fit, confidence stamped by a passed refutation,
            'prior' → fell back to the 0.60 prior (sparse / no history).
  - sparse data (few rows or <2 services) → confidence 'low', source 'prior'.
"""
from __future__ import annotations

import statistics
from typing import Any, Dict, List, Optional

from . import mesa_sim
from .mesa_sim import DEFAULT_INTERVENTION_STRENGTH, DEFAULT_SEED  # noqa: F401

try:
    from . import db
except Exception:  # pragma: no cover
    db = None  # type: ignore

try:
    from . import causal_validate
except Exception:  # pragma: no cover
    causal_validate = None  # type: ignore

MIN_ROWS = 200            # below this the fit is untrustworthy → prior
_DEF_SPREAD = 0.30
_DEF_DECAY = 0.985


def available_dowhy() -> bool:
    return bool(causal_validate is not None and causal_validate.available())


def _services_from_graph(graph) -> List[str]:
    """Extract bare service_id strings (drop the 'svc:' prefix) from the graph."""
    out: List[str] = []
    for nid, a in mesa_sim._g_nodes(graph):
        if a.get("kind") == "service" and isinstance(nid, str) and nid.startswith("svc:"):
            out.append(nid[4:])
    return out


def _top_cluster_id(graph) -> Optional[str]:
    ranked = mesa_sim._graph_root_causes(graph)
    return ranked[0].get("cluster_id") if ranked else None


def _daily_series(services: List[str]) -> List[Dict[str, Any]]:
    if db is None or not services:
        return []
    sql = (
        "SELECT date::date AS d, count(*) AS vol, "
        "avg(CASE WHEN lower(severity) IN ('high','critical') "
        "OR lower(coalesce(sentiment_label,'')) LIKE '%%negative%%' "
        "OR lower(coalesce(sentiment_label,'')) LIKE '%%high_severity%%' "
        "THEN 1.0 ELSE 0.0 END) AS neg "
        "FROM the_data WHERE service_id = ANY(%s) AND date IS NOT NULL "
        "GROUP BY 1 ORDER BY 1"
    )
    try:
        return db.fetchall(sql, ([list(services)][0],))  # %s ← list → ANY(...)
    except Exception:
        return []


def _weekly_by_service(services: List[str]) -> Dict[str, List[float]]:
    if db is None or not services:
        return {}
    sql = (
        "SELECT service_id, date_trunc('week', date::date) AS w, "
        "avg(CASE WHEN lower(severity) IN ('high','critical') "
        "OR lower(coalesce(sentiment_label,'')) LIKE '%%negative%%' "
        "OR lower(coalesce(sentiment_label,'')) LIKE '%%high_severity%%' "
        "THEN 1.0 ELSE 0.0 END) AS neg "
        "FROM the_data WHERE service_id = ANY(%s) AND date IS NOT NULL "
        "GROUP BY 1, 2 ORDER BY 1, 2"
    )
    try:
        rows = db.fetchall(sql, ([list(services)][0],))
    except Exception:
        return {}
    by: Dict[str, List[float]] = {}
    for r in rows or []:
        by.setdefault(str(r["service_id"]), []).append(float(r["neg"] or 0.0))
    return by


def _fit_decay(neg: List[float]) -> float:
    """Lag-1 autoregression of deviations from the mean → persistence (decay)."""
    if len(neg) < 4:
        return _DEF_DECAY
    mu = statistics.fmean(neg)
    dev = [x - mu for x in neg]
    num = sum(dev[i] * dev[i - 1] for i in range(1, len(dev)))
    den = sum(d * d for d in dev[:-1]) or 1e-9
    rho = num / den
    return float(max(0.95, min(0.999, 0.95 + 0.049 * max(0.0, min(1.0, rho)))))


def _fit_effect(weekly: Dict[str, List[float]]) -> tuple[Optional[float], int]:
    """Effect = mean over services of (peak − post-peak trough) / peak, weighted by length."""
    effs: List[tuple[float, int]] = []
    for _svc, neg in weekly.items():
        if len(neg) < 4:
            continue
        peak_i = max(range(len(neg)), key=lambda i: neg[i])
        peak = neg[peak_i]
        if peak <= 0.01:
            continue
        post = neg[peak_i + 1: peak_i + 9]      # up to 8 weeks after the peak
        if not post:
            continue
        trough = min(post)
        rel = (peak - trough) / peak
        effs.append((max(0.1, min(0.85, rel)), len(neg)))
    if not effs:
        return None, 0
    wsum = sum(w for _, w in effs) or 1
    eff = sum(e * w for e, w in effs) / wsum
    return float(eff), wsum


def calibrate(graph, treated_services: Optional[List[str]] = None,
              dsn: Optional[str] = None) -> Dict[str, Any]:
    """Return calibrated {effect_size, spread_rate, decay} + confidence + provenance.

    Always returns a usable dict; never raises. ``treated_services`` defaults to
    every service in the graph (bare service_id strings)."""
    services = treated_services or _services_from_graph(graph)
    out: Dict[str, Any] = {
        "available": True,
        "source": "prior",
        "effect_size": DEFAULT_INTERVENTION_STRENGTH,
        "spread_rate": _DEF_SPREAD,
        "decay": _DEF_DECAY,
        "n_rows": 0,
        "n_services": len(services),
        "confidence": "low",
        "refutation": {"available": False},
        "notes_ar": "تعذّر إيجاد سجل تاريخي كافٍ — استُخدمت قيمة افتراضية متحفّظة.",
    }
    if db is None or len(services) < 1:
        return out

    daily = _daily_series(services)
    n_rows = sum(int(r.get("vol", 0) or 0) for r in daily)
    out["n_rows"] = n_rows
    if n_rows < MIN_ROWS or len(services) < 2:
        out["confidence"] = "low"
        out["notes_ar"] = (
            f"سجل تاريخي محدود ({n_rows} إشارة، {len(services)} خدمة) — "
            "حجم الأثر افتراضي متحفّظ."
        )
        return out

    # data-driven fits
    neg_series = [float(r.get("neg") or 0.0) for r in daily]
    decay = _fit_decay(neg_series)
    weekly = _weekly_by_service(services)
    eff, wlen = _fit_effect(weekly)

    if eff is None:
        out["decay"] = decay
        out["confidence"] = "low"
        out["notes_ar"] = "لا يوجد نمط ذروة/تعافٍ واضح في السجل — أثر افتراضي."
        return out

    out["source"] = "data"
    out["effect_size"] = round(eff, 3)
    out["decay"] = round(decay, 4)
    out["spread_rate"] = round(max(0.1, min(0.5, 1.0 - decay + 0.30)), 3)
    out["confidence"] = "medium"
    out["notes_ar"] = (
        f"عُيّر حجم الأثر ({out['effect_size']}) من متوسط انخفاض الشكاوى بعد الذروة "
        f"عبر {len(weekly)} خدمة ({n_rows} إشارة)."
    )

    # optional DoWhy robustness — only ADJUSTS confidence
    if available_dowhy():
        try:
            cluster_id = _top_cluster_id(graph) or ""
            ref = causal_validate.refute(cluster_id, services)
            out["refutation"] = ref
            if ref.get("available") and ref.get("ok"):
                out["source"] = "dowhy"
                if ref.get("robust"):
                    out["confidence"] = "high"
                    out["notes_ar"] += " اجتاز فحص المتانة السببي (DoWhy)."
                elif ref.get("spurious"):
                    out["confidence"] = "low"
                    out["notes_ar"] += " تحذير: لم يجتز فحص المتانة السببي (ارتباط غير سببي محتمل)."
        except Exception:
            pass

    return out
