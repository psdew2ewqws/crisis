"""Concrete, step-by-step crisis IMPACT simulation for Jordan.

The agent-based engine (abm_sim) produces an abstract "risk %" intensity curve.
This module turns that envelope into a CONCRETE simulation of what actually
happens on the ground — who is affected, casualties, displaced, services
status — unfolding step by step over real time (Hour 0 -> Day 3 -> Week 1 ...).

Two grounding layers:
  • Deterministic core — Jordan demographics (real population per governorate) ×
    intensity × literature-informed impact ratios. Always available, never raises.
  • LLM layer — when a model is reachable (llm.available()), it rewrites the
    timeline with richer, paper-grounded specifics in strict JSON. Falls back to
    the deterministic timeline on any failure.

A second pass with ``intervene=True`` applies the calibrated intervention (with
realistic detection/decision/ramp lag) so the SOLUTION timeline shows reduced /
diverted impact step by step against the same baseline.

All figures are clearly labelled EXPLORATORY estimates — decision support, not a
calibrated forecast.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

try:
    from . import llm as _llm
except Exception:  # pragma: no cover
    _llm = None  # type: ignore

# ── Jordan demographics (2024 estimates, persons) ─────────────────────────────
# Keyed by the Arabic governorate name (matches the scenario `location` dropdown),
# with English + a population figure. Source: DoS Jordan population estimates.
JORDAN_POP: Dict[str, Dict[str, Any]] = {
    "عمان":    {"en": "Amman",   "pop": 4536000},
    "إربد":    {"en": "Irbid",   "pop": 2066000},
    "الزرقاء": {"en": "Zarqa",   "pop": 1490000},
    "المفرق":  {"en": "Mafraq",  "pop": 632000},
    "البلقاء": {"en": "Balqa",   "pop": 568000},
    "الكرك":   {"en": "Karak",   "pop": 358000},
    "جرش":     {"en": "Jerash",  "pop": 274000},
    "العقبة":  {"en": "Aqaba",   "pop": 222000},
    "مادبا":   {"en": "Madaba",  "pop": 221000},
    "عجلون":   {"en": "Ajloun",  "pop": 195000},
    "معان":    {"en": "Ma'an",   "pop": 174000},
    "الطفيلة": {"en": "Tafilah", "pop": 105000},
}
_TOTAL_POP = sum(v["pop"] for v in JORDAN_POP.values())

# Alternate spellings / districts → canonical governorate.
_GOV_ALIASES = {
    "عمّان": "عمان", "amman": "عمان", "اربد": "إربد", "irbid": "إربد",
    "الزرقا": "الزرقاء", "zarqa": "الزرقاء", "رمثا": "إربد", "ذيبان": "مادبا",
    "السلط": "البلقاء", "mafraq": "المفرق", "balqa": "البلقاء", "karak": "الكرك",
    "jerash": "جرش", "aqaba": "العقبة", "madaba": "مادبا", "ajloun": "عجلون",
    "maan": "معان", "tafilah": "الطفيلة",
}


def _resolve_govs(location: Optional[str]) -> List[str]:
    """Affected governorates: the chosen one (+ neighbours implicitly via national
    weighting) or all 12 weighted by population when none specified."""
    if location:
        loc = location.strip()
        if loc in JORDAN_POP:
            return [loc]
        canon = _GOV_ALIASES.get(loc.lower()) or _GOV_ALIASES.get(loc)
        if canon and canon in JORDAN_POP:
            return [canon]
        for ar, meta in JORDAN_POP.items():
            if loc and (loc in ar or ar in loc or meta["en"].lower() == loc.lower()):
                return [ar]
    return list(JORDAN_POP.keys())


# ── Domain detection ──────────────────────────────────────────────────────────
def _detect_domain(text: str, domain: str) -> str:
    t = (text or "").lower() + " " + (domain or "").lower()
    if any(k in t for k in ("زلزال", "هزة", "earthquake", "seismic", "هزّة")):
        return "earthquake"
    if any(k in t for k in ("فيضان", "سيول", "سيل", "flood", "غرق")):
        return "flood"
    if any(k in t for k in ("وباء", "جائحة", "عدوى", "epidemic", "pandemic", "outbreak", "مرض")):
        return "epidemic"
    if any(k in t for k in ("مياه", "ماء", "جفاف", "water", "drought")):
        return "water"
    if any(k in t for k in ("كهرباء", "طاقة", "energy", "power", "انقطاع التيار")):
        return "energy"
    return domain or "general"


# ── Phase templates per domain (label, relative time, intensity multiplier) ───
# multiplier shapes how impact accumulates across the phases (0..1 of peak).
_PHASES: Dict[str, List[Dict[str, Any]]] = {
    "earthquake": [
        {"t": "t0",    "ar": "اللحظة صفر — وقوع الزلزال", "phase": "impact",   "m": 0.55},
        {"t": "t+1h",  "ar": "الساعة الأولى",             "phase": "impact",   "m": 0.80},
        {"t": "t+6h",  "ar": "أول ٦ ساعات — البحث والإنقاذ", "phase": "response", "m": 1.00},
        {"t": "t+1d",  "ar": "اليوم الأول",               "phase": "response", "m": 1.00},
        {"t": "t+3d",  "ar": "اليوم الثالث — الإيواء",      "phase": "relief",   "m": 0.92},
        {"t": "t+7d",  "ar": "الأسبوع الأول",              "phase": "relief",   "m": 0.80},
        {"t": "t+30d", "ar": "الشهر الأول — التعافي",       "phase": "recovery", "m": 0.55},
    ],
    "flood": [
        {"t": "t0",    "ar": "بداية الفيضان",   "phase": "impact",   "m": 0.50},
        {"t": "t+6h",  "ar": "أول ٦ ساعات",     "phase": "impact",   "m": 0.85},
        {"t": "t+1d",  "ar": "اليوم الأول",     "phase": "response", "m": 1.00},
        {"t": "t+3d",  "ar": "اليوم الثالث",    "phase": "relief",   "m": 0.85},
        {"t": "t+7d",  "ar": "الأسبوع الأول",   "phase": "relief",   "m": 0.65},
        {"t": "t+30d", "ar": "الشهر الأول",     "phase": "recovery", "m": 0.45},
    ],
    "epidemic": [
        {"t": "t0",    "ar": "أول الحالات",      "phase": "impact",   "m": 0.20},
        {"t": "t+7d",  "ar": "الأسبوع الأول",    "phase": "impact",   "m": 0.45},
        {"t": "t+14d", "ar": "الأسبوع الثاني",   "phase": "response", "m": 0.80},
        {"t": "t+30d", "ar": "الشهر الأول — الذروة", "phase": "response", "m": 1.00},
        {"t": "t+60d", "ar": "الشهر الثاني",     "phase": "relief",   "m": 0.75},
        {"t": "t+90d", "ar": "الشهر الثالث — الانحسار", "phase": "recovery", "m": 0.40},
    ],
    "general": [
        {"t": "t0",    "ar": "بداية الأزمة",    "phase": "impact",   "m": 0.45},
        {"t": "t+1d",  "ar": "اليوم الأول",     "phase": "impact",   "m": 0.80},
        {"t": "t+3d",  "ar": "اليوم الثالث",    "phase": "response", "m": 1.00},
        {"t": "t+7d",  "ar": "الأسبوع الأول",   "phase": "relief",   "m": 0.85},
        {"t": "t+30d", "ar": "الشهر الأول",     "phase": "recovery", "m": 0.55},
    ],
}
_PHASES["water"] = _PHASES["general"]
_PHASES["energy"] = _PHASES["general"]

# Impact ratios per domain (fractions of EXPOSED population at PEAK intensity I=1).
# Conservative, literature-informed bands; clearly exploratory.
_RATIOS: Dict[str, Dict[str, float]] = {
    "earthquake": {"affected": 0.18, "deaths": 0.0011, "injured": 0.0052, "displaced": 0.060, "hosp": 1.0},
    "flood":      {"affected": 0.12, "deaths": 0.0003, "injured": 0.0018, "displaced": 0.045, "hosp": 0.6},
    "epidemic":   {"affected": 0.25, "deaths": 0.0040, "injured": 0.0,    "displaced": 0.0,   "hosp": 1.3},
    "water":      {"affected": 0.55, "deaths": 0.0001, "injured": 0.0008, "displaced": 0.010, "hosp": 0.5},
    "energy":     {"affected": 0.70, "deaths": 0.0,    "injured": 0.0004, "displaced": 0.0,   "hosp": 0.4},
    "general":    {"affected": 0.20, "deaths": 0.0002, "injured": 0.0015, "displaced": 0.020, "hosp": 0.5},
}


def _magnitude_from_text(text: str) -> Optional[float]:
    m = re.search(r"(\d(?:\.\d)?)\s*(?:درجة|ريختر|magnitude|mw|m\b)", (text or "").lower())
    if m:
        try:
            return float(m.group(1))
        except Exception:
            return None
    return None


def _infra_status(domain: str, frac: float) -> str:
    """Short Arabic infrastructure status for the phase intensity fraction."""
    if domain == "earthquake":
        if frac >= 0.9: return "انهيار مبانٍ، انقطاع كهرباء ومياه واسع، طرق مقطوعة"
        if frac >= 0.6: return "أضرار إنشائية، انقطاع جزئي للكهرباء والاتصالات"
        if frac >= 0.3: return "أضرار محدودة، ضغط على شبكات الطوارئ"
        return "عودة تدريجية للخدمات الأساسية"
    if domain == "flood":
        if frac >= 0.8: return "غمر أحياء، انقطاع طرق وكهرباء"
        if frac >= 0.4: return "تجمّعات مياه، إغلاق طرق"
        return "انحسار المياه وبدء التنظيف"
    if domain == "epidemic":
        if frac >= 0.9: return "إشغال أسرّة العناية فوق الطاقة"
        if frac >= 0.5: return "ضغط مرتفع على المستشفيات"
        return "تراجع الإشغال تدريجيًّا"
    if frac >= 0.7: return "ضغط واسع على الخدمات"
    if frac >= 0.4: return "تعطّل جزئي للخدمات"
    return "استقرار نسبي للخدمات"


def _deterministic_timeline(
    text: str, domain: str, govs: List[str], intensity: float,
    effect_size: float, intervene: bool, lags: Dict[str, int],
) -> Dict[str, Any]:
    """Build a concrete impact timeline from demographics × intensity × ratios."""
    dom = _detect_domain(text, domain)
    phases = _PHASES.get(dom, _PHASES["general"])
    ratios = _RATIOS.get(dom, _RATIOS["general"])
    exposed = sum(JORDAN_POP[g]["pop"] for g in govs if g in JORDAN_POP) or _TOTAL_POP

    # Intensity 0..1 from the ABM risk envelope; nudge by an explicit magnitude.
    I = max(0.1, min(1.0, intensity))
    mag = _magnitude_from_text(text)
    if mag is not None and dom == "earthquake":
        I = max(I, min(1.0, (mag - 4.0) / 3.0))   # M4→0, M7→1

    # Intervention reduces the impact ratios after it ramps in. The reduction at a
    # phase depends on how far past the ramp we are (earlier phases barely helped).
    detect = lags.get("detection_lag", 4)
    decide = lags.get("decision_lag", 3)
    ramp = lags.get("ramp_ticks", 6)
    # Map the simulation's relative ticks to our phases by index proportion.
    n = len(phases)

    def relief_at(idx: int) -> float:
        """0..effect_size — how much the intervention has reduced impact by phase idx."""
        if not intervene:
            return 0.0
        # intervention effective fraction grows after (detect+decide) up the ramp
        start = (detect + decide) / max(1, (detect + decide + ramp + 4))
        full = (detect + decide + ramp) / max(1, (detect + decide + ramp + 4))
        pos = idx / max(1, n - 1)
        if pos <= start:
            return 0.0
        if pos >= full:
            return effect_size
        return effect_size * (pos - start) / max(1e-6, (full - start))

    steps: List[Dict[str, Any]] = []
    peak_affected = exposed * ratios["affected"] * I
    for idx, ph in enumerate(phases):
        m = ph["m"]
        relief = relief_at(idx)
        scale = m * (1.0 - relief)
        affected = int(peak_affected * m)                       # affected is exposure-driven
        deaths = int(exposed * ratios["deaths"] * I * scale)
        injured = int(exposed * ratios["injured"] * I * scale)
        displaced = int(exposed * ratios["displaced"] * I * scale)
        hosp = int(min(200, 100 * ratios["hosp"] * I * m * (1.0 - 0.6 * relief)))
        by_gov = []
        for g in govs:
            if g not in JORDAN_POP:
                continue
            share = JORDAN_POP[g]["pop"] / exposed
            by_gov.append({
                "gov": JORDAN_POP[g]["en"], "name_ar": g,
                "affected": int(affected * share),
                "displaced": int(displaced * share),
            })
        steps.append({
            "t": ph["t"], "label_ar": ph["ar"], "phase": ph["phase"],
            "affected": affected, "casualties": deaths, "injured": injured,
            "displaced": displaced, "hospital_load_pct": hosp,
            "infrastructure": _infra_status(dom, m * (1.0 - 0.5 * relief)),
            "narrative_ar": _phase_narrative(dom, ph, affected, deaths, injured,
                                             displaced, intervene, relief),
            "by_gov": by_gov[:6],
        })

    totals = {
        "affected": max(s["affected"] for s in steps) if steps else 0,
        "casualties": max(s["casualties"] for s in steps) if steps else 0,
        "injured": max(s["injured"] for s in steps) if steps else 0,
        "displaced": max(s["displaced"] for s in steps) if steps else 0,
    }
    return {
        "engine": "deterministic",
        "domain": dom,
        "intervene": intervene,
        "exposed_population": exposed,
        "affected_governorates": [JORDAN_POP[g]["en"] for g in govs if g in JORDAN_POP],
        "intensity": round(I, 3),
        "steps": steps,
        "totals": totals,
        "method_note_ar": ("تقديرات استكشافية مبنية على عدد سكان المحافظات المتأثرة × شدّة "
                           "الأزمة × نسب أثر من الأدبيات — لدعم القرار، وليست تنبؤًا مُعايرًا."),
    }


def _phase_narrative(dom, ph, affected, deaths, injured, displaced, intervene, relief) -> str:
    a = f"{affected:,}".replace(",", "٬")
    base = ""
    if dom == "earthquake":
        if ph["phase"] == "impact":
            base = (f"تتضرّر مبانٍ ويُحتجز سكان تحت الأنقاض؛ نحو {a} شخص متأثّر مباشرة، "
                    f"مع {deaths:,} وفاة و{injured:,} إصابة أوّلية.")
        elif ph["phase"] == "response":
            base = (f"فرق البحث والإنقاذ تعمل؛ ترتفع الإصابات إلى {injured:,} ويُجلى "
                    f"{displaced:,} شخص إلى مراكز إيواء.")
        elif ph["phase"] == "relief":
            base = (f"تتركّز الجهود على الإيواء والمياه والرعاية؛ {displaced:,} نازح "
                    f"بحاجة إلى مأوى، مع خطر هزّات ارتدادية.")
        else:
            base = f"تبدأ إعادة التأهيل؛ يتناقص النازحون مع عودة الخدمات تدريجيًّا."
    elif dom == "epidemic":
        base = (f"عدد المصابين التراكمي نحو {a}، مع {deaths:,} وفاة وضغط متزايد "
                f"على المستشفيات.")
    elif dom == "flood":
        base = (f"يتأثّر نحو {a} شخص، ويُجلى {displaced:,}؛ طرق وأحياء مغمورة.")
    else:
        base = f"يتأثّر نحو {a} شخص بالأزمة في هذه المرحلة."
    if intervene and relief > 0.05:
        base += f" (التدخّل يخفّف الأثر بنحو {round(relief*100)}٪ في هذه المرحلة.)"
    return base


# ── LLM layer ─────────────────────────────────────────────────────────────────
def _llm_timeline(text: str, base: Dict[str, Any], papers: List[Dict[str, Any]],
                  intervene: bool, interventions: List[str]) -> Optional[Dict[str, Any]]:
    """Ask the model to rewrite the deterministic timeline with richer, paper-grounded
    specifics — STRICT JSON matching the same schema. Returns None on any failure."""
    if _llm is None or not _llm.available():
        return None
    ev_lines = []
    for p in papers[:4]:
        sn = (p.get("snippet") or "")[:200]
        ev_lines.append(f"- {p.get('title','')[:80]} ({p.get('year')}): {sn}")
    evidence = "\n".join(ev_lines) or "(لا مصادر)"
    skeleton = json.dumps({"steps": [
        {"t": s["t"], "label_ar": s["label_ar"], "phase": s["phase"],
         "affected": s["affected"], "casualties": s["casualties"],
         "injured": s["injured"], "displaced": s["displaced"],
         "hospital_load_pct": s["hospital_load_pct"]}
        for s in base["steps"]
    ]}, ensure_ascii=False)

    role = "حلّ" if intervene else "أزمة"
    iv = f"التدخّلات المتاحة: {', '.join(interventions)}." if (intervene and interventions) else ""
    sysmsg = (
        "أنت محاكي أزمات للأردن. أعطيتُك خطًّا زمنيًّا أوّليًّا بأرقام تقديرية "
        "وعدد سكان المحافظات وأدلّة علمية. أعد صياغة كل مرحلة بسرد واقعي محدّد "
        "(ماذا يحدث فعليًّا، من يتأثّر) واضبط الأرقام لتكون متّسقة مع الأدلّة وسكان "
        "الأردن. لا تختلق أرقامًا مبالغًا فيها. أعد JSON فقط بنفس البنية مع حقل "
        "narrative_ar عربي لكل مرحلة. لا نص خارج JSON."
    )
    user = (
        f"السيناريو ({role}): {text[:400]}\n"
        f"المجال: {base['domain']} | السكان المعرّضون: {base['exposed_population']:,}\n"
        f"{iv}\n"
        f"الأدلّة العلمية:\n{evidence}\n\n"
        f"الخط الزمني الأوّلي (اضبطه وأضف narrative_ar لكل مرحلة):\n{skeleton}\n\n"
        f"أعد JSON: {{\"steps\":[{{\"t\":..,\"label_ar\":..,\"phase\":..,\"affected\":int,"
        f"\"casualties\":int,\"injured\":int,\"displaced\":int,\"hospital_load_pct\":int,"
        f"\"infrastructure\":\"..\",\"narrative_ar\":\"..\"}}]}}"
    )
    try:
        out = _llm.chat(sysmsg, user, temperature=0.4, max_tokens=1400, timeout=40)
        if not out:
            return None
        # extract the first JSON object
        m = re.search(r"\{.*\}", out, re.DOTALL)
        if not m:
            return None
        parsed = json.loads(m.group(0))
        llm_steps = parsed.get("steps")
        if not isinstance(llm_steps, list) or not llm_steps:
            return None
        # merge: keep deterministic by_gov, take LLM narrative + adjusted figures
        merged_steps = []
        for i, base_step in enumerate(base["steps"]):
            ls = llm_steps[i] if i < len(llm_steps) else {}
            merged_steps.append({
                **base_step,
                "affected": int(ls.get("affected", base_step["affected"]) or base_step["affected"]),
                "casualties": int(ls.get("casualties", base_step["casualties"]) or base_step["casualties"]),
                "injured": int(ls.get("injured", base_step["injured"]) or base_step["injured"]),
                "displaced": int(ls.get("displaced", base_step["displaced"]) or base_step["displaced"]),
                "hospital_load_pct": int(ls.get("hospital_load_pct", base_step["hospital_load_pct"]) or base_step["hospital_load_pct"]),
                "infrastructure": (ls.get("infrastructure") or base_step["infrastructure"])[:120],
                "narrative_ar": (ls.get("narrative_ar") or base_step["narrative_ar"])[:400],
            })
        result = dict(base)
        result["engine"] = "llm"
        result["steps"] = merged_steps
        result["totals"] = {
            "affected": max(s["affected"] for s in merged_steps),
            "casualties": max(s["casualties"] for s in merged_steps),
            "injured": max(s["injured"] for s in merged_steps),
            "displaced": max(s["displaced"] for s in merged_steps),
        }
        result["method_note_ar"] = ("سرد مولّد بالذكاء الاصطناعي ومُقيَّد بعدد سكان الأردن "
                                    "والأدلّة العلمية والخط الزمني الكمّي — تقديرات استكشافية.")
        return result
    except Exception:
        return None


# ── Public entry ──────────────────────────────────────────────────────────────
def simulate_impact(
    text: str, *, domain: str = "", location: Optional[str] = None,
    intensity: float = 0.6, effect_size: float = 0.6, intervene: bool = False,
    lags: Optional[Dict[str, int]] = None, papers: Optional[List[Dict[str, Any]]] = None,
    interventions: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Produce a concrete step-by-step impact timeline (deterministic, LLM-enriched)."""
    govs = _resolve_govs(location)
    lags = lags or {"detection_lag": 4, "decision_lag": 3, "ramp_ticks": 6}
    base = _deterministic_timeline(text, domain, govs, intensity, effect_size, intervene, lags)
    enriched = _llm_timeline(text, base, papers or [], intervene, interventions or [])
    return enriched or base
