"""OpenAlex client — primary scholarly retriever. CC0 *metadata* (per-work content
license is read separately and gated downstream). No key needed to start; a free
OPENALEX_API_KEY raises the daily cap. Degrade-safe via scholar.http_json."""
from __future__ import annotations

import os
import urllib.parse
from typing import Any, Dict, List

from . import http_json, CONTACT

BASE = "https://api.openalex.org"
KEY = os.environ.get("OPENALEX_API_KEY", "")
_SELECT = "id,doi,title,publication_year,cited_by_count,open_access,abstract_inverted_index,primary_location"


def _abstract(inv: Any) -> str:
    """Reconstruct plain text from OpenAlex's abstract_inverted_index ({word:[pos]})."""
    if not isinstance(inv, dict):
        return ""
    pos: Dict[int, str] = {}
    for word, idxs in inv.items():
        for i in idxs:
            pos[i] = word
    return " ".join(pos[i] for i in sorted(pos))[:1200]


def _clean_doi(doi: Any) -> str:
    return (doi or "").replace("https://doi.org/", "").strip() if isinstance(doi, str) else ""


def _params(extra: dict) -> str:
    p = {"mailto": CONTACT, **extra}
    if KEY:
        p["api_key"] = KEY
    return urllib.parse.urlencode(p)


def search(query: str, *, jordan: bool = False, oa_only: bool = True,
           since: str = "2018-01-01", limit: int = 10) -> List[Dict[str, Any]]:
    filters = []
    if oa_only:
        filters.append("is_oa:true")
    if since:
        filters.append(f"from_publication_date:{since}")
    if jordan:
        filters.append("authorships.countries:JO")
    extra = {"search": query, "per_page": max(1, min(int(limit), 25)), "select": _SELECT}
    if filters:
        extra["filter"] = ",".join(filters)
    data = http_json(f"{BASE}/works?{_params(extra)}")
    out: List[Dict[str, Any]] = []
    for w in (data or {}).get("results", []):
        oa = w.get("open_access") or {}
        loc = w.get("primary_location") or {}
        out.append({
            "source": "openalex",
            "id": w.get("id"),
            "doi": _clean_doi(w.get("doi")),
            "title": w.get("title"),
            "year": w.get("publication_year"),
            "cited_by": w.get("cited_by_count") or 0,
            "is_oa": bool(oa.get("is_oa")),
            "oa_status": oa.get("oa_status"),
            "oa_url": oa.get("oa_url"),
            "pdf_url": loc.get("pdf_url"),
            "landing_url": loc.get("landing_page_url"),
            "license": loc.get("license"),
            "abstract": _abstract(w.get("abstract_inverted_index")),
        })
    return out


def year_counts(query: str, *, jordan: bool = True) -> List[Dict[str, Any]]:
    """Publication-year histogram (for a REAL, computed-live research-attention chart —
    never a fabricated series)."""
    extra = {"search": query, "group_by": "publication_year"}
    if jordan:
        extra["filter"] = "authorships.countries:JO"
    data = http_json(f"{BASE}/works?{_params(extra)}")
    rows = [{"year": g.get("key"), "count": g.get("count")} for g in (data or {}).get("group_by", [])]
    return sorted((r for r in rows if r.get("year")), key=lambda r: str(r["year"]))


def exists_doi(doi: str) -> bool:
    if not doi:
        return False
    d = http_json(f"{BASE}/works/https://doi.org/{urllib.parse.quote(doi)}?{_params({})}")
    return bool(isinstance(d, dict) and d.get("id"))
