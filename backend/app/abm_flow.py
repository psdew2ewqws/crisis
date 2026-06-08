"""Orchestration for the agent-based simulation (the "Agent-Based" tab).

The flow now uses scholarly retrieval as a first-class calibration source.
Papers are fetched BEFORE the simulation runs so their abstracts can inform:
  • the shock level   (crisis severity extracted from paper language)
  • the effect size   (intervention impact drawn from paper measurements)
  • the interventions (domain-specific actions named in the literature)

Sequence:
    intake → research_intake → calibrate+merge → simulate_problem
           → simulate_solution → compare → synthesize → done

research_intake runs two OpenAlex queries in parallel:
  1. "{domain} crisis Jordan" — local context
  2. "{domain} intervention effect" — solution evidence
Results are mined by abm_calibrate.extract_research_insights(), then merged
into the voc360 data calibration via abm_calibrate.merge_with_research().

Import-safe: degrades to grounded output if any optional dep is missing.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Iterator, List, Optional

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from . import abm_sim, abm_calibrate, mesa_sim

try:
    from . import research_agent as _research
except Exception:  # pragma: no cover
    _research = None  # type: ignore

try:
    from . import scenario as _scenario
except Exception:  # pragma: no cover
    _scenario = None  # type: ignore

try:
    from . import llm as _llm
except Exception:  # pragma: no cover
    _llm = None  # type: ignore

try:
    import langgraph  # noqa: F401
    _HAS_LANGGRAPH = True
except Exception:  # pragma: no cover
    _HAS_LANGGRAPH = False

router = APIRouter()
NDJSON = "application/x-ndjson"


class ABMScenarioIn(BaseModel):
    text: str = ""
    domain: Optional[str] = None
    case_hint: Optional[str] = None
    location: Optional[str] = None
    service: Optional[str] = None
    steps: int = 50
    seed: int = 42
    shock: float = abm_sim.DEFAULT_SHOCK


def _ev(stage: str, **data: Any) -> bytes:
    return (json.dumps({"stage": stage, **data}, ensure_ascii=False) + "\n").encode("utf-8")


def _resolve_case(body: ABMScenarioIn) -> Optional[str]:
    if body.case_hint:
        return body.case_hint
    if body.service:
        return f"service:{body.service}"
    if body.location:
        return f"gov:{body.location}"
    return None


def _fetch_papers(query: str, jordan: bool = True, limit: int = 8) -> List[Dict[str, Any]]:
    """Fetch verified open-access papers; returns [] on any failure."""
    if _research is None:
        return []
    try:
        res = _research.gather(query, jordan=jordan, limit=limit)
        return res.get("evidence", [])
    except Exception:
        return []


def _synthesize(text: str, sim: Dict[str, Any], calib: Dict[str, Any],
                research: Dict[str, Any]) -> str:
    rb, ra = sim.get("risk_before"), sim.get("risk_after")
    red = sim.get("risk_reduction")
    tl = sim.get("intervention_timeline") or []
    commit = next((e for e in tl if e.get("event") == "intervene"), None)
    when = f"بعد {commit['tick']} خطوة" if commit else "بعد فترة تأخّر"
    conf = {"high": "مرتفعة", "medium": "متوسطة", "low": "منخفضة"}.get(
        calib.get("confidence", "low"), "منخفضة")

    ivs = research.get("interventions", [])
    iv_note = f" التدخّلات المُستحسَنة من الأدبيات: {', '.join(ivs)}." if ivs else ""

    base = (
        f"يُظهر النموذج القائم على الوكلاء أنّ ترك الأزمة دون تدخّل يرفع مؤشّر الخطر إلى "
        f"{rb}٪. عند تدخّل الجهة المشغّلة {when} (مع تدرّج في الأثر), ينخفض الخطر إلى "
        f"{ra}٪ — أي تحسّن بمقدار {red} نقطة. المعايرة مستخلصة من السجلّ التاريخي "
        f"والأدبيات العلمية (ثقة {conf}).{iv_note} "
        f"الأرقام استكشافية لدعم القرار، وليست تنبؤًا مُعايرًا بالأيام."
    )
    if _llm is not None:
        try:
            if _llm.available():
                sysmsg = ("أنت محلّل أزمات. لخّص نتيجة محاكاة قائمة على الوكلاء في 3-4 جمل "
                          "بالعربية الفصحى المبسّطة، دون اختلاق أرقام جديدة.")
                user = f"الموقف: {text[:300]}\nالملخّص الكمّي: {base}"
                out = _llm.chat(sysmsg, user, temperature=0.3, max_tokens=220, timeout=12)
                if out and out.strip():
                    return out.strip()
        except Exception:
            pass
    return base


def run_abm_flow(body: ABMScenarioIn) -> Iterator[bytes]:
    """Yield NDJSON FlowEvent frames for the research-informed two-phase ABM."""
    text = (body.text or "").strip()
    steps = max(5, min(120, int(body.steps)))
    seed = int(body.seed)

    # ── intake ──
    case = _resolve_case(body)
    domain = body.domain or ""
    if _scenario is not None and not domain:
        try:
            domain = "water" if _scenario._is_jordan_drought(text, case) else ""
        except Exception:
            domain = ""
    yield _ev("intake", status="done",
              detail="تهيئة السيناريو وربطه بسياق الأردن",
              case=case, domain=domain, steps=steps, seed=seed)

    # ── seed society ──
    try:
        graph = mesa_sim.build_graph_for_case(case)
    except Exception as e:
        yield _ev("error", status="error", detail=f"تعذّر بناء الرسم: {e}")
        yield _ev("done", engine="abm", aborted=True)
        return
    probe = abm_sim.CrisisABM(graph, steps=steps, seed=seed, shock=body.shock)
    pops = probe._run_populations()
    yield _ev("seed_society", status="done",
              detail="بناء مجتمع الوكلاء من بيانات voc360",
              agent_populations=pops, n_nodes=mesa_sim._g_node_count(graph),
              engine_notes={"mesa": bool(abm_sim._HAVE_MESA),
                            "langgraph": bool(_HAS_LANGGRAPH),
                            "dowhy": bool(abm_calibrate.available_dowhy())})

    # ── research intake (BEFORE simulation) ──
    # Two queries: crisis context + intervention evidence.
    # Papers mined for severity → shock, effect sizes → calibration, interventions → operator strategy.
    yield _ev("research_intake", status="running",
              detail="استرجاع الأدلة العلمية لمعايرة المحاكاة")
    all_papers: List[Dict[str, Any]] = []
    research_query = ""
    if _research is not None and _scenario is not None:
        try:
            research_query = _scenario._research_query(text, domain)
            crisis_papers = _fetch_papers(research_query, jordan=True, limit=6)
            # Second query for intervention evidence (global, not Jordan-scoped)
            iv_query = f"{domain or 'crisis'} intervention effectiveness reduction"
            iv_papers = _fetch_papers(iv_query, jordan=False, limit=4)
            # Dedupe by DOI
            seen = set()
            for p in crisis_papers + iv_papers:
                key = p.get("doi") or p.get("url") or p.get("title", "")
                if key and key not in seen:
                    seen.add(key)
                    all_papers.append(p)
        except Exception:
            pass

    research_insights = abm_calibrate.extract_research_insights(all_papers, domain)
    yield _ev("research_intake", status="done",
              detail=f"استُخلصت رؤى من {research_insights.get('n_contributing',0)} ورقة",
              papers=all_papers,
              insights=research_insights,
              query=research_query)

    # ── calibrate — merge voc360 data + research insights ──
    yield _ev("calibrate", status="running", detail="معايرة أثر التدخّل (بيانات + أدبيات)")
    try:
        data_calib = abm_calibrate.calibrate(graph)
    except Exception:
        data_calib = {"available": True, "source": "prior",
                      "effect_size": abm_sim.DEFAULT_INTERVENTION_STRENGTH,
                      "confidence": "low", "refutation": {"available": False},
                      "notes_ar": "تعذّرت المعايرة — قيمة افتراضية."}
    calib = abm_calibrate.merge_with_research(data_calib, research_insights)

    # Shock: paper-derived severity blended with body.shock (70/30 toward paper when available)
    shock = body.shock
    if research_insights.get("shock_hint") is not None:
        paper_shock = float(research_insights["shock_hint"])
        shock = round(0.70 * paper_shock + 0.30 * body.shock, 3)

    yield _ev("calibrate", status="done", detail="اكتملت المعايرة",
              calibration=calib, shock_used=shock)

    # ── simulate both phases ──
    yield _ev("simulate_problem", status="running",
              detail="محاكاة الأزمة دون تدخّل (السيناريو المرجعي)")
    try:
        sim = abm_sim.run_two_phase(graph, steps=steps, seed=seed,
                                    calib=calib, shock=shock)
    except Exception as e:
        yield _ev("error", status="error", detail=f"تعذّرت المحاكاة: {e}")
        yield _ev("done", engine="abm", aborted=True)
        return
    arch = sim.get("per_archetype_series") or {}
    yield _ev("simulate_problem", status="done",
              detail="المسار دون تدخّل",
              series=sim.get("series_before"), seir=sim.get("seir_before"),
              risk=sim.get("risk_before"), per_archetype=arch.get("problem"))

    # Solution payload + intervention recommendations from research
    sim["research_interventions"] = research_insights.get("interventions", [])
    sim["research_sources"] = research_insights.get("sources", [])
    yield _ev("simulate_solution", status="done",
              detail="محاكاة التدخّل والحلّ المقترح", **sim)

    yield _ev("compare", status="done", detail="مقارنة المسارين",
              risk_before=sim.get("risk_before"), risk_after=sim.get("risk_after"),
              risk_reduction=sim.get("risk_reduction"),
              intervention_timeline=sim.get("intervention_timeline"),
              lags=sim.get("lags"))

    # ── synthesize (cites research interventions) ──
    yield _ev("synthesize", status="running", detail="صياغة الخلاصة")
    synthesis = _synthesize(text, sim, calib, research_insights)
    yield _ev("synthesize", status="done", detail="اكتملت الخلاصة",
              synthesis=synthesis,
              papers=all_papers,
              insights=research_insights)

    yield _ev("done", engine="abm")


@router.post("/api/abm/simulate")
def abm_simulate(body: ABMScenarioIn) -> StreamingResponse:
    """Stream the research-informed two-phase agent-based simulation as NDJSON."""
    return StreamingResponse(run_abm_flow(body), media_type=NDJSON)
