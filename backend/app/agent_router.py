"""Phase 2 — skill-based agent router.

Given a novel free-text crisis scenario, pick the RIGHT subset of agents to convene,
by SKILL/DOMAIN — keyword/domain matching is the always-available PRIMARY signal; a
real embedding cosine is an OPTIONAL boost layered on top (never the only signal).

The router invents no new agents: every card references an EXISTING persona key from
``debate.py`` (the analyst/advocate/skeptic/synthesizer ROLES + the 9 EXPERTS). The
PERSONAS map below mirrors those names so this module stays import-light and
side-effect-free (importing it makes ZERO network calls and does not pull debate's
heavy dependency graph — the scenario orchestrator wires the chosen keys to debate's
turn helpers at run time).

Degradation contract:
  • Card embedding vectors are built LAZILY on first call, and ONLY when ``llm.embed``
    returns a real vector — hash-noise is never cached (a later call, after Ollama
    recovers, will populate them).
  • When no real query vector is available (Ollama down), the embedding term is 0 and
    keyword + domain affinity carry the selection — still grounded, never empty.
  • Floor roles (analyst + synthesizer) are ALWAYS seated so the panel is never empty;
    specialists are capped (default 4).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

try:
    from . import llm
except Exception:  # pragma: no cover
    llm = None  # type: ignore

try:
    from . import lessons  # for infer_domain only (import-safe)
except Exception:  # pragma: no cover
    lessons = None  # type: ignore


# Persona key -> Arabic name. Mirrors debate.ROLES / debate.SYNTH / debate.EXPERTS.
PERSONAS: Dict[str, str] = {
    "analyst": "المحلّل",
    "advocate": "المدافع",
    "skeptic": "المُعارِض",
    "synthesizer": "المُنسّق",
    "data": "خبير البيانات",
    "service": "خبير الخدمات",
    "citizen": "ممثّل المواطن",
    "ops": "خبير التنفيذ",
    "risk": "مدقّق المخاطر",
    "priority": "محلّل الأولويات",
    "comms": "خبير الاتصال الحكومي",
    "budget": "خبير الموازنة",
    "legal": "المستشار التنظيمي",
}

# Always seated — the panel is never empty and always has a framer + a closer.
FLOOR: List[str] = ["analyst", "synthesizer"]

DOMAINS = ("water", "healthcare", "supply_chain", "public_service", "other")

# Which specialist lenses each domain pulls in (a soft prior, not a hard filter).
_DOMAIN_AFFINITY: Dict[str, set] = {
    "water":          {"ops", "service", "data", "risk", "citizen"},
    "healthcare":     {"service", "citizen", "risk", "ops"},
    "supply_chain":   {"ops", "data", "budget", "priority"},
    "public_service": {"service", "citizen", "ops", "comms"},
    "other":          {"data", "risk", "priority"},
}

# Selectable specialists (floor roles excluded). Each references a debate persona key.
# keywords are bilingual trigger tokens; utterances seed the lazy embedding vector.
CARDS: List[Dict[str, Any]] = [
    {"key": "advocate", "base": 0.34,
     "keywords": {"حلول", "تدخل", "معالجة", "solution", "intervention", "propose"},
     "utterances": ["نقترح حلًا عمليًا لمعالجة جذر المشكلة", "propose a practical intervention to fix the root cause"]},
    {"key": "skeptic", "base": 0.34,
     "keywords": {"سبب", "عرض", "بديل", "شك", "symptom", "alternative", "uncertain", "challenge"},
     "utterances": ["هل هذا سبب جذري أم عرَض لخلل أعمق؟", "is this a root cause or merely a symptom"]},
    {"key": "data",
     "keywords": {"بيانات", "أرقام", "إحصاء", "معدل", "اتجاه", "data", "numbers", "statistics", "trend", "rate"},
     "utterances": ["تحليل حجم البلاغات والشدّة والاتجاه", "analyse complaint volume, severity and trend"]},
    {"key": "service",
     "keywords": {"خدمة", "تشغيل", "شبكة", "جهة", "صيانة", "service", "operations", "network", "outage", "maintenance"},
     "utterances": ["تشغيل الخدمة والجهة المالكة والصيانة", "service operations, the owning authority and maintenance"]},
    {"key": "citizen",
     "keywords": {"مواطن", "يومي", "حياة", "ناس", "جمهور", "citizen", "daily", "people", "public", "household"},
     "utterances": ["أثر المشكلة على حياة المواطن اليومية", "the impact on citizens' daily life"]},
    {"key": "ops",
     "keywords": {"تنفيذ", "معالجة", "سرعة", "ميداني", "إصلاح", "implement", "response", "deploy", "field", "repair", "fix"},
     "utterances": ["أسرع معالجة ميدانية بأثر ملموس", "the fastest field response with measurable impact"]},
    {"key": "risk",
     "keywords": {"خطر", "مخاطر", "تحقق", "سلامة", "تصعيد", "risk", "verify", "safety", "danger", "escalation", "hazard"},
     "utterances": ["تدقيق المخاطر وقوة الإثبات قبل القرار", "audit risk and evidence strength before deciding"]},
    {"key": "priority",
     "keywords": {"أولوية", "ترتيب", "الأهم", "priority", "rank", "urgent", "triage"},
     "utterances": ["ترتيب المحاور حسب الأثر وقابلية التنفيذ", "rank issues by impact and feasibility"]},
    {"key": "comms",
     "keywords": {"تواصل", "إعلام", "رسالة", "ذعر", "توعية", "communication", "media", "message", "panic", "awareness", "public"},
     "utterances": ["رسالة تطمين وتوعية للجمهور", "a reassuring public awareness message"]},
    {"key": "budget",
     "keywords": {"كلفة", "تكلفة", "موازنة", "تمويل", "cost", "budget", "funding", "money", "expense"},
     "utterances": ["أعلى أثر مقابل أقل كلفة", "highest impact at lowest cost"]},
    {"key": "legal",
     "keywords": {"قانون", "نظام", "لائحة", "إجراء", "تنظيم", "law", "regulation", "policy", "legal", "procedure", "compliance"},
     "utterances": ["خلل في إجراء أو لائحة يلزم تعديلها", "a flawed procedure or regulation that needs amending"]},
]
_CARD_BY_KEY = {c["key"]: c for c in CARDS}

# Lazy, real-embedding-only card vectors (never cache hash-noise).
_CARD_VECS: Dict[str, List[float]] = {}
_CARD_VECS_BUILT = False


def _keyword_score(text_norm: str, card: Dict[str, Any]) -> float:
    """Saturating keyword signal in [0,1]. Substring match (on the lowercased text)
    so Arabic morphology is tolerated — keyword «قانون» still matches «قانوني»,
    «تنظيم» matches «تنظيمي». A few strong hits already saturate so an explicitly
    named lens (legal/budget/comms) can outweigh a generic domain-affinity prior."""
    kws = card.get("keywords") or set()
    hits = sum(1 for k in kws if k in text_norm)
    return min(hits, 3) / 3.0


def _ensure_card_vecs() -> bool:
    """Build card embedding vectors once, ONLY from real model embeddings. Returns
    True if real vectors are available. Never caches hash-noise; safe to retry."""
    global _CARD_VECS_BUILT
    if _CARD_VECS_BUILT:
        return True
    if llm is None or not llm.available():
        return False
    for c in CARDS:
        try:
            v = llm.embed(" ".join(c["utterances"]))
            if v:
                _CARD_VECS[c["key"]] = v
        except Exception:
            pass
    if _CARD_VECS:
        _CARD_VECS_BUILT = True
    return _CARD_VECS_BUILT


def _cosine(a: List[float], b: List[float]) -> float:
    if not a or not b:
        return 0.0
    n = min(len(a), len(b))
    dot = sum(a[i] * b[i] for i in range(n))
    import math
    na = math.sqrt(sum(a[i] * a[i] for i in range(n))) or 1.0
    nb = math.sqrt(sum(b[i] * b[i] for i in range(n))) or 1.0
    return dot / (na * nb)


def select_agents(
    text: str,
    qvec: Optional[List[float]] = None,
    retrieved_cases: Optional[List[Dict[str, Any]]] = None,
    *,
    domain: Optional[str] = None,
    cap: int = 4,
) -> List[Dict[str, Any]]:
    """Choose the agent roster for a scenario.

    text            : the free-text crisis scenario.
    qvec            : a REAL scenario embedding, or None. A hash vector must NOT be
                      passed here — pass None when Ollama is down.
    retrieved_cases : lessons retrieved for this scenario; their domains nudge the
                      specialist selection toward the actual precedents.
    Returns floor roles + up to ``cap`` specialists as
    [{key, name, score, reason, group, floor}].
    """
    dom = domain or (lessons.infer_domain(None, text) if lessons else "other")
    affinity = _DOMAIN_AFFINITY.get(dom, set())
    text_norm = (text or "").lower()

    # domains present among the retrieved precedents → small per-domain affinity union
    retr_domains = {
        (c.get("domain") or "") for c in (retrieved_cases or []) if c.get("domain")
    }
    retr_affinity = set().union(*[_DOMAIN_AFFINITY.get(d, set()) for d in retr_domains]) if retr_domains else set()

    use_emb = bool(qvec) and _ensure_card_vecs()
    engine = "llm" if use_emb else "grounded"

    scored: List[Dict[str, Any]] = []
    for c in CARDS:
        key = c["key"]
        base = float(c.get("base", 0.10))
        kw = _keyword_score(text_norm, c)
        dom_aff = 0.35 if key in affinity else 0.0
        retr_aff = 0.10 if key in retr_affinity else 0.0
        emb = 0.0
        if use_emb and key in _CARD_VECS:
            emb = max(0.0, _cosine(qvec, _CARD_VECS[key]))
        score = base + 0.60 * kw + dom_aff + retr_aff + 0.30 * emb
        reason_bits = []
        if dom_aff:
            reason_bits.append(f"مجال «{dom}»")
        if kw > 0:
            reason_bits.append("تطابق كلمات")
        if retr_aff:
            reason_bits.append("سوابق مسترجَعة")
        if emb > 0.25:
            reason_bits.append("تشابه دلالي")
        scored.append({
            "key": key, "name": PERSONAS.get(key, key), "group": "specialist",
            "score": round(score, 4), "floor": False,
            "reason": "، ".join(reason_bits) or "عامّ",
        })

    scored.sort(key=lambda x: -x["score"])
    specialists = scored[: max(2, min(int(cap), len(scored)))]

    roster: List[Dict[str, Any]] = [
        {"key": k, "name": PERSONAS[k], "group": "floor", "score": 1.0,
         "floor": True, "reason": "دور أساسي"}
        for k in FLOOR
    ]
    roster.extend(specialists)
    # attach the routing engine so the caller can flag grounded-only selection
    for r in roster:
        r["engine"] = engine
    return roster


def roster_keys(roster: List[Dict[str, Any]]) -> List[str]:
    return [r["key"] for r in roster]
