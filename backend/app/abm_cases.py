"""Query ai_case_studies for historical crisis precedents to ground the simulation.

The table holds 2,472 real-world crisis cases (IFRC, UNICEF, OCHA, FEMA, WHO …),
each with structured crisis / impact / solution text.  This module:

  1. Maps the detected simulation domain to the relevant disaster_type values.
  2. Scores rows by geographic proximity (Jordan → Middle East → global).
  3. Extracts numeric impact estimates from the impact field (deaths, displaced …).
  4. Returns structured precedents used by abm_flow for calibration and narrative.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

try:
    from . import db as _db
except Exception:  # pragma: no cover
    _db = None  # type: ignore

# ── Domain → disaster_type mapping ───────────────────────────────────────────
_DOMAIN_TYPES: Dict[str, List[str]] = {
    "earthquake": ["Earthquake", "Earthquake, Tsunami", "Earthquake, Flood",
                   "Earthquake, Conflict", "Earthquake, Landslide", "Earthquake, Nuclear"],
    "flood":      ["Flood", "Pluvial/Flash Flood", "Flood, Cyclone/Hurricane",
                   "Flood, Drought", "Flood, Pandemic", "Flood, Conflict",
                   "Flood, Infrastructure Failure", "Storm Surge"],
    "epidemic":   ["Pandemic", "Epidemic", "Epidemic, Cholera", "Epidemic, Dengue",
                   "Epidemic, Ebola", "Epidemic, Mpox", "Health Emergency",
                   "Pandemic, Epidemic", "Pandemic, Conflict", "Pandemic, Refugee Crisis",
                   "Pandemic, Avian Influenza", "Conflict, Pandemic"],
    "water":      ["Drought", "Drought, Conflict", "Drought, Pandemic",
                   "Infrastructure Failure, Drought", "Infrastructure Failure"],
    "energy":     ["Infrastructure Failure", "Industrial"],
    "conflict":   ["Conflict", "Conflict, Displacement", "Conflict, Refugee Crisis",
                   "Conflict, Pandemic", "Conflict, Famine", "Humanitarian Crisis",
                   "Complex Emergency"],
    "general":    [],   # falls through to all types
}

# ── Geographic priority ───────────────────────────────────────────────────────
_JORDAN_KEYWORDS = ["jordan", "الأردن", "jordania"]
_MIDEAST_KEYWORDS = ["syria", "lebanon", "iraq", "turkey", "palestine", "egypt",
                     "saudi", "israel", "middle east", "mena", "arab"]

# ── Numeric extraction from impact text ───────────────────────────────────────
_DEATH_RE = re.compile(
    r"(?:kill(?:ed)?|death|died?|fatal|casualt|وفاة|قتيل)\D{0,20}?([\d,\.]+)\s*(?:k\b|thousand)?",
    re.IGNORECASE,
)
_DISPLACED_RE = re.compile(
    r"(?:displace|evacuate|homeless|shelter|نازح|نازحين)\D{0,20}?([\d,\.]+)\s*(?:m\b|million|k\b|thousand)?",
    re.IGNORECASE,
)
_AFFECTED_RE = re.compile(
    r"(?:affect(?:ed)?|impact(?:ed)?|متأثّر|تضرّر)\D{0,20}?([\d,\.]+)\s*(?:m\b|million|k\b|thousand)?",
    re.IGNORECASE,
)


def _parse_num(m: Optional[re.Match], text_suffix: str = "") -> Optional[int]:
    if not m:
        return None
    try:
        raw = m.group(1).replace(",", "").replace(".", "")
        n = int(raw)
        suffix = (text_suffix + m.group(0)).lower()
        if "million" in suffix or " m" in suffix:
            n *= 1_000_000
        elif "thousand" in suffix or " k" in suffix:
            n *= 1_000
        return n if n > 0 else None
    except Exception:
        return None


def extract_impact_numbers(impact_text: str) -> Dict[str, Optional[int]]:
    """Pull deaths, displaced, affected counts from a free-text impact field."""
    t = impact_text or ""
    return {
        "deaths":    _parse_num(_DEATH_RE.search(t)),
        "displaced": _parse_num(_DISPLACED_RE.search(t)),
        "affected":  _parse_num(_AFFECTED_RE.search(t)),
    }


# ── Geographic scoring ─────────────────────────────────────────────────────────
def _geo_score(country: str) -> int:
    c = (country or "").lower()
    if any(k in c for k in _JORDAN_KEYWORDS):
        return 0   # exact Jordan match
    if any(k in c for k in _MIDEAST_KEYWORDS):
        return 1   # Middle East / MENA
    return 2       # global


# ── Main query ────────────────────────────────────────────────────────────────
def search_cases(
    domain: str,
    location: Optional[str] = None,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """Return historical case studies matching the crisis domain + geographic context.

    Results are scored: Jordan-specific first, then Middle East, then global.
    Each result includes extracted numeric impact estimates alongside raw text.
    """
    if _db is None:
        return []

    types = _DOMAIN_TYPES.get(domain.lower(), [])
    try:
        if types:
            # Build IN clause with literals (all safe, no user input in type list)
            in_clause = ",".join(f"'{t}'" for t in types)
            rows = _db.fetchall(
                f"SELECT id, title, country, disaster_type, crisis, impact, solution, source_site "
                f"FROM ai_case_studies "
                f"WHERE disaster_type IN ({in_clause}) "
                f"ORDER BY length(coalesce(solution,'')) DESC "
                f"LIMIT 60"          # fetch more, then score + trim
            )
        else:
            # General / unknown domain — fetch recent well-documented cases
            rows = _db.fetchall(
                "SELECT id, title, country, disaster_type, crisis, impact, solution, source_site "
                "FROM ai_case_studies "
                "WHERE solution IS NOT NULL "
                "ORDER BY length(coalesce(solution,'')) DESC "
                "LIMIT 60"
            )
    except Exception:
        return []

    if not rows:
        return []

    # Score and sort by geo proximity, then solution richness
    scored = sorted(
        rows,
        key=lambda r: (_geo_score(r.get("country") or ""), -len(r.get("solution") or "")),
    )

    results = []
    for r in scored[:limit]:
        nums = extract_impact_numbers(r.get("impact") or "")
        results.append({
            "id":            r["id"],
            "title":         r["title"],
            "country":       r["country"],
            "disaster_type": r["disaster_type"],
            "source_site":   r["source_site"],
            "crisis":        (r["crisis"] or "")[:400],
            "impact":        (r["impact"] or "")[:400],
            "solution":      (r["solution"] or "")[:400],
            "impact_numbers": nums,          # extracted: deaths, displaced, affected
            "geo_tier":      _geo_score(r.get("country") or ""),  # 0=Jordan,1=ME,2=global
        })
    return results


def calibrate_from_cases(cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Derive impact ratio adjustments from real case numbers.

    If matching cases have extractable numbers, blend them with the default
    literature ratios to ground the impact timeline in actual events.
    Returns a dict that abm_impact can use to adjust its estimates.
    """
    if not cases:
        return {"available": False}

    death_ratios, displaced_ratios, affect_ratios = [], [], []
    for c in cases:
        nums = c.get("impact_numbers") or {}
        deaths = nums.get("deaths")
        displaced = nums.get("displaced")
        affected = nums.get("affected")
        # Only use if at least one figure is plausible
        if deaths and 10 < deaths < 5_000_000:
            death_ratios.append(deaths)
        if displaced and 100 < displaced < 50_000_000:
            displaced_ratios.append(displaced)
        if affected and 100 < affected < 100_000_000:
            affect_ratios.append(affected)

    def safe_mean(lst: list) -> Optional[float]:
        return sum(lst) / len(lst) if lst else None

    top = cases[0]
    return {
        "available":       True,
        "n_cases":         len(cases),
        "top_case":        top["title"],
        "top_country":     top["country"],
        "geo_tier":        top["geo_tier"],
        "mean_deaths":     safe_mean(death_ratios),
        "mean_displaced":  safe_mean(displaced_ratios),
        "mean_affected":   safe_mean(affect_ratios),
        "solutions":       [c["solution"] for c in cases if c.get("solution")][:3],
        "notes_ar": (
            f"معلومات مستخلصة من {len(cases)} حالة تاريخية موثّقة "
            f"(المصدر: {top['source_site']}, {top['country']})."
        ),
    }
