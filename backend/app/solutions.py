"""Valid-Solution engine for the AEGIS Deer Graph — voc360 → root cause → countermeasure.

Turns the ranked RIL problem clusters (the root-cause layer) into *grounded,
actionable* solutions: cause → countermeasure(s), each tagged with the owning
agency, an expected-impact statement, a feasibility band and a timeframe.

The engine is deliberately deterministic and import-safe:

  * It builds on ``rootcause.rank_root_causes`` (real ril_problem_clusters rows).
  * It classifies each cluster by Arabic *theme* using a keyword→countermeasure
    map grounded in the real canonical labels observed in voc360
    (urgent-service fees, the BRT / rapid bus, park-and-ride, road excavations,
    the Takaful platform, National-Aid-Fund delays, ID issuance, e-service
    system errors, school overcrowding / labs, exam difficulty, queues …).
  * Because ``ril_problem_clusters.canonical_label_en`` is NULL in voc360, the
    English label is produced *at build time* by the same theme map (Track 3:
    translate Arabic labels with no LLM key required).
  * Real per-cluster signal counts are pulled from the text-recovery linker
    (``linker.cluster_signal_counts``) when ``backend/data/links.json`` exists;
    otherwise the cluster ``member_count`` is used as the grounded fallback.
  * An *optional* narration is requested from the LOCAL model via
    ``llm.narrate``; if the module or local server is unreachable the engine
    falls back to a deterministic, fully-grounded ``recommendation`` string.

No external API key is required.  voc360 is read-only.  Real columns only.

Public API
----------
``valid_solutions(limit=8) -> list[dict]`` where each item is::

    {
      "cluster_id", "label_ar", "label_en", "theme",
      "members", "signal_count", "severity_avg", "score",
      "actions": [
        {"agency", "action", "expected_impact", "feasibility", "timeframe"}
      ],
      "confidence",          # 0..1, grounded in evidence volume + severity
      "recommendation",      # one-paragraph plan (LLM-narrated or fallback)
      "evidence",            # up to 2 real citizen-report snippets
      "narrated",            # bool — True if the local model enriched the text
    }
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# --- import shim: usable as a package (app.solutions) or flat (solutions) -----
try:  # pragma: no cover - import shim
    from . import rootcause
except Exception:  # pragma: no cover
    import rootcause  # type: ignore

# The text-recovery linker (T1) is optional: it provides real signal counts.
try:  # pragma: no cover - optional dependency
    from . import linker as _linker  # type: ignore
except Exception:  # pragma: no cover
    try:
        import linker as _linker  # type: ignore
    except Exception:
        _linker = None  # type: ignore

# The local-model narrator (T3) is optional: graceful deterministic fallback.
try:  # pragma: no cover - optional dependency
    from . import llm as _llm  # type: ignore
except Exception:  # pragma: no cover
    try:
        import llm as _llm  # type: ignore
    except Exception:
        _llm = None  # type: ignore

try:  # pragma: no cover - lessons memory (semantic retrieval)
    from . import lessons as _lessons  # type: ignore
except Exception:  # pragma: no cover
    try:
        import lessons as _lessons  # type: ignore
    except Exception:
        _lessons = None  # type: ignore


# ===========================================================================
# Theme map — grounded in the REAL canonical_label_ar values in voc360.
#
# Each theme carries:
#   * keys      : Arabic (+ a few latin) substrings that identify the theme.
#                 Labels are normalised (diacritics/tatweel stripped) before
#                 matching so e.g. "الخدمة" and "الخدمه" both hit.
#   * label_en  : build-time English translation of the cluster theme (Track 3).
#   * actions   : list of (agency, action, expected_impact, feasibility,
#                 timeframe) countermeasures, ordered most-impactful first.
#
# feasibility ∈ {"high","medium","low"} ; timeframe is a human band.
# ===========================================================================
_THEMES: List[Dict[str, Any]] = [
    {
        "id": "urgent_service_fees",
        "keys": ("رسوم الخدمه المستعجله", "رسوم الخدمه", "الخدمه المستعجله",
                 "غاليه", "الرسوم"),
        "label_en": "Urgent-service fees perceived as expensive",
        "actions": [
            {"agency": "Ministry of Digital Economy & Entrepreneurship / Sanad",
             "action": "Publish a transparent fee tier (standard vs. expedited) and "
                       "show the price + ETA before the citizen pays.",
             "expected_impact": "Cuts fee-related complaints by setting expectations up front.",
             "feasibility": "high", "timeframe": "1–2 months"},
            {"agency": "Ministry of Finance",
             "action": "Review the expedited-fee schedule against actual processing cost "
                       "and introduce a means-tested or low-income waiver.",
             "expected_impact": "Reduces perceived unfairness for vulnerable applicants.",
             "feasibility": "medium", "timeframe": "3–6 months"},
        ],
    },
    {
        "id": "brt_rapid_bus",
        "keys": ("الباص السريع", "باص سريع", "brt", "الباص", "التردد", "الازمه"),
        "label_en": "BRT / rapid-bus service — capacity & frequency",
        "actions": [
            {"agency": "Greater Amman Municipality — Amman Bus / BRT",
             "action": "Increase peak-hour frequency on the busiest BRT corridors and "
                       "add buses where headways exceed the published target.",
             "expected_impact": "Shortens wait times; converts crowding complaints into praise.",
             "feasibility": "medium", "timeframe": "2–4 months"},
            {"agency": "Greater Amman Municipality",
             "action": "Deploy real-time arrival displays / app ETAs at high-traffic stops.",
             "expected_impact": "Lowers uncertainty-driven dissatisfaction at stops.",
             "feasibility": "high", "timeframe": "1–3 months"},
        ],
    },
    {
        "id": "park_and_ride",
        "keys": ("مواقف اركن وانطلق", "اركن وانطلق", "مواقف", "دوار", "ركن"),
        "label_en": "Park-and-ride / parking provision near transit hubs",
        "actions": [
            {"agency": "Greater Amman Municipality — Transport",
             "action": "Expand park-and-ride capacity at the busiest interchange roundabouts "
                       "and signpost availability.",
             "expected_impact": "Encourages modal shift to BRT; eases roadside congestion.",
             "feasibility": "medium", "timeframe": "3–6 months"},
            {"agency": "Greater Amman Municipality",
             "action": "Add live parking-occupancy signage / app integration.",
             "expected_impact": "Reduces circling traffic and parking-search frustration.",
             "feasibility": "high", "timeframe": "1–3 months"},
        ],
    },
    {
        "id": "road_excavations",
        "keys": ("حفريات", "حفر", "شارع المدينه المنوره", "شارع", "طريق",
                 "بنيه", "طرق_وبنيه_تحتيه", "بنيه تحتيه"),
        "label_en": "Road excavations / infrastructure works disrupting streets",
        "actions": [
            {"agency": "Greater Amman Municipality — Roads & Infrastructure",
             "action": "Coordinate utility excavations through a single dig-permit calendar "
                       "and enforce rapid resurfacing SLAs after works close.",
             "expected_impact": "Fewer prolonged open trenches; less vehicle damage.",
             "feasibility": "medium", "timeframe": "3–6 months"},
            {"agency": "Greater Amman Municipality",
             "action": "Publish a live works map and SMS/affected-area notifications.",
             "expected_impact": "Sets expectations and re-routes drivers around active sites.",
             "feasibility": "high", "timeframe": "1–2 months"},
        ],
    },
    {
        "id": "takaful_platform",
        "keys": ("منصه تكافل", "تكافل"),
        "label_en": "Takaful social-support platform issues",
        "actions": [
            {"agency": "National Aid Fund — Takaful programme",
             "action": "Audit the most common Takaful application errors and add inline "
                       "validation + a guided application wizard.",
             "expected_impact": "Reduces failed/abandoned applications and re-submissions.",
             "feasibility": "high", "timeframe": "1–3 months"},
            {"agency": "Ministry of Digital Economy & Entrepreneurship",
             "action": "Add a status tracker and a fast-track support channel for the platform.",
             "expected_impact": "Cuts repeat contacts and clarifies application state.",
             "feasibility": "medium", "timeframe": "2–4 months"},
        ],
    },
    {
        "id": "national_aid_delay",
        "keys": ("صندوق المعونه الوطنيه", "المعونه الوطنيه", "صندوق المعونه",
                 "الدعم المالي", "تاخر الدعم", "المعونه", "الدعم"),
        "label_en": "National-Aid-Fund support payment delays",
        "actions": [
            {"agency": "National Aid Fund",
             "action": "Set and publish a payment-disbursement SLA and proactively notify "
                       "beneficiaries when a payment is delayed and why.",
             "expected_impact": "Reduces anxiety-driven complaints about late support.",
             "feasibility": "medium", "timeframe": "2–4 months"},
            {"agency": "Ministry of Finance / National Aid Fund",
             "action": "Identify and fix the recurring bottleneck causing the longest delays.",
             "expected_impact": "Shortens the disbursement tail for the worst-affected cases.",
             "feasibility": "medium", "timeframe": "3–6 months"},
        ],
    },
    {
        "id": "id_issuance",
        "keys": ("الهويه", "هويتي", "بدل فاقد", "اصدار الهويه", "محطه الاصدار",
                 "الاحوال", "جوازات", "جواز"),
        "label_en": "Civil-status ID / document issuance experience",
        "actions": [
            {"agency": "Civil Status & Passports Department",
             "action": "Streamline the lost/replacement-ID flow and offer online pre-booking "
                       "to cut on-site processing time.",
             "expected_impact": "Lowers turnaround and reduces in-person waits.",
             "feasibility": "high", "timeframe": "1–3 months"},
            {"agency": "Civil Status & Passports Department",
             "action": "Surface clear required-document checklists before the visit.",
             "expected_impact": "Fewer wasted trips and re-visits for missing papers.",
             "feasibility": "high", "timeframe": "1–2 months"},
        ],
    },
    {
        "id": "eservice_errors",
        "keys": ("طلب الكتروني", "خطا بالنظام", "النظام", "الكتروني", "الكترون",
                 "الخدمات_الالكترونيه", "تطبيق", "خطا"),
        "label_en": "E-service / online application system errors",
        "actions": [
            {"agency": "Ministry of Digital Economy & Entrepreneurship / Sanad",
             "action": "Instrument the e-service forms, capture the top failing steps, and "
                       "fix the highest-frequency submission errors.",
             "expected_impact": "Raises successful first-attempt submissions.",
             "feasibility": "high", "timeframe": "1–3 months"},
            {"agency": "Sanad platform team",
             "action": "Add graceful error messages with recovery guidance and auto-save.",
             "expected_impact": "Reduces abandonment when an error occurs mid-application.",
             "feasibility": "high", "timeframe": "1–2 months"},
        ],
    },
    {
        "id": "school_capacity",
        "keys": ("اكتظاظ", "50 طالب", "البيئه الصفيه", "التهويه", "نظافه المدرسه",
                 "مدرسه", "مختبرات", "التعليم المهني", "الصف"),
        "label_en": "School overcrowding, facilities & lab conditions",
        "actions": [
            {"agency": "Ministry of Education",
             "action": "Prioritise capacity relief (additional sections / classrooms) at the "
                       "most overcrowded schools flagged by these reports.",
             "expected_impact": "Lowers per-class load toward target ratios.",
             "feasibility": "low", "timeframe": "6–12 months"},
            {"agency": "Ministry of Education — facilities",
             "action": "Fund ventilation, cleanliness and updated vocational-lab upgrades for "
                       "the flagged schools.",
             "expected_impact": "Improves the in-class learning environment near-term.",
             "feasibility": "medium", "timeframe": "3–6 months"},
        ],
    },
    {
        "id": "exam_quality",
        "keys": ("امتحان", "اسئله", "التوجيهي", "الفيزياء", "الكيمياء",
                 "تعجيزيه", "وقت امتحان", "الوزاره مر"),
        "label_en": "Exam difficulty / timing & question fairness",
        "actions": [
            {"agency": "Ministry of Education — Exams & Assessment",
             "action": "Review flagged papers for difficulty calibration and allotted-time "
                       "adequacy, and standardise the question bank.",
             "expected_impact": "Improves perceived fairness of high-stakes exams.",
             "feasibility": "medium", "timeframe": "1 exam cycle"},
            {"agency": "Ministry of Education",
             "action": "Publish sample papers and a clear time-per-section guide ahead of exams.",
             "expected_impact": "Sets expectations and reduces timing-related distress.",
             "feasibility": "high", "timeframe": "1–2 months"},
        ],
    },
    {
        "id": "service_centre_queue",
        "keys": ("طابور", "كاونترات", "كاونتر", "مراكز_الخدمه", "المبني",
                 "المستعجل", "خدمه الجمهور"),
        "label_en": "Service-centre queues & counter capacity",
        "actions": [
            {"agency": "Owning service agency (service centre)",
             "action": "Open additional counters at peak periods and add a queue-ticketing / "
                       "appointment system.",
             "expected_impact": "Cuts on-site waiting time and walk-away frustration.",
             "feasibility": "high", "timeframe": "1–3 months"},
            {"agency": "Owning service agency",
             "action": "Shift high-volume transactions online to reduce footfall.",
             "expected_impact": "Lowers physical queue length over time.",
             "feasibility": "medium", "timeframe": "3–6 months"},
        ],
    },
]

# A generic theme used when no keyword matches — still actionable & grounded.
_GENERIC = {
    "id": "general",
    "label_en": "General service-quality issue",
    "actions": [
        {"agency": "Owning service agency",
         "action": "Triage the cluster's citizen reports, identify the dominant "
                   "failure mode, and assign an owner with a corrective-action plan.",
         "expected_impact": "Converts an unowned complaint cluster into a tracked fix.",
         "feasibility": "high", "timeframe": "1–2 months"},
        {"agency": "VOC 360 programme office",
         "action": "Re-measure complaint volume on this cluster 30 days after action "
                   "to confirm the intervention worked.",
         "expected_impact": "Closes the loop and verifies real-world impact.",
         "feasibility": "high", "timeframe": "ongoing"},
    ],
}


# ---------------------------------------------------------------------------
# Arabic normalisation — mirrors linker.normalize_ar so theme matching is
# robust to diacritics / ة-ه / ى-ي variants without importing the linker.
# ---------------------------------------------------------------------------
_DIACRITICS = "".join(chr(c) for c in range(0x0610, 0x061B)) + \
    "".join(chr(c) for c in range(0x064B, 0x0660)) + "ـ"  # + tatweel
_TRANS = {ord(c): None for c in _DIACRITICS}
_TRANS.update({
    ord("أ"): "ا", ord("إ"): "ا", ord("آ"): "ا",
    ord("ى"): "ي", ord("ة"): "ه", ord("ؤ"): "و", ord("ئ"): "ي",
})


def _norm(s: Optional[str]) -> str:
    if not s:
        return ""
    return " ".join(s.translate(_TRANS).lower().split())


def _classify(label_ar: str) -> Dict[str, Any]:
    """Return the best-matching theme dict for an Arabic cluster label."""
    low = _norm(label_ar)
    best: Optional[Dict[str, Any]] = None
    best_hits = 0
    for theme in _THEMES:
        hits = sum(1 for k in theme["keys"] if _norm(k) in low)
        if hits > best_hits:
            best, best_hits = theme, hits
    return best or _GENERIC


# ---------------------------------------------------------------------------
# Signal counts — prefer the real text-recovery linker; fall back to members.
# ---------------------------------------------------------------------------
def _signal_counts() -> Dict[str, int]:
    if _linker is None:
        return {}
    try:
        links = _linker.load_links()  # type: ignore[attr-defined]
        if not links:
            return {}
        return dict(_linker.cluster_signal_counts(links))  # type: ignore[attr-defined]
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Confidence — grounded in evidence volume (members + recovered signals) and
# severity.  Bounded to [0.30, 0.95] so it never reads as fabricated certainty.
# ---------------------------------------------------------------------------
def _confidence(members: int, signal_count: int, severity_avg: float) -> float:
    import math

    volume = members + signal_count
    vol_term = math.log10(volume + 1) / 3.0          # ~0 at 0, ~1 at ~1000
    sev_term = max(0.0, min(1.0, float(severity_avg)))
    raw = 0.30 + 0.45 * min(1.0, vol_term) + 0.20 * sev_term
    return round(max(0.30, min(0.95, raw)), 2)


def _sev_word(severity_avg: float) -> str:
    s = float(severity_avg)
    return "high" if s >= 0.5 else "moderate" if s >= 0.3 else "low"


# ---------------------------------------------------------------------------
# Recommendation — deterministic, fully-grounded paragraph.  This is also the
# fallback used whenever the local model is unreachable.
# ---------------------------------------------------------------------------
def _fallback_recommendation(item: Dict[str, Any]) -> str:
    lead = item["actions"][0]
    vol = item["members"]
    sig = item["signal_count"]
    vol_phrase = f"{vol} clustered citizen report" + ("s" if vol != 1 else "")
    if sig:
        vol_phrase += f" ({sig} matched source signals)"
    return (
        f"Root cause '{item['label_en']}' is backed by {vol_phrase} at "
        f"{_sev_word(item['severity_avg'])} severity. Primary countermeasure: "
        f"{lead['agency']} — {lead['action']} {lead['expected_impact']} "
        f"Feasibility {lead['feasibility']}, {lead['timeframe']}. Track whether "
        f"complaint volume on this cluster falls after the intervention."
    )


def _narrate(item: Dict[str, Any]) -> tuple[str, bool]:
    """Try the LOCAL model for a grounded narration; else deterministic fallback.

    The local narrator is passed a strict, grounded prompt built only from real
    cluster facts.  Any failure (module absent, server down, bad/empty output)
    falls back to ``_fallback_recommendation`` so the API never blocks on the LLM.
    """
    fallback = _fallback_recommendation(item)
    if _llm is None or not hasattr(_llm, "narrate"):
        return fallback, False
    actions_txt = "; ".join(
        f"{a['agency']}: {a['action']} (feasibility {a['feasibility']}, {a['timeframe']})"
        for a in item["actions"]
    )
    facts = (
        f"Root cause (English): {item['label_en']}. "
        f"Root cause (Arabic, verbatim): {item['label_ar']}. "
        f"Evidence: {item['members']} clustered reports, "
        f"{item['signal_count']} matched source signals, "
        f"severity {item['severity_avg']} ({_sev_word(item['severity_avg'])}). "
        f"Candidate countermeasures: {actions_txt}."
    )
    lessons_block = ""
    if _lessons is not None:
        try:
            lessons_block = _lessons.lessons_context_block(
                domain=_lessons.infer_domain(None, item.get("label_en") or item.get("label_ar") or ""),
                root_cause_category=_lessons._slug(item.get("label_en") or item.get("label_ar") or ""),
                query=item.get("label_en") or item.get("label_ar"),
                limit=3,
            )
        except Exception:
            lessons_block = ""
    prompt = (
        "You are an AEGIS public-service operations analyst. Using ONLY the facts "
        "below, write ONE concise paragraph (<=80 words) recommending the single "
        "most effective countermeasure for this root cause, naming the owning "
        "agency and the expected impact. Do not invent numbers, agencies or facts "
        "not given.\n\nFACTS:\n" + facts
    )
    if lessons_block:
        prompt += "\n\n" + lessons_block
    try:
        out = _llm.narrate(
            prompt,
            context={"past_lessons": lessons_block} if lessons_block else None,
        )  # type: ignore[attr-defined]
        text = (out or "").strip() if isinstance(out, str) else ""
        if len(text) >= 40:
            return text, True
    except Exception:
        pass
    return fallback, False


# ===========================================================================
# Public API
# ===========================================================================
def valid_solutions(limit: int = 8, narrate: bool = True) -> List[Dict[str, Any]]:
    """Return ranked, grounded cause→countermeasure solutions from voc360.

    Parameters
    ----------
    limit   : max number of root-cause clusters to turn into solutions.
    narrate : if True (default) attempt LOCAL-model enrichment of each
              recommendation, with a deterministic grounded fallback.

    Each returned dict matches the D-solution contract (see module docstring).
    """
    ranked = rootcause.rank_root_causes(limit)
    signal_counts = _signal_counts()

    out: List[Dict[str, Any]] = []
    for r in ranked:
        cid = r["cluster_id"]
        label_ar = r.get("label_ar") or ""
        theme = _classify(label_ar)
        members = int(r.get("members") or 0)
        signal_count = int(signal_counts.get(cid, 0))
        severity_avg = float(r.get("severity_avg") or 0.0)
        # Track 3: English label is built here (canonical_label_en is NULL in voc360).
        label_en = r.get("label_en") or theme["label_en"]

        item: Dict[str, Any] = {
            "cluster_id": cid,
            "label_ar": label_ar,
            "label_en": label_en,
            "theme": theme["id"],
            "members": members,
            "signal_count": signal_count,
            "severity_avg": round(severity_avg, 2),
            "score": r.get("score"),
            "actions": [dict(a) for a in theme["actions"]],
            "confidence": _confidence(members, signal_count, severity_avg),
            "evidence": [e for e in (r.get("evidence") or [])[:2]],
        }
        rec, narrated = _narrate(item) if narrate else (_fallback_recommendation(item), False)
        item["recommendation"] = rec
        item["narrated"] = narrated
        out.append(item)

    return out


if __name__ == "__main__":  # pragma: no cover - manual smoke test
    import json

    sols = valid_solutions(5, narrate=False)
    print(f"{len(sols)} valid solutions\n")
    for s in sols:
        print(f"[{s['theme']}] {s['label_en']}  "
              f"(members={s['members']}, signals={s['signal_count']}, "
              f"conf={s['confidence']})")
        print("  ->", s["recommendation"])
        print()
    print(json.dumps(sols[0], ensure_ascii=False, indent=2))
