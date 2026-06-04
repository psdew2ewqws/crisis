"""report_swarm.py — RUNTIME multi-agent DELIBERATION for the crisis report.

This is the opposite of report_writer.py (which fills deterministic templates instantly).
Here a panel of persona-agents actually REASONS over the grounded facts and NEGOTIATES the
report across rounds, streamed live (NDJSON) so the operator watches the analysis happen:

    preflight -> round 1: each persona ANALYSES its domain (with reasoning)
              -> round 2: a negotiation round (challengers critique + reconcile)
              -> synthesis: the lead integrates the debate into a reasoned report
              -> report (structured sections) -> done

It needs a REACHABLE chat model (local Ollama, or a cloud model via GEMMA_BASE_URL). When no
model is reachable it streams a clear notice and FALLS BACK to the deterministic report_writer
so the user is never blocked — but the genuine deliberation only happens with a live model.
Every persona is grounded in the same facts and told not to invent numbers.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterator, List, Optional

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

try:
    from . import expert_chat as _ec   # reuse its model transport (local or cloud)
except Exception:  # pragma: no cover
    _ec = None  # type: ignore
try:
    from . import report_writer
except Exception:  # pragma: no cover
    report_writer = None  # type: ignore

router = APIRouter()
NDJSON = "application/x-ndjson"
MAX_TOKENS = 420

_BASE_SYS = (
    "أنت عضو في فريق إدارة أزمات للشرق الأوسط يكتب تقرير حالة لمتّخذ قرار. تحلّل بعمق وتبرّر "
    "استنتاجك بالأرقام المعطاة فقط — لا تختلق رقمًا أو مصدرًا. تتحدّث بالعربية الفصحى المهنية وبإيجاز "
    "محكم. ناقش ما قاله زملاؤك صراحةً (وافق أو اعترض مع التبرير)."
)

PERSONAS = [
    {"key": "lead", "name": "مدير أزمات الشرق الأوسط",
     "role": "قيادة الخلاصة والتقييم العام والمفاضلة بين الخيارات."},
    {"key": "water", "name": "محلّل الموارد المائية",
     "role": "تحليل المياه: السدود، الجوفية، الفاقد، وأثر عجز الأمطار، ولماذا التحلية لا تُجدي خلال سنة."},
    {"key": "humanitarian", "name": "قائد العمليات الإنسانية",
     "role": "أثر الأزمة على السكان والخدمات والمجتمعات المضيفة واللاجئين (تأطير تجميعي)."},
    {"key": "economist", "name": "الخبير الاقتصادي",
     "role": "الأثر الاقتصادي والغذائي: الأعلاف والثروة الحيوانية والأسعار والعملة، وتصحيح مغالطة المجاعة."},
    {"key": "comms", "name": "مسؤول اتصال المخاطر",
     "role": "تأطير عدم اليقين بلغة معايرة، وما الذي يجب توصيله ومتى."},
    {"key": "reviewer", "name": "مدقّق الإسناد",
     "role": "تحدّي كل ادّعاء: هل يُسنَد إلى الأرقام؟ أين المبالغة؟ ما الفجوة؟ تقرّر جاهزية النشر."},
]
_REBUTTERS = ["water", "economist", "humanitarian", "reviewer"]  # rebut each other per round
_VOTERS = ["reviewer", "lead", "water", "economist"]             # vote-to-converge panel


def _persona(key: str) -> Dict[str, str]:
    return next(pp for pp in PERSONAS if pp["key"] == key)


def _vote_is_ready(v: str) -> bool:
    """Tolerant parse of a convergence vote. Reads the first meaningful line and accepts
    «جاهز»/ready even with markdown, bullets, or quotes; rejects «غير جاهز»/«غير-جاهز»/not-ready.
    Defaults to NOT ready (the old brittle ``startswith('جاهز')`` misread every markdown/negated vote)."""
    for line in (v or "").splitlines():
        t = re.sub(r"^[\s*_#>\-••\"'«»·.:\(\)]+", "", line).strip()
        if not t:
            continue
        low = t.lower().replace(" ", "")
        if t.startswith("غير") or "notready" in low or "غير-جاهز" in t or "غيرجاهز" in low:
            return False
        if t.startswith("جاهز") or low.startswith("ready") or '"ready":true' in low:
            return True
        return False  # only the first meaningful line decides
    return False


def _facts_block(payload: Dict[str, Any]) -> str:
    sim = payload.get("sim") or {}
    det = payload.get("detection") or {}
    pred = payload.get("prediction") or {}
    ctx = report_writer.build_context(payload) if report_writer else {}
    lines = [
        f"الموقف: {(payload.get('text') or '').strip()}",
        f"الخطر المركّب دون تدخّل {ctx.get('risk_before','—')}/100 ({det.get('severity_ar','—')}، "
        f"{'متصاعد' if det.get('escalating') else 'مستقرّ'})؛ مع الروافع {ctx.get('risk_after','—')}/100 "
        f"({ctx.get('risk_delta','—')} نقطة).",
    ]
    if sim.get("engine") == "cascade":
        lines += [
            f"عجز الأمطار {ctx.get('rainfall_deficit','—')}؛ إجهاد القطاعات: مياه {ctx.get('sector_water','—')}، "
            f"زراعة {ctx.get('sector_agriculture','—')}، جوفية {ctx.get('sector_groundwater','—')}، اجتماعي {ctx.get('sector_social','—')}.",
            f"مونتي كارلو P10/P50/P90 = {ctx.get('mc_p10','—')}/{ctx.get('mc_p50','—')}/{ctx.get('mc_p90','—')}.",
            f"حقائق مقاسة: حصّة الفرد {ctx.get('renewable_pc','—')} م³ (2022)؛ السحب {ctx.get('withdrawals_pct','—')}%؛ "
            f"الفاقد ~{ctx.get('nrw_pct','—')}%؛ الجوفي ~{ctx.get('gw_ratio','—')}×؛ السدود {ctx.get('dam_latest','—')} مليون م³ (≈15%)؛ "
            f"استيراد الحبوب >{ctx.get('grain_import_pct','—')}% واحتياطي ~{ctx.get('grain_reserve','—')} أشهر؛ التحلية ~{ctx.get('desal_year','—')}.",
        ]
    refs = (sim.get("references") or [])[:6]
    if refs:
        lines.append("مراجع متاحة: " + "؛ ".join(r.get("name", "") for r in refs if r.get("name")))
    # Verified legal scholarly evidence (OpenAlex/Crossref/Unpaywall...) — for the agents to cite.
    evid = (payload.get("evidence") or [])[:5]
    cited = [f"{(e.get('title') or '').strip()[:90]}"
             f"{' (' + str(e.get('year')) + ')' if e.get('year') else ''}"
             for e in evid if e.get("title")]
    if cited:
        lines.append("أدلّة علمية مُتحقَّقة للاستشهاد (لا تختلق غيرها): " + "؛ ".join(cited))
    return "\n".join(lines)


def _ev(stage: str, **d: Any) -> bytes:
    return (json.dumps({"stage": stage, **d}, ensure_ascii=False) + "\n").encode("utf-8")


def _turn(system_extra: str, user: str, num_predict: int = 460) -> str:
    if _ec is None:
        return ""
    txt, _ok = _ec._call_model([
        {"role": "system", "content": _BASE_SYS + " " + system_extra},
        {"role": "user", "content": user},
    ], num_predict=num_predict)
    return (txt or "").strip()


# Final-report skeleton: the coordinator writes each section as its own (untruncated)
# call so the report is complete and rich, every section grounded in the live debate.
# A comprehensive, government-grade report skeleton. Each section is its own untruncated
# generation so the whole document runs 5+ pages of dense, decision-useful Arabic prose.
_REPORT_SECTIONS = [
    ("الملخّص التنفيذي", "Executive Summary (BLUF)",
     "اكتب الملخّص التنفيذي بأسلوب «الخلاصة أولًا»: القرار الحاسم المطلوب الآن، الأساس الرقمي له، والكلفة المتوقّعة "
     "للتأخير. 4–6 جمل مكثّفة موجّهة لمتّخذ القرار."),
    ("توصيف الموقف والسياق الزمني", "Situation & Timeline",
     "صِف الموقف بدقّة: ما الذي يحدث، أين، منذ متى، وما المؤشّرات المبكّرة؛ ضع خطًّا زمنيًّا مختصرًا (قبل/الآن/أفق 12 شهرًا) "
     "وميّز الصدمة الحادّة عن الهشاشة المزمنة بالأرقام."),
    ("التقييم العام ومستوى الخطر", "Overall Assessment & Risk Level",
     "قدّم التقييم العام: الشدّة والاتجاه ومؤشّر الخطر المركّب قبل/بعد الروافع، وأين تقع الرافعة الأكثر أثرًا وكم نقطة تشتريها، "
     "ومستوى الثقة في القراءة."),
    ("تحليل السبب الجذري وسلسلة التصعيد", "Root Cause & Cascade Chain",
     "حلّل السبب الجذري وسلسلة الانتقال السببية عبر القطاعات (كيف يقود العامل الأوّل إلى الثاني فالثالث)، وحدّد نقاط القطع "
     "التي يوقف التدخّل عندها التصعيد."),
    ("التحليل متعدّد القطاعات", "Multi-Sector Analysis",
     "حلّل كل قطاع ذي صلة على حدة (مثل: المياه، الزراعة، الجوفية، الصحّة، الطاقة، الاجتماعي حسب السيناريو): لكلٍّ الاحتياج ثمّ "
     "الاستجابة ثمّ الفجوة المتبقّية، مستندًا لأرقام الإجهاد القطاعي."),
    ("الأثر الاقتصادي والمالي", "Economic & Financial Impact",
     "اشرح الأثر الاقتصادي والمالي وقنوات الانتقال (الأعلاف والثروة الحيوانية، الأسعار، فاتورة الاستيراد، العملة والسيولة)، "
     "وصحّح أي مغالطة شائعة (مثل «مجاعة الخبز») بالأرقام؛ ميّز المقاس عن التقديري."),
    ("الأثر الإنساني والاجتماعي", "Humanitarian & Social Impact",
     "اشرح الأثر على السكّان والخدمات الأساسية والفئات الأكثر هشاشة والمجتمعات المضيفة واللاجئين، ومخاطر التوتّر الاجتماعي، "
     "بتأطير وطنيّ تجميعيّ دون استهداف فئويّ."),
    ("عدم اليقين والسيناريوهات", "Uncertainty & Scenarios",
     "اعرض عدم اليقين كجوهر الرسالة: مدى مونتي كارلو P10/P50/P90، السيناريو المتفائل والوسيط والمتشائم، ولماذا يُخطَّط على "
     "الطرف المرتفع مع إبراز الوسيط؛ ولا تخلط الرقم الحتميّ بوسيط مونتي كارلو."),
    ("الأدلّة والسوابق والمصادر", "Evidence, Precedents & Sources",
     "لخّص الأدلّة العلمية المُتحقَّقة (المذكورة في الحقائق فقط) والسوابق التاريخية ذات الصلة وما تعلّمناه منها؛ أسنِد كل ادّعاء "
     "ولا تختلق مصدرًا. إن غابت الأدلّة فصرّح بذلك."),
    ("خيارات التدخّل والمفاضلة", "Intervention Options & Trade-offs",
     "اعرض 3–4 خيارات تدخّل بديلة، ولكلٍّ: الأثر المتوقّع، الكلفة/الجدوى، السرعة، والمخاطر؛ ثمّ قارن بينها صراحةً ورجّح الأفضل "
     "مع تبرير المفاضلة."),
    ("خطة العمل الموصى بها", "Recommended Action Plan",
     "اكتب خطة عمل مرحلية قابلة للتنفيذ: فوريًّا (هذا الموسم)، ثمّ قصير/متوسط الأمد، ثمّ بنيويًّا بعيد الأمد؛ لكل إجراء الجهة "
     "المعنية ومؤشّر نجاح قابل للقياس وإطار زمنيّ."),
    ("المخاطر والافتراضات ومؤشّرات المتابعة", "Risks, Assumptions & Monitoring",
     "اذكر الافتراضات الحرجة التي يقوم عليها التحليل، المخاطر المتبقّية وما قد يُبطل الخطة، ومجموعة مؤشّرات متابعة محدّدة "
     "(ماذا نراقب، وعتبات التنبيه) لإعادة التقييم الدوريّ."),
]


class DeliberateIn(BaseModel):
    text: str = ""
    sim: Optional[dict] = None
    detection: Optional[dict] = None
    prediction: Optional[dict] = None
    confidence: Optional[dict] = None
    references: Optional[list] = None
    evidence: Optional[list] = None
    rounds: int = 2


def deliberate(payload: Dict[str, Any]) -> Iterator[bytes]:
    facts = _facts_block(payload)
    model_ok = bool(_ec and _ec.model_available())
    yield _ev("preflight", model_ok=model_ok, model=getattr(_ec, "GEMMA_MODEL", "") if _ec else "")

    # No live model -> stream a clear notice + the deterministic grounded report (never block).
    if not model_ok:
        yield _ev("fallback", reason="no_model",
                  message_ar="لا يوجد نموذج لغوي متاح للمداولة الحيّة الآن (النموذج المحلي/السحابي غير متصل). "
                             "هذا تقرير حتميّ مُسنَد فوريّ؛ لتشغيل مداولة الوكلاء الحيّة شغّل نموذجًا (Ollama محليًّا "
                             "أو وجّه GEMMA_BASE_URL إلى النموذج السحابي).")
        if report_writer is not None:
            doc = report_writer.render(payload)
            yield _ev("report", sections=doc["sections"], key_figures=doc["key_figures"],
                      references=doc["references"], deliberated=False)
        yield _ev("done", deliberated=False)
        return

    # ---- Round 1: each persona analyses its domain (with reasoning) ----
    transcript: List[str] = []
    for p in PERSONAS:
        text = _turn(
            f"دورك: {p['name']} — {p['role']}",
            f"الحقائق المشتركة:\n{facts}\n\nحلّل مجال اختصاصك أنت فقط في فقرتين موجزتين: ما استنتاجك وما مبرّره "
            f"بالأرقام المعطاة؟ لا تكتب تقريرًا كاملًا ولا ترويسات «إلى/من/تقرير حالة» — ابدأ مباشرة بالتحليل.")
        if not text:
            continue
        transcript.append(f"[{p['name']}] {text}")
        yield _ev("agent", persona=p["name"], role=p["key"], round=1, phase="analysis", text=text)

    # ---- Negotiation rounds: explicit agent-to-agent rebuttals, then a vote-to-converge.
    #      The panel decides when it is done (early stop on consensus, else maxRounds). ----
    max_rounds = max(2, min(int(payload.get("rounds", 3)), 5))
    converged = False
    r = 1
    while r < max_rounds and not converged:
        r += 1
        for key in _REBUTTERS:
            p = _persona(key)
            prior = "\n".join(transcript[-10:])
            text = _turn(
                f"دورك: {p['name']} — {p['role']}",
                f"الحقائق:\n{facts}\n\nالمداولة حتى الآن:\n{prior}\n\nخاطِب زميلًا بالاسم: وافقه أو اعترض عليه مع التبرير "
                f"بالأرقام، ثم اقترح تعديلًا محدّدًا على التقرير. جملتان أو ثلاث فقط، بلا ترويسات تقرير، ابدأ مباشرة.")
            if not text:
                continue
            transcript.append(f"[{p['name']} · ج{r}] {text}")
            yield _ev("agent", persona=p["name"], role=p["key"], round=r, phase="negotiation", text=text)

        # convergence vote
        ready = 0
        prior = "\n".join(transcript[-12:])
        for key in _VOTERS:
            p = _persona(key)
            v = _turn(
                f"دورك: {p['name']} — {p['role']}",
                f"بناءً على المداولة أدناه، هل التقرير جاهز للنشر لمتّخذ القرار؟ أجب بصيغة محدّدة: السطر الأوّل كلمة واحدة "
                f"فقط «جاهز» أو «غير جاهز»، ثمّ سطر ثانٍ بالسبب في جملة قصيرة. لا تكتب تقريرًا ولا فقرات.\n\nالمداولة:\n{prior}",
                num_predict=70)
            is_ready = _vote_is_ready(v)
            ready += 1 if is_ready else 0
            yield _ev("agent", persona=p["name"], role=p["key"], round=r, phase="vote", text=v)
        converged = ready >= 3   # majority of the 4-member panel
        yield _ev("tally", round=r, ready=ready, total=len(_VOTERS), converged=converged)

    # ---- Synthesis: the coordinator writes a COMPLETE, rich report — one
    #      untruncated call PER section, each grounded in the facts + the live debate,
    #      so nothing is cut off the way a single 512-token call was. ----
    yield _ev("synthesis", message_ar="يصيغ المُنسّق التقرير النهائي من خلاصة المداولة، قسمًا بقسم…",
              sections_total=len(_REPORT_SECTIONS))
    debate = "\n".join(transcript)
    converged_note = "وصل الفريق إلى توافق." if converged else "لم يكتمل التوافق؛ التقرير يدمج الخلاف المتبقّي."
    sections: List[Dict[str, Any]] = []
    for i, (title_ar, title_en, instruction) in enumerate(_REPORT_SECTIONS, 1):
        body = _turn(
            "دورك: المُنسّق الذي يكتب التقرير النهائي لصانع القرار مدمجًا خلاصة مداولة الفريق.",
            f"الحقائق:\n{facts}\n\nمداولة الفريق (استند إليها صراحةً):\n{debate}\n\nالمطلوب الآن — {instruction}\n"
            "ادخل في صلب هذا القسم مباشرة دون مقدّمة ودون إعادة تلخيص الوضع العام ودون عنوان ودون ترويسات «إلى/من». "
            "اكتب نثرًا عربيًّا رسميًّا غنيًّا ومفصّلًا (فقرتان إلى ثلاث فقرات، نحو 180–260 كلمة). أسنِد كل رقم إلى الحقائق "
            "المعطاة ولا تختلق رقمًا.",
            num_predict=1000)
        paras = [p.strip() for p in re.split(r"\n+", body or "")
                 if p.strip() and not p.strip().startswith("#")]
        if paras:
            sections.append({"title_ar": title_ar, "title_en": title_en, "paragraphs": paras})
        yield _ev("section", index=i, total=len(_REPORT_SECTIONS), title_ar=title_ar, ok=bool(paras))

    # Key figures + references stay deterministic & sourced (exact numbers, never model-made).
    det = report_writer.render(payload) if report_writer else {"sections": [], "key_figures": [], "references": {}}
    if len(sections) < 3:                      # model under-produced → fall back to the rich template
        sections = det["sections"]
    yield _ev("report", sections=sections, key_figures=det.get("key_figures", []),
              references=det.get("references", {}), deliberated=True, converged=converged,
              converged_note=converged_note)
    yield _ev("done", deliberated=True, turns=len(transcript))


@router.post("/api/scenario/report/deliberate")
def scenario_deliberate(body: DeliberateIn) -> StreamingResponse:
    return StreamingResponse(deliberate(body.model_dump()), media_type=NDJSON)
