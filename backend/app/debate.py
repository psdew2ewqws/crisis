"""AEGIS Crisis — multi-agent DEBATE engine (debate.router).

A small "society of agents" that ARGUES over the real voc360 evidence and lands
on a synthesized, Arabic-first solution — inspired by MiroFish / CAMEL-OASIS
(agents debate → a report agent synthesizes), but scoped to one decision and
GROUNDED: the shared dossier is assembled by composing the existing proof
helpers (whys + validate + evidence + forecast), so no agent invents facts.

Roles (each a distinct persona, Arabic-speaking):
  • المحلّل   (analyst)     — states what the data shows, nothing more.
  • المدافع   (advocate)    — argues this IS the root cause + proposes a fix.
  • المُعارِض (skeptic)     — challenges: cause vs symptom, coverage, alternatives.
  • المُنسّق   (synthesizer) — weighs the debate → final solution + confidence.

Each turn is produced by the LOCAL model (``llm.chat``, Ollama) when reachable;
when it is not, a deterministic Arabic argument is built from the same facts so
the feature still works (clearly flagged ``engine: "grounded"``).

  POST /api/debate   body {type: service|cluster|all, key?, rounds?}
       → streams NDJSON events: dossier → turn* → synthesis → done
"""
from __future__ import annotations

import json
from typing import Any, Dict, Iterator, List, Optional

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

try:
    from . import proof  # reuse the grounded dossier helpers
except Exception:  # pragma: no cover
    proof = None  # type: ignore
try:
    from . import llm
except Exception:  # pragma: no cover
    llm = None  # type: ignore
try:
    from . import memory_light  # LightMem-AEGIS consolidated topic memory
except Exception:  # pragma: no cover
    memory_light = None  # type: ignore

router = APIRouter()
NDJSON = "application/x-ndjson"

VERDICT_AR = {"valid": "مؤكَّد", "weak": "ضعيف", "insufficient": "غير كافٍ"}


# =========================================================================== #
# Dossier — the shared, grounded evidence every agent argues over.            #
# =========================================================================== #
def build_dossier(stype: str, key: Optional[str], depth: int = 5) -> Optional[Dict[str, Any]]:
    if proof is None:
        return None
    cluster_id = proof._resolve_cluster(stype, key)
    if not cluster_id:
        return None
    service = key if stype == "service" else None
    # LightMem: consolidated, topic-separated memory (clean) instead of raw noise
    memory: list = []
    if memory_light is not None:
        try:
            memory = memory_light.memory_for_cluster(cluster_id, limit=6)
        except Exception:
            memory = []
    return {
        "cluster_id": cluster_id,
        "subject": proof._build_subject(stype, key, cluster_id),
        "why": proof._why_bundle(stype, key, cluster_id, depth),
        "validation": proof._validation(cluster_id, service),
        "evidence": proof._evidence_segments(cluster_id, limit=6),
        "memory": memory,
        "forecast": proof._forecast(stype, key, cluster_id),
    }


def _label(d: Dict[str, Any]) -> str:
    s = d["subject"]
    return s.get("label_ar") or s.get("label_en") or s.get("cluster_id", "")[:8]


def _short(text: Optional[str], words: int = 5, chars: int = 90) -> str:
    """Clip a long Arabic label/quote (voc360 cluster labels are often raw
    citizen sentences) down to a clean, readable phrase."""
    t = (text or "").strip()
    if not t:
        return ""
    parts = t.split()
    if len(parts) > words:
        t = " ".join(parts[:words]) + "…"
    if len(t) > chars:
        t = t[:chars].rstrip() + "…"
    return t


def _short_label(d: Dict[str, Any]) -> str:
    s = d["subject"]
    return _short(s.get("label_ar")) or (s.get("label_en") or s.get("cluster_id", "")[:8])


def _factor(d: Dict[str, Any]) -> str:
    """The dominant sub-theme / factor (depth-1 of the why-chain), if any."""
    chain = (d.get("why") or {}).get("why_chain") or []
    for st in chain:
        if st.get("depth") in (1, "1") and (st.get("because") or st.get("because_en")):
            return st.get("because") or st.get("because_en")
    return _label(d)


def _facts_block(d: Dict[str, Any]) -> str:
    """Compact Arabic-first evidence block handed to every agent verbatim."""
    s = d["subject"]
    v = d.get("validation") or {}
    fc = d.get("forecast") or {}
    esc = (fc.get("escalation") or {}) if isinstance(fc, dict) else {}
    services = "، ".join(f"{svc} ({w})" for svc, w in (s.get("services") or [])[:5]) or "—"
    root = (d.get("why") or {}).get("root") or _factor(d)
    lines = [
        f"الموضوع (السبب الجذري المُرشّح): {_short_label(d)}  [{s.get('cluster_id','')[:8]}]",
        f"حجم الأدلة: {s.get('members', 0)} بلاغًا · متوسط الشدّة: {s.get('severity_avg', 0)} · إشارات مرتبطة: {s.get('signals', 0)}",
        f"الخدمات الأكثر تأثرًا: {services}",
        f"السلسلة السببية المُستخلصة: {root}" if root else "",
        f"نتيجة التحقّق: {VERDICT_AR.get(str(v.get('verdict')).lower(), v.get('verdict','—'))} · الثقة: {round(float(v.get('confidence') or 0)*100)}%",
    ]
    if esc:
        trend = "تصاعد" if esc.get("escalating") else "استقرار"
        lines.append(f"التنبؤ (٣٠ يومًا): {trend} · النسبة {round(float(esc.get('ratio') or 1), 2)}")
    # LightMem: topic-separated consolidated memory (compressed, de-noised) — the
    # agents argue over these clean topics instead of a raw quote dump.
    mem = d.get("memory") or []
    if mem:
        topics = "\n".join(
            f"  - «{m.get('topic')}» ({m.get('count')} بلاغ): {_short(m.get('summary'), words=22, chars=170)}"
            for m in mem[:5]
        )
        lines.append("محاور الشكوى المُجمّعة (ذاكرة LightMem):\n" + topics)
    else:
        ev = (d.get("evidence") or [])
        quotes = "\n".join(f"  - «{_short(e.get('segment_text'), words=14, chars=140)}»" for e in ev[:4] if e.get("segment_text"))
        if quotes:
            lines.append("عيّنات من أصوات المواطنين (حرفية):\n" + quotes)
    return "\n".join(x for x in lines if x)


# =========================================================================== #
# Agent personas.                                                             #
# =========================================================================== #
_BASE_SYS = (
    "أنت عضو في فريق تحليل أزمات للخدمات الحكومية الأردنية (منصّة AEGIS). "
    "تتحدث بالعربية الفصحى المبسّطة وبإيجاز. اعتمد فقط على الأدلة المعطاة ولا "
    "تختلق أرقامًا أو أسماء خدمات أو أسبابًا غير موجودة. كن واضحًا لمستخدم عادي."
)

ROLES: List[Dict[str, str]] = [
    {
        "key": "analyst", "name": "المحلّل",
        "task": "اعرض ما تقوله البيانات بدقّة في جملتين: ما هو السبب الأبرز وما حجم الأدلة عليه. لا تقترح حلولًا بعد.",
    },
    {
        "key": "advocate", "name": "المدافع",
        "task": "جادل بأن هذا هو السبب الجذري الحقيقي مستندًا إلى أصوات المواطنين، ثم اقترح حلًا عمليًا واحدًا واضحًا. جملتان أو ثلاث.",
    },
    {
        "key": "skeptic", "name": "المُعارِض",
        "task": "شكّك بمنطق: هل هذا سبب جذري أم مجرد عرَض؟ اذكر خطرًا أو سببًا بديلًا محتملًا، واستند إلى نتيجة التحقّق والثقة. جملتان أو ثلاث.",
    },
]

SYNTH = {
    "key": "synthesizer", "name": "المُنسّق",
    "task": (
        "بعد سماع المحلّل والمدافع والمُعارِض، قدّم الخلاصة لمستخدم عادي في ٣-٤ جمل: "
        "ما السبب الأرجح ولماذا، ما مستوى الثقة، ثم خطوة تنفيذية واحدة محدّدة للجهة المالكة. ابدأ بالخلاصة مباشرة."
    ),
}


# =========================================================================== #
# Turn generation — LLM when up, deterministic Arabic otherwise.              #
# =========================================================================== #
def _llm_turn(role: Dict[str, str], facts: str, transcript: List[Dict[str, str]]) -> Optional[str]:
    if llm is None:
        return None
    prior = "\n".join(f"{t['name']}: {t['text']}" for t in transcript) or "(لا نقاش سابق بعد)"
    user = (
        f"الأدلة المشتركة (من بيانات voc360 الحقيقية):\n{facts}\n\n"
        f"النقاش حتى الآن:\n{prior}\n\n"
        f"دورك ({role['name']}): {role['task']}"
    )
    try:
        return llm.chat(_BASE_SYS + " دورك: " + role["name"] + ".", user,
                        temperature=0.4, max_tokens=200, timeout=12)
    except Exception:
        return None


def _det_turn(role_key: str, d: Dict[str, Any]) -> str:
    """Deterministic Arabic argument from the real facts (LLM-down fallback).

    Uses a short clean label and refers back to it as «هذا المحور» to avoid the
    long-label repetition that makes the text hard to read.
    """
    s = d["subject"]
    label = _short_label(d)
    members = s.get("members", 0)
    sev = s.get("severity_avg", 0)
    v = d.get("validation") or {}
    verdict = VERDICT_AR.get(str(v.get("verdict")).lower(), "—")
    conf = round(float(v.get("confidence") or 0) * 100)
    # prefer a CLEAN, de-noised LightMem topic summary over a raw member quote
    mem = d.get("memory") or []
    if mem:
        quote = _short(mem[0].get("summary"), words=24, chars=170)
    else:
        ev = (d.get("evidence") or [])
        quote = next((_short(e.get("segment_text"), words=16, chars=150) for e in ev if e.get("segment_text")), None)
    services = "، ".join(svc for svc, _ in (s.get("services") or [])[:3]) or "الجهة المالكة"
    fc = d.get("forecast") or {}
    esc = (fc.get("escalation") or {}) if isinstance(fc, dict) else {}

    if role_key == "analyst":
        return (
            f"تُظهر البيانات أن «{label}» هو المحور المهيمن، بـ{members} بلاغًا "
            f"ومتوسط شدّة {sev}. الخدمات الأكثر تأثرًا: {services}."
        )
    if role_key == "advocate":
        q = f" ومن أصوات المواطنين: «{quote}»." if quote else "."
        return (
            f"أرى أن هذا المحور سبب جذري حقيقي لا مجرد مصادفة، إذ تتركّز عليه الأدلة وحجم البلاغات.{q} "
            f"الحل المقترح: توجيهه إلى {services} مع معالجة جذر المشكلة ومتابعة أثر التدخّل."
        )
    if role_key == "skeptic":
        tail = ""
        if esc:
            tail = (" ومع توقّع تصاعد الحجم، تبقى الأولوية مرتفعة." if esc.get("escalating")
                    else " كما أن الاتجاه مستقر، ما يخفّف الإلحاح.")
        return (
            f"لكن بحذر: نتيجة التحقّق «{verdict}» بثقة {conf}% فقط. هل هو سبب جذري فعلًا أم عرَض "
            f"لخلل أعمق في الإجراءات؟ يُنصح بفحص نسبة التغطية والأسباب البديلة قبل الجزم.{tail}"
        )
    # synthesizer
    return (
        f"الخلاصة: «{label}» هو السبب الأرجح حاليًا، يسنده {members} بلاغًا ومتوسط شدّة {sev}، "
        f"بمستوى ثقة {conf}% (تقييم {verdict}). "
        f"الخطوة التنفيذية: توجيهه إلى {services}، ومعالجة جذره، ثم قياس انخفاض البلاغات بعد التدخّل."
    )


def _citations(d: Dict[str, Any]) -> List[Dict[str, Any]]:
    s = d["subject"]
    out: List[Dict[str, Any]] = [{"type": "cluster", "id": s.get("cluster_id"), "label": _label(d)}]
    for svc, w in (s.get("services") or [])[:4]:
        out.append({"type": "service", "id": svc, "weight": w})
    for e in (d.get("evidence") or [])[:4]:
        if e.get("segment_text"):
            out.append({"type": "segment", "text": e["segment_text"]})
    return out


# =========================================================================== #
# Orchestration.                                                              #
# =========================================================================== #
def run_debate(stype: str, key: Optional[str]) -> Iterator[Dict[str, Any]]:
    d = build_dossier(stype, key)
    if not d:
        yield {"type": "error", "error": "لا يمكن تحديد سبب جذري لهذا الموضوع."}
        return

    using_llm = bool(llm and llm.available())
    s = d["subject"]
    yield {
        "type": "dossier",
        "subject": {
            "cluster_id": s.get("cluster_id"), "label_ar": s.get("label_ar"),
            "label_en": s.get("label_en"), "members": s.get("members"),
            "severity_avg": s.get("severity_avg"), "signals": s.get("signals"),
            "services": s.get("services"),
        },
        "validation": {"verdict": (d.get("validation") or {}).get("verdict"),
                       "confidence": (d.get("validation") or {}).get("confidence")},
        "memory": [{"topic": m.get("topic"), "summary": m.get("summary"), "count": m.get("count")}
                   for m in (d.get("memory") or [])[:5]],
        "memory_engine": "LightMem",
        "engine": "llm" if using_llm else "grounded",
        "model": (llm.LLM_MODEL if (using_llm and llm) else None),
        "report_url": f"/api/report/{s.get('cluster_id')}.xlsx",
    }

    facts = _facts_block(d)
    transcript: List[Dict[str, str]] = []

    # TOPIC DELEGATES — one agent per LightMem consolidated topic, so the swarm
    # SCALES WITH THE DATA (MiroFish-style: more topics → more voices). Each
    # delegate states why its facet of the issue matters before the role debate.
    for m in (d.get("memory") or [])[:8]:
        topic, count, summary = m.get("topic"), m.get("count"), m.get("summary")
        text = None
        if using_llm:
            try:
                text = llm.chat(
                    _BASE_SYS + f" دورك: مندوب محور «{topic}».",
                    f"الأدلة المشتركة:\n{facts}\n\nأنت مندوب محور «{topic}» ({count} بلاغ). "
                    f"اعرض في جملة واحدة لماذا يستحق هذا المحور الاهتمام ضمن القضية.",
                    temperature=0.4, max_tokens=110, timeout=10,
                )
            except Exception:
                text = None
        engine = "llm" if text else "grounded"
        if not text:
            text = (f"محور «{topic}» يضم {count} بلاغًا: {_short(summary, words=20, chars=150)} "
                    f"— أحد أوجه المشكلة التي يجب أخذها بالحسبان.")
        transcript.append({"name": f"مندوب · {topic}", "text": text})
        yield {"type": "turn", "role": "delegate", "agent": f"مندوب · {topic}",
               "text": text, "engine": engine}

    for role in ROLES:
        text = _llm_turn(role, facts, transcript) if using_llm else None
        engine = "llm" if text else "grounded"
        if not text:
            text = _det_turn(role["key"], d)
        transcript.append({"name": role["name"], "text": text})
        yield {"type": "turn", "role": role["key"], "agent": role["name"],
               "text": text, "engine": engine}

    # synthesis
    synth_text = _llm_turn(SYNTH, facts, transcript) if using_llm else None
    synth_engine = "llm" if synth_text else "grounded"
    if not synth_text:
        synth_text = _det_turn("synthesizer", d)
    yield {
        "type": "synthesis", "role": "synthesizer", "agent": SYNTH["name"],
        "text": synth_text, "engine": synth_engine,
        "confidence": (d.get("validation") or {}).get("confidence"),
        "verdict": (d.get("validation") or {}).get("verdict"),
        "citations": _citations(d),
        "report_url": f"/api/report/{s.get('cluster_id')}.xlsx",
    }
    yield {"type": "done"}


# =========================================================================== #
# Route.                                                                      #
# =========================================================================== #
class DebateIn(BaseModel):
    type: str = "all"
    key: Optional[str] = None
    rounds: Optional[int] = 1  # reserved for future multi-round


@router.post("/api/debate")
def debate(body: DebateIn) -> StreamingResponse:
    stype = body.type if body.type in ("service", "cluster", "all") else "all"

    def gen() -> Iterator[bytes]:
        try:
            for ev in run_debate(stype, body.key):
                yield (json.dumps(ev, ensure_ascii=False) + "\n").encode("utf-8")
        except Exception as e:  # never break the stream
            yield (json.dumps({"type": "error", "error": str(e)}, ensure_ascii=False) + "\n").encode("utf-8")

    return StreamingResponse(gen(), media_type=NDJSON)


__all__ = ["router", "run_debate", "build_dossier"]
