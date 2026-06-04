"""Crossref client — DOI existence + reference graph + license. This is the deterministic
ANTI-FABRICATION gate: a real DOI resolves (200), a fabricated DOI 404s. Polite pool via
mailto. Degrade-safe."""
from __future__ import annotations

import urllib.parse
from typing import Any, Dict, List, Optional

from . import http_json, CONTACT

BASE = "https://api.crossref.org"


def exists_doi(doi: str) -> bool:
    if not doi:
        return False
    d = http_json(f"{BASE}/works/{urllib.parse.quote(doi)}?mailto={CONTACT}")
    return bool(isinstance(d, dict) and d.get("status") == "ok"
                and (d.get("message") or {}).get("DOI"))


def meta(doi: str) -> Optional[Dict[str, Any]]:
    d = http_json(f"{BASE}/works/{urllib.parse.quote(doi)}?mailto={CONTACT}")
    m = (d or {}).get("message") or {}
    if not m:
        return None
    issued = ((m.get("issued") or {}).get("date-parts") or [[None]])[0] or [None]
    return {
        "doi": m.get("DOI"),
        "title": (m.get("title") or [None])[0],
        "year": issued[0],
        "container": (m.get("container-title") or [None])[0],
        "license": [lic.get("URL") for lic in (m.get("license") or []) if lic.get("URL")],
    }
