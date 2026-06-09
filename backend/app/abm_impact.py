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

# Real Jordanian hospitals per governorate (major public + university + military).
JORDAN_HOSPITALS: Dict[str, List[str]] = {
    "عمان":    ["مدينة الحسين الطبية", "مستشفى البشير", "مستشفى الجامعة الأردنية", "مستشفى الأمير حمزة"],
    "إربد":    ["مستشفى الملك المؤسس عبدالله الجامعي", "مستشفى الأميرة بسمة", "مستشفى إربد التخصصي"],
    "الزرقاء": ["مستشفى الأمير فيصل", "مستشفى الزرقاء الحكومي", "مستشفى الأمير هاشم العسكري"],
    "المفرق":  ["مستشفى المفرق الحكومي", "مستشفى الزعتري الميداني"],
    "البلقاء": ["مستشفى السلط الحكومي", "مستشفى الأمير حمزة"],
    "الكرك":   ["مستشفى الكرك الحكومي", "مستشفى الإيمان"],
    "جرش":     ["مستشفى جرش الحكومي"],
    "العقبة":  ["مستشفى الأمير هاشم", "مستشفى الأميرة هيا العسكري"],
    "مادبا":   ["مستشفى مادبا الحكومي"],
    "عجلون":   ["مستشفى عجلون الحكومي", "مستشفى الإيمان"],
    "معان":    ["مستشفى معان الحكومي", "مستشفى الأمير زيد بن الحسين"],
    "الطفيلة": ["مستشفى الطفيلة الحكومي"],
}

# Real Jordanian landmarks / infrastructure referenced in narratives, by domain.
JORDAN_LANDMARKS: Dict[str, List[str]] = {
    "earthquake": ["وسط البلد", "جبل عمّان", "مخيّم الوحدات", "الطريق الصحراوي", "جسر عبدون"],
    "flood":      ["البحر الميت", "وادي الموجب", "السيل/وسط عمّان", "البتراء", "وادي رم"],
    "water":      ["سد الوحدة", "سد الملك طلال", "محطة الزارة–ماعين", "ناقل الديسي", "شبكة مياهنا"],
    "epidemic":   ["وزارة الصحة", "مراكز الرعاية الأولية", "مخيّم الزعتري", "مخيّم الأزرق"],
    "energy":     ["شركة الكهرباء الوطنية", "محطة الحسين الحرارية", "مصفاة البترول الأردنية"],
    "general":    ["مطار الملكة علياء الدولي", "الطريق الصحراوي", "مناطق التنمية"],
}


def _hospitals_for(govs: List[str], limit: int = 5) -> List[str]:
    out: List[str] = []
    for g in govs:
        for h in JORDAN_HOSPITALS.get(g, []):
            if h not in out:
                out.append(h)
    return out[:limit]


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
        """0..effect_size — how much the intervention has reduced impact by phase idx.

        A PREPAREDNESS floor (30% of the effect) applies from the very first phase —
        building codes, drills and pre-positioned response reduce even the acute toll —
        while the remaining 70% (active operator response) ramps in after the
        detection + decision + ramp lag. So the solution beats the crisis at the peak
        too, not only in later phases."""
        if not intervene:
            return 0.0
        immediate = 0.30 * effect_size                      # preparedness, from t0
        active = 0.70 * effect_size                          # operator response, lagged
        start = (detect + decide) / max(1, (detect + decide + ramp + 4))
        full = (detect + decide + ramp) / max(1, (detect + decide + ramp + 4))
        pos = idx / max(1, n - 1)
        if pos <= start:
            ramped = 0.0
        elif pos >= full:
            ramped = active
        else:
            ramped = active * (pos - start) / max(1e-6, (full - start))
        return min(effect_size, immediate + ramped)

    hospitals = _hospitals_for(govs)
    landmarks = JORDAN_LANDMARKS.get(dom, JORDAN_LANDMARKS["general"])

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
                                             displaced, intervene, relief, hospitals, landmarks),
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
        "national_population": _TOTAL_POP,
        "affected_governorates": [JORDAN_POP[g]["en"] for g in govs if g in JORDAN_POP],
        "affected_governorates_ar": [g for g in govs if g in JORDAN_POP],
        "hospitals": hospitals,
        "landmarks": landmarks,
        "intensity": round(I, 3),
        "steps": steps,
        "totals": totals,
        "method_note_ar": ("تقديرات استكشافية مبنية على عدد سكان المحافظات المتأثرة في الأردن × "
                           "شدّة الأزمة × نسب أثر من الأدبيات — لدعم القرار، وليست تنبؤًا مُعايرًا."),
    }


def _phase_narrative(dom, ph, affected, deaths, injured, displaced, intervene, relief,
                     hospitals=None, landmarks=None) -> str:
    a = f"{affected:,}".replace(",", "٬")
    hosp = (hospitals or [])
    h1 = hosp[0] if hosp else "المستشفيات الحكومية"
    h2 = hosp[1] if len(hosp) > 1 else h1
    lm = (landmarks or [])
    place = lm[0] if lm else "المناطق المتأثّرة"
    base = ""
    if dom == "earthquake":
        if ph["phase"] == "impact":
            base = (f"تتضرّر مبانٍ في {place} ويُحتجز سكان تحت الأنقاض؛ نحو {a} شخص متأثّر مباشرة، "
                    f"مع {deaths:,} وفاة و{injured:,} إصابة أوّلية تتدفّق إلى {h1}.")
        elif ph["phase"] == "response":
            base = (f"فرق الدفاع المدني تعمل في البحث والإنقاذ؛ ترتفع الإصابات إلى {injured:,}، "
                    f"ويتجاوز {h1} و{h2} طاقتهما الاستيعابية، ويُجلى {displaced:,} شخص إلى مراكز الإيواء.")
        elif ph["phase"] == "relief":
            base = (f"تتركّز الجهود على الإيواء والمياه والرعاية؛ {displaced:,} نازح بحاجة إلى مأوى، "
                    f"مع استمرار الضغط على {h1} وخطر هزّات ارتدادية.")
        else:
            base = "تبدأ إعادة الإعمار؛ يتناقص النازحون وتعود خدمات المستشفيات تدريجيًّا."
    elif dom == "epidemic":
        base = (f"عدد المصابين التراكمي نحو {a}، مع {deaths:,} وفاة وضغط متزايد على "
                f"{h1} وأقسام العناية الحثيثة.")
    elif dom == "flood":
        base = (f"يتأثّر نحو {a} شخص قرب {place}، ويُجلى {displaced:,}؛ طرق وأحياء مغمورة "
                f"وتحويل المصابين إلى {h1}.")
    elif dom == "water":
        base = (f"ينقطع الماء عن نحو {a} شخص؛ ضغط على {h1} لحالات الجفاف والأمراض المنقولة بالمياه، "
                f"واعتماد متزايد على مصادر مثل {place}.")
    else:
        base = f"يتأثّر نحو {a} شخص بالأزمة في هذه المرحلة، مع ضغط على {h1}."
    if intervene and relief > 0.05:
        base += f" (التدخّل يخفّف الأثر بنحو {round(relief*100)}٪ في هذه المرحلة.)"
    return base


# ── LLM layer ─────────────────────────────────────────────────────────────────
def _parse_narratives(out: str, n: int) -> Optional[List[str]]:
    """Robustly extract narrative strings from a model reply — tolerant of markdown
    fences, {"narratives":[...]}, a bare array, or a numbered list. None if nothing."""
    if not out:
        return None
    cleaned = re.sub(r"```(?:json)?", "", out).strip()
    # 1) JSON object with a list under a known key
    for m in re.finditer(r"\{.*\}", cleaned, re.DOTALL):
        try:
            obj = json.loads(m.group(0))
        except Exception:
            continue
        if isinstance(obj, dict):
            for key in ("narratives", "steps", "phases", "items"):
                v = obj.get(key)
                if isinstance(v, list) and v:
                    lst = [x if isinstance(x, str)
                           else (x.get("narrative_ar") or x.get("narrative") or "")
                           for x in v]
                    lst = [s for s in lst if s]
                    if lst:
                        return lst
    # 2) bare JSON array of strings
    m = re.search(r"\[.*\]", cleaned, re.DOTALL)
    if m:
        try:
            arr = json.loads(m.group(0))
            strs = [x for x in arr if isinstance(x, str) and x.strip()]
            if strs:
                return strs
        except Exception:
            pass
    # 3) line list (strip bullets/numbering)
    lines = [re.sub(r"^\s*(?:[-*•]|\d+[.)،-])\s*", "", ln).strip() for ln in cleaned.splitlines()]
    lines = [ln for ln in lines if len(ln) > 15]
    return lines or None


def _clean_narr(s: str) -> str:
    """Strip an echoed 'سرد N:' / 'النص N:' / 'N:' prefix the model sometimes adds."""
    return re.sub(r"^\s*(?:سرد|النص|المرحلة)?\s*\d+\s*[:：.\-]\s*", "", s or "").strip()


def _llm_timeline(text: str, base: Dict[str, Any], papers: List[Dict[str, Any]],
                  intervene: bool, interventions: List[str]) -> Optional[Dict[str, Any]]:
    """Enrich ONLY the per-phase narrative via the model — the numbers stay
    demographically grounded. Asks for a simple JSON array of strings, which the
    model reproduces far more reliably than a full numeric schema. None on failure."""
    if _llm is None or not _llm.available():
        return None
    ev_lines = []
    for p in papers[:4]:
        sn = (p.get("snippet") or "")[:180]
        if sn:
            ev_lines.append(f"- {p.get('title','')[:80]} ({p.get('year')}): {sn}")
    evidence = "\n".join(ev_lines) or "(لا مصادر)"

    n = len(base["steps"])
    phase_facts = "\n".join(
        f"{i+1}. {s['label_ar']} — متأثّرون {s['affected']:,}، وفيات {s['casualties']:,}، "
        f"إصابات {s['injured']:,}، نازحون {s['displaced']:,}، إشغال المستشفيات {s['hospital_load_pct']}٪"
        for i, s in enumerate(base["steps"])
    )
    role = "بعد تطبيق التدخّل والحلول" if intervene else "دون أيّ تدخّل"
    iv = f" التدخّلات المتاحة: {', '.join(interventions)}." if (intervene and interventions) else ""

    hosp_names = "، ".join(base.get("hospitals", [])[:5]) or "المستشفيات الحكومية"
    landmarks = "، ".join(base.get("landmarks", [])[:5])
    govs_ar = "، ".join(base.get("affected_governorates_ar", []))
    nat_pop = base.get("national_population", 0)

    sysmsg = (
        "أنت محاكي أزمات خبير بالأردن. اسرد ما يحدث فعليًّا في كل مرحلة بلغة عربية "
        "واضحة ومحدّدة (من يتأثّر، ماذا يحدث على الأرض، حالة الخدمات والبنية التحتية). "
        "استخدم أسماء مستشفيات ومعالم أردنية حقيقية من القائمة المُعطاة، ولا تخترع أسماء "
        "أو أرقامًا غير موجودة. "
        f"أعد مصفوفة JSON من {n} نصوص فقط بالترتيب: [\"سرد 1\", \"سرد 2\", ...]. "
        "لا تكتب أيّ شيء خارج المصفوفة."
    )
    user = (
        f"السيناريو ({role}): {text[:400]}\n"
        f"المجال: {base['domain']} | المحافظات المتأثّرة: {govs_ar}\n"
        f"السكان المعرّضون: {base['exposed_population']:,} من أصل {nat_pop:,} في الأردن.{iv}\n"
        f"مستشفيات أردنية حقيقية لاستخدامها بالاسم: {hosp_names}\n"
        f"معالم/بنية تحتية أردنية: {landmarks}\n"
        f"الأدلّة العلمية:\n{evidence}\n\n"
        f"المراحل وأرقامها (اسرد كلًّا منها في ٢-٣ جمل واذكر مستشفى أو معلمًا حقيقيًّا عند الملاءمة):\n{phase_facts}\n\n"
        f"أعد مصفوفة JSON من {n} نصًّا عربيًّا بالترتيب."
    )
    try:
        out = _llm.chat(sysmsg, user, temperature=0.5, max_tokens=1600, timeout=120)
        narrs = _parse_narratives(out or "", n)
        if not narrs:
            return None
        merged_steps = []
        for i, base_step in enumerate(base["steps"]):
            narr = (_clean_narr(narrs[i]) if i < len(narrs) else "") or base_step["narrative_ar"]
            merged_steps.append({**base_step, "narrative_ar": narr[:500]})
        result = dict(base)
        result["engine"] = "llm"
        result["steps"] = merged_steps
        result["method_note_ar"] = (
            "الأرقام مُقدّرة من سكان الأردن × الشدّة × نسب الأدبيات؛ والسرد مولّد "
            "بالذكاء الاصطناعي ومُقيَّد بهذه الأرقام والأدلّة — تقديرات استكشافية لدعم القرار.")
        return result
    except Exception:
        return None


# ── Public entry ──────────────────────────────────────────────────────────────
def simulate_impact(
    text: str, *, domain: str = "", location: Optional[str] = None,
    intensity: float = 0.6, effect_size: float = 0.6, intervene: bool = False,
    lags: Optional[Dict[str, int]] = None, papers: Optional[List[Dict[str, Any]]] = None,
    interventions: Optional[List[str]] = None,
    case_studies: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Produce a concrete step-by-step impact timeline (deterministic, case-grounded, LLM-enriched).

    case_studies (from ai_case_studies table) add two things:
      1. Real impact figures blended into the deterministic baseline.
      2. Case solutions fed into the LLM narrative as proven precedents.
    """
    govs = _resolve_govs(location)
    lags = lags or {"detection_lag": 4, "decision_lag": 3, "ramp_ticks": 6}
    base = _deterministic_timeline(text, domain, govs, intensity, effect_size, intervene, lags)

    # Blend real case impact numbers into the baseline totals when available
    if case_studies:
        base = _blend_case_numbers(base, case_studies, govs)

    # Build combined evidence: papers + case study solutions for the LLM
    all_evidence = list(papers or [])
    for c in (case_studies or [])[:3]:
        if c.get("solution"):
            all_evidence.append({
                "title": c.get("title", ""),
                "year": None,
                "snippet": f"الحل الموثّق: {c['solution'][:300]}",
            })

    enriched = _llm_timeline(text, base, all_evidence, intervene,
                             interventions or [c.get("solution","")[:80] for c in (case_studies or [])[:2]])
    return enriched or base


def _blend_case_numbers(base: Dict[str, Any],
                        case_studies: List[Dict[str, Any]],
                        govs: List[str]) -> Dict[str, Any]:
    """Blend real case impact numbers (from ai_case_studies) into the deterministic base.

    We extract deaths/displaced/affected from each case's impact text, compute a
    scaled estimate for the Jordan exposure, and gently adjust the peak step.
    Only used when at least one case has extractable numbers.
    """
    exposed = base.get("exposed_population", 1)
    death_hints, disp_hints = [], []
    for c in case_studies:
        imp = c.get("impact_numbers") or {}
        # Each case covers its own country's population — scale to our exposed population
        # using a conservative fraction (don't blindly scale M+ case figures 1:1)
        d = imp.get("deaths")
        di = imp.get("displaced")
        if d and 10 < d < 500_000:
            death_hints.append(d)
        if di and 100 < di < 5_000_000:
            disp_hints.append(di)

    if not death_hints and not disp_hints:
        return base  # nothing to blend

    import statistics
    steps = list(base.get("steps", []))
    if not steps:
        return base

    # Find peak step and adjust its figures toward the case-study mean
    peak_idx = max(range(len(steps)), key=lambda i: steps[i].get("casualties", 0))
    step = dict(steps[peak_idx])
    if death_hints:
        case_mean = statistics.median(death_hints)
        # Blend 60% deterministic + 40% case evidence (case values are raw, not scaled)
        orig = step.get("casualties", 0)
        # Scale case mean by ratio of our exposed pop to a typical country (5M baseline)
        scaled = case_mean * (exposed / 5_000_000)
        blended = int(0.60 * orig + 0.40 * scaled)
        if blended > 0:
            step["casualties"] = blended
    if disp_hints:
        case_mean = statistics.median(disp_hints)
        orig = step.get("displaced", 0)
        scaled = case_mean * (exposed / 5_000_000)
        blended = int(0.60 * orig + 0.40 * scaled)
        if blended > 0:
            step["displaced"] = blended

    steps[peak_idx] = step
    result = dict(base)
    result["steps"] = steps
    result["totals"] = {
        "affected":   max(s["affected"]   for s in steps),
        "casualties": max(s["casualties"] for s in steps),
        "injured":    max(s["injured"]    for s in steps),
        "displaced":  max(s["displaced"]  for s in steps),
    }
    result["method_note_ar"] = (
        base.get("method_note_ar", "") +
        f" | أرقام الذروة مُعدَّلة بمزج {len(case_studies)} حالة تاريخية موثّقة."
    )
    return result
