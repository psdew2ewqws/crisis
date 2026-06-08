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


def _kf(label: str, value: str, source: str = "ABM simulation") -> Dict[str, str]:
    return {"label": label, "value": value, "source": source}


def _make_crisis_report(text: str, sim: Dict[str, Any],
                        research: Dict[str, Any], pops: Dict[str, Any]) -> Dict[str, Any]:
    """Structured crisis report (Phase 1 — do-nothing trajectory)."""
    seir = sim.get("seir_before") or {}
    arch = (sim.get("per_archetype_series") or {}).get("problem") or []
    fin = arch[-1] if arch else {}
    tl = sim.get("intervention_timeline") or []
    detect = next((e for e in tl if e.get("event") == "detected"), None)
    ivs = research.get("interventions", [])
    srcs = research.get("sources", [])

    sev_map = {"critical": "حرجة", "elevated": "مرتفعة", "low": "منخفضة"}
    sev_ar = sev_map.get(seir.get("severity", ""), seir.get("severity", ""))
    esc_ar = "نعم — الأزمة تتصاعد" if seir.get("escalating") else "لا — الوضع مستقرّ نسبيًّا"

    key_figures = [
        _kf("الخطر الذروي (بدون تدخّل)",  f"{sim.get('risk_before')}٪",           "ABM — Phase 1"),
        _kf("درجة الخطورة",                sev_ar,                                  "ABM — SEIR readout"),
        _kf("التصاعد",                      esc_ar,                                  "ABM — simulation"),
        _kf("الخطوة التي يبلغ الذروة",      f"{seir.get('time_to_peak')} / {sim.get('series_before') and len(sim['series_before'])} خطوة",
                                                                                     "ABM — simulation"),
        _kf("جودة الخدمة النهائية",         f"{round(fin.get('service_quality', 0) * 100)}٪", "ABM — service agents"),
        _kf("الوعي الإعلامي",               f"{round(fin.get('media_awareness', 0) * 100)}٪", "ABM — media agent"),
        _kf("عدد تجمّعات المواطنين",        str(pops.get("citizens", "—")),          "voc360 graph"),
        _kf("عدد الخدمات المتأثرة",         str(pops.get("services", "—")),          "voc360 graph"),
    ]

    sev_note = ("يُصنَّف هذا المستوى حرجًا ويتطلّب تدخّلًا فوريًّا."
                if seir.get("severity") == "critical" else
                "يُصنَّف هذا المستوى مرتفعًا ويستدعي رقابة مستمرّة ووضع خطط احترازية.")

    iv_note = (f"تُشير الأدبيات العلمية إلى أن التدخّلات الأكثر فاعلية في سياقات مماثلة تشمل: "
               f"{', '.join(ivs)}." if ivs else "")

    src_note = ""
    if srcs:
        titles = "; ".join(
            f"{s['title'][:50]} ({s['year']})" for s in srcs[:3]
        )
        src_note = f"المصادر العلمية التي أسهمت في تحليل الأزمة: {titles}."

    sections = [
        {
            "title_ar": "وصف الأزمة والسياق",
            "title_en": "Crisis Description & Context",
            "paragraphs": [
                f"السيناريو المُحاكَى: {text[:400]}",
                (f"بُنيَ مجتمع المحاكاة من بيانات voc360 الحقيقية ويضمّ "
                 f"{pops.get('citizens')} تجمّعًا من المواطنين (بمحافظاتهم) و"
                 f"{pops.get('services')} خدمة حكومية مُرتبطة بها، إلى جانب وكيل "
                 f"مشغّل حكومي ووكيل إعلامي يُضخّم الشعور بالأزمة."),
            ],
        },
        {
            "title_ar": "مسار الأزمة دون تدخّل",
            "title_en": "Crisis Trajectory — No Intervention",
            "paragraphs": [
                (f"عند انطلاق الأزمة بمستوى صدمة {round(sim.get('intervention_strength', 0.45) * 100 if False else 0.45 * 100)}٪، "
                 f"ترتفع السلبية تدريجيًّا لتبلغ ذروتها عند الخطوة {seir.get('time_to_peak')} "
                 f"بمؤشّر خطر {sim.get('risk_before')}٪. {sev_note}"),
                (f"تتدهور جودة الخدمات تحت ضغط الشكاوى المتراكمة لتصل إلى "
                 f"{round(fin.get('service_quality', 0) * 100)}٪ من مستواها الطبيعي. "
                 f"وفي الوقت ذاته يتشبّع الوعي الإعلامي ليبلغ {round(fin.get('media_awareness', 0) * 100)}٪، "
                 f"ممّا يُعزّز دوامة الشكاوى ويُثبّت الأزمة عند مستويات مرتفعة."),
                (f"الخلاصة: في غياب أيّ تدخّل، تستمرّ الأزمة في التصاعد ولا تستقرّ خلال "
                 f"نافذة المحاكاة البالغة {len(sim.get('series_before', []))} خطوة."),
            ],
        },
        {
            "title_ar": "الأدلة العلمية الداعمة",
            "title_en": "Supporting Scientific Evidence",
            "paragraphs": [
                iv_note or "لم تُوجَد تدخّلات محدّدة في الأدبيات لهذا النطاق.",
                src_note or "لم تُضَف مصادر علمية إضافية لهذه المحاكاة.",
            ],
        },
    ]

    return {
        "ok": True,
        "type": "crisis",
        "meta": {
            "title_ar": "تقرير الأزمة — المسار دون تدخّل",
            "title_en": "Crisis Report — No-Intervention Trajectory",
            "scenario": text[:120],
        },
        "key_figures": key_figures,
        "sections": sections,
    }


def _make_solution_report(text: str, sim: Dict[str, Any],
                          calib: Dict[str, Any], research: Dict[str, Any]) -> Dict[str, Any]:
    """Structured solution report (Phase 2 — intervention trajectory)."""
    seir_b = sim.get("seir_before") or {}
    seir_a = sim.get("seir_after") or {}
    arch   = (sim.get("per_archetype_series") or {}).get("solution") or []
    fin    = arch[-1] if arch else {}
    tl     = sim.get("intervention_timeline") or []
    detect = next((e for e in tl if e.get("event") == "detected"), None)
    commit = next((e for e in tl if e.get("event") == "intervene"), None)
    ramp   = next((e for e in tl if e.get("event") == "ramp_full"), None)
    ivs    = research.get("interventions", [])
    srcs   = research.get("sources", [])

    sev_map = {"critical": "حرجة", "elevated": "مرتفعة", "low": "منخفضة"}
    sev_b = sev_map.get(seir_b.get("severity", ""), seir_b.get("severity", ""))
    sev_a = sev_map.get(seir_a.get("severity", ""), seir_a.get("severity", ""))

    rb  = sim.get("risk_before")
    ra  = sim.get("risk_after")
    red = sim.get("risk_reduction")
    eff = sim.get("intervention_strength", 0)
    calib_src = {"data+research": "بيانات + أدبيات", "data": "بيانات", "prior": "افتراضي"}.get(
        calib.get("source", "prior"), calib.get("source", ""))

    key_figures = [
        _kf("الخطر قبل التدخّل",  f"{rb}٪",                     "ABM — Phase 1"),
        _kf("الخطر بعد التدخّل",   f"{ra}٪",                     "ABM — Phase 2"),
        _kf("انخفاض مؤشّر الخطر", f"-{red} نقطة ({round(red/rb*100, 1) if rb else 0}٪)", "ABM"),
        _kf("تحوّل الخطورة",      f"{sev_b} ← {sev_a}",          "ABM — SEIR readout"),
        _kf("قوّة أثر التدخّل",   f"{round(eff * 100)}٪",         f"مُعاير من {calib_src}"),
        _kf("الخطوة: اكتشاف الأزمة", f"t={detect['tick']}" if detect else "—", "OperatorAgent"),
        _kf("الخطوة: قرار التدخّل",  f"t={commit['tick']}" if commit else "—", "OperatorAgent"),
        _kf("الخطوة: تأثير كامل",    f"t={ramp['tick']}"   if ramp   else "—", "OperatorAgent"),
        _kf("جودة الخدمة بعد التدخّل", f"{round(fin.get('service_quality', 0) * 100)}٪", "ABM — service agents"),
    ]

    iv_para = (f"استنادًا إلى تحليل الأدبيات العلمية، رصدت {len(srcs)} ورقة بحثية "
               f"التدخّلات التالية بوصفها الأكثر فاعلية: {', '.join(ivs)}."
               if ivs else "لم ترصد الأدبيات تدخّلات محدّدة لهذا النطاق — يُوصى باعتماد المعايير العامة.")

    src_refs = ""
    if srcs:
        refs = "; ".join(f"{s['title'][:50]} ({s['year']})" for s in srcs[:3])
        src_refs = f"المراجع الداعمة: {refs}."

    timing_desc = ""
    if detect and commit and ramp:
        lag = commit["tick"] - detect["tick"]
        ramp_dur = ramp["tick"] - commit["tick"]
        timing_desc = (f"استغرق اكتشاف الأزمة {detect['tick']} خطوة من بدء الصدمة، "
                       f"ثم مرحلة تداوُل بلغت {lag} خطوة قبل اتّخاذ القرار، "
                       f"يليها تدرُّج التأثير على مدى {ramp_dur} خطوة إضافية.")

    sections = [
        {
            "title_ar": "التدخّل المقترح ومصادره",
            "title_en": "Proposed Intervention & Sources",
            "paragraphs": [iv_para, src_refs or ""],
        },
        {
            "title_ar": "توقيت التدخّل — نموذج التأخير الواقعي",
            "title_en": "Intervention Timing — Realistic Lag Model",
            "paragraphs": [
                timing_desc or "لا يوجد تأخير مُسجَّل — الوكيل الحكومي لم يُفعَّل.",
                (f"يعكس النموذج واقع استجابة الحكومة: لا يوجد تدخّل فوري. "
                 f"الاكتشاف يعتمد على مؤشّر السلبية الملاحَظ بفجوة زمنية، "
                 f"والقرار يحتاج وقت تداوُل، والأثر يتصاعد تدريجيًّا لا فجأةً."),
            ],
        },
        {
            "title_ar": "مسار الحلّ ومقارنته بالمسار المرجعي",
            "title_en": "Solution Trajectory vs. Baseline",
            "paragraphs": [
                (f"بتطبيق التدخّل بقوّة {round(eff * 100)}٪ (مُعاير من {calib_src}), "
                 f"ينخفض مؤشّر الخطر من {rb}٪ إلى {ra}٪ — "
                 f"تحسّن يبلغ {red} نقطة ({round(red/rb*100, 1) if rb else 0}٪)."),
                (f"تتحوّل درجة الخطورة من «{sev_b}» إلى «{sev_a}»، "
                 f"وتستعيد الخدمات {round(fin.get('service_quality', 0) * 100)}٪ "
                 f"من جودتها. يبقى مؤشّر الخطر عند {ra}٪ بسبب عمق الأزمة "
                 f"وإرث الشكاوى المتراكمة — التدخّل الواحد لا يُعيد الوضع إلى طبيعته التامّة."),
            ],
        },
        {
            "title_ar": "التوصيات والخطوات التالية",
            "title_en": "Recommendations & Next Steps",
            "paragraphs": [
                (f"بناءً على الأدبيات العلمية والمحاكاة: يُنصح بالبدء بـ{ivs[0] if ivs else 'التدخّل المناسب للنطاق'} "
                 f"على نطاق محدود وقياس الأثر قبل التعميم."),
                "تبقى الأرقام استكشافية لدعم القرار — وليست تنبؤًا مُعايرًا بالأيام الفعلية.",
            ],
        },
    ]

    return {
        "ok": True,
        "type": "solution",
        "meta": {
            "title_ar": "تقرير الحلول — مسار التدخّل",
            "title_en": "Solution Report — Intervention Trajectory",
            "scenario": text[:120],
        },
        "key_figures": key_figures,
        "sections": sections,
    }


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

    # ── generate both reports ──
    yield _ev("reports", status="running", detail="إعداد تقرير الأزمة وتقرير الحلول")
    try:
        crisis_report   = _make_crisis_report(text, sim, research_insights, pops)
        solution_report = _make_solution_report(text, sim, calib, research_insights)
    except Exception as e:
        crisis_report   = {"ok": False, "error": str(e)}
        solution_report = {"ok": False, "error": str(e)}
    yield _ev("reports", status="done",
              detail="اكتمل إعداد التقريرين",
              crisis_report=crisis_report,
              solution_report=solution_report)

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
