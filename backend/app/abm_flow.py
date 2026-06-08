"""Orchestration for the agent-based simulation (the "Agent-Based" tab).

Sequences the two-phase ABM as a streamed flow — mirroring deer_flow.py's
staged FlowEvent pattern — and exposes it at ``POST /api/abm/simulate`` as an
NDJSON stream the frontend consumes line by line:

    intake → seed_society → calibrate → simulate_problem
           → simulate_solution → compare → evidence → synthesize → done

Calibration runs BEFORE both phases so the do-nothing problem and the
intervention solution share the same data-fit spread/decay (a clean A/B whose
only difference is the operator). Each stage emits ``{stage, status, detail,
...data}``; the ``simulate_solution`` frame carries the full simulate payload at
top level so the existing ScenarioCharts component renders it unchanged.

Import-safe: degrades to grounded output if the LLM is down; never requires
langgraph/mesa/dowhy.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Iterator, Optional

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from . import abm_sim, abm_calibrate, mesa_sim

try:
    from . import research_agent as _research
except Exception:  # pragma: no cover
    _research = None  # type: ignore

try:
    from . import scenario as _scenario  # reuse _is_jordan_drought + domain seeds
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
    location: Optional[str] = None      # governorate id (seeds the graph)
    service: Optional[str] = None       # service_id (seeds the graph)
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


def _synthesize(text: str, sim: Dict[str, Any], calib: Dict[str, Any]) -> str:
    rb, ra = sim.get("risk_before"), sim.get("risk_after")
    red = sim.get("risk_reduction")
    tl = sim.get("intervention_timeline") or []
    commit = next((e for e in tl if e.get("event") == "intervene"), None)
    when = f"بعد {commit['tick']} خطوة من بدء الأزمة" if commit else "بعد فترة تأخّر واقعية"
    conf = {"high": "مرتفعة", "medium": "متوسطة", "low": "منخفضة"}.get(
        calib.get("confidence", "low"), "منخفضة")
    base = (
        f"يُظهر النموذج القائم على الوكلاء أنّ ترك الأزمة دون تدخّل يرفع مؤشّر الخطر إلى "
        f"{rb}٪. عند تدخّل الجهة المشغّلة {when} (مع تدرّج في الأثر), ينخفض الخطر إلى "
        f"{ra}٪ — أي تحسّن بمقدار {red} نقطة. حجم أثر التدخّل مُعاير من السجلّ التاريخي "
        f"(ثقة {conf}). الأرقام استكشافية لدعم القرار، وليست تنبؤًا مُعايرًا بالأيام."
    )
    if _llm is not None:
        try:
            if _llm.available():
                sysmsg = ("أنت محلّل أزمات. لخّص نتيجة محاكاة قائمة على الوكلاء في 3-4 جمل "
                          "بالعربية الفصحى المبسّطة، دون اختلاق أرقام جديدة.")
                user = f"الموقف: {text[:300]}\nالملخّص الكمّي: {base}"
                out = _llm.chat(sysmsg, user, temperature=0.3, max_tokens=200, timeout=12)
                if out and out.strip():
                    return out.strip()
        except Exception:
            pass
    return base


def run_abm_flow(body: ABMScenarioIn) -> Iterator[bytes]:
    """Yield NDJSON FlowEvent frames for the two-phase agent-based simulation."""
    text = (body.text or "").strip()
    steps = max(5, min(120, int(body.steps)))
    seed = int(body.seed)

    # ── intake ──
    case = _resolve_case(body)
    domain = body.domain
    if _scenario is not None and not domain:
        try:
            domain = "water" if _scenario._is_jordan_drought(text, case) else None
        except Exception:
            domain = None
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

    # ── calibrate (grounds BOTH phases) ──
    yield _ev("calibrate", status="running", detail="معايرة أثر التدخّل من السجلّ التاريخي")
    try:
        calib = abm_calibrate.calibrate(graph)
    except Exception:
        calib = {"available": True, "source": "prior",
                 "effect_size": abm_sim.DEFAULT_INTERVENTION_STRENGTH,
                 "confidence": "low", "refutation": {"available": False},
                 "notes_ar": "تعذّرت المعايرة — قيمة افتراضية."}
    yield _ev("calibrate", status="done",
              detail="اكتملت المعايرة", calibration=calib)

    # ── run both phases (deterministic, shared seed) ──
    yield _ev("simulate_problem", status="running",
              detail="محاكاة الأزمة دون تدخّل (السيناريو المرجعي)")
    try:
        sim = abm_sim.run_two_phase(graph, steps=steps, seed=seed,
                                    calib=calib, shock=body.shock)
    except Exception as e:
        yield _ev("error", status="error", detail=f"تعذّرت المحاكاة: {e}")
        yield _ev("done", engine="abm", aborted=True)
        return
    arch = sim.get("per_archetype_series") or {}
    yield _ev("simulate_problem", status="done",
              detail="المسار دون تدخّل",
              series=sim.get("series_before"), seir=sim.get("seir_before"),
              risk=sim.get("risk_before"), per_archetype=arch.get("problem"))

    # ── solution phase: full payload at top level (ScenarioCharts reads it) ──
    yield _ev("simulate_solution", status="done",
              detail="محاكاة التدخّل والحلّ المقترح", **sim)

    # ── compare ──
    yield _ev("compare", status="done", detail="مقارنة المسارين",
              risk_before=sim.get("risk_before"), risk_after=sim.get("risk_after"),
              risk_reduction=sim.get("risk_reduction"),
              intervention_timeline=sim.get("intervention_timeline"),
              lags=sim.get("lags"))

    # ── evidence: scholarly references (OpenAlex open-access) ──
    # Mirrors the evidence stage in scenario.py. OpenAlex indexes millions of
    # peer-reviewed papers; where open-access PDFs exist, their URLs are returned
    # (the same papers Sci-Hub provides, via legal open-access routes).
    if _research is not None and _scenario is not None:
        try:
            q = _scenario._research_query(text, domain or "")
            yield _ev("evidence", status="running", detail="البحث في الأدلة العلمية", query=q)
            res = _research.gather(q, jordan=True, limit=8)
            yield _ev("evidence", status="done",
                      items=res.get("evidence", []),
                      count=len(res.get("evidence", [])),
                      abstained=res.get("abstained", True),
                      query=q)
        except Exception:
            yield _ev("evidence", status="done", items=[], count=0, abstained=True)

    # ── synthesize ──
    yield _ev("synthesize", status="running", detail="صياغة الخلاصة")
    synthesis = _synthesize(text, sim, calib)
    yield _ev("synthesize", status="done", detail="اكتملت الخلاصة", synthesis=synthesis)

    yield _ev("done", engine="abm")


@router.post("/api/abm/simulate")
def abm_simulate(body: ABMScenarioIn) -> StreamingResponse:
    """Stream the two-phase agent-based simulation as NDJSON."""
    return StreamingResponse(run_abm_flow(body), media_type=NDJSON)
