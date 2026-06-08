"""Live Middle East crisis-signal RSS aggregator — in-memory, no database.

Fetches a set of regional news RSS feeds on a 90-second background loop, parses
each item with :mod:`feedparser`, geolocates it from a keyword→centroid table,
classifies category + severity with keyword heuristics, deduplicates by a hash of
the article link, and keeps a rolling window of the most-recent
:class:`CrisisSignal` items in memory. The ``api_rss`` router serves them at
``/api/rss/signals|sources|stats``.

Design notes
------------
* **No DB.** Everything lives in a module-level store guarded by a lock. The old
  ``aegis_news`` table and its migration are gone.
* **Resilient.** A single dead/relocated feed never crashes a fetch cycle — the
  per-feed error is logged and recorded in the source-status table, and the rest
  of the feeds still load. If *every* feed fails we keep serving the last good
  data instead of returning nothing.
* **Cheap.** No external geocoding/news APIs: geolocation is a hardcoded
  place-name → centroid table covering the Middle East + North Africa.
"""
from __future__ import annotations

import hashlib
import html
import logging
import re
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests

try:
    import feedparser  # type: ignore
except Exception:  # pragma: no cover - feedparser is a hard dep but stay import-safe
    feedparser = None  # type: ignore

from pydantic import BaseModel

log = logging.getLogger("aegis.rss")

# ── Configuration ────────────────────────────────────────────────────────────
FETCH_INTERVAL_SECONDS = 90
MAX_ITEMS = 500
_REQUEST_TIMEOUT = 15
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

# (display name, feed URL). Some may be dead/relocated — the fetch loop skips any
# that fail and records the error in the source-status table.
_FEEDS: List[Tuple[str, str]] = [
    ("Al Jazeera English",   "https://www.aljazeera.com/xml/rss/all.xml"),
    ("Al Jazeera Arabic",    "https://www.aljazeera.net/aljazeerarss/a7c186be-1baa-4bd4-9d80-a84db769f779/73d0e1b4-532f-45ef-b135-bfdff8b8cab9"),
    ("Al Arabiya English",   "https://english.alarabiya.net/tools/rss"),
    ("Gulf News",            "https://gulfnews.com/rss"),
    ("Jordan Times",         "https://www.jordantimes.com/rss.xml"),
    ("Middle East Eye",      "https://www.middleeasteye.net/rss"),
    ("Middle East Monitor",  "https://www.middleeastmonitor.com/feed/"),
    ("Arab News",            "https://www.arabnews.com/rss.xml"),
    ("The National UAE",     "https://www.thenationalnews.com/arc/outboundfeeds/rss/?outputType=xml"),
    ("Times of Israel",      "https://www.timesofisrael.com/feed/"),
    # Reliable, bot-friendly regional desks — keep coverage strong even when the
    # outlets above are blocked/relocated from a given network.
    ("BBC Middle East",      "https://feeds.bbci.co.uk/news/world/middle_east/rss.xml"),
    ("France24 Middle East", "https://www.france24.com/en/middle-east/rss"),
]

# ── Geolocation table ────────────────────────────────────────────────────────
# place needle → (country, lat, lng). Latin needles are matched on word
# boundaries; non-ASCII (Arabic) needles via plain substring. First match wins,
# title scanned before summary. Cities resolve to their own coordinates but carry
# the country name so map + stats group correctly.
_PLACES: List[Tuple[str, str, float, float]] = [
    # Jordan
    ("amman", "Jordan", 31.95, 35.93), ("jordan", "Jordan", 31.95, 35.93),
    ("عمان", "Jordan", 31.95, 35.93), ("الأردن", "Jordan", 31.95, 35.93),
    # Palestine
    ("gaza", "Palestine", 31.50, 34.47), ("ramallah", "Palestine", 31.90, 35.20),
    ("west bank", "Palestine", 31.95, 35.30), ("rafah", "Palestine", 31.29, 34.25),
    ("khan younis", "Palestine", 31.34, 34.30), ("palestin", "Palestine", 31.90, 35.20),
    ("غزة", "Palestine", 31.50, 34.47), ("رام الله", "Palestine", 31.90, 35.20),
    ("الضفة", "Palestine", 31.95, 35.30), ("فلسطين", "Palestine", 31.90, 35.20),
    # Israel
    ("tel aviv", "Israel", 32.08, 34.78), ("jerusalem", "Israel", 31.78, 35.22),
    ("al-quds", "Israel", 31.78, 35.22), ("al quds", "Israel", 31.78, 35.22),
    ("haifa", "Israel", 32.79, 34.99), ("israel", "Israel", 32.08, 34.78),
    ("تل أبيب", "Israel", 32.08, 34.78), ("القدس", "Israel", 31.78, 35.22),
    ("إسرائيل", "Israel", 32.08, 34.78),
    # Lebanon
    ("beirut", "Lebanon", 33.89, 35.50), ("lebanon", "Lebanon", 33.89, 35.50),
    ("بيروت", "Lebanon", 33.89, 35.50), ("لبنان", "Lebanon", 33.89, 35.50),
    # Syria
    ("damascus", "Syria", 33.51, 36.29), ("dimashq", "Syria", 33.51, 36.29),
    ("aleppo", "Syria", 36.20, 37.16), ("homs", "Syria", 34.73, 36.71),
    ("syria", "Syria", 33.51, 36.29), ("دمشق", "Syria", 33.51, 36.29),
    ("حلب", "Syria", 36.20, 37.16), ("سوريا", "Syria", 33.51, 36.29),
    # Iraq
    ("baghdad", "Iraq", 33.31, 44.36), ("erbil", "Iraq", 36.19, 44.01),
    ("basra", "Iraq", 30.51, 47.78), ("mosul", "Iraq", 36.34, 43.13),
    ("iraq", "Iraq", 33.31, 44.36), ("بغداد", "Iraq", 33.31, 44.36),
    ("أربيل", "Iraq", 36.19, 44.01), ("البصرة", "Iraq", 30.51, 47.78),
    ("العراق", "Iraq", 33.31, 44.36),
    # Egypt
    ("cairo", "Egypt", 30.04, 31.24), ("alexandria", "Egypt", 31.20, 29.92),
    ("egypt", "Egypt", 30.04, 31.24), ("القاهرة", "Egypt", 30.04, 31.24),
    ("الإسكندرية", "Egypt", 31.20, 29.92), ("مصر", "Egypt", 30.04, 31.24),
    # Saudi Arabia
    ("riyadh", "Saudi Arabia", 24.71, 46.68), ("jeddah", "Saudi Arabia", 21.49, 39.19),
    ("mecca", "Saudi Arabia", 21.39, 39.86), ("saudi", "Saudi Arabia", 24.71, 46.68),
    ("الرياض", "Saudi Arabia", 24.71, 46.68), ("جدة", "Saudi Arabia", 21.49, 39.19),
    ("السعودية", "Saudi Arabia", 24.71, 46.68),
    # UAE
    ("abu dhabi", "UAE", 24.45, 54.38), ("dubai", "UAE", 25.20, 55.27),
    ("emirates", "UAE", 24.45, 54.38), ("u.a.e", "UAE", 24.45, 54.38),
    ("أبوظبي", "UAE", 24.45, 54.38), ("دبي", "UAE", 25.20, 55.27),
    ("الإمارات", "UAE", 24.45, 54.38),
    # Gulf states
    ("kuwait", "Kuwait", 29.38, 47.99), ("الكويت", "Kuwait", 29.38, 47.99),
    ("manama", "Bahrain", 26.23, 50.59), ("bahrain", "Bahrain", 26.23, 50.59),
    ("البحرين", "Bahrain", 26.23, 50.59),
    ("doha", "Qatar", 25.29, 51.53), ("qatar", "Qatar", 25.29, 51.53),
    ("الدوحة", "Qatar", 25.29, 51.53), ("قطر", "Qatar", 25.29, 51.53),
    ("muscat", "Oman", 23.59, 58.41), ("oman", "Oman", 23.59, 58.41),
    ("عُمان", "Oman", 23.59, 58.41), ("سلطنة عمان", "Oman", 23.59, 58.41),
    # Yemen
    ("sanaa", "Yemen", 15.37, 44.19), ("aden", "Yemen", 12.79, 45.02),
    ("yemen", "Yemen", 15.37, 44.19), ("صنعاء", "Yemen", 15.37, 44.19),
    ("عدن", "Yemen", 12.79, 45.02), ("اليمن", "Yemen", 15.37, 44.19),
    # Iran
    ("tehran", "Iran", 35.69, 51.39), ("iran", "Iran", 35.69, 51.39),
    ("طهران", "Iran", 35.69, 51.39), ("إيران", "Iran", 35.69, 51.39),
    # Turkey
    ("ankara", "Turkey", 39.93, 32.86), ("istanbul", "Turkey", 41.01, 28.98),
    ("turkey", "Turkey", 39.93, 32.86), ("türkiye", "Turkey", 39.93, 32.86),
    ("أنقرة", "Turkey", 39.93, 32.86), ("إسطنبول", "Turkey", 41.01, 28.98),
    ("تركيا", "Turkey", 39.93, 32.86),
    # North Africa
    ("tripoli", "Libya", 32.89, 13.19), ("libya", "Libya", 32.89, 13.19),
    ("طرابلس", "Libya", 32.89, 13.19), ("ليبيا", "Libya", 32.89, 13.19),
    ("tunis", "Tunisia", 36.81, 10.18), ("tunisia", "Tunisia", 36.81, 10.18),
    ("تونس", "Tunisia", 36.81, 10.18),
    ("rabat", "Morocco", 34.02, -6.84), ("casablanca", "Morocco", 33.57, -7.59),
    ("morocco", "Morocco", 34.02, -6.84), ("الرباط", "Morocco", 34.02, -6.84),
    ("المغرب", "Morocco", 34.02, -6.84),
    ("algiers", "Algeria", 36.75, 3.06), ("algeria", "Algeria", 36.75, 3.06),
    ("الجزائر", "Algeria", 36.75, 3.06),
    ("khartoum", "Sudan", 15.50, 32.56), ("sudan", "Sudan", 15.50, 32.56),
    ("الخرطوم", "Sudan", 15.50, 32.56), ("السودان", "Sudan", 15.50, 32.56),
]

# Pre-compile a word-boundary regex for each Latin needle (Arabic stays substring).
_PLACE_MATCHERS: List[Tuple[Any, str, float, float]] = []
for _needle, _country, _lat, _lng in _PLACES:
    if _needle.isascii():
        _PLACE_MATCHERS.append((re.compile(r"\b" + re.escape(_needle) + r"\b"), _country, _lat, _lng))
    else:
        _PLACE_MATCHERS.append((_needle, _country, _lat, _lng))

# ── Category + severity keyword tables ───────────────────────────────────────
# Keyword tables are bilingual: the working feeds include Arabic-language desks
# (Al Jazeera Arabic), so Arabic stems are listed alongside English ones.
_CATEGORY_KW: List[Tuple[str, Tuple[str, ...]]] = [
    ("conflict", ("war", "military", "attack", "bomb", "strike", "airstrike", "missile",
                  "soldier", "troops", "ceasefire", "clashes", "militia", "insurgent",
                  "explosion", "shelling", "offensive", "hostage", "drone",
                  "غارة", "قصف", "هجوم", "صاروخ", "حرب", "اشتباك", "انفجار", "جيش", "عسكري")),
    ("disaster", ("earthquake", "flood", "wildfire", "fire", "drought", "storm", "tsunami",
                  "landslide", "cyclone", "hurricane", "volcanic", "famine",
                  "زلزال", "فيضان", "حريق", "سيول", "جفاف", "إعصار", "مجاعة")),
    ("health",   ("pandemic", "epidemic", "outbreak", "cholera", "virus", "hospital", "who",
                  "disease", "vaccination", "health crisis", "infection", "malnutrition",
                  "وباء", "مستشفى", "تفشي", "مرض", "إصابة", "لقاح", "صحة")),
    ("political", ("election", "protest", "government", "parliament", "coup", "sanctions",
                   "diplomacy", "summit", "referendum", "minister", "president", "talks",
                   "انتخابات", "احتجاج", "حكومة", "برلمان", "عقوبات", "مفاوضات", "وزير", "رئيس")),
    ("economic", ("inflation", "unemployment", "debt", "oil price", "trade", "gdp",
                  "recession", "currency", "economic crisis", "poverty", "budget",
                  "تضخم", "بطالة", "اقتصاد", "ديون", "أسعار", "فقر", "موازنة")),
]

_SEVERITY_KW: List[Tuple[str, Tuple[str, ...]]] = [
    ("critical", ("kill", "killed", "death toll", "massacre", "emergency", "catastrophe",
                  "mass casualty", "genocide", "deadly", "dead", "fatalities",
                  "قتلى", "قتيل", "مقتل", "مجزرة", "شهداء", "وفاة", "كارثة", "طوارئ")),
    ("high",     ("injured", "wounded", "escalation", "crisis", "urgent", "displaced",
                  "refugees", "evacuat", "siege",
                  "جرحى", "مصابين", "إصابات", "تصعيد", "أزمة", "نزوح", "لاجئين", "حصار")),
    ("medium",   ("tensions", "concerns", "damage", "warning", "threat", "dispute",
                  "clash", "unrest",
                  "توتر", "تحذير", "تهديد", "أضرار", "قلق", "نزاع")),
]

# ── In-memory store ──────────────────────────────────────────────────────────
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_lock = threading.RLock()
_signals: Dict[str, "CrisisSignal"] = {}      # id → signal (rolling window, ≤ MAX_ITEMS)
_sources: Dict[str, Dict[str, Any]] = {}       # name → status row
_last_fetch: Optional[datetime] = None
_fetcher_started = False


# ── Model ────────────────────────────────────────────────────────────────────
class CrisisSignal(BaseModel):
    id: str
    title: str
    summary: str
    source: str
    link: str
    published: datetime
    country: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    category: str = "other"
    severity: str = "low"


# ── Helpers ──────────────────────────────────────────────────────────────────
def _now() -> datetime:
    return datetime.now(timezone.utc)


def _strip_html(s: Optional[str]) -> str:
    if not s:
        return ""
    return _WS_RE.sub(" ", html.unescape(_TAG_RE.sub(" ", s))).strip()


def _hash(link: str) -> str:
    return hashlib.sha1(link.encode("utf-8")).hexdigest()[:16]


def _to_datetime(entry: Any) -> datetime:
    """Best-effort published time from a feedparser entry; falls back to now()."""
    for key in ("published_parsed", "updated_parsed"):
        st = getattr(entry, key, None) or (entry.get(key) if isinstance(entry, dict) else None)
        if st:
            try:
                return datetime(*st[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return _now()


def _geolocate(title: str, summary: str) -> Tuple[Optional[str], Optional[float], Optional[float]]:
    """Return (country, lat, lng) from the first place-name found in title→summary."""
    for text in (title or "", summary or ""):
        if not text:
            continue
        low = text.lower()
        for matcher, country, lat, lng in _PLACE_MATCHERS:
            if isinstance(matcher, str):
                if matcher in text:           # Arabic substring (case preserved)
                    return country, lat, lng
            elif matcher.search(low):         # Latin word-boundary match
                return country, lat, lng
    return None, None, None


def _classify(title: str, summary: str) -> Tuple[str, str]:
    """Return (category, severity) from keyword heuristics; first match wins."""
    blob = f"{title} {summary}".lower()
    category = "other"
    for cat, kws in _CATEGORY_KW:
        if any(kw in blob for kw in kws):
            category = cat
            break
    severity = "low"
    for sev, kws in _SEVERITY_KW:
        if any(kw in blob for kw in kws):
            severity = sev
            break
    return category, severity


def _build_signal(source_name: str, entry: Any) -> Optional["CrisisSignal"]:
    title = _strip_html(getattr(entry, "title", "") or "")
    link = (getattr(entry, "link", "") or "").strip()
    if not title or not link:
        return None
    summary = _strip_html(getattr(entry, "summary", "") or getattr(entry, "description", "") or "")
    if len(summary) > 600:
        summary = summary[:600].rstrip() + "…"
    country, lat, lng = _geolocate(title, summary)
    category, severity = _classify(title, summary)
    return CrisisSignal(
        id=_hash(link),
        title=title,
        summary=summary,
        source=source_name,
        link=link,
        published=_to_datetime(entry),
        country=country, lat=lat, lng=lng,
        category=category, severity=severity,
    )


def _fetch_feed(name: str, url: str) -> List["CrisisSignal"]:
    """Fetch + parse one feed. Raises on network/parse failure (caller handles)."""
    if feedparser is None:
        raise RuntimeError("feedparser not installed")
    resp = requests.get(url, headers=_HEADERS, timeout=_REQUEST_TIMEOUT)
    resp.raise_for_status()
    parsed = feedparser.parse(resp.content)
    out: List[CrisisSignal] = []
    for entry in getattr(parsed, "entries", []) or []:
        sig = _build_signal(name, entry)
        if sig is not None:
            out.append(sig)
    return out


# ── Fetch cycle ──────────────────────────────────────────────────────────────
def fetch_once() -> Dict[str, Any]:
    """Run one fetch cycle across all feeds. Never raises."""
    global _last_fetch
    start = time.time()
    new_count = 0
    ok_sources = 0
    collected: List[CrisisSignal] = []

    for name, url in _FEEDS:
        try:
            items = _fetch_feed(name, url)
            collected.extend(items)
            ok_sources += 1
            with _lock:
                _sources[name] = {
                    "name": name, "url": url, "status": "ok",
                    "last_fetch": _now().isoformat(), "item_count": len(items),
                }
        except Exception as e:
            log.warning("RSS feed failed: %s (%s) — %s", name, url, e)
            with _lock:
                prev = _sources.get(name, {})
                _sources[name] = {
                    "name": name, "url": url, "status": "error",
                    "last_fetch": prev.get("last_fetch"), "item_count": 0,
                }

    # If every feed failed, keep the last good data rather than wiping the store.
    if not collected:
        log.warning("RSS fetch cycle produced no items — keeping previous data")
        with _lock:
            _last_fetch = _now()
        return {"new": 0, "sources": ok_sources, "total": len(_signals)}

    with _lock:
        for sig in collected:
            if sig.id not in _signals:
                new_count += 1
            _signals[sig.id] = sig
        # Roll the window: keep the MAX_ITEMS most recent by published time.
        if len(_signals) > MAX_ITEMS:
            keep = sorted(_signals.values(), key=lambda s: s.published, reverse=True)[:MAX_ITEMS]
            _signals.clear()
            _signals.update({s.id: s for s in keep})
        _last_fetch = _now()
        total = len(_signals)

    elapsed_ms = int((time.time() - start) * 1000)
    log.info("RSS fetch complete: %d new signals from %d sources (%dms)",
             new_count, ok_sources, elapsed_ms)
    return {"new": new_count, "sources": ok_sources, "total": total}


def _fetch_loop() -> None:
    while True:
        try:
            fetch_once()
        except Exception as e:  # pragma: no cover - defensive
            log.warning("RSS fetch loop error: %s", e)
        time.sleep(FETCH_INTERVAL_SECONDS)


def start_background_fetcher() -> None:
    """Start the 90s background fetch loop exactly once (idempotent)."""
    global _fetcher_started
    with _lock:
        if _fetcher_started:
            return
        _fetcher_started = True
    threading.Thread(target=_fetch_loop, name="aegis-rss-fetcher", daemon=True).start()
    log.info("RSS background fetcher started (interval=%ds)", FETCH_INTERVAL_SECONDS)


# ── Public read API (consumed by api_rss router) ─────────────────────────────
def get_signals(
    country: Optional[str] = None,
    category: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 100,
) -> Dict[str, Any]:
    limit = max(1, min(MAX_ITEMS, int(limit)))
    with _lock:
        items = list(_signals.values())
        total = len(items)
        last = _last_fetch.isoformat() if _last_fetch else None
        source_count = sum(1 for s in _sources.values() if s.get("status") == "ok")
    if country:
        cl = country.lower()
        items = [s for s in items if (s.country or "").lower() == cl]
    if category:
        items = [s for s in items if s.category == category]
    if severity:
        items = [s for s in items if s.severity == severity]
    items.sort(key=lambda s: s.published, reverse=True)
    items = items[:limit]
    return {
        "signals": [s.model_dump(mode="json") for s in items],
        "last_fetch": last,
        "source_count": source_count,
        "total_count": total,
    }


def get_sources() -> Dict[str, Any]:
    with _lock:
        # Include feeds that haven't reported yet (first cycle still running).
        known = dict(_sources)
    rows = []
    for name, url in _FEEDS:
        row = known.get(name) or {
            "name": name, "url": url, "status": "pending",
            "last_fetch": None, "item_count": 0,
        }
        rows.append(row)
    return {"sources": rows}


def get_stats() -> Dict[str, Any]:
    with _lock:
        items = list(_signals.values())
    by_country: Dict[str, int] = {}
    by_category: Dict[str, int] = {}
    by_severity: Dict[str, int] = {}
    for s in items:
        if s.country:
            by_country[s.country] = by_country.get(s.country, 0) + 1
        by_category[s.category] = by_category.get(s.category, 0) + 1
        by_severity[s.severity] = by_severity.get(s.severity, 0) + 1
    return {
        "total_signals": len(items),
        "by_country": dict(sorted(by_country.items(), key=lambda kv: kv[1], reverse=True)),
        "by_category": by_category,
        "by_severity": by_severity,
    }
