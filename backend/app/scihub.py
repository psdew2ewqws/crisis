"""Sci-Hub integration — resolves DOIs to direct PDF download URLs.

For papers that are not freely available through OpenAlex's open-access routes,
this module queries live Sci-Hub mirrors to obtain the direct PDF link.
It is used by research_agent.gather() as a fallback: OpenAlex finds the paper
metadata; Sci-Hub provides the full-text PDF URL when no legal OA link exists.

Design:
  • Tries mirrors in order, stops at first success.
  • Extracts the /storage/.../*.pdf path pattern Sci-Hub embeds in its HTML.
  • Returns the full URL (mirror + path) so callers can present it directly.
  • Never downloads or stores the PDF — only the URL is resolved.
  • Degrades gracefully: returns None on any failure, never raises.
  • In-memory TTL cache (1 hour per DOI) to avoid hammering mirrors on repeat calls.
"""
from __future__ import annotations

import re
import time
import threading
from typing import Any, Dict, Optional

import requests
from bs4 import BeautifulSoup

# ── Live mirrors (ordered by reliability) ────────────────────────────────────
MIRRORS = [
    "https://sci-hub.ru",
    "https://sci-hub.st",
    "https://sci-hub.shop",
    "https://sci-hub.mksa.top",
]

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

_PDF_RE = re.compile(
    r"['\"](\S+\.pdf(?:#[^'\"]*)?)['\"]",
    re.IGNORECASE,
)

_CACHE: Dict[str, Dict[str, Any]] = {}   # doi -> {url, ts}
_CACHE_TTL = 3600                         # 1 hour
_LOCK = threading.Lock()


def _extract_pdf_path(html: str) -> Optional[str]:
    """Extract the /storage/.../*.pdf path from a Sci-Hub page."""
    soup = BeautifulSoup(html, "html.parser")

    # 1) Direct <a href="...pdf"> link
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if ".pdf" in href.lower():
            return href

    # 2) Regex over the raw HTML (handles inline JS / data-attributes)
    for m in _PDF_RE.finditer(html):
        candidate = m.group(1)
        # must look like a path or URL, not a CSS class
        if "/" in candidate and len(candidate) > 10:
            return candidate

    return None


def resolve(doi: str, timeout: float = 15.0) -> Optional[str]:
    """Resolve a DOI to a direct PDF URL via Sci-Hub.

    Returns a full https:// URL, or None if the paper is not found or all
    mirrors fail. Result is cached for 1 hour.
    """
    doi = (doi or "").strip()
    if not doi:
        return None

    # Cache hit?
    with _LOCK:
        cached = _CACHE.get(doi)
        if cached and (time.time() - cached["ts"]) < _CACHE_TTL:
            return cached.get("url")

    result: Optional[str] = None
    for mirror in MIRRORS:
        try:
            resp = requests.get(
                f"{mirror}/{doi}",
                headers=_HEADERS,
                timeout=timeout,
                allow_redirects=True,
            )
            if resp.status_code != 200:
                continue
            # "المقال غير موجود" = article not found
            if "غير موجود" in resp.text or "not found" in resp.text.lower():
                continue

            path = _extract_pdf_path(resp.text)
            if not path:
                continue

            # Build the full URL
            if path.startswith("http"):
                result = path
            elif path.startswith("//"):
                result = "https:" + path
            else:
                result = mirror + "/" + path.lstrip("/")

            # Strip trailing fragment for the clean URL
            result = result.split("#")[0] if "#" in result else result
            break

        except requests.exceptions.Timeout:
            continue
        except Exception:
            continue

    # Cache the outcome (even None, so we don't retry for an hour)
    with _LOCK:
        _CACHE[doi] = {"url": result, "ts": time.time()}

    return result


def enrich_evidence(items: list) -> list:
    """Add a `scihub_url` field to evidence items that lack an open-access PDF.

    Only calls Sci-Hub for items that:
      • have a DOI
      • are NOT already gold/diamond/green open-access (those have free PDFs)
    Returns the same list with `scihub_url` populated where found.
    """
    closed = {"bronze", "closed", "hybrid", None}
    enriched = []
    for item in items:
        doi = item.get("doi")
        oa_status = item.get("oa_status")
        # Already free — skip to save mirror bandwidth
        if oa_status not in closed:
            enriched.append({**item, "scihub_url": None})
            continue
        if not doi:
            enriched.append({**item, "scihub_url": None})
            continue
        url = resolve(doi)
        enriched.append({**item, "scihub_url": url})
    return enriched


def check_mirrors() -> dict:
    """Probe all mirrors and return their status (for diagnostics)."""
    results = {}
    for mirror in MIRRORS:
        try:
            resp = requests.get(mirror, headers=_HEADERS, timeout=10)
            results[mirror] = {"status": resp.status_code, "ok": resp.status_code == 200}
        except Exception as e:
            results[mirror] = {"status": None, "ok": False, "error": str(e)[:60]}
    return results
