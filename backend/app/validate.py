"""Case validation — is a RIL problem cluster really a *root cause*?

`validate_case(cluster_id, service)` scores a cluster on FIVE weighted, fully
grounded checks against real voc360 data and returns a verdict
(``valid`` | ``weak`` | ``insufficient``) + confidence + per-check detail.

Every number/detail is a RETRIEVED fact — never fabricated. The local LLM
(``llm.narrate``) only PHRASES the ``summary``; it never invents the verdict or
any figure (same trust boundary as ``solutions._narrate``). The module is
import-safe: missing optional engines (forecaster / mesa_sim / llm / torch /
timesfm) degrade to a partial verdict, and every endpoint helper is
try/except-wrapped so it never raises.

Reused real contracts (verified against the existing backend):
- ``db.fetchall(sql, params)`` with psycopg dict ``%(name)s`` params.
- ``cluster_link.cluster_signals(cid)`` -> int recovered signals;
  ``cluster_link.cluster_services(cid)`` -> [(service, count), ...].
- ``ril_cluster_members ⋈ ril_text_segments`` with ``distance_to_centroid``.
- The cluster's daily series is built over its **service set** (record_id does
  NOT join ``the_data`` — the parallel-layer rule the graph already uses).
- ``forecaster.forecast_series(y, horizon)`` -> {source, mean, lo, hi};
  ``forecaster.escalation(history, fc_mean, window)`` -> {ratio, escalating, ...}.
- ``mesa_sim.simulate(case, intervene=True, intervention_node="cluster:<id>")``
  -> {before, after, delta:{mean_negativity_final, ...}, root_cause, ...}.
- ``rootcause.rank_root_causes(limit)`` for the rank endpoint.
- ``main_v2.translate_label(ar, en)`` for the English gloss.
"""
from __future__ import annotations

from typing import Any, Optional

from . import db

# --- optional engines: import-safe, never hard-depend ----------------------
try:  # real cluster -> signal / service recovery (Track 1, text-matched)
    from . import cluster_link  # type: ignore
except Exception:  # pragma: no cover
    cluster_link = None  # type: ignore

try:  # statistical-or-TimesFM forecaster (D-forecast / FORECASTING_RECIPE)
    from . import forecaster  # type: ignore
except Exception:  # pragma: no cover
    forecaster = None  # type: ignore

try:  # Mesa propagation sim (heavy but local, no torch)
    from . import mesa_sim  # type: ignore
except Exception:  # pragma: no cover
    mesa_sim = None  # type: ignore

try:  # ranking engine for the /rank endpoint
    from . import rootcause  # type: ignore
except Exception:  # pragma: no cover
    rootcause = None  # type: ignore

try:  # LOCAL model — phrases the summary only; grounded fallback exists
    from . import llm as _llm  # type: ignore
except Exception:  # pragma: no cover
    _llm = None  # type: ignore

try:  # Arabic -> English gloss (best-effort)
    from . import main_v2 as _main_v2  # type: ignore
except Exception:  # pragma: no cover
    _main_v2 = None  # type: ignore


# ===========================================================================
# AEGIS palette tokens (mirrors graph_builder severity tone / frontend tokens)
# ===========================================================================
TONE_GOOD = "#34D399"   # good
TONE_WARN = "#FBBF24"   # warn
TONE_BAD = "#F04359"    # danger
TONE_MUTED = "#8B8D96"  # muted

VERDICT_TONE = {
    "valid": TONE_GOOD,
    "weak": TONE_WARN,
    "insufficient": TONE_BAD,
}

# Five weighted checks; weights sum to 1.0 (D-validate contract).
WEIGHTS = {
    "coverage": 0.30,
    "evidence_sufficiency": 0.20,
    "temporal_trend": 0.20,
    "sim_impact": 0.20,
    "symptom_vs_cause": 0.10,
}

# Arabic-keyword specificity heuristic (mirrors graph_builder._KW intent):
# cause-MECHANISM terms read as a real root cause; generic-symptom terms do not.
_CAUSE_KW = (
    "تأخير", "تاخير", "رسوم", "منصة", "نظام", "تطبيق", "خطأ", "عطل", "بطء",
    "ازدحام", "نقص", "غياب", "عدم الرد", "انقطاع", "حفريات", "صيانة", "إجراء",
    "اجراء", "سياسة", "آلية", "اليه", "توقف", "فساد", "احتيال", "تكرار",
    "delay", "fee", "platform", "system", "error", "outage", "process",
    "policy", "shortage", "queue", "crowd", "corruption",
)
_SYMPTOM_KW = (
    "سيء", "سيئة", "مشكلة", "شكوى", "سوء", "غير راضي", "تعب", "زعل", "ممل",
    "bad", "poor", "issue", "problem", "complaint", "unhappy", "terrible",
)


# ===========================================================================
# helpers
# ===========================================================================
def _translate(ar: Optional[str], en: Optional[str]) -> str:
    if _main_v2 is not None and hasattr(_main_v2, "translate_label"):
        try:
            out = _main_v2.translate_label(ar, en)  # type: ignore[attr-defined]
            if isinstance(out, str) and out.strip():
                return out
        except Exception:
            pass
    return (en or ar or "").strip() or "(unknown cluster)"


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def _cluster_row(cluster_id: str) -> dict[str, Any]:
    """Real ril_problem_clusters facts for the target cluster (or empty)."""
    try:
        row = db.fetchone(
            """
            select cluster_id, canonical_label_ar, canonical_label_en, service_id,
                   coalesce(member_count,0)  as member_count,
                   coalesce(severity_avg,0)  as severity_avg,
                   first_seen, last_seen, status
            from ril_problem_clusters
            where cluster_id = %(cid)s
            """,
            {"cid": cluster_id},
        )
        return row or {}
    except Exception:
        return {}


def _check(name: str, passed: bool, score: float, detail: str,
           evidence: Optional[list[Any]] = None,
           value: Optional[Any] = None) -> dict[str, Any]:
    return {
        "name": name,
        "weight": WEIGHTS[name],
        "pass": bool(passed),
        "score": round(_clamp01(score), 3),
        "detail": detail,
        "value": value,
        "evidence": evidence or [],
    }


# ===========================================================================
# CHECK 1 — coverage (0.30): real recovered signal share for this cluster
# ===========================================================================
def _check_coverage(cluster_id: str, service: Optional[str]) -> dict[str, Any]:
    if cluster_link is None:
        return _check("coverage", False, 0.0,
                      "cluster_link unavailable — cannot recover signal coverage.")
    try:
        services = cluster_link.cluster_services(cluster_id) or []
    except Exception:
        services = []
    try:
        total_signals = int(cluster_link.cluster_signals(cluster_id) or 0)
    except Exception:
        total_signals = 0

    svc_map = {str(s): int(c) for s, c in services}
    if service:
        signals = svc_map.get(service, 0)
        scope = f"service {service}"
    else:
        signals = total_signals
        scope = "all mapped services"

    # share of this cluster's recovered signals carried by the scoped service
    share = (signals / total_signals) if total_signals else 0.0
    # score blends absolute signal floor (5+) with the per-service share
    by_floor = _clamp01(signals / 20.0)              # 20 signals -> full credit
    by_share = _clamp01(share) if service else by_floor
    score = max(by_floor, 0.5 * by_floor + 0.5 * by_share)
    passed = signals >= 5
    top = ", ".join(f"{s} ({c})" for s, c in services[:3]) or "none"
    detail = (
        f"{signals} recovered signal(s) for {scope}"
        f" of {total_signals} cluster-linked"
        f" (top services: {top})."
    )
    return _check("coverage", passed, score, detail,
                  evidence=services[:3], value=signals)


# ===========================================================================
# CHECK 2 — evidence sufficiency (0.20): member segments + distinct texts
# ===========================================================================
def _check_evidence(cluster_id: str) -> dict[str, Any]:
    members = 0
    distinct = 0
    samples: list[str] = []
    try:
        agg = db.fetchone(
            """
            select count(*)                                   as members,
                   count(distinct left(s.segment_text, 60))   as distinct_texts
            from ril_cluster_members m
            join ril_text_segments s on s.segment_id = m.segment_id
            where m.cluster_id = %(cid)s
              and s.segment_text is not null
            """,
            {"cid": cluster_id},
        ) or {}
        members = int(agg.get("members") or 0)
        distinct = int(agg.get("distinct_texts") or 0)
    except Exception:
        pass

    try:
        rows = db.fetchall(
            """
            select s.segment_text
            from ril_cluster_members m
            join ril_text_segments s on s.segment_id = m.segment_id
            where m.cluster_id = %(cid)s
              and s.segment_text is not null
            order by m.distance_to_centroid asc nulls last
            limit 3
            """,
            {"cid": cluster_id},
        )
        samples = [(r["segment_text"] or "")[:140] for r in rows if r.get("segment_text")]
    except Exception:
        samples = []

    # full credit at ~15 distinct citizen texts; floor at members>=5 & distinct>=3
    score = max(_clamp01(members / 20.0), _clamp01(distinct / 15.0))
    passed = members >= 5 and distinct >= 3
    detail = (
        f"{members} clustered citizen segment(s), "
        f"{distinct} distinct (closest-to-centroid samples retained)."
    )
    return _check("evidence_sufficiency", passed, score, detail,
                  evidence=samples, value=members)


# ===========================================================================
# CHECK 3 — temporal trend (0.20): cluster service-set daily volume escalating?
# ===========================================================================
def _cluster_daily_volume(cluster_id: str) -> list[float]:
    """Dense daily count over the cluster's mapped service set (parallel rule)."""
    services: list[str] = []
    if cluster_link is not None:
        try:
            services = [str(s) for s, _ in (cluster_link.cluster_services(cluster_id) or [])]
        except Exception:
            services = []
    if not services:
        return []
    try:
        rows = db.fetchall(
            """
            select date_trunc('day', nullif(date::text, '')::timestamp)::date as ds,
                   count(*) as v
            from the_data
            where service_id = any(%(svcs)s)
              and nullif(date::text, '')::timestamp is not null
            group by 1 order by 1
            """,
            {"svcs": services},
        )
    except Exception:
        return []
    if not rows:
        return []

    # densify the inclusive calendar, filling missing days with 0 volume
    import datetime as _dt
    by_day = {r["ds"]: float(r["v"]) for r in rows}
    lo, hi = rows[0]["ds"], rows[-1]["ds"]
    out: list[float] = []
    d = lo
    one = _dt.timedelta(days=1)
    guard = 0
    while d <= hi and guard < 4000:  # series <= ~3200 pts; guard against runaway
        out.append(by_day.get(d, 0.0))
        d += one
        guard += 1
    return out


def _check_temporal(cluster_id: str) -> dict[str, Any]:
    if forecaster is None:
        return _check("temporal_trend", False, 0.0,
                      "forecaster unavailable — cannot assess temporal trend.")
    y = _cluster_daily_volume(cluster_id)
    if len(y) < 14:
        return _check("temporal_trend", False, 0.0,
                      f"insufficient history ({len(y)} day(s)) to assess trend.",
                      value=len(y))
    try:
        fc = forecaster.forecast_series(y, horizon=14)
        fc_mean = fc.get("mean") or []
        source = fc.get("source", "stat")
    except Exception:
        return _check("temporal_trend", False, 0.0,
                      "forecast_series failed — trend unknown.")
    try:
        esc = forecaster.escalation(y, fc_mean, window=14)
        ratio = float(esc.get("ratio") or 1.0)
        escalating = bool(esc.get("escalating"))
    except Exception:
        # local escalation fallback: forecast-window mean vs trailing-14 mean
        recent = sum(y[-14:]) / 14.0
        fut = (sum(fc_mean) / len(fc_mean)) if fc_mean else 0.0
        ratio = (fut / recent) if recent > 0 else (2.0 if fut > 0 else 1.0)
        escalating = ratio >= 1.2
    # score scales 1.0x..1.5x ratio -> 0..1 (clamped); declining => 0
    score = _clamp01((ratio - 1.0) / 0.5)
    detail = (
        f"forecast/recent volume ratio {ratio:.2f} over 14d "
        f"({'escalating' if escalating else 'flat/declining'}; {source})."
    )
    return _check("temporal_trend", escalating, score, detail, value=round(ratio, 3))


# ===========================================================================
# CHECK 4 — sim impact (0.20): does intervening on this cluster move the needle?
# ===========================================================================
def _check_sim(cluster_id: str, service: Optional[str]) -> dict[str, Any]:
    if mesa_sim is None:
        return _check("sim_impact", False, 0.0,
                      "mesa_sim unavailable — cannot simulate intervention.")
    try:
        res = mesa_sim.simulate(
            case=service,
            intervene=True,
            intervention_node=f"cluster:{cluster_id}",
        )
    except Exception:
        return _check("sim_impact", False, 0.0,
                      "simulation failed — intervention impact unknown.")
    delta = (res or {}).get("delta") or {}
    try:
        dneg = float(delta.get("mean_negativity_final", 0.0))
    except Exception:
        dneg = 0.0
    dcrit = int(delta.get("n_critical_final", 0) or 0)
    # delta>0 means intervention REDUCED negativity vs no-action baseline
    passed = dneg > 0.002
    score = _clamp01(dneg / 0.05)  # ~0.05 reduction -> full credit
    detail = (
        f"intervening on cluster:{cluster_id[:8]} reduces final mean negativity "
        f"by {dneg:+.4f} (Δcritical {dcrit:+d})."
    )
    return _check("sim_impact", passed, score, detail, value=round(dneg, 4))


# ===========================================================================
# CHECK 5 — symptom vs cause (0.10): Arabic-keyword specificity heuristic
# ===========================================================================
def _check_symptom_vs_cause(cluster: dict[str, Any]) -> dict[str, Any]:
    text = " ".join(str(cluster.get(k) or "") for k in
                    ("canonical_label_ar", "canonical_label_en")).lower()
    cause_hits = sum(1 for kw in _CAUSE_KW if kw in text)
    symptom_hits = sum(1 for kw in _SYMPTOM_KW if kw in text)
    # a labelled cause-mechanism beats a generic symptom; ties favour the label
    is_cause = cause_hits > 0 and cause_hits >= symptom_hits
    score = _clamp01(0.5 + 0.25 * cause_hits - 0.25 * symptom_hits)
    detail = (
        f"label specificity: {cause_hits} cause-mechanism term(s) vs "
        f"{symptom_hits} generic-symptom term(s) "
        f"-> {'specific cause' if is_cause else 'reads as a symptom'}."
    )
    return _check("symptom_vs_cause", is_cause, score, detail,
                  value={"cause": cause_hits, "symptom": symptom_hits})


# ===========================================================================
# verdict + LLM summary (phrasing only)
# ===========================================================================
def _decide(checks: list[dict[str, Any]]) -> tuple[str, float, int]:
    by = {c["name"]: c for c in checks}
    weighted = sum(c["score"] * c["weight"] for c in checks)
    confidence = _clamp01(weighted)
    score100 = int(round(100 * confidence))
    n_pass = sum(1 for c in checks if c["pass"])
    cov_pass = by.get("coverage", {}).get("pass", False)
    ev_pass = by.get("evidence_sufficiency", {}).get("pass", False)

    if score100 >= 65 and cov_pass and ev_pass and n_pass >= 3:
        verdict = "valid"
    elif score100 >= 40 and n_pass >= 2:
        verdict = "weak"
    else:
        verdict = "insufficient"
    return verdict, confidence, score100


def _summary(target: dict[str, Any], verdict: str, score100: int,
             checks: list[dict[str, Any]]) -> str:
    label = target.get("label", "(cluster)")
    bullets = "; ".join(
        f"{c['name']} {'PASS' if c['pass'] else 'weak'} ({c['detail']})"
        for c in checks
    )
    deterministic = (
        f"Verdict: {verdict.upper()} — '{label}' scores {score100}/100 as a root "
        f"cause. Checks: {bullets}"
    )
    if _llm is None or not hasattr(_llm, "narrate"):
        return deterministic
    facts = (
        f"Cluster: {label} (id {target.get('cluster_id')}). "
        f"Verdict: {verdict}. Score: {score100}/100. "
        + " ".join(
            f"{c['name']}={'pass' if c['pass'] else 'weak'} (score {c['score']}, {c['detail']})"
            for c in checks
        )
    )
    prompt = (
        "You are an AEGIS public-service analyst validating a root cause. Using "
        "ONLY the facts below, write ONE concise paragraph (<=70 words) stating "
        "the verdict and the single strongest and single weakest check. Do NOT "
        "invent any number, agency, or fact not given; keep Arabic labels "
        "verbatim.\n\nFACTS:\n" + facts
    )
    try:
        out = _llm.narrate(prompt, context={
            "case": target.get("cluster_id"),
            "verdict": verdict,
            "score": score100,
            "checks": [{"label": c["name"], "value": c["detail"]} for c in checks],
        })
        text = (out or "").strip() if isinstance(out, str) else ""
        if len(text) >= 40:
            return text
    except Exception:
        pass
    return deterministic


# ===========================================================================
# public entry point
# ===========================================================================
def validate_case(cluster_id: str, service: Optional[str] = None) -> dict[str, Any]:
    """Validate whether ``cluster_id`` is a real root cause.

    Returns ``{verdict, confidence, score, target, checks, summary, tone}``.
    Never raises; each check degrades to a (pass=False, score=0) partial.
    """
    row = _cluster_row(cluster_id)
    label = _translate(row.get("canonical_label_ar"), row.get("canonical_label_en"))
    target = {
        "cluster_id": cluster_id,
        "service": service,
        "label": label,
        "label_ar": row.get("canonical_label_ar"),
        "label_en": row.get("canonical_label_en"),
        "member_count": int(row.get("member_count") or 0),
        "severity_avg": round(float(row.get("severity_avg") or 0.0), 2),
        "first_seen": str(row.get("first_seen")) if row.get("first_seen") else None,
        "last_seen": str(row.get("last_seen")) if row.get("last_seen") else None,
        "exists": bool(row),
    }

    # run the five checks, each independently fault-isolated
    runners = [
        lambda: _check_coverage(cluster_id, service),
        lambda: _check_evidence(cluster_id),
        lambda: _check_temporal(cluster_id),
        lambda: _check_sim(cluster_id, service),
        lambda: _check_symptom_vs_cause(row),
    ]
    names = ["coverage", "evidence_sufficiency", "temporal_trend",
             "sim_impact", "symptom_vs_cause"]
    checks: list[dict[str, Any]] = []
    for name, run in zip(names, runners):
        try:
            checks.append(run())
        except Exception as exc:  # pragma: no cover - belt-and-suspenders
            checks.append(_check(name, False, 0.0, f"check error: {exc}"))

    verdict, confidence, score100 = _decide(checks)
    summary = _summary(target, verdict, score100, checks)

    return {
        "verdict": verdict,
        "confidence": round(confidence, 3),
        "score": score100,
        "target": target,
        "checks": checks,
        "summary": summary,
        "tone": VERDICT_TONE[verdict],
        "weights": WEIGHTS,
    }


def validate_rank(limit: int = 8) -> dict[str, Any]:
    """Validate the top-ranked root-cause clusters (for /validate/rank)."""
    items: list[dict[str, Any]] = []
    ranked: list[dict[str, Any]] = []
    if rootcause is not None:
        try:
            ranked = rootcause.rank_root_causes(limit=limit) or []
        except Exception:
            ranked = []
    for r in ranked:
        cid = r.get("cluster_id")
        if not cid:
            continue
        try:
            v = validate_case(cid)
        except Exception:
            continue
        items.append({
            "rank": r.get("rank"),
            "cluster_id": cid,
            "label": v["target"]["label"],
            "members": r.get("members"),
            "severity_avg": r.get("severity_avg"),
            "verdict": v["verdict"],
            "confidence": v["confidence"],
            "score": v["score"],
            "tone": v["tone"],
        })
    return {"count": len(items), "items": items}


__all__ = ["validate_case", "validate_rank", "WEIGHTS", "VERDICT_TONE"]
