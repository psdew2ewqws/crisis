"""Scenario engine — crisis DETECTION + PREDICTION for a novel, unseen situation.

The operator describes a crisis in free text (Arabic or English). A Case-Based Reasoning
loop turns it into a grounded verdict:

    parse → RETRIEVE timestamp-weighted historical crises (lessons RAG)
          → SELECT the right agents by skill (agent_router)
          → SIMULATE the propagation + intervention (mesa_sim before/after)
          → (optional) DEBATE among the selected agents
          → DETECT + PREDICT: deterministic fusion → severity, escalation, likely
            outcome, which historical intervention worked, with calibrated confidence
            and full provenance (each claim cites a source_case_id + ts).

Trust boundary (per the consultancy review): every load-bearing number — detection,
prediction, confidence — is computed DETERMINISTICALLY from retrieval + Mesa. The local
LLM only NARRATES (the optional debate). So a down Ollama lowers fluency, never blocks,
and never silently fabricates: it degrades to grounded-keyword retrieval with a hard
confidence cap. The Mesa "step" is a relative propagation tick and is never mixed with
the forecaster's wall-clock days.

    POST /api/scenario/detect   {text, domain?, horizon_days?, run_debate?, top_k?, case_hint?}
         → NDJSON stream: parse → retrieve → select_agents → simulate → [debate] → detect_predict → done
    POST /api/scenario/retain   {text, intervention, risk_before, risk_after, outcome, approved, ...}
         → approval-gated write-back into the lessons RAG (closes the CBR loop)
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterator, List, Optional

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

try:
    from . import lessons
except Exception:  # pragma: no cover
    lessons = None  # type: ignore
try:
    from . import agent_router
except Exception:  # pragma: no cover
    agent_router = None  # type: ignore
try:
    from . import mesa_sim
except Exception:  # pragma: no cover
    mesa_sim = None  # type: ignore
try:
    from . import forecaster
except Exception:  # pragma: no cover
    forecaster = None  # type: ignore
try:
    from . import debate as _debate
except Exception:  # pragma: no cover
    _debate = None  # type: ignore
try:
    from . import llm
except Exception:  # pragma: no cover
    llm = None  # type: ignore
try:
    from . import lessons_pinecone as _vs
except Exception:  # pragma: no cover
    _vs = None  # type: ignore
try:
    from . import scenario_runs
except Exception:  # pragma: no cover
    scenario_runs = None  # type: ignore
try:
    from . import db
except Exception:  # pragma: no cover
    db = None  # type: ignore
try:
    from . import cascade_sim
except Exception:  # pragma: no cover
    cascade_sim = None  # type: ignore
try:
    from . import research_agent
except Exception:  # pragma: no cover
    research_agent = None  # type: ignore
try:
    from . import guardrails_gateway as _guard
except Exception:  # pragma: no cover
    _guard = None  # type: ignore
try:
    from . import report_writer
except Exception:  # pragma: no cover
    report_writer = None  # type: ignore
try:
    from . import expert_chat as _ec
except Exception:  # pragma: no cover
    _ec = None  # type: ignore


# AR/EN domain -> English scholarly-search seed (OpenAlex is English-indexed).
_DOMAIN_QUERY = {
    "water": "Jordan water scarcity supply crisis",
    "health": "Jordan hospital emergency department overcrowding health system capacity",
    "energy": "Jordan electricity power outage energy crisis",
    "sanitation": "Jordan wastewater sanitation public health",
    "waste": "Jordan solid waste management crisis",
    "food": "Jordan food security prices import dependency",
    "agriculture": "Jordan agriculture livestock drought impact",
    "refugees": "Jordan refugees host community services strain",
    "transport": "Jordan transport road congestion crisis",
    "education": "Jordan education school capacity crisis",
    "economy": "Jordan inflation economic crisis cost of living",
    "environment": "Jordan environment climate crisis",
    "disaster": "Jordan flood flash flood disaster response",
}


def _research_query(text: str, domain: str) -> str:
    """Build an English scholarly-search query for ANY scenario (OpenAlex is English-only).
    Prefer a quick local-model translation of the Arabic scenario; degrade to a domain seed."""
    seed = _DOMAIN_QUERY.get((domain or "").lower(), "")
    try:
        if _ec is not None and _ec.model_available():
            txt, ok = _ec._call_model([
                {"role": "system", "content": "Convert an Arabic crisis scenario into a concise English "
                 "academic search query. Output ONLY 5-8 English keywords — no Arabic, no punctuation, "
                 "no explanation."},
                {"role": "user", "content": (text or "").strip()[:500]},
            ], num_predict=40)
            kw = " ".join((txt or "").split())[:120]
            has_arabic = any("؀" <= ch <= "ۿ" for ch in kw)
            if ok and kw and not has_arabic:
                return ("Jordan " + kw).strip()
    except Exception:
        pass
    return seed or f"Jordan {domain or 'crisis'} public services"


def _is_jordan_drought(text: str, case_hint: Optional[str]) -> bool:
    """Route Jordan drought / no-rain scenarios to the WEF-nexus cascade (real data),
    not the complaint-sentiment graph."""
    if case_hint == "scenario:jordan_drought_1yr":
        return True
    t = (text or "").lower()
    jordan = any(k in t for k in ("الأردن", "jordan", "الزرقاء", "عمّان", "عمان", "المفرق"))
    drought = any(k in t for k in ("جفاف", "مطر", "أمطار", "تمطر", "المياه", "drought", "rain", "water"))
    return jordan and drought

router = APIRouter()
NDJSON = "application/x-ndjson"

# Minimum distinct precedents below which we refuse a numeric confidence.
MIN_CORPUS = 3
# In LLM-down (grounded-keyword) mode, confidence is hard-capped — retrieval quality
# is keyword-only and must not look authoritative.
GROUNDED_CONF_CAP = 0.35

# ---- Arabic labels for every enum (Arabic-first end to end) ---------------- #
SEVERITY_AR = {"low": "منخفضة", "elevated": "مرتفعة", "critical": "حرجة"}
BAND_AR = {"high": "مرتفع", "medium": "متوسط", "low": "منخفض"}
RISK_SRC_AR = {"simulated": "محاكاة", "heuristic": "تقديري", "measured": "مقيس"}
OUTCOME_AR = {
    "validated_success": "نجاح مؤكَّد", "partial_success": "نجاح جزئي", "contained": "احتواء",
    "failed": "فشل", "rejected": "مرفوض", "no_improvement": "دون تحسّن", "made_worse": "تفاقم",
}
FLAG_AR = {
    "pinecone_empty": "مخزن المتجهات فارغ — اعتمدنا المحاكاة فقط",
    "ollama_down": "النموذج المحلي متوقّف — التحليل مبني على الكلمات المفتاحية",
    "grounded_keyword": "استرجاع بالكلمات المفتاحية (بدون تضمين دلالي)",
    "no_historical_analog": "لا توجد سابقة تاريخية قريبة",
    "weak_analog": "السوابق المسترجَعة ضعيفة الصلة",
    "sparse_corpus": "قاعدة السوابق محدودة",
    "recency_inert": "وزن الحداثة غير مؤثّر (تواريخ متقاربة)",
}


class ScenarioIn(BaseModel):
    text: str = ""
    domain: Optional[str] = None
    horizon_days: int = 14
    run_debate: bool = False
    top_k: int = 6
    case_hint: Optional[str] = None     # e.g. "service:Sanad" / "cluster:<id>"
    location: Optional[str] = None      # governorate (from the dropdown)
    service: Optional[str] = None       # service_id (from the dropdown)
    solution: Optional[str] = None      # operator's proposed solution to validate/optimize
    # Live RSS news articles to use as contextual evidence (from /api/news or /api/news-analysis).
    # These appear as a "Live News Context" panel in the UI and are passed to agents as
    # supplementary observations — they do NOT enter the confidence calculation so they
    # cannot inflate the analytical verdict.
    rss_articles: Optional[List[Dict[str, Any]]] = None


class RetainIn(BaseModel):
    text: str = ""
    domain: Optional[str] = None
    intervention: str = ""
    risk_before: float = 0.0
    risk_after: float = 0.0
    outcome: str = "validated_success"
    worked: Optional[bool] = None
    source_case_id: str = ""
    confidence: float = 0.7
    approved: bool = False              # write-back is approval-gated


# --------------------------------------------------------------------------- #
# intake: guard + script detection + light injection neutralization           #
# --------------------------------------------------------------------------- #
_INJECT = re.compile(
    r"(ignore (all|previous|the above)|disregard .* instructions|system\s*:|"
    r"you are now|تجاهل (كل|التعليمات|ما سبق)|أنت الآن)",
    re.IGNORECASE,
)


def _detect_script(text: str) -> str:
    return "ar" if re.search(r"[؀-ۿ]", text or "") else "latin"


def _neutralize(text: str) -> str:
    """Defang obvious prompt-injection before any text reaches llm.chat."""
    return _INJECT.sub("⟨—⟩", text or "")


def _intake_guard(text: str) -> List[str]:
    warnings: List[str] = []
    t = (text or "").strip()
    if not t:
        warnings.append("الرجاء وصف الأزمة بنص قصير.")
    elif len(t) < 8:
        warnings.append("الوصف قصير جدًّا — أضف تفاصيل (الخدمة، الموقع، العَرَض) لنتيجة أدقّ.")
    return warnings


# --------------------------------------------------------------------------- #
# retrieval helpers                                                           #
# --------------------------------------------------------------------------- #
def _distinct_by_source(cases: List[dict]) -> List[dict]:
    seen, out = set(), []
    for c in cases:
        sid = c.get("source_case_id") or c.get("id")
        if sid in seen:
            continue
        seen.add(sid)
        out.append(c)
    return out


def _is_provisional(c: dict) -> bool:
    """A self-authored run breadcrumb (auto-fed from a prior simulation), NOT a
    human-validated precedent. These are recall-only: they must never fire a verdict
    or inflate confidence, otherwise the engine launders its own guesses into
    self-confirming 'successes' (a degrade loop)."""
    return (str(c.get("risk_source") or "") == "run"
            or str(c.get("source_case_id") or "").startswith("run:"))


def _compact_series(series: list) -> List[dict]:
    """Slim the Mesa SimResult series to what the before/after charts need."""
    out = []
    for i, p in enumerate(series or []):
        out.append({
            "step": int(p.get("step", i)),
            "mean_negativity": round(float(p.get("mean_negativity", 0.0)), 4),
            "n_critical": int(p.get("n_critical", 0)),
        })
    return out


def _improvement(c: dict) -> float:
    """Risk reduction (positive = good). lessons store risk_delta = after - before."""
    try:
        return float(c.get("risk_before") or 0) - float(c.get("risk_after") or 0)
    except (TypeError, ValueError):
        return 0.0


def _citation(c: dict) -> dict:
    return {
        "source_case_id": c.get("source_case_id"),
        "ts": (c.get("ts") or "")[:10],
        "kind": c.get("kind") or "success",
        "outcome": c.get("outcome"),
        "outcome_ar": OUTCOME_AR.get(c.get("outcome") or "", c.get("outcome")),
        "risk_source": c.get("risk_source") or "simulated",
        "risk_source_ar": RISK_SRC_AR.get(c.get("risk_source") or "simulated", "محاكاة"),
        "lesson": (c.get("lesson_text") or "")[:240],
        "relevance": c.get("relevance"),
    }


# --------------------------------------------------------------------------- #
# Phase 3 — scenario simulation seeding                                       #
# --------------------------------------------------------------------------- #
def simulate_scenario(
    case_hint: Optional[str],
    top_lesson: Optional[dict] = None,
    *,
    steps: int = 40,
    strength: Optional[float] = None,
) -> Dict[str, Any]:
    """Build the scenario graph (synthetic fallback when offline / not in voc360) and run
    the before/after intervention. intervention_strength is taken from ``strength`` when
    given (the solution-evaluator seeds it from the proposed solution's alignment), else
    from the top retrieved success lesson's measured risk reduction. Never raises."""
    # Jordan drought / no-rain -> the deterministic WEF-nexus cascade (real data + Monte-Carlo
    # + references), NOT the complaint-sentiment graph (which returns a constant 43.2).
    if case_hint == "scenario:jordan_drought_1yr" and cascade_sim is not None:
        try:
            return cascade_sim.study()
        except Exception:
            pass
    if mesa_sim is None:
        return {"available": False}
    # explicit strength wins; else seed from the precedent (bounded); else the default
    if strength is None:
        strength = mesa_sim.DEFAULT_INTERVENTION_STRENGTH
        if top_lesson is not None:
            imp = _improvement(top_lesson)        # 0..100 risk points reduced
            if imp > 0:
                strength = max(0.3, min(0.9, imp / 100.0 + 0.3))
    strength = max(0.1, min(0.95, float(strength)))
    try:
        graph = mesa_sim.build_graph_for_case(case_hint)
        n_nodes = mesa_sim._g_node_count(graph)
        ba = mesa_sim.run_before_after(
            graph, intervention_node=None, intervention_strength=strength, steps=steps
        )
        seir_before = mesa_sim.seir_readout(ba["before"]["series"], n_nodes)
        seir_after = mesa_sim.seir_readout(ba["after"]["series"], n_nodes)
        risk_before = round(seir_before["peak_negativity"] * 100, 1)
        risk_after = round(seir_after["peak_negativity"] * 100, 1)
        return {
            "available": True,
            "engine": ba["before"].get("engine"),
            "n_nodes": n_nodes,
            "intervention_node": ba.get("intervention_node"),
            "intervention_strength": round(strength, 3),
            "risk_before": risk_before,
            "risk_after": risk_after,
            "risk_reduction": round(risk_before - risk_after, 1),
            "seir_before": seir_before,
            "seir_after": seir_after,
            "series_before": _compact_series(ba["before"]["series"]),
            "series_after": _compact_series(ba["after"]["series"]),
        }
    except Exception as e:  # surface, don't crash the stream
        return {"available": False, "error": str(e)[:160]}


def _escalation_signal(case_hint: Optional[str], sim: dict, horizon_days: int) -> Dict[str, Any]:
    """The 'will it escalate?' signal. For a voc360-resolvable service/cluster use the REAL
    wall-clock complaint-volume forecast; for a purely novel scenario use the simulation's
    relative-tick readout. The two are kept SEPARATE (never cross tick and day domains)."""
    # real-volume path
    if case_hint and forecaster is not None and ":" in str(case_hint):
        ent, _, key = str(case_hint).partition(":")
        if ent in ("service", "cluster") and key:
            try:
                fc = forecaster.forecast(ent, key, metric="volume", horizon=horizon_days)
                esc = fc.get("escalation") or {}
                if fc.get("history_points", 0) > 0:
                    return {
                        "source": "forecast",
                        "escalating": bool(esc.get("escalating")),
                        "ratio": esc.get("ratio"),
                        "horizon_days": horizon_days,
                        "forecast_source": fc.get("source"),
                    }
            except Exception:
                pass
    # simulation path (novel scenario)
    seir = (sim or {}).get("seir_before") or {}
    return {
        "source": "simulation",
        "escalating": bool(seir.get("escalating")),
        "peak_critical_frac": seir.get("peak_critical_frac"),
        "ticks_to_settle": seir.get("ticks_to_settle"),
        "note": "إشارة من المحاكاة (خطوات نسبية، ليست أيامًا)",
    }


# --------------------------------------------------------------------------- #
# Phase 6 — scenario-local debate over the SELECTED agents                     #
# --------------------------------------------------------------------------- #
def _role_for(key: str) -> dict:
    if _debate is not None:
        for r in getattr(_debate, "ROLES", []):
            if r["key"] == key:
                return r
        if getattr(_debate, "SYNTH", {}).get("key") == key:
            return _debate.SYNTH
        for e in getattr(_debate, "EXPERTS", []):
            if e["key"] == key:
                return e
    name = agent_router.PERSONAS.get(key, key) if agent_router else key
    return {"key": key, "name": name, "task": "قدّم رأيك بإيجاز مستندًا إلى الأدلة."}


def _scenario_facts(text: str, cases: List[dict], sim: dict, esc: dict) -> str:
    lines = [f"الموقف (نص المُشغّل): {text.strip()[:400]}"]
    if cases:
        lines.append("سوابق تاريخية قريبة:")
        for c in cases[:3]:
            tag = "✓ نجح" if (c.get("kind") or "success") == "success" else "✗ فشل"
            lines.append(
                f"  - [{tag}] {(c.get('lesson_text') or '')[:160]} "
                f"(المصدر {c.get('source_case_id')} · {(c.get('ts') or '')[:10]})"
            )
    if sim.get("available"):
        lines.append(
            f"المحاكاة: الخطر قبل {sim.get('risk_before')} ← بعد التدخّل {sim.get('risk_after')} "
            f"(انخفاض {sim.get('risk_reduction')})."
        )
    lines.append("التصعيد المتوقّع: " + ("نعم" if esc.get("escalating") else "مستقر") + ".")
    return "\n".join(lines)


def _det_turn(role_key: str, text: str, cases: List[dict], sim: dict, esc: dict) -> str:
    top = cases[0] if cases else {}
    red = sim.get("risk_reduction")
    if role_key == "analyst":
        n = len(_distinct_by_source(cases))
        return (f"تشير المعطيات إلى موقف يشبه {n} سابقة موثّقة، "
                f"وأبرزها «{(top.get('root_cause_category') or 'غير محدّد')}». لا حلول بعد.")
    if role_key == "advocate":
        return (f"أرى أن التدخّل المقترح فعّال: في السوابق المشابهة خفّض الخطر "
                f"بمقدار يقارب {red if red is not None else '—'} نقطة. أقترح تطبيقه ومتابعة الأثر.")
    if role_key == "skeptic":
        tail = " ومع توقّع التصعيد تبقى الأولوية مرتفعة." if esc.get("escalating") else " والاتجاه يبدو مستقرًّا."
        return ("بحذر: هل التشابه مع السوابق كافٍ؟ يلزم التأكّد من اختلاف السياق قبل التعميم." + tail)
    if role_key == "synthesizer":
        return (f"الخلاصة: الموقف "
                f"{'قابل للتصعيد' if esc.get('escalating') else 'تحت السيطرة نسبيًّا'}؛ "
                f"التدخّل الأقرب للنجاح مستمدّ من السوابق، والخطوة التالية تطبيقه مع قياس الأثر.")
    # any expert lens — keep it short + grounded
    return f"من منظور {agent_router.PERSONAS.get(role_key, role_key)}: الأولوية لمعالجة الجذر مع متابعة قابلة للقياس."


def _stream_debate(roster, text, cases, sim, esc, using_llm) -> Iterator[Dict[str, Any]]:
    facts = _scenario_facts(text, cases, sim, esc)
    # order: analyst first, synthesizer last, specialists in between
    keys = [r["key"] for r in roster]
    ordered = ([k for k in keys if k == "analyst"]
               + [k for k in keys if k not in ("analyst", "synthesizer")]
               + [k for k in keys if k == "synthesizer"])
    transcript: List[dict] = []
    for key in ordered:
        role = _role_for(key)
        text_out = None
        eng = "grounded"
        if using_llm and _debate is not None:
            try:
                text_out = _debate._llm_turn(role, facts, transcript)
                eng = "llm" if text_out else "grounded"
            except Exception:
                text_out = None
        if not text_out:
            text_out = _det_turn(key, text, cases, sim, esc)
        transcript.append({"name": role["name"], "text": text_out})
        yield {"role": key, "agent": role["name"], "text": text_out, "engine": eng}


# --------------------------------------------------------------------------- #
# fusion — deterministic detection + prediction                               #
# --------------------------------------------------------------------------- #
def _fuse(text, cases, sim, esc, flags, engine) -> Dict[str, Any]:
    # Only HUMAN-VALIDATED precedents may fire a verdict or set confidence. Self-authored
    # run breadcrumbs are excluded here (they remain visible as recalled past runs) so the
    # engine cannot confirm its own guesses into precedents — see _is_provisional().
    verified = [c for c in cases if not _is_provisional(c)]
    distinct = _distinct_by_source(verified)
    successes = [c for c in distinct if (c.get("kind") or "success") == "success"]
    failures = [c for c in distinct if c.get("kind") == "failure"]
    n = len(distinct)

    # severity: blend simulation + retrieval support
    sim_sev = (sim.get("seir_before") or {}).get("severity", "low") if sim.get("available") else "low"
    escalating = bool(esc.get("escalating"))
    severity = sim_sev
    if escalating and severity == "low":
        severity = "elevated"

    # likely outcome: modal outcome over DISTINCT precedents
    likely_outcome, outcome_ar = None, None
    if distinct:
        from collections import Counter
        modal = Counter([c.get("outcome") for c in distinct if c.get("outcome")]).most_common(1)
        if modal:
            likely_outcome = modal[0][0]
            outcome_ar = OUTCOME_AR.get(likely_outcome, likely_outcome)

    # which historical intervention worked best (max risk reduction among successes)
    best = max(successes, key=_improvement, default=None)
    which_worked = None
    if best is not None and _improvement(best) > 0:
        which_worked = {
            "intervention": (best.get("intervention") or "")[:300],
            "risk_reduction": round(_improvement(best), 1),
            "source_case_id": best.get("source_case_id"),
            "ts": (best.get("ts") or "")[:10],
            "risk_source": best.get("risk_source") or "simulated",
            "risk_source_ar": RISK_SRC_AR.get(best.get("risk_source") or "simulated", "محاكاة"),
        }

    # anti-patterns (retrieved failures) — the Validator surfaces & down-weights
    anti = [{"warning": (c.get("lesson_text") or "")[:200],
             "avoid_when": (c.get("applicable_when") or "")[:160],
             "source_case_id": c.get("source_case_id")} for c in failures[:3]]

    # confidence — deterministic, LLM-independent
    rels = [float(c.get("relevance") or 0.0) for c in verified]
    mean_rel = min(1.0, sum(rels) / len(rels)) if rels else 0.0
    agreement = (max(len(successes), len(failures)) / n) if n else 0.0
    valid = (sum(float(c.get("confidence") or 0.5) for c in distinct) / n) if n else 0.0
    raw = round(mean_rel * agreement * valid, 3)

    if engine == "grounded":
        numeric, band = round(min(raw, GROUNDED_CONF_CAP), 3), "low"
    elif "no_historical_analog" in flags or n == 0:
        numeric, band = round(min(raw, 0.25), 3), "low"
    elif n < MIN_CORPUS:
        numeric, band = round(min(raw, 0.4), 3), "low"
        if "sparse_corpus" not in flags:
            flags.append("sparse_corpus")
    else:
        numeric = raw
        band = "high" if raw >= 0.6 else "medium" if raw >= 0.35 else "low"
    # an active anti-pattern caps confidence one band down
    if anti and band == "high":
        band, numeric = "medium", min(numeric, 0.55)

    return {
        "detection": {
            "is_crisis": severity in ("elevated", "critical") or escalating,
            "severity": severity,
            "severity_ar": SEVERITY_AR.get(severity, severity),
            "escalating": escalating,
            "escalation_source": esc.get("source"),
            "has_precedent": n > 0,
        },
        "prediction": {
            "likely_outcome": likely_outcome,
            "likely_outcome_ar": outcome_ar,
            "which_intervention_worked": which_worked,
            "risk_trajectory": {
                "risk_before": sim.get("risk_before"),
                "risk_after": sim.get("risk_after"),
                "risk_reduction": sim.get("risk_reduction"),
                "risk_source": "simulated" if sim.get("available") else None,
                "risk_source_ar": "محاكاة" if sim.get("available") else None,
            },
            "avoid": anti,
        },
        "confidence": {
            "band": band,
            "band_ar": BAND_AR.get(band, band),
            "score": numeric,
            "breakdown": {
                "mean_relevance": round(mean_rel, 3),
                "outcome_agreement": round(agreement, 3),
                "validation_factor": round(valid, 3),
                "distinct_precedents": n,
            },
        },
        "degradation_flags": flags,
        "degradation_flags_ar": [FLAG_AR.get(f, f) for f in flags],
        "citations": [_citation(c) for c in verified],
    }


# --------------------------------------------------------------------------- #
# orchestrator                                                                #
# --------------------------------------------------------------------------- #
def _ev(stage: str, **data) -> bytes:
    return (json.dumps({"stage": stage, **data}, ensure_ascii=False) + "\n").encode("utf-8")


# --------------------------------------------------------------------------- #
# solution validator / optimizer                                              #
# --------------------------------------------------------------------------- #
def _overlap(sol_tokens: set, text: str) -> float:
    t = {w for w in re.split(r"\W+", (text or "").lower()) if len(w) > 2}
    if not sol_tokens or not t:
        return 0.0
    return len(sol_tokens & t) / len(sol_tokens)


def _optimize_solution(sol: str, graft: Optional[str], alignment: str, using_llm: bool) -> str:
    g = (graft or "").strip()[:160]
    if using_llm and llm is not None:
        try:
            sysmsg = ("أنت مستشار أزمات. حسّن الحل المقترح بإيجاز بالعربية الفصحى المبسّطة، "
                      "مستندًا إلى ما نجح تاريخيًّا فقط، دون اختلاق أرقام أو وقائع.")
            user = (f"الحل المقترح: {sol}\n"
                    + (f"تدخّل ناجح سابق مشابه: {g}\n" if g else "")
                    + "أعطِ نسخة محسّنة من الحل في جملتين، تبدأ بالحل مباشرة.")
            out = llm.chat(sysmsg, user, temperature=0.4, max_tokens=180, timeout=12)
            if out:
                return out.strip()
        except Exception:
            pass
    if alignment == "matches_anti_pattern":
        return ("تنبيه: حلّك يقترب من نمط فشل سابق. عدّله ليعالج جذر المشكلة"
                + (f"، مع الاستفادة ممّا نجح تاريخيًّا: «{g}»." if g else "."))
    if g:
        return (f"حلّك في الاتجاه الصحيح. لتعزيز الأثر، ادمج ما نجح تاريخيًّا: «{g}»، "
                f"مع متابعة قابلة للقياس بعد التطبيق.")
    return "حلّك جديد دون سابقة قريبة؛ طبّقه على نطاق محدود أولًا وقِس الأثر قبل التعميم."


def _evaluate_solution(text: str, solution: str, cases: List[dict],
                       case_hint: Optional[str], using_llm: bool) -> Dict[str, Any]:
    sol = (solution or "").strip()
    sol_tokens = {w for w in re.split(r"\W+", sol.lower()) if len(w) > 2}
    successes = [c for c in cases if (c.get("kind") or "success") == "success"]
    failures = [c for c in cases if c.get("kind") == "failure"]

    best_succ, best_succ_score = None, 0.0
    for c in successes:
        s = _overlap(sol_tokens, c.get("intervention"))
        if s > best_succ_score:
            best_succ, best_succ_score = c, s
    best_fail, best_fail_score = None, 0.0
    for c in failures:
        s = max(_overlap(sol_tokens, c.get("intervention")),
                _overlap(sol_tokens, c.get("applicable_when")))
        if s > best_fail_score:
            best_fail, best_fail_score = c, s

    if best_fail_score >= 0.4 and best_fail_score >= best_succ_score:
        alignment, alignment_ar = "matches_anti_pattern", "يشبه نمطًا فاشلًا سابقًا — يُنصح بتعديله"
    elif best_succ_score >= 0.3:
        alignment, alignment_ar = "aligned_with_success", "متوافق مع تدخّل ناجح سابق"
    else:
        alignment, alignment_ar = "novel", "حلّ جديد لا سابقة قريبة له"
    align_score = round(best_succ_score, 3)

    optimized = _optimize_solution(sol, best_succ.get("intervention") if best_succ else None,
                                   alignment, using_llm)

    # expected results: simulate WITH this solution; strength seeded from alignment
    strength = max(0.35, min(0.9, 0.4 + 0.45 * align_score))
    sim = simulate_scenario(case_hint, None, strength=strength)
    expected = {
        "risk_before": sim.get("risk_before"),
        "risk_after": sim.get("risk_after"),
        "risk_reduction": sim.get("risk_reduction"),
        "escalating": bool((sim.get("seir_before") or {}).get("escalating")),
        "engine": sim.get("engine"),
    }
    band = ("high" if alignment == "aligned_with_success" and align_score >= 0.5
            else "medium" if best_succ_score >= 0.3 else "low")
    return {
        "alignment": alignment,
        "alignment_ar": alignment_ar,
        "alignment_score": align_score,
        "matched_success": _citation(best_succ) if best_succ else None,
        "matched_anti_pattern": ({"warning": (best_fail.get("lesson_text") or "")[:200],
                                  "source_case_id": best_fail.get("source_case_id")}
                                 if (best_fail and best_fail_score >= 0.4) else None),
        "optimized_solution": optimized,
        "expected_results": expected,
        "confidence_band": band,
        "confidence_band_ar": BAND_AR.get(band, band),
    }


def _feed_provisional(text: str, domain: str, service: str, location: str,
                      verdict: dict, sim: dict) -> None:
    """LEARN: write this run back into the lessons RAG as a LOW-WEIGHT provisional
    precedent (deterministic id, confidence 0.2, risk_source='run')."""
    if lessons is None:
        return
    try:
        pred = verdict.get("prediction") or {}
        rb, ra = sim.get("risk_before"), sim.get("risk_after")
        rid = (scenario_runs.run_id(text, service or "", location or "")
               if scenario_runs else "run:" + lessons._slug(text))
        payload = lessons.ReflectIn(
            domain=domain,
            root_cause_category=lessons._slug(text)[:48],
            root_cause_details=text.strip()[:1000],
            intervention=((pred.get("which_intervention_worked") or {}).get("intervention")
                          or "محاكاة سيناريو (تدخّل مقترح آليًّا)"),
            risk_before=float(rb) if rb is not None else 50.0,
            risk_after=float(ra) if ra is not None else 50.0,
            outcome="contained",
            worked=None,   # UNVERIFIED: a run is not a confirmed success — only human RETAIN sets that
            source_case_id=rid,
            confidence=0.2,
            risk_source="run",
        )
        lessons.reflect_and_store_lesson(payload)
    except Exception:
        pass


def run_scenario(body: ScenarioIn) -> Iterator[bytes]:
    text_raw = (body.text or "").strip()
    flags: List[str] = []

    # ---- guardrails: input rail (fail-closed on harm/scope/jurisdiction) ----
    if _guard is not None:
        rail = _guard.input_rail(text_raw)
        if rail["action"] == "refuse":
            yield _ev("guardrail", action="refuse", reason=rail["reason"],
                      message_ar=rail["reason_ar"], flags=rail["flags"])
            yield _ev("done", aborted=True, reason=rail["reason"])
            return
        text = rail["cleaned"] or text_raw
        if rail["flags"]:
            flags.extend(rail["flags"])  # e.g. injection / pii surfaced downstream
    else:
        text = _neutralize(text_raw)

    # ---- parse ----
    warnings = _intake_guard(text)
    script = _detect_script(text)
    domain = body.domain or (lessons.infer_domain(None, text) if lessons else "other")
    using_llm = bool(llm is not None and llm.available())
    if not using_llm:
        flags.append("ollama_down")
    qvec, qvec_real = (None, False)
    if lessons is not None and text:
        qvec, qvec_real = lessons._embed_real(text)
    yield _ev("parse", script=script, domain=domain, using_llm=using_llm, warnings=warnings)
    if warnings and not text:
        yield _ev("done", aborted=True, reason="empty_input")
        return

    # ---- retrieve ----
    pinecone_empty = False
    try:
        if _vs is not None and _vs.available():
            st = _vs.ensure_schema()
            pinecone_empty = bool(st.get("ok") and int(st.get("count", 0)) == 0)
    except Exception:
        pinecone_empty = False
    if pinecone_empty:
        flags.append("pinecone_empty")
    if not qvec_real and "grounded_keyword" not in flags:
        flags.append("grounded_keyword")

    cases: List[dict] = []
    if lessons is not None:
        try:
            # Broad recall: crisis analogies are cross-domain, so we do NOT hard-filter
            # by domain (which would return 0 when the domain bucket is empty). Domain
            # stays a soft signal for agent routing + the scorer's small same-domain bonus.
            cases = lessons.retrieve_relevant_lessons(
                query=text, domain=None, limit=max(1, min(int(body.top_k), 12))
            )
        except Exception:
            cases = []
    cases = _distinct_by_source(cases)
    # reject / weak-analog flagging
    best_rel = max((float(c.get("relevance") or 0.0) for c in cases), default=0.0)
    if not cases:
        flags.append("no_historical_analog")
    elif qvec_real and best_rel < 0.30:
        flags.append("weak_analog")
    # recency-inert flag: all ts within ~1 day / missing
    ts_days = {(c.get("ts") or "")[:10] for c in cases if c.get("ts")}
    if cases and len(ts_days) <= 1:
        flags.append("recency_inert")
    yield _ev("retrieve", count=len(cases),
              cases=[_citation(c) for c in cases], best_relevance=round(best_rel, 4))

    # ---- live news context (does NOT affect confidence — observation layer only) ----
    news_articles: List[Dict[str, Any]] = list(body.rss_articles or [])
    if not news_articles and body.location and db is not None:
        # Auto-fetch up to 20 recent articles for the requested governorate.
        try:
            rows = db.fetchall(
                "SELECT title, summary, source, gov, "
                "to_char(published AT TIME ZONE 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"') AS published "
                "FROM aegis_news WHERE gov = %s ORDER BY published DESC NULLS LAST LIMIT 20",
                (body.location,),
            )
            news_articles = [dict(r) for r in (rows or [])]
        except Exception:
            news_articles = []
    if news_articles:
        yield _ev("news_context", count=len(news_articles),
                  gov=body.location,
                  articles=[{
                      "title":     a.get("title", ""),
                      "summary":   (a.get("summary") or "")[:200],
                      "source":    a.get("source", ""),
                      "gov":       a.get("gov"),
                      "published": a.get("published"),
                  } for a in news_articles[:20]])

    # ---- recall similar PAST RUNS (learning memory) ----
    if scenario_runs is not None:
        try:
            past = scenario_runs.recall_similar(text, domain, limit=3)
            if past:
                yield _ev("history", runs=past, total=scenario_runs.stats().get("total_runs", 0))
        except Exception:
            pass

    # ---- select agents ----
    roster = []
    if agent_router is not None:
        try:
            roster = agent_router.select_agents(
                text, qvec if qvec_real else None, cases, domain=domain
            )
        except Exception:
            roster = []
    yield _ev("select_agents",
              agents=[{"key": r["key"], "name": r["name"], "score": r["score"],
                       "reason": r["reason"], "floor": r["floor"]} for r in roster],
              engine=(roster[0]["engine"] if roster else "grounded"))

    # ---- simulate ----
    # Build the case from the dropdowns first (service seeds the graph directly; a
    # location scopes it by governorate), then fall back to a retrieved cluster.
    case_hint = body.case_hint
    if not case_hint and body.service:
        case_hint = f"service:{body.service}"
    if not case_hint and body.location:
        case_hint = f"gov:{body.location}"
    if not case_hint:
        for c in cases:
            sid = str(c.get("source_case_id") or "")
            if sid.startswith("cluster:"):
                case_hint = sid
                break
    # Jordan drought / no-rain -> the cited WEF-nexus cascade flagship
    is_drought = _is_jordan_drought(text, case_hint)
    if is_drought:
        case_hint = "scenario:jordan_drought_1yr"
    top_success = next((c for c in cases if (c.get("kind") or "success") == "success"), None)
    sim = simulate_scenario(case_hint, top_success)
    esc = _escalation_signal(case_hint, sim, body.horizon_days)
    keys = ["available", "engine", "risk_before", "risk_after", "risk_reduction",
            "intervention_strength", "n_nodes", "seir_before", "seir_after",
            "series_before", "series_after"]
    if sim.get("engine") == "cascade":
        keys += ["rainfall_ratio", "sectors_after", "montecarlo", "non_mitigating",
                 "edge_weights", "baseline", "references", "label"]
    yield _ev("simulate", **{k: sim.get(k) for k in keys if k in sim}, escalation=esc)

    # ---- evidence: real, verified references (legal research agent) — for EVERY scenario ----
    # OpenAlex is English-indexed, so we search with an English query: the drought flagship
    # uses a curated seed; any other scenario gets one built from its domain / a model translation
    # of the Arabic text (never the raw Arabic, which retrieves nothing).
    if research_agent is not None:
        try:
            q = ("Jordan drought water scarcity groundwater agriculture"
                 if is_drought else _research_query(text, domain))
            ev = research_agent.gather(q, jordan=True, limit=6)
            yield _ev("evidence", items=ev.get("evidence", []),
                      count=len(ev.get("evidence", [])), abstained=ev.get("abstained"), query=q)
        except Exception:
            pass

    # ---- optional debate (gated: requested OR mixed precedents) AND meaningful ----
    successes = [c for c in cases if (c.get("kind") or "success") == "success"]
    failures = [c for c in cases if c.get("kind") == "failure"]
    should_debate = bool(body.run_debate or (successes and failures))
    if should_debate and roster:
        for turn in _stream_debate(roster, text, cases, sim, esc, using_llm):
            yield _ev("debate", **turn)

    # ---- detect + predict (deterministic fusion) ----
    engine = "grounded" if not qvec_real else "llm"
    verdict = _fuse(text, cases, sim, esc, flags, engine)
    yield _ev("detect_predict", **verdict)

    # ---- optional: validate + optimize the operator's proposed solution ----
    if (body.solution or "").strip():
        try:
            yield _ev("solution_eval",
                      **_evaluate_solution(text, body.solution, cases, case_hint, using_llm))
        except Exception:
            pass

    # ---- LEARN + SAVE this iteration (PII redacted on the write path) ----
    try:
        store_text = _guard.redact_pii(text) if _guard else text
        if scenario_runs is not None:
            scenario_runs.save_run(text=store_text, domain=domain, service=body.service or "",
                                   location=body.location or "", verdict=verdict, sim=sim)
        _feed_provisional(store_text, domain, body.service or "", body.location or "", verdict, sim)
    except Exception:
        pass

    yield _ev("done", engine=engine)


# --------------------------------------------------------------------------- #
# routes                                                                      #
# --------------------------------------------------------------------------- #
_OPTIONS_CACHE: Optional[dict] = None


@router.get("/api/scenario/options")
def scenario_options() -> dict:
    """Locations (governorates) + services for the scenario dropdowns, by volume."""
    global _OPTIONS_CACHE
    if _OPTIONS_CACHE is not None:
        return _OPTIONS_CACHE
    out: dict = {"locations": [], "services": []}
    if db is not None:
        try:
            out["locations"] = [
                {"value": r["governorate"], "count": int(r["n"])}
                for r in db.fetchall(
                    "select governorate, count(*) n from the_data "
                    "where governorate is not null and governorate <> '' group by 1 order by 2 desc")
                if r.get("governorate")
            ]
            out["services"] = [
                {"value": r["service_id"], "count": int(r["n"])}
                for r in db.fetchall(
                    "select service_id, count(*) n from the_data "
                    "where service_id is not null and service_id <> '' group by 1 order by 2 desc")
                if r.get("service_id")
            ]
            _OPTIONS_CACHE = out   # cache only on success
        except Exception:
            pass
    return out


@router.post("/api/scenario/detect")
def scenario_detect(body: ScenarioIn) -> StreamingResponse:
    return StreamingResponse(run_scenario(body), media_type=NDJSON)


class ReportIn(BaseModel):
    text: str = ""
    sim: Optional[dict] = None
    detection: Optional[dict] = None
    prediction: Optional[dict] = None
    confidence: Optional[dict] = None
    references: Optional[list] = None
    evidence: Optional[list] = None


@router.post("/api/scenario/report")
def scenario_report(body: ReportIn) -> dict:
    """Deterministic WRITTEN report (rich Arabic prose + structured references) from the
    accumulated run facts. Never raises; works with Ollama down."""
    if report_writer is None:
        return {"ok": False, "error": "report_writer unavailable"}
    from datetime import datetime, timezone
    gen = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    try:
        return {"ok": True, **report_writer.render(body.model_dump(), generated_at=gen)}
    except Exception as e:
        return {"ok": False, "error": str(e)[:160]}


@router.post("/api/scenario/retain")
def scenario_retain(body: RetainIn) -> dict:
    """Approval-gated write-back: close the CBR loop by storing an acted-on case.
    Deterministic id (source_case_id) makes re-submitting idempotent; semantic dedup
    only happens when Ollama is up (handled inside lessons)."""
    if not body.approved:
        return {"stored": False, "reason": "not_approved",
                "message_ar": "لم تُحفظ الحالة — تتطلّب موافقة المُشغّل."}
    if lessons is None:
        return {"stored": False, "reason": "lessons_unavailable"}
    payload = lessons.ReflectIn(
        domain=body.domain,
        root_cause_category=lessons._slug(body.text or body.intervention),
        root_cause_details=body.text,
        intervention=body.intervention,
        risk_before=body.risk_before,
        risk_after=body.risk_after,
        outcome=body.outcome,        # type: ignore[arg-type]
        worked=body.worked,
        source_case_id=body.source_case_id or f"scenario:{lessons._slug(body.text)}",
        confidence=body.confidence,
        risk_source="measured",
    )
    try:
        pub = lessons.reflect_and_store_lesson(payload)
        return {"stored": True, "id": pub.get("id"),
                "source_case_id": pub.get("source_case_id"),
                "message_ar": "تم حفظ الحالة في ذاكرة السوابق."}
    except Exception as e:
        return {"stored": False, "reason": str(e)[:160]}
