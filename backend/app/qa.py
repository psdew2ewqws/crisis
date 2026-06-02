"""Grounded Q&A engine for voc360 — D-qa.

A deterministic, retrieval-first question-answering layer over the live voc360
Voice-of-Customer database. The hard rule (the trust boundary): **every number,
label and citation in an answer is RETRIEVED from real voc360 rows; the local
LLM only re-phrases those facts.** If the model is down, drifts, or invents a
number not present in ``facts[]``, the deterministic ``summary`` IS the answer.

Public surface (consumed by the ``api_v3`` router):

    ask(question: str, case: str | None = None) -> dict

Response shape::

    {question, intent, grounded: bool, answer: str,
     facts: [{label, value}],
     citations: [{type:"cluster|service|segment|engine", id?, label?|text?}],
     engine: "llm" | "fallback",
     followups: [str]}

Grounding decisions baked in (verified against the live schema + sibling code):
  * negativity predicate mirrors ``api_kpis``:
    ``lower(sentiment_label) like 'negative%%' or like 'high_severity%%'``.
  * daily timestamp key: ``nullif(date::text, '')::timestamp`` — both columns
    exist; ``observed_at`` is sometimes NULL on app-review rows.
  * the RIL cluster layer (``ril_*``) does NOT join ``the_data`` by id — a cluster
    is mapped to its services via ``cluster_link`` (text-recovered), never a join.
  * all params bound via psycopg ``%(name)s`` dict params (``db.fetchall`` supports
    both tuple and dict params).

Import-safe everywhere: ``db``/``llm`` are the only hard imports (both stdlib-only
transitively); every richer engine (``rootcause``, ``cluster_link``, ``solutions``,
``mesa_sim``, ``forecaster``/``forecast``, ``whys``, ``validate``, ``main_v2``) is
imported behind try/except and used only if present. No torch/timesfm dependency.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional, Tuple

# --- hard, always-present deps -------------------------------------------------
from . import db  # read-only voc360 access: fetchall(sql, params)->list[dict]

try:  # the LOCAL narration node (Ollama/OpenAI-compatible + grounded fallback)
    from . import llm
except Exception:  # pragma: no cover - llm should always import, but stay safe
    llm = None  # type: ignore

# --- optional engines (import-safe; used only when available) ------------------
try:
    from . import rootcause  # rank_root_causes(limit) -> [...]
except Exception:  # pragma: no cover
    rootcause = None  # type: ignore

try:
    from . import cluster_link  # cluster_services / cluster_signals / edges / links
except Exception:  # pragma: no cover
    cluster_link = None  # type: ignore

try:
    from . import solutions  # valid_solutions(limit, narrate)
except Exception:  # pragma: no cover
    solutions = None  # type: ignore

try:
    from . import mesa_sim  # simulate(case, intervene, ...)
except Exception:  # pragma: no cover
    mesa_sim = None  # type: ignore

# Forecaster: the v3 build names it `forecaster` (D-forecast); an older sketch
# called it `forecast`. Accept either, behind try/except, never hard-depend.
_forecaster = None
for _name in ("forecaster", "forecast"):
    try:
        _mod = __import__(f"{__package__}.{_name}", fromlist=[_name])
        if hasattr(_mod, "forecast_series") or hasattr(_mod, "forecast"):
            _forecaster = _mod
            break
    except Exception:  # pragma: no cover
        continue

try:
    from . import whys  # ask_whys({type,key}, max_depth, lang) -> {chain, root, graph, ...}
except Exception:  # pragma: no cover
    whys = None  # type: ignore

try:
    from . import validate as _validate  # validate_case(cluster_id, service) -> {...}
except Exception:  # pragma: no cover
    _validate = None  # type: ignore

try:
    from . import main_v2  # translate_label(ar, en), _norm_ar(s)
except Exception:  # pragma: no cover
    main_v2 = None  # type: ignore


# ===========================================================================
# Small grounded helpers (no fabrication; pure SQL/aggregation).
# ===========================================================================

# Exact negativity predicate from api_kpis (kept consistent with the KPI cards).
_NEG_PRED = (
    "(lower(sentiment_label) like 'negative%%' "
    "or lower(sentiment_label) like 'high_severity%%')"
)
# Daily timestamp expression (both columns exist; observed_at can be NULL).
_TS = "nullif(date::text, '')::timestamp"


def _translate(label_ar: Optional[str], label_en: Optional[str] = None) -> str:
    """English gloss for a cluster/service label (real ``canonical_label_en`` first)."""
    if main_v2 is not None and hasattr(main_v2, "translate_label"):
        try:
            return main_v2.translate_label(label_ar, label_en)
        except Exception:
            pass
    if label_en and str(label_en).strip():
        return str(label_en).strip()
    return (str(label_ar).strip() if label_ar else "") or "Unlabelled cluster"


def _norm(s: Optional[str]) -> str:
    if main_v2 is not None and hasattr(main_v2, "_norm_ar"):
        try:
            return main_v2._norm_ar(s)
        except Exception:
            pass
    if not s:
        return ""
    return re.sub(r"\s+", " ", str(s)).strip().lower()


def _safe_fetchall(sql: str, params: Optional[dict] = None) -> List[Dict[str, Any]]:
    """``db.fetchall`` that never raises — a DB blip degrades to an empty result."""
    try:
        return db.fetchall(sql, params)
    except Exception:
        return []


def _safe_fetchone(sql: str, params: Optional[dict] = None) -> Optional[Dict[str, Any]]:
    rows = _safe_fetchall(sql, params)
    return rows[0] if rows else None


def _services() -> List[Tuple[str, int]]:
    """Distinct real ``the_data.service_id`` values ranked by volume (cached)."""
    rows = _safe_fetchall(
        "select service_id, count(*) c from the_data "
        "where service_id is not null group by 1 order by c desc"
    )
    return [(r["service_id"], int(r["c"])) for r in rows]


# Cheap English-alias map so "bus"/"passports"/"transit" resolve to Arabic ids.
_ALIASES: List[Tuple[str, str]] = [
    ("sanad", "Sanad"), ("amman bus", "Amman Bus"), ("bus", "Amman Bus"),
    ("bekhedmetkom", "Bekhedmetkom"), ("bkhidmatkom", "Bekhedmetkom"),
    ("transit", "نقل_عام"), ("transport", "نقل_عام"), ("public transit", "نقل_عام"),
    ("نقل", "نقل_عام"),
    ("passport", "جوازات_السفر"), ("جواز", "جوازات_السفر"),
    ("road", "طرق_وبنية_تحتية"), ("infrastructure", "طرق_وبنية_تحتية"),
    ("e-service", "الخدمات_الإلكترونية"), ("electronic", "الخدمات_الإلكترونية"),
    ("service centre", "مراكز_الخدمة"), ("service center", "مراكز_الخدمة"),
]


def resolve_service(question: str) -> Optional[str]:
    """Best-effort: map free text to a real ``the_data.service_id``.

    Strategy: (1) direct case-insensitive substring against the real distinct
    ids; (2) the small English-alias table; (3) None. Never invents an id.
    """
    q = (question or "").lower()
    svcs = _services()
    by_vol = sorted(svcs, key=lambda x: -x[1])
    # (1) direct substring against the real ids (prefer the highest-volume hit).
    for sid, _c in by_vol:
        s = sid.lower()
        if s and (s in q or q in s):
            return sid
    # (2) alias table -> real id (only if that id actually exists).
    ids = {s for s, _ in svcs}
    for needle, target in _ALIASES:
        if needle in q and target in ids:
            return target
    return None


def resolve_cluster(question: str) -> Optional[Dict[str, Any]]:
    """Map free text to a real ``ril_problem_clusters`` row, by fuzzy label match.

    Returns the cluster row dict (cluster_id, labels, member_count, severity_avg,
    first/last seen) or None. Pure substring scoring over normalised Arabic — no
    fabrication.
    """
    q_norm = _norm(question)
    if not q_norm:
        return None
    rows = _safe_fetchall(
        "select cluster_id, canonical_label_ar, canonical_label_en, service_id, "
        "coalesce(member_count,0) member_count, coalesce(severity_avg,0) severity_avg, "
        "first_seen, last_seen "
        "from ril_problem_clusters where coalesce(member_count,0) > 1 "
        "order by coalesce(member_count,0)*(0.5+coalesce(severity_avg,0)) desc"
    )
    best: Optional[Dict[str, Any]] = None
    best_score = 0.0
    for r in rows:
        la = _norm(r.get("canonical_label_ar"))
        le = (r.get("canonical_label_en") or "").lower()
        score = 0.0
        # whole-label containment is the strongest signal
        if la and la in q_norm:
            score += 3.0 + len(la) / 40.0
        if le and le in q_norm:
            score += 3.0
        # token overlap (Arabic label tokens present in the question)
        toks = [t for t in la.split() if len(t) >= 3]
        if toks:
            hit = sum(1 for t in toks if t in q_norm)
            score += hit / len(toks)
        # weight slightly by cluster size so a tie favours the dominant cluster
        if score > 0:
            score += min(1.0, r["member_count"] / 600.0) * 0.25
        if score > best_score:
            best_score, best = score, r
    return best if best_score >= 1.0 else None


def _cluster_signals(cid: str) -> int:
    if cluster_link is not None:
        try:
            return int(cluster_link.cluster_signals(cid))
        except Exception:
            pass
    return 0


def _cluster_services(cid: str) -> List[Tuple[str, int]]:
    if cluster_link is not None:
        try:
            return [tuple(x) for x in cluster_link.cluster_services(cid)]
        except Exception:
            pass
    return []


def _segments(cid: str, limit: int = 3) -> List[str]:
    """Representative member ``segment_text`` for a cluster (closest-to-centroid)."""
    rows = _safe_fetchall(
        "select s.segment_text "
        "from ril_cluster_members m "
        "join ril_text_segments s on s.segment_id = m.segment_id "
        "where m.cluster_id = %(cid)s and length(s.segment_text) > 8 "
        "order by m.distance_to_centroid asc nulls last limit %(lim)s",
        {"cid": cid, "lim": limit},
    )
    return [r["segment_text"] for r in rows if r.get("segment_text")]


def _daily_volume(service: str) -> List[float]:
    """Dense, gap-filled daily volume for a service (oldest→newest), for forecasting."""
    rows = _safe_fetchall(
        f"select date_trunc('day', {_TS})::date d, count(*) v "
        f"from the_data where service_id = %(svc)s and {_TS} is not null "
        f"group by 1 order by 1",
        {"svc": service},
    )
    if not rows:
        return []
    import datetime as _dt

    by_day = {r["d"]: int(r["v"]) for r in rows}
    lo, hi = rows[0]["d"], rows[-1]["d"]
    out: List[float] = []
    day = lo
    while day <= hi:
        out.append(float(by_day.get(day, 0)))
        day = day + _dt.timedelta(days=1)
    return out


def _forecast(service: Optional[str], cid: Optional[str], horizon: int = 14) -> Optional[Dict[str, Any]]:
    """Run the optional forecaster on a service (or a cluster's service set).

    Returns ``{mean, source, escalation:{ratio,escalating,...}}`` or None when the
    forecaster module is unavailable / the series is too short. Honest ``source``.
    """
    if _forecaster is None:
        return None
    svc = service
    if svc is None and cid:
        svcs = _cluster_services(cid)
        svc = svcs[0][0] if svcs else None
    if not svc:
        return None
    y = _daily_volume(svc)
    if len(y) < 8:
        return None
    try:
        if hasattr(_forecaster, "forecast_series"):
            fc = _forecaster.forecast_series(y, horizon=horizon, season=7)
            mean = fc.get("mean") or fc.get("forecast") or []
            source = fc.get("source") or fc.get("method") or "statistical"
        else:  # pragma: no cover - alt module shape
            fc = _forecaster.forecast(y, horizon)  # type: ignore
            mean = fc.get("mean") or fc.get("forecast") or []
            source = fc.get("source") or fc.get("method") or "statistical"
    except Exception:
        return None
    esc = None
    try:
        if hasattr(_forecaster, "escalation"):
            esc = _forecaster.escalation(y, list(mean))
    except Exception:
        esc = None
    if esc is None:  # derive a grounded escalation flag from the numbers we have
        recent = sum(y[-14:]) / max(1, len(y[-14:]))
        fut = sum(mean) / max(1, len(mean)) if mean else 0.0
        ratio = (fut / recent) if recent > 0 else (2.0 if fut > 0 else 1.0)
        esc = {"recent_mean": round(recent, 1), "forecast_mean": round(fut, 1),
               "ratio": round(ratio, 2), "escalating": bool(ratio >= 1.2)}
    return {"mean": list(mean), "source": source, "escalation": esc, "service": svc}


# ===========================================================================
# The grounding prompt + the numeric guard (the trust boundary).
# ===========================================================================
QA_GROUNDING_PROMPT = (
    "أنت محلّل بيانات لمنصة voc360 لخدمات الجمهور في الأردن. "
    "أجب بالعربية الفصحى البسيطة والواضحة بحيث يفهمها المواطن العادي. "
    "اعتمد فقط على الحقائق (FACTS) المعطاة أدناه، واذكر الأرقام كما هي تمامًا "
    "دون تغيير أو تقريب. لا تضِف أي رقم أو خدمة أو عنقود أو جهة أو سبب أو اتجاه "
    "غير موجود في الحقائق، ولا تختلق أي معلومة. أبقِ التسميات العربية واقتباسات "
    "المواطنين كما هي حرفيًا. إذا كانت الحقائق لا تجيب عن السؤال، فأجب حرفيًا: "
    "\"I don't have voc360 data to answer that.\" "
    "كن مختصرًا (من 3 إلى 6 جمل)."
)

_NUM_RE = re.compile(r"\d+(?:[.,]\d+)?")


def _fact_number_set(facts: List[Dict[str, Any]]) -> set:
    """Collect every numeric token that appears in ``facts`` values (the allow-list)."""
    nums: set = set()
    for f in facts or []:
        v = f.get("value")
        for tok in _NUM_RE.findall(str(v)):
            nums.add(tok.replace(",", ""))
    return nums


def _llm_phrase(question: str, facts: List[Dict[str, Any]], summary: str,
                case: Optional[str], root_causes: Optional[list] = None) -> Tuple[str, str]:
    """Ask the LOCAL model to re-phrase ``facts`` under strict grounding.

    Returns ``(answer, engine)``. The numeric guard discards any model output
    that introduces a number not present in the facts — in which case the
    deterministic ``summary`` is returned with engine="fallback".
    """
    if llm is None:
        return summary, "fallback"
    context = {
        "case": case,
        "question": question,
        "facts": facts,
        "root_causes": root_causes or [],
    }
    try:
        text = llm.narrate(QA_GROUNDING_PROMPT + f"\n\nQUESTION: {question}", context)
    except Exception:
        return summary, "fallback"
    if not text or not str(text).strip():
        return summary, "fallback"
    text = str(text).strip()
    # Numeric guard: every number the model emits must exist in the facts.
    allow = _fact_number_set(facts)
    for tok in _NUM_RE.findall(text):
        norm = tok.replace(",", "")
        if norm in allow:
            continue
        # tolerate years already present in fact date strings & trivially-zero/round
        if any(norm in str(f.get("value")) for f in facts):
            continue
        return summary, "fallback"  # the model drifted -> use the grounded summary
    return text, "llm"


def _F(label: str, value: Any) -> Dict[str, Any]:
    return {"label": label, "value": value}


def _pct(n: int, d: int) -> int:
    return round(100.0 * n / d) if d else 0


def _result(question: str, intent: str, *, grounded: bool, answer: str,
            facts: List[Dict[str, Any]], citations: List[Dict[str, Any]],
            engine: str, followups: List[str]) -> Dict[str, Any]:
    return {
        "question": question,
        "intent": intent,
        "grounded": bool(grounded),
        "answer": answer,
        "facts": facts,
        "citations": citations,
        "engine": engine,
        "followups": followups,
    }


_NO_DATA = "I don't have voc360 data to answer that."


# ===========================================================================
# Intent classifier — rule-based AR+EN keyword, first-match-wins.
# ===========================================================================
# Order matters: earlier = higher priority. Each (intent, [triggers]).
_INTENTS: List[Tuple[str, List[str]]] = [
    ("compare", [
        "compare", "vs", "versus", "compared to", "compared with",
        "difference between", "which is worse", "which is better",
        "more complaints than", "worse than", "better than",
        "مقارنة", "مقابل", "الفرق بين", "أيهما", "قارن",
    ]),
    ("forecast", [
        "forecast", "predict", "projection", "outlook", "next 30 days",
        "next month", "next week", "coming weeks", "will it rise", "will grow",
        "escalate", "escalating", "escalation", "going forward",
        "توقع", "تنبؤ", "سيرتفع", "سيزيد", "تصعيد", "يتفاقم", "الشهر القادم",
    ]),
    ("recent_spike", [
        "what changed", "this week", "last 7 days", "week over week",
        "spike", "spiked", "spiking", "surge", "surged", "jumped",
        "what's new", "what is new", "recently",
        "ماذا تغير", "هذا الأسبوع", "ارتفاع مفاجئ", "تصاعد",
    ]),
    ("trend", [
        "getting better", "getting worse", "better or worse", "improving",
        "worsening", "deteriorating", "declining", "trend", "trending",
        "over time", "rising", "falling", "month over month",
        "أفضل", "أسوأ", "يتحسن", "يتفاقم", "اتجاه", "بمرور الوقت",
    ]),
    ("sentiment", [
        "sentiment", "mood", "tone", "satisfaction", "how do citizens feel",
        "negative share", "positive", "rating trend",
        "المشاعر", "الرضا", "كيف يشعر",
    ]),
    ("citizen_voice", [
        "what are citizens saying", "what are people saying", "citizen voice",
        "actual complaints", "real complaints", "evidence quotes", "show me quotes",
        "sample complaints", "verbatims", "in their own words",
        "ماذا يقول المواطنون", "آراء المواطنين", "اقتباسات", "أمثلة",
    ]),
    ("governorate", [
        "which governorate", "worst governorate", "by governorate", "per governorate",
        "geographic", "region", "province",
        "أي محافظة", "أسوأ محافظة", "محافظة",
    ]),
    ("solution", [
        "what should we do", "what can we do", "how do we fix", "how to fix",
        "how do we solve", "how to solve", "solution for", "recommendation",
        "recommend", "what's the fix", "action plan", "remedy", "mitigate",
        "ماذا نفعل", "كيف نحل", "ما الحل", "توصية",
    ]),
    ("validate", [
        "validate", "is it really the root cause", "really the root cause",
        "confirm root cause", "prove", "verify cause", "how confident",
        "confidence", "valid or symptom", "root cause or symptom",
        "هل فعلا السبب الجذري", "تحقق من السبب", "أثبت",
    ]),
    ("why_chain", [
        "why chain", "why-chain", "5 whys", "five whys", "5-whys",
        "walk me through why", "step by step why", "chain of why",
        "root-cause chain", "rootcause chain", "trace the cause",
        "سلسلة الأسباب", "لماذا ثم لماذا", "خطوة بخطوة",
    ]),
    ("cluster_subthemes", [
        "sub-themes", "subthemes", "sub themes", "the whys", "inside cluster",
        "within cluster", "breakdown of cluster", "themes in", "components of",
        "drill into cluster", "what makes up",
        "المواضيع الفرعية", "أسباب فرعية", "داخل العنقود",
    ]),
    ("root_cause", [
        "root cause", "root-cause", "why does", "why is", "what causes",
        "what is causing", "underlying cause", "real reason", "what drives",
        "main reason", "behind", "driving",
        "السبب الجذري", "ما سبب", "لماذا", "سبب المشكلة",
    ]),
    ("count", [
        "how many", "how much", "count", "number of", "total",
        "complaints about", "reports about", "signals about", "volume of",
        "كم عدد", "كم شكوى", "عدد الشكاوى",
    ]),
    ("source_channel", [
        "which source", "what source", "source of complaints", "which channel",
        "what channel", "channel breakdown", "which platform", "by source",
        "by channel", "by platform", "biggest source", "where are complaints coming from",
        "أي مصدر", "أي قناة", "مصدر الشكاوى",
    ]),
    ("temporal_onset", [
        "when did", "since when", "when did it start", "first appear",
        "first seen", "how long has", "began", "started", "onset", "emerged",
        "متى بدأ", "منذ متى", "أول مرة",
    ]),
    ("top_problems", [
        "top problems", "biggest problems", "main problems", "worst problems",
        "top root causes", "biggest issues", "top issues", "main complaints",
        "what are the problems", "top concerns",
        "أكبر المشاكل", "أهم المشاكل", "المشاكل الحالية",
    ]),
    ("national_summary", [
        "national summary", "state of public services", "overall picture",
        "how are services doing", "overview", "big picture", "national view",
        "country-wide", "national snapshot", "current situation",
        "ملخص وطني", "حالة الخدمات", "نظرة عامة", "الوضع الحالي",
    ]),
    ("owner", [
        "which agency", "which service owns", "who owns", "who is responsible",
        "responsible for", "ownership", "which department", "who handles",
        "accountable for",
        "مسؤول عن", "أي جهة", "من المسؤول",
    ]),
]


def classify(question: str) -> str:
    q = (question or "").lower()
    for intent, triggers in _INTENTS:
        for t in triggers:
            if t in q:
                return intent
    return "overview"


# ===========================================================================
# Retrieval + composition per intent.
# Each retriever returns a fully-formed result dict via ``_result``.
# ===========================================================================

def _strip_topic(question: str, triggers: List[str]) -> str:
    """Remove trigger phrases so what's left is the topic to resolve."""
    q = question or ""
    low = q.lower()
    for t in sorted(triggers, key=len, reverse=True):
        idx = low.find(t)
        if idx >= 0:
            q = (q[:idx] + " " + q[idx + len(t):]).strip()
            low = q.lower()
    return re.sub(r"\b(about|for|of|on|the|في|عن|لـ)\b", " ", q, flags=re.I).strip()


def _resolve_any(question: str, case: Optional[str]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Resolve the question to (cluster_row, service_id). Cluster wins.

    ``case`` is honoured first: a cluster_id-looking case resolves a cluster, a
    service-looking case resolves a service.
    """
    cl = resolve_cluster(question)
    svc = resolve_service(question)
    if cl is None and case:
        row = _safe_fetchone(
            "select cluster_id, canonical_label_ar, canonical_label_en, service_id, "
            "coalesce(member_count,0) member_count, coalesce(severity_avg,0) severity_avg, "
            "first_seen, last_seen from ril_problem_clusters where cluster_id = %(c)s",
            {"c": case},
        )
        if row:
            cl = row
    if svc is None and case:
        ids = {s for s, _ in _services()}
        if case in ids:
            svc = case
    return cl, svc


# --- root_cause ----------------------------------------------------------------
def retrieve_root_cause(question: str, case: Optional[str]) -> Dict[str, Any]:
    cl, svc = _resolve_any(question, case)
    cid = None
    if cl is None and svc is not None:
        # service topic -> its dominant cluster via the text linker
        if rootcause is not None:
            for r in rootcause.rank_root_causes(20):
                if any(s == svc for s, _ in _cluster_services(r["cluster_id"])):
                    cl = {
                        "cluster_id": r["cluster_id"],
                        "canonical_label_ar": r["label_ar"],
                        "canonical_label_en": r.get("label_en"),
                        "member_count": r["members"],
                        "severity_avg": r["severity_avg"],
                        "first_seen": None, "last_seen": None,
                    }
                    break
    if cl is None and rootcause is not None:
        ranked = rootcause.rank_root_causes(1)
        if ranked:
            r = ranked[0]
            cl = {
                "cluster_id": r["cluster_id"], "canonical_label_ar": r["label_ar"],
                "canonical_label_en": r.get("label_en"), "member_count": r["members"],
                "severity_avg": r["severity_avg"], "first_seen": None, "last_seen": None,
            }
    if cl is None:
        return _result(question, "root_cause", grounded=False, answer=_NO_DATA,
                       facts=[], citations=[], engine="fallback",
                       followups=_followups_root_cause(None))
    cid = cl["cluster_id"]
    label_ar = cl.get("canonical_label_ar") or ""
    label_en = _translate(label_ar, cl.get("canonical_label_en"))
    members = int(cl.get("member_count") or 0)
    sev = round(float(cl.get("severity_avg") or 0.0), 2)
    signals = _cluster_signals(cid)
    owners = _cluster_services(cid)
    owner_clause = ""
    if owners:
        os, oc = owners[0]
        owner_clause = f" Most signals are owned by the {_translate(os)} service ({oc})."
    segs = _segments(cid, 3)

    facts = [
        _F("Root-cause cluster (EN)", label_en),
        _F("Root-cause cluster (AR)", label_ar),
        _F("Member reports", members),
        _F("Avg severity", sev),
        _F("Recovered signals", signals),
    ]
    if owners:
        facts.append(_F("Owning service", f"{_translate(owners[0][0])} ({owners[0][1]})"))
    summary = (
        f"The dominant root cause is '{label_en}' ({label_ar}), grounded in "
        f"{members} clustered citizen reports at avg severity {sev}, with "
        f"{signals} real voc360 signals recovered to it by text-match.{owner_clause}"
    )
    if segs:
        summary += f" Citizens say: «{segs[0][:140]}»."
    citations = [{"type": "cluster", "id": cid, "label": label_ar}]
    citations += [{"type": "segment", "id": cid, "text": s[:140]} for s in segs]
    if owners:
        citations.append({"type": "service", "id": owners[0][0], "label": _translate(owners[0][0])})

    answer, engine = _llm_phrase(question, facts, summary, case or owners[0][0] if owners else case)
    return _result(question, "root_cause", grounded=True, answer=answer, facts=facts,
                   citations=citations, engine=engine,
                   followups=_followups_root_cause(label_en))


def _followups_root_cause(label: Optional[str]) -> List[str]:
    lbl = label or "this cluster"
    return [
        f"What are the dominant sub-themes inside {lbl} (the full 5-Whys chain)?",
        f"Is {lbl} really the root cause — validate its coverage, evidence, and trend?",
        f"Is {lbl} getting better or worse, and is it forecast to escalate?",
    ]


# --- cluster_subthemes ---------------------------------------------------------
def retrieve_cluster_subthemes(question: str, case: Optional[str]) -> Dict[str, Any]:
    cl, _svc = _resolve_any(question, case)
    if cl is None:
        # offer the available clusters rather than fabricate
        top = rootcause.rank_root_causes(8) if rootcause is not None else []
        opts = ", ".join(f"{_translate(r['label_ar'], r.get('label_en'))} ({r['members']})" for r in top)
        ans = (f"I don't have a cluster matching that topic. Clusters I can break "
               f"down: {opts}.") if opts else _NO_DATA
        return _result(question, "cluster_subthemes", grounded=False, answer=ans,
                       facts=[], citations=[], engine="fallback", followups=[])
    cid = cl["cluster_id"]
    label_ar = cl.get("canonical_label_ar") or ""
    label_en = _translate(label_ar, cl.get("canonical_label_en"))
    # Prefer the whys engine's sub-theme extraction when present.
    subthemes: List[Dict[str, Any]] = []
    if whys is not None:
        try:
            chain = whys.ask_whys({"type": "cluster", "key": cid}, max_depth=3, lang="ar")
            for step in chain.get("chain", []):
                for st in (step.get("subthemes") or []):
                    subthemes.append({"term": st.get("term"), "count": st.get("count")})
        except Exception:
            subthemes = []
    if not subthemes:  # deterministic Arabic-keyword fallback over member segments
        segs = _safe_fetchall(
            "select s.segment_text from ril_cluster_members m "
            "join ril_text_segments s on s.segment_id = m.segment_id "
            "where m.cluster_id = %(cid)s and length(s.segment_text) > 8 "
            "order by m.distance_to_centroid asc nulls last",
            {"cid": cid},
        )
        subthemes = _extract_terms([r["segment_text"] for r in segs], top_k=6)

    members = int(cl.get("member_count") or 0)
    sev = round(float(cl.get("severity_avg") or 0.0), 2)
    facts = [_F("Cluster (EN)", label_en), _F("Cluster (AR)", label_ar),
             _F("Member reports", members), _F("Avg severity", sev)]
    lines = []
    for i, st in enumerate(subthemes[:6], 1):
        if not st.get("term"):
            continue
        cnt = st.get("count")
        facts.append(_F(f"Sub-theme {i}", f"{st['term']} ({cnt})" if cnt is not None else st["term"]))
        lines.append(f"{i}. {st['term']}" + (f" — {cnt} segments" if cnt is not None else ""))
    samples = _segments(cid, 2)
    summary = (
        f"Cluster '{label_en}' ({label_ar}) groups {members} citizen problem-"
        f"segments (avg severity {sev}). Dominant sub-themes (the 'whys' inside): "
        + "; ".join(lines) + "."
    )
    if samples:
        summary += f" e.g. «{samples[0][:140]}»."
    citations = [{"type": "cluster", "id": cid, "label": label_ar}]
    citations += [{"type": "segment", "id": cid, "text": s[:140]} for s in samples]
    grounded = bool(lines)
    answer, engine = _llm_phrase(question, facts, summary, case) if grounded else (summary, "fallback")
    return _result(question, "cluster_subthemes", grounded=grounded, answer=answer,
                   facts=facts, citations=citations, engine=engine,
                   followups=[
                       f"What are citizens actually saying about {label_en}?",
                       f"Which service owns {label_en}, and is it the real root cause?",
                       f"Is {label_en} getting better or worse — forecast its volume.",
                   ])


def _extract_terms(segments: List[str], top_k: int = 6) -> List[Dict[str, Any]]:
    """Tiny Arabic-aware unigram frequency extractor (deterministic, no deps)."""
    from collections import Counter

    stop = {"في", "من", "على", "الى", "إلى", "عن", "مع", "هذا", "هذه", "ان", "أن",
            "the", "and", "for", "with", "that", "this", "are", "was", "not", "you"}
    counts: Counter = Counter()
    for seg in segments:
        norm = _norm(seg)
        for tok in norm.split():
            if len(tok) >= 3 and tok not in stop:
                counts[tok] += 1
    return [{"term": t, "count": c} for t, c in counts.most_common(top_k) if c >= 2]


# --- why_chain -----------------------------------------------------------------
def retrieve_why_chain(question: str, case: Optional[str]) -> Dict[str, Any]:
    cl, svc = _resolve_any(question, case)
    start = None
    if cl is not None:
        start = {"type": "cluster", "key": cl["cluster_id"]}
        entity_label = _translate(cl.get("canonical_label_ar"), cl.get("canonical_label_en"))
    elif svc is not None:
        start = {"type": "service", "key": svc}
        entity_label = _translate(svc)
    else:
        start = {"type": "all", "key": None}
        entity_label = "the national VOC graph"

    if whys is None:
        # Degrade to the root-cause answer (still grounded) — no fabrication.
        rc = retrieve_root_cause(question, case)
        rc["intent"] = "why_chain"
        return rc

    try:
        chain = whys.ask_whys(start, max_depth=5, lang="ar")
    except Exception:
        rc = retrieve_root_cause(question, case)
        rc["intent"] = "why_chain"
        return rc

    steps = chain.get("chain", [])
    if not steps:
        return _result(question, "why_chain", grounded=False,
                       answer=f"I don't have enough linked signals to build a why-chain for {entity_label}.",
                       facts=[], citations=[], engine="fallback", followups=[])
    facts: List[Dict[str, Any]] = []
    lines: List[str] = []
    citations: List[Dict[str, Any]] = []
    for st in steps:
        d = st.get("depth")
        q = st.get("question") or ""
        because = st.get("because") or ""
        because_en = st.get("because_en") or ""
        sig = st.get("signals")
        conf = st.get("confidence")
        facts.append(_F(f"Why #{d}: {q}",
                        f"{because} ({because_en}) — {sig} signals, conf {conf}"))
        lines.append(f"{d}. WHY {q} → BECAUSE {because} ({because_en}) "
                     f"— {sig} signals, confidence {conf}.")
        for ev in (st.get("evidence") or [])[:2]:
            citations.append({"type": "segment", "id": st.get("node_id"), "text": str(ev)[:140]})
    root = chain.get("root") or (steps[-1] if steps else {})
    facts.append(_F("Root cause", f"{root.get('because_en')} ({root.get('because')})"))
    facts.append(_F("Chain depth", len(steps)))
    summary = (
        f"Grounded {len(steps)}-step why-chain for {entity_label}:\n" + "\n".join(lines)
        + f"\nRoot cause: {root.get('because_en')} ({root.get('because')})."
    )
    answer, engine = _llm_phrase(question, facts, summary, case)
    out = _result(question, "why_chain", grounded=True, answer=answer, facts=facts,
                  citations=citations, engine=engine,
                  followups=[
                      f"Validate: is the root cause really the cause for {entity_label}?",
                      f"Forecast {entity_label} complaint volume — is it escalating?",
                      f"What is the recommended action for {entity_label}'s root cause?",
                  ])
    if chain.get("graph"):
        out["graph"] = chain["graph"]
    return out


# --- validate ------------------------------------------------------------------
def retrieve_validate(question: str, case: Optional[str]) -> Dict[str, Any]:
    cl, svc = _resolve_any(question, case)
    if cl is None:
        return _result(question, "validate", grounded=False,
                       answer="I don't have a clustered root cause matching that to validate.",
                       facts=[], citations=[], engine="fallback", followups=[])
    cid = cl["cluster_id"]
    label_en = _translate(cl.get("canonical_label_ar"), cl.get("canonical_label_en"))
    if _validate is not None and hasattr(_validate, "validate_case"):
        try:
            v = _validate.validate_case(cid, svc)
        except Exception:
            v = None
    else:
        v = None
    if v is None:
        # Grounded partial validation from coverage + evidence alone (no fabrication).
        signals = _cluster_signals(cid)
        members = int(cl.get("member_count") or 0)
        owners = _cluster_services(cid)
        svc_total = 0
        if owners:
            row = _safe_fetchone(
                "select count(*) n from the_data where service_id = %(s)s", {"s": owners[0][0]})
            svc_total = int(row["n"]) if row else 0
        coverage = round(signals / svc_total, 3) if svc_total else 0.0
        passes = (signals >= 20 or coverage >= 0.05) and members >= 5
        verdict = "valid" if (passes and members >= 8) else ("weak" if passes else "insufficient")
        facts = [_F("Verdict", verdict), _F("Recovered signals", signals),
                 _F("Coverage", coverage), _F("Member reports", members)]
        summary = (
            f"Verdict: {verdict.upper()} — '{label_en}' is backed by {members} clustered "
            f"segments and {signals} recovered signals (coverage {coverage:.0%}). "
            f"(Full multi-axis validation engine unavailable; this is the coverage+evidence check.)"
        )
        answer, engine = _llm_phrase(question, facts, summary, case)
        return _result(question, "validate", grounded=True, answer=answer, facts=facts,
                       citations=[{"type": "cluster", "id": cid, "label": cl.get("canonical_label_ar")}],
                       engine=engine, followups=_followups_validate(label_en))

    verdict = v.get("verdict", "insufficient")
    conf = v.get("confidence")
    facts = [_F("Verdict", verdict), _F("Confidence", conf)]
    lines = []
    for ch in v.get("checks", []):
        nm = ch.get("name")
        ok = "PASS" if ch.get("pass") else "weak"
        facts.append(_F(nm, f"{ch.get('value', ch.get('detail', ''))} — {ok}"))
        lines.append(f"  • {nm}: {ch.get('detail', ch.get('value', ''))} — {ok}.")
    summary = (
        f"Verdict: {verdict.upper()} — '{label_en}'. "
        f"Confidence {conf}.\n" + "\n".join(lines)
    )
    citations = [{"type": "cluster", "id": cid, "label": cl.get("canonical_label_ar")}]
    answer, engine = _llm_phrase(question, facts, summary, case)
    return _result(question, "validate", grounded=True, answer=answer, facts=facts,
                   citations=citations, engine=engine, followups=_followups_validate(label_en))


def _followups_validate(label: str) -> List[str]:
    return [
        f"What are the dominant sub-themes inside {label} (the deeper whys)?",
        f"Is {label} forecast to keep escalating over the next 30 days?",
        f"What valid solution would reduce {label}, and what does the simulation predict?",
    ]


# --- count ---------------------------------------------------------------------
def retrieve_count(question: str, case: Optional[str]) -> Dict[str, Any]:
    cl, svc = _resolve_any(question, case)
    where = ""
    params: Dict[str, Any] = {}
    scope = ""
    cid = None
    if cl is not None:
        cid = cl["cluster_id"]
        svc_list = [s for s, _ in _cluster_services(cid)]
        if svc_list:
            where = "service_id = any(%(svc_list)s)"
            params["svc_list"] = svc_list
            scope = f" linked to cluster '{_translate(cl.get('canonical_label_ar'), cl.get('canonical_label_en'))}'"
        else:
            return _result(question, "count", grounded=False, answer=_NO_DATA,
                           facts=[], citations=[], engine="fallback", followups=[])
    elif svc is not None:
        where = "service_id = %(svc)s"
        params["svc"] = svc
        scope = f", filtered to {_translate(svc)}"
    else:
        topic = _strip_topic(question, _trigger_for("count"))
        if not topic:
            return _result(question, "count", grounded=False, answer=_NO_DATA,
                           facts=[], citations=[], engine="fallback", followups=[])
        where = "coalesce(text_clean, text) ilike %(kw)s"
        params["kw"] = f"%{topic}%"
        scope = f", matched by text search for '{topic}'"

    head = _safe_fetchone(
        f"select count(*) total, "
        f"count(*) filter (where severity in ('high','critical')) high_critical, "
        f"count(*) filter (where {_NEG_PRED}) negative, "
        f"min({_TS}) first_seen, max({_TS}) last_seen "
        f"from the_data where {where}",
        params,
    )
    if not head or not head["total"]:
        return _result(question, "count", grounded=False,
                       answer=f"No matching complaints were found{scope or ''} in voc360 (the_data).",
                       facts=[_F("total", 0)], citations=[], engine="fallback", followups=[])
    total = int(head["total"])
    hc = int(head["high_critical"] or 0)
    neg = int(head["negative"] or 0)
    src = _safe_fetchall(
        f"select source_type, count(*) n from the_data where {where} and source_type is not null "
        f"group by 1 order by n desc limit 1", params)
    top_src = src[0] if src else None
    facts = [
        _F("Total complaints/signals", total),
        _F("High/critical severity", hc),
        _F("Negative sentiment", neg),
        _F("% negative", _pct(neg, total)),
        _F("% high/critical", _pct(hc, total)),
        _F("First seen", str(head.get("first_seen"))),
        _F("Last seen", str(head.get("last_seen"))),
    ]
    if top_src:
        facts.append(_F("Top source", f"{top_src['source_type']} ({top_src['n']})"))
    summary = (
        f"There are {total} complaints/signals{scope}. Of these, {hc} are high or "
        f"critical severity ({_pct(hc, total)}%) and {neg} carry negative sentiment "
        f"({_pct(neg, total)}%)."
    )
    if top_src:
        summary += f" Mostly via {top_src['source_type']} ({top_src['n']})."
    summary += f" They span {head.get('first_seen')} to {head.get('last_seen')}."
    citations: List[Dict[str, Any]] = [{"type": "service", "id": "the_data", "label": "the_data"}]
    if cid:
        citations.append({"type": "cluster", "id": cid, "label": cl.get("canonical_label_ar")})
    answer, engine = _llm_phrase(question, facts, summary, case)
    return _result(question, "count", grounded=True, answer=answer, facts=facts,
                   citations=citations, engine=engine,
                   followups=[
                       "What are the dominant sub-themes inside these complaints?",
                       "Is this complaint volume rising or falling — what's the forecast?",
                       "Which governorate or service has the worst share of these?",
                   ])


# --- governorate ---------------------------------------------------------------
def retrieve_governorate(question: str, case: Optional[str]) -> Dict[str, Any]:
    svc = resolve_service(question) or (case if case in {s for s, _ in _services()} else None)
    if not svc:
        # national: which governorate is worst overall (by negative share, volume floor)
        rows = _safe_fetchall(
            f"select governorate, count(*) signals, "
            f"count(*) filter (where {_NEG_PRED}) negative, "
            f"count(*) filter (where severity in ('high','critical')) critical "
            f"from the_data where governorate is not null "
            f"group by 1 having count(*) >= 3 "
            f"order by (count(*) filter (where {_NEG_PRED}))::float/greatest(count(*),1) desc, signals desc")
        if not rows:
            return _result(question, "governorate", grounded=False,
                           answer="Unknown — almost all the_data.governorate values are NULL, so I can't rank governorates.",
                           facts=[], citations=[], engine="fallback", followups=[])
        top = rows[0]
        facts = [_F("Worst governorate", top["governorate"]),
                 _F("Signals", int(top["signals"])),
                 _F("Negative", int(top["negative"])),
                 _F("% negative", _pct(int(top["negative"]), int(top["signals"])))]
        summary = (f"Among governorate-tagged signals, the worst is {top['governorate']} — "
                   f"{top['negative']}/{top['signals']} negative "
                   f"({_pct(int(top['negative']), int(top['signals']))}%).")
        answer, engine = _llm_phrase(question, facts, summary, case)
        return _result(question, "governorate", grounded=True, answer=answer, facts=facts,
                       citations=[{"type": "service", "id": "the_data", "label": "the_data.governorate"}],
                       engine=engine, followups=[])
    rows = _safe_fetchall(
        f"select governorate, count(*) signals, "
        f"count(*) filter (where {_NEG_PRED}) negative, "
        f"count(*) filter (where sentiment_label is not null) sentiment_known, "
        f"count(*) filter (where severity in ('high','critical')) critical, "
        f"count(*) filter (where severity is not null) severity_known "
        f"from the_data where service_id = %(svc)s and governorate is not null "
        f"group by 1 having count(*) >= 3 "
        f"order by (count(*) filter (where {_NEG_PRED}))::float/greatest(count(*) filter (where sentiment_label is not null),1) desc, signals desc",
        {"svc": svc})
    cov = _safe_fetchone(
        "select count(*) total, count(*) filter (where governorate is not null) geo_tagged, "
        "count(distinct governorate) filter (where governorate is not null) distinct_govs "
        "from the_data where service_id = %(svc)s", {"svc": svc})
    geo_tagged = int(cov["geo_tagged"]) if cov else 0
    total = int(cov["total"]) if cov else 0
    if not rows or geo_tagged == 0:
        return _result(question, "governorate", grounded=False,
                       answer=(f"Unknown — {_translate(svc)} has {geo_tagged}/{total} signals "
                               f"with a governorate, so there isn't enough geographic data to name a worst governorate."),
                       facts=[_F("geo-tagged", geo_tagged), _F("total", total)],
                       citations=[{"type": "service", "id": svc, "label": _translate(svc)}],
                       engine="fallback", followups=[])
    top = rows[0]
    neg_pct = _pct(int(top["negative"]), int(top["sentiment_known"] or 0)) if top["sentiment_known"] else 0
    crit_pct = _pct(int(top["critical"]), int(top["severity_known"] or 0)) if top["severity_known"] else 0
    facts = [
        _F("Service", _translate(svc)),
        _F("Worst governorate", top["governorate"]),
        _F("Negative there", f"{top['negative']}/{top['sentiment_known']}"),
        _F("% negative", neg_pct),
        _F("High/critical", f"{top['critical']}/{top['severity_known']}"),
        _F("% high/critical", crit_pct),
        _F("Governorate-tagged share", f"{geo_tagged}/{total}"),
    ]
    summary = (
        f"For {_translate(svc)}, the worst governorate is {top['governorate']} — "
        f"{top['negative']}/{top['sentiment_known']} signals there are negative ({neg_pct}%) "
        f"and {top['critical']}/{top['severity_known']} are high/critical ({crit_pct}%). "
        f"Note: only {geo_tagged}/{total} of this service's signals carry a governorate."
    )
    answer, engine = _llm_phrase(question, facts, summary, case)
    return _result(question, "governorate", grounded=True, answer=answer, facts=facts,
                   citations=[{"type": "service", "id": svc, "label": _translate(svc)}],
                   engine=engine, followups=[
                       f"Why is {top['governorate']} the worst for {_translate(svc)}?",
                       f"Show {_translate(svc)}'s trend in {top['governorate']} — is it escalating?",
                   ])


# --- source_channel ------------------------------------------------------------
def retrieve_source_channel(question: str, case: Optional[str]) -> Dict[str, Any]:
    svc = resolve_service(question) or (case if case in {s for s, _ in _services()} else None)
    where = "(%(svc)s::text is null or service_id = %(svc)s::text)"
    params = {"svc": svc}
    rows = _safe_fetchall(
        f"select source_type, count(*) total, count(*) filter (where {_NEG_PRED}) negative "
        f"from the_data where source_type is not null and {where} "
        f"group by 1 order by negative desc nulls last, total desc limit 6", params)
    if not rows:
        return _result(question, "source_channel", grounded=False,
                       answer=f"I don't have voc360 signals for {_translate(svc) if svc else 'that scope'} to attribute a source.",
                       facts=[], citations=[], engine="fallback", followups=[])
    denom = _safe_fetchone(
        f"select count(*) total, count(*) filter (where {_NEG_PRED}) negative "
        f"from the_data where {where}", params)
    t1 = rows[0]
    scope = _translate(svc) if svc else "all services nationally"
    total = int(denom["total"]) if denom else 0
    facts = [
        _F("Scope", scope),
        _F("Top source", t1["source_type"]),
        _F("Top source total", int(t1["total"])),
        _F("Top source negative", int(t1["negative"] or 0)),
        _F("Share of volume", _pct(int(t1["total"]), total)),
    ]
    if len(rows) > 1:
        facts.append(_F("Next source", f"{rows[1]['source_type']} ({int(rows[1]['negative'] or 0)} negative)"))
    summary = (
        f"For {scope}, complaints are driven primarily by the {t1['source_type']} source — "
        f"{t1['total']} signals ({_pct(int(t1['total']), total)}% of volume), of which "
        f"{int(t1['negative'] or 0)} are negative/high-severity."
    )
    if len(rows) > 1:
        summary += f" Next-largest: {rows[1]['source_type']} ({int(rows[1]['negative'] or 0)} negative)."
    quote = _safe_fetchone(
        f"select coalesce(text_clean,text) q from the_data "
        f"where source_type = %(ts)s and {where} and coalesce(text_clean,text) is not null and {_NEG_PRED} "
        f"order by (severity='critical') desc limit 1",
        {**params, "ts": t1["source_type"]})
    citations = [{"type": "service", "id": "the_data", "label": "the_data.source_type"}]
    if quote and quote.get("q"):
        summary += f" Citizens via {t1['source_type']} say: «{quote['q'][:140]}»."
        citations.append({"type": "segment", "id": "the_data", "text": quote["q"][:140]})
    answer, engine = _llm_phrase(question, facts, summary, case)
    return _result(question, "source_channel", grounded=True, answer=answer, facts=facts,
                   citations=citations, engine=engine,
                   followups=[
                       f"Is the {t1['source_type']} volume rising or falling?",
                       f"What sub-themes dominate the {t1['source_type']} complaints?",
                   ])


# --- citizen_voice -------------------------------------------------------------
def retrieve_citizen_voice(question: str, case: Optional[str]) -> Dict[str, Any]:
    cl, svc = _resolve_any(question, case)
    if cl is not None:
        cid = cl["cluster_id"]
        label = _translate(cl.get("canonical_label_ar"), cl.get("canonical_label_en"))
        quotes = _segments(cid, 6)
        if not quotes:
            return _result(question, "citizen_voice", grounded=False,
                           answer=f"I don't have citizen evidence for {label} in voc360.",
                           facts=[], citations=[], engine="fallback", followups=[])
        facts = [_F("Topic", label), _F("Member reports", int(cl.get("member_count") or 0)),
                 _F("Quotes shown", len(quotes))]
        summary = (f"Real citizen voices for '{label}':\n" +
                   "\n".join(f"• «{q[:200]}»" for q in quotes[:5]))
        citations = [{"type": "segment", "id": cid, "text": q[:140]} for q in quotes[:5]]
        answer, engine = _llm_phrase(question, facts, summary, case)
        return _result(question, "citizen_voice", grounded=True, answer=answer, facts=facts,
                       citations=citations, engine=engine,
                       followups=[f"What is the root cause behind these complaints about {label}?",
                                  f"Is the volume of complaints about {label} rising or falling?"])
    # signal-layer verbatims
    where = ""
    params: Dict[str, Any] = {}
    label = "this topic"
    if svc is not None:
        where = "service_id = %(svc)s"
        params["svc"] = svc
        label = _translate(svc)
    else:
        topic = _strip_topic(question, _trigger_for("citizen_voice"))
        if not topic:
            return _result(question, "citizen_voice", grounded=False, answer=_NO_DATA,
                           facts=[], citations=[], engine="fallback", followups=[])
        where = "coalesce(text_clean,text) ilike %(kw)s"
        params["kw"] = f"%{topic}%"
        label = topic
    rows = _safe_fetchall(
        f"select coalesce(text_clean,text) quote, source_type, severity, sentiment_label, "
        f"{_TS} at, governorate, record_id "
        f"from the_data where {where} and coalesce(text_clean,text) is not null "
        f"and length(coalesce(text_clean,text)) >= 12 "
        f"and coalesce(spam_flag,false)=false and coalesce(duplicate_flag,false)=false "
        f"order by ({_NEG_PRED}) desc, "
        f"case severity when 'critical' then 4 when 'high' then 3 when 'medium' then 2 when 'low' then 1 else 0 end desc, "
        f"at desc nulls last limit 8", params)
    if not rows:
        return _result(question, "citizen_voice", grounded=False,
                       answer=f"I don't have citizen evidence for {label} in voc360.",
                       facts=[], citations=[], engine="fallback", followups=[])
    cnt = _safe_fetchone(
        f"select count(*) total, count(*) filter (where {_NEG_PRED}) negative, "
        f"count(*) filter (where severity in ('high','critical')) severe "
        f"from the_data where {where}", params)
    total = int(cnt["total"]) if cnt else len(rows)
    neg = int(cnt["negative"]) if cnt else 0
    severe = int(cnt["severe"]) if cnt else 0
    facts = [_F("Signals about topic", total), _F("Negative", neg),
             _F("High/critical", severe), _F("Quotes shown", min(6, len(rows)))]
    lines = []
    citations = []
    for r in rows[:6]:
        meta = f"{r.get('source_type')} · {r.get('severity') or r.get('sentiment_label')}"
        lines.append(f"• «{r['quote'][:200]}» — [{meta}]")
        citations.append({"type": "segment", "id": str(r.get("record_id")), "text": r["quote"][:140]})
    summary = (f"Across {total} citizen signals about {label} ({neg} negative, {severe} "
               f"high/critical), citizens say:\n" + "\n".join(lines))
    answer, engine = _llm_phrase(question, facts, summary, case)
    return _result(question, "citizen_voice", grounded=True, answer=answer, facts=facts,
                   citations=citations, engine=engine,
                   followups=[f"What is the root cause behind these complaints about {label}?",
                              f"Is the volume of complaints about {label} rising or falling?"])


# --- sentiment / trend ---------------------------------------------------------
def retrieve_trend(question: str, case: Optional[str], intent: str = "trend") -> Dict[str, Any]:
    cl, svc = _resolve_any(question, case)
    target_svc = svc
    label = None
    cid = None
    if target_svc is None and cl is not None:
        cid = cl["cluster_id"]
        owners = _cluster_services(cid)
        target_svc = owners[0][0] if owners else None
        label = _translate(cl.get("canonical_label_ar"), cl.get("canonical_label_en"))
    if target_svc is None:
        return _result(question, intent, grounded=False,
                       answer="I couldn't resolve a service or cluster to judge a trend.",
                       facts=[], citations=[], engine="fallback", followups=[])
    if label is None:
        label = _translate(target_svc)
    cmp = _safe_fetchone(
        f"select "
        f"count(*) filter (where {_TS} >= (select max({_TS}) from the_data) - interval '30 days') recent_vol, "
        f"count(*) filter (where {_TS} >= (select max({_TS}) from the_data) - interval '60 days' "
        f"   and {_TS} < (select max({_TS}) from the_data) - interval '30 days') prior_vol, "
        f"count(*) filter (where {_TS} >= (select max({_TS}) from the_data) - interval '30 days' and {_NEG_PRED}) recent_neg, "
        f"count(*) filter (where {_TS} >= (select max({_TS}) from the_data) - interval '30 days' and sentiment_label is not null) recent_known, "
        f"count(*) filter (where {_TS} >= (select max({_TS}) from the_data) - interval '60 days' "
        f"   and {_TS} < (select max({_TS}) from the_data) - interval '30 days' and {_NEG_PRED}) prior_neg, "
        f"count(*) filter (where {_TS} >= (select max({_TS}) from the_data) - interval '60 days' "
        f"   and {_TS} < (select max({_TS}) from the_data) - interval '30 days' and sentiment_label is not null) prior_known "
        f"from the_data where service_id = %(svc)s",
        {"svc": target_svc})
    if not cmp or (not cmp["recent_vol"] and not cmp["prior_vol"]):
        return _result(question, intent, grounded=False,
                       answer=f"I don't have enough recent history for {label} to call a trend.",
                       facts=[], citations=[], engine="fallback", followups=[])
    rv, pv = int(cmp["recent_vol"] or 0), int(cmp["prior_vol"] or 0)
    vol_delta = round((rv - pv) / pv * 100) if pv else None
    neg_recent = _pct(int(cmp["recent_neg"] or 0), int(cmp["recent_known"] or 0))
    neg_prior = _pct(int(cmp["prior_neg"] or 0), int(cmp["prior_known"] or 0))
    neg_delta = neg_recent - neg_prior
    fc = _forecast(target_svc, cid, horizon=30)
    esc = fc["escalation"]["escalating"] if fc else None
    method = fc["source"] if fc else "n/a"
    # worst-of verdict
    vol_up = (vol_delta or 0) > 5
    neg_up = neg_delta > 3
    if vol_up and neg_up:
        verdict = "getting WORSE"
    elif (vol_delta or 0) < -5 and neg_delta < -3:
        verdict = "getting BETTER"
    elif (vol_delta is None) and abs(neg_delta) < 3:
        verdict = "roughly STABLE"
    else:
        verdict = "MIXED"
    facts = [
        _F("Service/cluster", label),
        _F("Recent 30d volume", rv),
        _F("Prior 30d volume", pv),
        _F("Volume delta %", vol_delta if vol_delta is not None else "n/a"),
        _F("Recent negative %", neg_recent),
        _F("Prior negative %", neg_prior),
        _F("Negative delta pts", neg_delta),
        _F("Forecast escalating", esc if esc is not None else "n/a"),
        _F("Forecast method", method),
    ]
    summary = (
        f"{label} is {verdict}: complaint volume {rv} (last 30d) vs {pv} (prior 30d)"
        + (f" ({vol_delta:+}%)" if vol_delta is not None else "")
        + f", negative share {neg_recent}% vs {neg_prior}% ({neg_delta:+} pts)."
    )
    if fc:
        summary += f" The {method} forecast over the next 30 days is {'escalating' if esc else 'not escalating'}."
    quote = _safe_fetchone(
        f"select coalesce(text_clean,text) q from the_data where service_id = %(svc)s "
        f"and coalesce(text_clean,text) is not null and {_TS} >= (select max({_TS}) from the_data) - interval '30 days' "
        f"order by ({_NEG_PRED}) desc, {_TS} desc nulls last limit 1", {"svc": target_svc})
    citations = [{"type": "service", "id": target_svc, "label": label}]
    if fc:
        citations.append({"type": "engine", "id": "forecast", "label": method})
    if quote and quote.get("q"):
        summary += f" Recent voice: «{quote['q'][:140]}»."
        citations.append({"type": "segment", "id": "the_data", "text": quote["q"][:140]})
    answer, engine = _llm_phrase(question, facts, summary, case)
    return _result(question, intent, grounded=True, answer=answer, facts=facts,
                   citations=citations, engine=engine,
                   followups=[
                       f"What sub-themes inside {label} grew the most (the whys)?",
                       f"Forecast the next 30 days for {label} — will it keep escalating?",
                       f"Which governorate or source is making {label} worse right now?",
                   ])


# --- forecast ------------------------------------------------------------------
def retrieve_forecast(question: str, case: Optional[str]) -> Dict[str, Any]:
    cl, svc = _resolve_any(question, case)
    cid = cl["cluster_id"] if cl is not None else None
    label = (_translate(cl.get("canonical_label_ar"), cl.get("canonical_label_en"))
             if cl is not None else (_translate(svc) if svc else None))
    if svc is None and cl is None:
        # national: rank services by escalation if the forecaster is present
        return _retrieve_escalation_scan(question, case)
    fc = _forecast(svc, cid, horizon=30)
    if fc is None:
        # degrade to the recent-vs-prior trend (still grounded)
        return retrieve_trend(question, case, intent="forecast")
    label = label or _translate(fc["service"])
    esc = fc["escalation"]
    trailing = esc["recent_mean"]
    proj = esc["forecast_mean"]
    ratio = esc["ratio"]
    verdict = "escalating" if esc["escalating"] else ("declining" if ratio < 0.85 else "stable")
    facts = [
        _F("Scope", label),
        _F("Trailing daily mean", trailing),
        _F("Projected daily mean", proj),
        _F("Ratio", ratio),
        _F("Verdict", verdict),
        _F("Forecaster", fc["source"]),
    ]
    summary = (
        f"Over the trailing window, {label} averaged {trailing} signals/day. The "
        f"{fc['source']} model projects ~{proj}/day over the next 30 days "
        f"(ratio {ratio}) → verdict: {verdict}."
    )
    citations = [{"type": "engine", "id": "forecast", "label": fc["source"]},
                 {"type": "service", "id": fc["service"], "label": _translate(fc["service"])}]
    if cid:
        citations.append({"type": "cluster", "id": cid, "label": cl.get("canonical_label_ar")})
    answer, engine = _llm_phrase(question, facts, summary, case)
    return _result(question, "forecast", grounded=True, answer=answer, facts=facts,
                   citations=citations, engine=engine,
                   followups=[
                       f"Is the NEGATIVE-sentiment share for {label} forecast to rise too?",
                       f"Across all services/clusters, which problem is escalating fastest?",
                       f"If we intervene on {label} now, what does the simulation say?",
                   ])


def _retrieve_escalation_scan(question: str, case: Optional[str]) -> Dict[str, Any]:
    """National: which service is forecast to escalate next."""
    candidates: List[Dict[str, Any]] = []
    for sid, vol in _services()[:12]:
        fc = _forecast(sid, None, horizon=14)
        if not fc:
            continue
        esc = fc["escalation"]
        growth = esc["ratio"] - 1.0
        if esc["escalating"] and esc["recent_mean"] >= 2:
            candidates.append({"service": sid, "label": _translate(sid),
                               "base": esc["recent_mean"], "proj": esc["forecast_mean"],
                               "growth": growth, "source": fc["source"]})
    candidates.sort(key=lambda c: -c["growth"])
    if not candidates:
        n = len(_services()[:12])
        ans = (f"No clear escalation detected in the next 14 days across {n} services "
               f"analysed; volumes look flat-to-declining within forecast bands.")
        return _result(question, "forecast", grounded=True, answer=ans,
                       facts=[_F("services analysed", n), _F("escalating", 0)],
                       citations=[{"type": "engine", "id": "forecast", "label": "statistical"}],
                       engine="fallback", followups=[])
    top = candidates[0]
    facts = [
        _F("Most likely to escalate", top["label"]),
        _F("Trailing daily mean", top["base"]),
        _F("Projected daily mean", top["proj"]),
        _F("Growth", f"{round(top['growth']*100)}%"),
        _F("Forecaster", top["source"]),
    ]
    summary = (
        f"Most likely to escalate next (14-day forecast): {top['label']}. Recent "
        f"baseline ≈ {top['base']} signals/day; the forecast projects ≈ {top['proj']}/day, "
        f"a {round(top['growth']*100)}% rise. Forecaster: {top['source']}."
    )
    if len(candidates) > 1:
        also = ", ".join(f"{c['label']} (+{round(c['growth']*100)}%)" for c in candidates[1:3])
        summary += f" Also rising: {also}."
    answer, engine = _llm_phrase(question, facts, summary, case)
    return _result(question, "forecast", grounded=True, answer=answer, facts=facts,
                   citations=[{"type": "engine", "id": "forecast", "label": top["source"]},
                              {"type": "service", "id": top["service"], "label": top["label"]}],
                   engine=engine,
                   followups=[
                       f"Why is {top['label']} escalating? (run the 5-whys why-chain)",
                       f"Show the 14-day volume forecast for {top['label']} with confidence bands.",
                       f"If we intervene on {top['label']} now, what does the simulation say?",
                   ])


# --- recent_spike --------------------------------------------------------------
def retrieve_recent_spike(question: str, case: Optional[str]) -> Dict[str, Any]:
    rows = _safe_fetchall(
        "with d as (select nullif(date,'')::date dy, service_id, severity, sentiment_label "
        "  from the_data where date is not null and date <> '' and service_id is not null), "
        "mx as (select max(dy) maxd from d), "
        "win as (select service_id, "
        "  count(*) filter (where dy > maxd - interval '7 days') last7, "
        "  count(*) filter (where dy <= maxd - interval '7 days' and dy > maxd - interval '14 days') prev7, "
        "  count(*) filter (where dy > maxd - interval '7 days' "
        "    and (severity in ('high','critical') "
        "      or sentiment_label in ('negative_citizen_sentiment','high_severity_complaint'))) neg7 "
        "  from d, mx group by service_id) "
        "select service_id, last7, prev7, neg7, (last7-prev7) delta, "
        "  case when prev7=0 then null else round((last7-prev7)::numeric/prev7*100,0) end pct_change, "
        "  (prev7=0 and last7>0) is_new "
        "from win where last7 >= 3 order by (last7-prev7) desc, last7 desc limit 6")
    maxd_row = _safe_fetchone("select max(nullif(date,'')::date) maxd from the_data where date <> ''")
    maxd = str(maxd_row["maxd"]) if maxd_row else "?"
    if not rows:
        return _result(question, "recent_spike", grounded=False,
                       answer=(f"No recent change detected: the latest voc360 data day is {maxd} "
                               f"and no service crossed the 3-signal threshold in the trailing week."),
                       facts=[_F("latest data day", maxd)], citations=[], engine="fallback", followups=[])
    movers = rows[:4]
    facts = [_F("Latest data day", maxd), _F("Movers", len(movers))]
    lines = []
    for r in movers:
        if r["is_new"]:
            lines.append(f"{r['service_id']}: {r['last7']} signals this week, none prior — newly surfaced.")
            facts.append(_F(r["service_id"], f"{r['last7']} (new this week)"))
        else:
            lines.append(f"{r['service_id']}: {r['last7']} vs {r['prev7']} last week "
                         f"({'+' if (r['pct_change'] or 0) >= 0 else ''}{r['pct_change']}%), "
                         f"{r['neg7']} high-severity/negative.")
            facts.append(_F(r["service_id"], f"{r['last7']} vs {r['prev7']} ({r['pct_change']}%)"))
    summary = (f"In the 7 days ending {maxd} (latest data), {len(movers)} service(s) moved vs "
               f"the prior week:\n" + "\n".join(f"• {ln}" for ln in lines))
    answer, engine = _llm_phrase(question, facts, summary, case)
    top = movers[0]["service_id"]
    return _result(question, "recent_spike", grounded=True, answer=answer, facts=facts,
                   citations=[{"type": "service", "id": "the_data", "label": "the_data"}],
                   engine=engine,
                   followups=[
                       f"Why did {top} spike this week — run the 5-whys root-cause chain.",
                       f"Will {top} keep rising? Show the 14-day forecast and escalation risk.",
                       f"Show the sample citizen reports behind this week's biggest mover.",
                   ])


# --- solution ------------------------------------------------------------------
def retrieve_solution(question: str, case: Optional[str]) -> Dict[str, Any]:
    cl, svc = _resolve_any(question, case)
    cid = cl["cluster_id"] if cl is not None else None
    if cid is None and svc is not None and rootcause is not None:
        for r in rootcause.rank_root_causes(20):
            if any(s == svc for s, _ in _cluster_services(r["cluster_id"])):
                cid = r["cluster_id"]
                cl = {"cluster_id": cid, "canonical_label_ar": r["label_ar"],
                      "canonical_label_en": r.get("label_en"), "member_count": r["members"],
                      "severity_avg": r["severity_avg"]}
                break
    if cid is None:
        return _result(question, "solution", grounded=False,
                       answer="I couldn't match a root-cause cluster to recommend an action for.",
                       facts=[], citations=[], engine="fallback", followups=[])
    item = None
    if solutions is not None:
        try:
            for s in solutions.valid_solutions(limit=20, narrate=False):
                if s["cluster_id"] == cid:
                    item = s
                    break
        except Exception:
            item = None
    label_en = _translate(cl.get("canonical_label_ar"), cl.get("canonical_label_en"))
    if item is None or not item.get("actions"):
        return _result(question, "solution", grounded=False,
                       answer=f"I don't have a grounded recommended action for {label_en}.",
                       facts=[_F("cluster", label_en)],
                       citations=[{"type": "cluster", "id": cid, "label": cl.get("canonical_label_ar")}],
                       engine="fallback", followups=[])
    a0 = item["actions"][0]
    facts = [
        _F("Cluster", label_en),
        _F("Agency", a0.get("agency")),
        _F("Action", a0.get("action")),
        _F("Expected impact", a0.get("expected_impact")),
        _F("Feasibility", a0.get("feasibility")),
        _F("Member reports", item.get("members")),
        _F("Signal count", item.get("signal_count")),
    ]
    summary = (
        f"To address {label_en}, the recommended action is: {a0.get('agency')} — "
        f"{a0.get('action')} Expected impact: {a0.get('expected_impact')} "
        f"(feasibility {a0.get('feasibility')}, {a0.get('timeframe')}). This is grounded "
        f"in {item.get('members')} clustered citizen reports ({item.get('signal_count')} matched signals)."
    )
    citations = [{"type": "cluster", "id": cid, "label": cl.get("canonical_label_ar")}]
    for ev in (item.get("evidence") or [])[:2]:
        citations.append({"type": "segment", "id": cid, "text": str(ev)[:140]})
    answer, engine = _llm_phrase(question, facts, summary, case)
    return _result(question, "solution", grounded=True, answer=answer, facts=facts,
                   citations=citations, engine=engine,
                   followups=[
                       f"Is {label_en} really the root cause, or just a symptom? (validate)",
                       f"Which agency owns {label_en} and what's their current SLA?",
                       f"How much would complaints drop if we act — show the simulation.",
                   ])


# --- compare -------------------------------------------------------------------
def retrieve_compare(question: str, case: Optional[str]) -> Dict[str, Any]:
    svcs = _services()
    ids = {s for s, _ in svcs}
    q = (question or "").lower()
    matched: List[str] = []
    for sid, _c in sorted(svcs, key=lambda x: -len(x[0])):
        if sid.lower() in q and sid not in matched:
            matched.append(sid)
    for needle, target in _ALIASES:
        if needle in q and target in ids and target not in matched:
            matched.append(target)
    if len(matched) < 2:
        return _result(question, "compare", grounded=False,
                       answer=("I couldn't identify both items to compare. Known services include: "
                               + ", ".join(s for s, _ in svcs[:6]) + "."),
                       facts=[], citations=[], engine="fallback", followups=[])
    a, b = matched[0], matched[1]

    def _side(sid: str) -> Dict[str, Any]:
        row = _safe_fetchone(
            f"select count(*) total, count(*) filter (where {_NEG_PRED}) negative, "
            f"count(*) filter (where severity in ('high','critical')) high_sev, "
            f"round(avg(rating)::numeric,2) avg_rating "
            f"from the_data where service_id = %(s)s", {"s": sid})
        return row or {"total": 0, "negative": 0, "high_sev": 0, "avg_rating": None}

    sa, sb = _side(a), _side(b)
    ta, tb = int(sa["total"] or 0), int(sb["total"] or 0)
    pa, pb = _pct(int(sa["negative"] or 0), ta), _pct(int(sb["negative"] or 0), tb)
    worse = a if pa >= pb else b
    facts = [
        _F(f"{_translate(a)} signals", ta),
        _F(f"{_translate(a)} % negative", pa),
        _F(f"{_translate(a)} high/critical", int(sa["high_sev"] or 0)),
        _F(f"{_translate(b)} signals", tb),
        _F(f"{_translate(b)} % negative", pb),
        _F(f"{_translate(b)} high/critical", int(sb["high_sev"] or 0)),
        _F("Worse on negativity", _translate(worse)),
    ]
    summary = (
        f"Comparing {_translate(a)} and {_translate(b)}: {_translate(a)} has {ta} signals "
        f"({pa}% negative, {int(sa['high_sev'] or 0)} high/critical) vs {_translate(b)}'s {tb} "
        f"({pb}% negative, {int(sb['high_sev'] or 0)}). {_translate(worse)} is worse on negativity."
    )
    citations = [{"type": "service", "id": a, "label": _translate(a)},
                 {"type": "service", "id": b, "label": _translate(b)}]
    answer, engine = _llm_phrase(question, facts, summary, case)
    return _result(question, "compare", grounded=True, answer=answer, facts=facts,
                   citations=citations, engine=engine,
                   followups=[
                       f"Why is {_translate(worse)} worse — show the why-chain?",
                       f"Forecast both for the next 30 days — which escalates first?",
                       f"Which governorate drives the gap between {_translate(a)} and {_translate(b)}?",
                   ])


# --- top_problems --------------------------------------------------------------
def retrieve_top_problems(question: str, case: Optional[str]) -> Dict[str, Any]:
    ranked = rootcause.rank_root_causes(5) if rootcause is not None else []
    if not ranked:
        return _result(question, "top_problems", grounded=False,
                       answer="No clustered root causes are available to rank right now.",
                       facts=[], citations=[], engine="fallback", followups=[])
    facts: List[Dict[str, Any]] = []
    lines: List[str] = []
    citations: List[Dict[str, Any]] = []
    for r in ranked:
        label = _translate(r["label_ar"], r.get("label_en"))
        owners = _cluster_services(r["cluster_id"])
        owner = f"{_translate(owners[0][0])} ({owners[0][1]})" if owners else "n/a"
        facts.append(_F(f"#{r['rank']} {label}", f"{r['members']} reports, severity {r['severity_avg']}"))
        lines.append(f"#{r['rank']} {label} — {r['members']} reports, severity {r['severity_avg']}; "
                     f"mainly affects {owner}.")
        citations.append({"type": "cluster", "id": r["cluster_id"], "label": r["label_ar"]})
        if r.get("evidence"):
            citations.append({"type": "segment", "id": r["cluster_id"], "text": str(r["evidence"][0])[:140]})
    summary = ("The top problems right now (ranked by citizen-report volume × severity):\n"
               + "\n".join(lines))
    answer, engine = _llm_phrase(question, facts, summary, case, root_causes=ranked)
    return _result(question, "top_problems", grounded=True, answer=answer, facts=facts,
                   citations=citations, engine=engine,
                   followups=[
                       f"Drill into #1 — what are the sub-themes (the whys)?",
                       f"Which of these top problems is forecast to escalate next?",
                       f"What's a valid solution for the top root cause?",
                   ])


# --- temporal_onset ------------------------------------------------------------
def retrieve_temporal_onset(question: str, case: Optional[str]) -> Dict[str, Any]:
    cl, svc = _resolve_any(question, case)
    label = None
    where = ""
    params: Dict[str, Any] = {}
    cid = None
    first_seen_cluster = None
    if cl is not None:
        cid = cl["cluster_id"]
        label = _translate(cl.get("canonical_label_ar"), cl.get("canonical_label_en"))
        first_seen_cluster = cl.get("first_seen")
        owners = _cluster_services(cid)
        if owners:
            svc = owners[0][0]
    if svc is not None:
        where = "service_id = %(svc)s"
        params["svc"] = svc
        if label is None:
            label = _translate(svc)
    else:
        return _result(question, "temporal_onset", grounded=False,
                       answer="I couldn't resolve a service or cluster to find an onset date.",
                       facts=[], citations=[], engine="fallback", followups=[])
    row = _safe_fetchone(
        f"select min({_TS})::date first_signal, max({_TS})::date last_signal, count(*) total "
        f"from the_data where {_TS} is not null and {where}", params)
    if not row or not row["total"]:
        return _result(question, "temporal_onset", grounded=False,
                       answer=f"I don't have temporal data for {label}.",
                       facts=[], citations=[], engine="fallback", followups=[])
    first = first_seen_cluster or row["first_signal"]
    facts = [
        _F("First recorded", str(first)),
        _F("Latest activity", str(row["last_signal"])),
        _F("Matching signals", int(row["total"])),
    ]
    summary = (f"Problem '{label}' was first recorded on {first}"
               + (" (RIL cluster first_seen)" if first_seen_cluster else " (earliest matching signal)")
               + f", with latest activity on {row['last_signal']} across {row['total']} matching signals.")
    citations = [{"type": "service", "id": svc, "label": label}]
    if cid:
        citations.append({"type": "cluster", "id": cid, "label": cl.get("canonical_label_ar")})
    answer, engine = _llm_phrase(question, facts, summary, case)
    return _result(question, "temporal_onset", grounded=True, answer=answer, facts=facts,
                   citations=citations, engine=engine,
                   followups=[
                       f"What is the root cause behind '{label}' since it started?",
                       f"Is '{label}' getting better or worse — forecast the next 30 days?",
                   ])


# --- owner ---------------------------------------------------------------------
def retrieve_owner(question: str, case: Optional[str]) -> Dict[str, Any]:
    cl, _svc = _resolve_any(question, case)
    if cl is None and rootcause is not None:
        cl = resolve_cluster(question)
    if cl is None:
        return _result(question, "owner", grounded=False,
                       answer="I don't have a problem cluster matching that to attribute an owner.",
                       facts=[], citations=[], engine="fallback", followups=[])
    cid = cl["cluster_id"]
    label = _translate(cl.get("canonical_label_ar"), cl.get("canonical_label_en"))
    owners = _cluster_services(cid)
    total = _cluster_signals(cid)
    if not owners:
        return _result(question, "owner", grounded=False,
                       answer=f"I couldn't recover an owning service for '{label}'.",
                       facts=[_F("cluster", label)],
                       citations=[{"type": "cluster", "id": cid, "label": cl.get("canonical_label_ar")}],
                       engine="fallback", followups=[])
    owner_svc, owner_count = owners[0]
    denom = sum(c for _, c in owners) or 1
    share = round(owner_count / denom, 2)
    facts = [
        _F("Problem", label),
        _F("Owning service", _translate(owner_svc)),
        _F("Owner signal count", owner_count),
        _F("Recovered signals total", total),
        _F("Owner share", f"{round(share*100)}%"),
    ]
    summary = (
        f"Problem '{label}' is owned primarily by the {_translate(owner_svc)} service — it "
        f"carries {owner_count} of {total} recovered signals on this problem ({round(share*100)}%)."
    )
    if len(owners) > 1:
        summary += f" Ownership is shared with {_translate(owners[1][0])} ({owners[1][1]} signals)."
    citations = [{"type": "cluster", "id": cid, "label": cl.get("canonical_label_ar")},
                 {"type": "service", "id": owner_svc, "label": _translate(owner_svc)}]
    answer, engine = _llm_phrase(question, facts, summary, case)
    return _result(question, "owner", grounded=True, answer=answer, facts=facts,
                   citations=citations, engine=engine,
                   followups=[
                       f"What are the dominant sub-themes inside '{label}' (the whys)?",
                       f"What is the valid solution for '{label}' and who should act?",
                       f"Is '{label}' getting worse — forecast the owning service.",
                   ])


# --- national_summary / overview ----------------------------------------------
def retrieve_national_summary(question: str, case: Optional[str]) -> Dict[str, Any]:
    agg = _safe_fetchone(
        f"select count(*) total, "
        f"count(distinct service_id) filter (where service_id is not null) services, "
        f"count(distinct source_type) sources, "
        f"count(*) filter (where severity in ('high','critical')) critical, "
        f"count(*) filter (where severity is not null) severity_known, "
        f"count(*) filter (where sentiment_label is not null and {_NEG_PRED}) negative, "
        f"count(*) filter (where sentiment_label is not null) sentiment_known, "
        f"min(date) first_day, max(date) last_day "
        f"from the_data")
    if not agg or not agg["total"]:
        return _result(question, "national_summary", grounded=False, answer=_NO_DATA,
                       facts=[], citations=[], engine="fallback", followups=[])
    total = int(agg["total"])
    neg_pct = _pct(int(agg["negative"] or 0), int(agg["sentiment_known"] or 0))
    crit_pct = _pct(int(agg["critical"] or 0), int(agg["severity_known"] or 0))
    worst = _safe_fetchall(
        f"select service_id, count(*) n, count(*) filter (where {_NEG_PRED}) neg "
        f"from the_data where service_id is not null group by 1 order by neg desc, n desc limit 3")
    ranked = rootcause.rank_root_causes(3) if rootcause is not None else []
    facts = [
        _F("Total signals", total),
        _F("Services", int(agg["services"] or 0)),
        _F("Sources", int(agg["sources"] or 0)),
        _F("% negative", neg_pct),
        _F("% high/critical", crit_pct),
        _F("First day", str(agg["first_day"])),
        _F("Last day", str(agg["last_day"])),
    ]
    for w in worst:
        facts.append(_F(f"Worst: {w['service_id']}", f"{w['neg']} negative / {w['n']} total"))
    rc_lines = []
    citations: List[Dict[str, Any]] = [{"type": "service", "id": "the_data", "label": "the_data (national)"}]
    for r in ranked:
        label = _translate(r["label_ar"], r.get("label_en"))
        facts.append(_F(f"Root cause #{r['rank']}", f"{label} — {r['members']} reports"))
        rc_lines.append(f"{label} ({r['members']} reports)")
        citations.append({"type": "cluster", "id": r["cluster_id"], "label": r["label_ar"]})
    worst_str = ", ".join(f"{w['service_id']} ({w['neg']} negative)" for w in worst)
    summary = (
        f"Across {total} citizen signals spanning {agg['services']} services and "
        f"{agg['sources']} sources ({agg['first_day']}→{agg['last_day']}), {neg_pct}% of "
        f"rated signals are negative and {crit_pct}% are high/critical. "
        f"Most negative load: {worst_str}."
    )
    if rc_lines:
        summary += f" Dominant root causes: {', '.join(rc_lines)}."
    answer, engine = _llm_phrase(question, facts, summary, None, root_causes=ranked)
    return _result(question, "national_summary", grounded=True, answer=answer, facts=facts,
                   citations=citations, engine=engine,
                   followups=[
                       "Which service should we prioritise first?",
                       "Show the why-chain for the top root cause.",
                       "Which problem is forecast to escalate over the next 14 days?",
                       "Break the national picture down by governorate.",
                   ])


# ===========================================================================
# Dispatch table.
# ===========================================================================
_RETRIEVERS: Dict[str, Callable[[str, Optional[str]], Dict[str, Any]]] = {
    "root_cause": retrieve_root_cause,
    "cluster_subthemes": retrieve_cluster_subthemes,
    "why_chain": retrieve_why_chain,
    "validate": retrieve_validate,
    "count": retrieve_count,
    "governorate": retrieve_governorate,
    "source_channel": retrieve_source_channel,
    "citizen_voice": retrieve_citizen_voice,
    "trend": retrieve_trend,
    "sentiment": retrieve_trend,
    "forecast": retrieve_forecast,
    "recent_spike": retrieve_recent_spike,
    "solution": retrieve_solution,
    "compare": retrieve_compare,
    "top_problems": retrieve_top_problems,
    "temporal_onset": retrieve_temporal_onset,
    "owner": retrieve_owner,
    "national_summary": retrieve_national_summary,
    "overview": retrieve_national_summary,
}


def _trigger_for(intent: str) -> List[str]:
    for name, trigs in _INTENTS:
        if name == intent:
            return trigs
    return []


# ===========================================================================
# Public entry point.
# ===========================================================================
def ask(question: str, case: Optional[str] = None) -> Dict[str, Any]:
    """Answer a free-text question, grounded entirely in real voc360 data.

    1. classify intent (rule-based AR+EN keyword, first-match-wins).
    2. retrieve real data for that intent → facts + citations + deterministic summary.
    3. LLM re-phrases the facts under strict grounding (numeric guard); on any
       miss the deterministic summary IS the answer.

    Never raises; degrades to a grounded "no data" answer. The LLM never sources
    a fact — it only phrases retrieved ones.
    """
    question = (question or "").strip()
    if not question:
        return _result("", "overview", grounded=False,
                       answer="Ask me about a service, root cause, forecast, or the national picture.",
                       facts=[], citations=[], engine="fallback", followups=[])
    intent = classify(question)
    retriever = _RETRIEVERS.get(intent, retrieve_national_summary)
    # `sentiment` and `trend` share a retriever but differ in the label passed.
    try:
        if retriever is retrieve_trend:
            return retrieve_trend(question, case, intent=intent)
        return retriever(question, case)
    except Exception:
        # Last-resort grounded degrade — never 500 the caller.
        try:
            return retrieve_national_summary(question, case)
        except Exception:
            return _result(question, intent, grounded=False, answer=_NO_DATA,
                           facts=[], citations=[], engine="fallback", followups=[])


__all__ = ["ask", "classify", "resolve_service", "resolve_cluster",
           "QA_GROUNDING_PROMPT"]


# ===========================================================================
# Manual smoke test (exercises classification + the grounded fallback path).
# ===========================================================================
if __name__ == "__main__":  # pragma: no cover
    import json

    for q in [
        "What is the root cause behind National Aid Fund delays?",
        "How many complaints about Sanad?",
        "Which service will escalate next?",
        "Compare Sanad and Amman Bus",
        "What are the top problems right now?",
        "Give me a national summary",
        "Is Sanad getting better or worse?",
        "What are citizens saying about Amman Bus?",
    ]:
        res = ask(q)
        print(f"\nQ: {q}\n  intent={res['intent']} grounded={res['grounded']} "
              f"engine={res['engine']} facts={len(res['facts'])}")
        print("  A:", res["answer"][:200].replace("\n", " "))
