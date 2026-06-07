"""Live RSS news for Jordan, geolocated to governorates.

Pulls one Google News RSS *search* per governorate (Arabic query), parses it
with the stdlib XML parser, assigns each article to a governorate
(deterministic from the query, refined by an alias keyword second-pass),
de-duplicates across queries, and serves the result from a 5-minute in-memory
TTL cache.

Persistence: after every RSS refresh, articles are upserted into the
``aegis_news`` table (see migrations/create_news_table.py). On startup the
cache is seeded from the DB so the first API call is instant even before the
first RSS refresh completes.

The router in ``main_v2.py`` imports this lazily via ``_opt_import`` and the
``GET /api/news`` endpoint calls :func:`get_news_by_gov`. If this module fails
to import the endpoint degrades gracefully.
"""
from __future__ import annotations

import hashlib
import html
import re
import threading
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional
from urllib.parse import quote
from xml.etree import ElementTree as ET

import requests

# ── Governorates ────────────────────────────────────────────────────────────
# Canonical ids MUST match GOV_ID in the frontend JordanMap.tsx:
# maan / jerash / ajloun (not ma'an / jarash / ajlun).
_GOV_ALIASES: Dict[str, List[str]] = {
    "amman":   ["amman", "عمان"],
    "zarqa":   ["zarqa", "الزرقاء", "الزرقا"],
    "irbid":   ["irbid", "إربد", "اربد"],
    "balqa":   ["balqa", "balqaa", "البلقاء", "السلط"],
    "mafraq":  ["mafraq", "المفرق"],
    "madaba":  ["madaba", "مادبا"],
    "karak":   ["karak", "al karak", "الكرك"],
    "tafilah": ["tafilah", "tafila", "الطفيلة"],
    "maan":    ["maan", "ma'an", "معان"],
    "aqaba":   ["aqaba", "العقبة"],
    "ajloun":  ["ajloun", "ajlun", "عجلون"],
    "jerash":  ["jerash", "jarash", "جرش"],
}
# The Arabic name used to *query* Google News for each governorate.
_GOV_QUERY_AR: Dict[str, str] = {
    "amman": "عمان", "zarqa": "الزرقاء", "irbid": "إربد", "balqa": "البلقاء",
    "mafraq": "المفرق", "madaba": "مادبا", "karak": "الكرك", "tafilah": "الطفيلة",
    "maan": "معان", "aqaba": "العقبة", "ajloun": "عجلون", "jerash": "جرش",
}

_TTL_SECONDS = 300
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}
_ATOM = "{http://www.w3.org/2005/Atom}"
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

_cache: Dict[str, Any] = {"data": None, "ts": 0.0}
_lock = threading.Lock()

# ── DB setup (lazy, import-safe) ─────────────────────────────────────────────
_db_write: Any = None
_db_read: Any = None
_table_ready = False


def _init_db() -> None:
    global _db_write, _db_read, _table_ready
    if _table_ready:
        return
    try:
        from . import db_write as _w
        from . import db as _r
        _db_write = _w
        _db_read = _r
        # Ensure table exists (idempotent).
        from .migrations.create_news_table import ensure_table
        ensure_table()
        _table_ready = True
    except Exception:
        _table_ready = False  # degraded — no DB persistence, in-memory only


# Run DB init at module import time (non-fatal).
try:
    _init_db()
except Exception:
    pass


# ── Helpers ───────────────────────────────────────────────────────────────────
def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _feed_url(gov_id: str) -> str:
    ar = _GOV_QUERY_AR.get(gov_id, gov_id)
    q = quote(ar) + "%20" + quote("الأردن")  # append "Jordan" to suppress foreign towns
    return f"https://news.google.com/rss/search?q={q}&hl=ar&gl=JO&ceid=JO:ar"


def _strip_html(s: Optional[str]) -> str:
    if not s:
        return ""
    return _WS_RE.sub(" ", html.unescape(_TAG_RE.sub(" ", s))).strip()


def _to_iso(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    raw = raw.strip()
    # RFC 822 (RSS pubDate)
    try:
        dt = parsedate_to_datetime(raw)
        if dt is not None:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        pass
    # ISO-8601 (Atom updated/published)
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return None


def _norm(s: str) -> str:
    return _WS_RE.sub(" ", (s or "").lower()).strip()


def _extract_gov(*texts: str) -> Optional[str]:
    """Substring alias match against the article text → canonical gov id."""
    blob = _norm(" ".join(t for t in texts if t))
    for gid, aliases in _GOV_ALIASES.items():
        for a in aliases:
            if a and a.lower() in blob:
                return gid
    return None


def _parse_feed(xml_bytes: bytes) -> List[Dict[str, Any]]:
    """Parse an RSS 2.0 or Atom feed into raw item dicts."""
    out: List[Dict[str, Any]] = []
    try:
        root = ET.fromstring(xml_bytes)
    except Exception:
        return out

    items = root.findall(".//item")
    if items:  # RSS 2.0
        for it in items:
            title = (it.findtext("title") or "").strip()
            link = (it.findtext("link") or "").strip()
            desc = _strip_html(it.findtext("description"))
            pub = _to_iso(it.findtext("pubDate"))
            src_el = it.find("source")
            source = (src_el.text.strip() if src_el is not None and src_el.text else "")
            if title and link:
                out.append({"title": title, "link": link, "summary": desc,
                            "published": pub, "source": source})
        return out

    # Atom fallback
    for en in root.findall(f".//{_ATOM}entry"):
        title = (en.findtext(f"{_ATOM}title") or "").strip()
        link = ""
        link_el = en.find(f"{_ATOM}link")
        if link_el is not None:
            link = (link_el.get("href") or "").strip()
        summary = _strip_html(en.findtext(f"{_ATOM}summary")
                              or en.findtext(f"{_ATOM}content"))
        pub = _to_iso(en.findtext(f"{_ATOM}updated")
                      or en.findtext(f"{_ATOM}published"))
        src_el = en.find(f"{_ATOM}source")
        source = ""
        if src_el is not None:
            source = (src_el.findtext(f"{_ATOM}title") or "").strip()
        if title and link:
            out.append({"title": title, "link": link, "summary": summary,
                        "published": pub, "source": source})
    return out


# ── Database persistence ──────────────────────────────────────────────────────
_UPSERT_SQL = """
INSERT INTO aegis_news (id, title, summary, source, link, published, gov, fetched_at)
VALUES (%s, %s, %s, %s, %s, %s::timestamptz, %s, now())
ON CONFLICT (id) DO UPDATE SET
    title      = EXCLUDED.title,
    summary    = EXCLUDED.summary,
    source     = EXCLUDED.source,
    gov        = EXCLUDED.gov,
    fetched_at = now()
"""

_SEED_SQL = """
SELECT id, title, summary, source, link,
       to_char(published AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS published,
       gov
FROM aegis_news
ORDER BY published DESC NULLS LAST
LIMIT 2000
"""


def _persist(items_flat: List[Dict[str, Any]]) -> None:
    """Upsert a batch of items into aegis_news."""
    if not _table_ready or _db_write is None or not items_flat:
        return
    try:
        with _db_write.get_conn() as conn:
            with conn.cursor() as cur:
                for item in items_flat:
                    cur.execute(_UPSERT_SQL, (
                        item["id"],
                        item["title"][:500],
                        item["summary"][:500],
                        item["source"][:200],
                        item["link"][:1000],
                        item.get("published"),
                        item.get("gov"),
                    ))
            conn.commit()
    except Exception:
        pass  # persistence failure must never break the API response


def _seed_from_db() -> Optional[Dict[str, Any]]:
    """Build a payload from the DB to seed the in-memory cache on startup."""
    if not _table_ready or _db_read is None:
        return None
    try:
        rows = _db_read.fetchall(_SEED_SQL)
        if not rows:
            return None
        by_gov: Dict[str, List[Dict[str, Any]]] = {}
        national: List[Dict[str, Any]] = []
        for r in rows:
            item = {
                "id":        r["id"],
                "title":     r["title"],
                "summary":   r["summary"],
                "source":    r["source"],
                "link":      r["link"],
                "published": r["published"],
                "gov":       r["gov"],
            }
            if r["gov"]:
                by_gov.setdefault(r["gov"], []).append(item)
            else:
                national.append(item)
        total = sum(len(v) for v in by_gov.values()) + len(national)
        return {
            "generated_at": _now_iso(),
            "ttl_seconds":  _TTL_SECONDS,
            "total":        total,
            "by_gov":       by_gov,
            "national":     national,
            "source":       "google_news_rss",
            "seeded_from":  "db",
        }
    except Exception:
        return None


# ── RSS refresh ───────────────────────────────────────────────────────────────
def _refresh() -> Dict[str, Any]:
    """Fetch all 12 governorate feeds, geolocate, dedup, persist, and group."""
    seen_keys: set = set()
    by_gov: Dict[str, List[Dict[str, Any]]] = {}
    national: List[Dict[str, Any]] = []
    errors: List[str] = []
    all_items: List[Dict[str, Any]] = []

    for gid in _GOV_ALIASES:
        try:
            r = requests.get(_feed_url(gid), headers=_HEADERS, timeout=15)
            if r.status_code != 200:
                errors.append(f"{gid}:{r.status_code}")
                continue
            raw_items = _parse_feed(r.content)
        except Exception as e:
            errors.append(f"{gid}:{type(e).__name__}")
            continue

        for raw in raw_items:
            title, link = raw["title"], raw["link"]
            source = raw.get("source") or ""
            clean_title = title
            if " - " in title:
                head, _, tail = title.rpartition(" - ")
                if head and tail:
                    clean_title = head.strip()
                    if not source:
                        source = tail.strip()

            tkey = _norm(clean_title)
            lkey = link.strip()
            if tkey in seen_keys or lkey in seen_keys:
                continue
            seen_keys.add(tkey)
            seen_keys.add(lkey)

            detected = _extract_gov(clean_title, raw.get("summary", ""))
            gov = detected or gid

            summary = (raw.get("summary") or "")[:280]
            item = {
                "id":        hashlib.sha1(link.encode("utf-8")).hexdigest()[:12],
                "title":     clean_title,
                "summary":   summary,
                "source":    source or "Google News",
                "link":      link,
                "published": raw.get("published"),
                "gov":       gov,
            }
            by_gov.setdefault(gov, []).append(item)
            all_items.append(item)

    # Sort each bucket newest-first (nulls last).
    for items in by_gov.values():
        items.sort(key=lambda x: x["published"] or "", reverse=True)

    total = sum(len(v) for v in by_gov.values()) + len(national)
    payload: Dict[str, Any] = {
        "generated_at": _now_iso(),
        "ttl_seconds":  _TTL_SECONDS,
        "total":        total,
        "by_gov":       by_gov,
        "national":     national,
        "source":       "google_news_rss",
    }
    if errors and total == 0:
        payload["source"] = "fallback"
        payload["error"] = "; ".join(errors[:6])

    # Persist to DB in the background so the caller gets the response immediately.
    if all_items:
        t = threading.Thread(target=_persist, args=(all_items,), daemon=True)
        t.start()

    return payload


# ── Public API ────────────────────────────────────────────────────────────────
def get_news_by_gov(force: bool = False) -> Dict[str, Any]:
    """Return governorate-grouped news, served from a 5-minute TTL cache.

    On the very first call the cache is seeded from the DB (instant response)
    while a background RSS refresh is not yet due. Subsequent calls within the
    TTL window return the cached copy. After TTL expiry the next call triggers
    a fresh RSS fetch and DB upsert.
    """
    now = time.time()
    with _lock:
        # Seed cache from DB on very first call if empty.
        if _cache["data"] is None:
            seeded = _seed_from_db()
            if seeded:
                _cache["data"] = seeded
                _cache["ts"] = now  # treat DB seed as a fresh load

        fresh = (
            _cache["data"] is not None
            and (now - _cache["ts"]) < _TTL_SECONDS
        )
        if fresh and not force:
            return _cache["data"]

        data = _refresh()
        # Keep last good payload on total fetch failure.
        if data.get("total", 0) == 0 and _cache["data"] is not None:
            return _cache["data"]
        _cache["data"] = data
        _cache["ts"] = now
        return data
