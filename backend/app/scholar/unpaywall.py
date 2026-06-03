"""Unpaywall client — legal open-access resolver for a DOI. Gate downstream on an
explicit CC license; treat 'bronze' (free-to-read != reusable) as link-only. Degrade-safe."""
from __future__ import annotations

import urllib.parse
from typing import Any, Dict, Optional

from . import http_json, CONTACT

BASE = "https://api.unpaywall.org/v2"


def best_oa(doi: str) -> Optional[Dict[str, Any]]:
    if not doi:
        return None
    d = http_json(f"{BASE}/{urllib.parse.quote(doi)}?email={CONTACT}")
    if not isinstance(d, dict):
        return None
    loc = d.get("best_oa_location") or {}
    return {
        "is_oa": bool(d.get("is_oa")),
        "oa_status": d.get("oa_status"),
        "pdf_url": loc.get("url_for_pdf"),
        "url": loc.get("url"),
        "license": loc.get("license"),
        "reusable": (d.get("oa_status") in ("gold", "hybrid")) and bool(loc.get("license")),
    }
