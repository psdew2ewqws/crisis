"""provenance.verify_source(ref) — the single highest-value anti-fabrication primitive.

Returns verified=True ONLY when a reference actually EXISTS:
  • an internal id (cluster:/case:/run:/scenario:) — a real row we authored, OR
  • a DOI that resolves via Crossref (then OpenAlex) — a fabricated DOI 404s, a real one 200s, OR
  • a URL on a trusted legal-API host we already query.

Pure-Python urllib, short cache, degrade-safe — runs with Ollama DOWN. Every solution
claim/citation should pass through this before it is shown as grounded; on failure it is
badged 'unverified' (never silently shown as a source)."""
from __future__ import annotations

import re
import time
from typing import Any, Dict

try:
    from .scholar import crossref, openalex
except Exception:  # pragma: no cover
    crossref = openalex = None  # type: ignore

_CACHE: Dict[str, tuple] = {}
_TTL = 3600.0
_DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\"'<>]+")
_TRUSTED = re.compile(
    r"(worldbank\.org|api\.openalex\.org|openalex\.org|reliefweb\.int|api\.crossref\.org|"
    r"crossref\.org|unpaywall\.org|ebi\.ac\.uk|fao\.org|who\.int|unicef\.org|ipcc\.ch|"
    r"greenclimate\.fund|mwi\.gov\.jo)"
)


def _doi(ref: str) -> str:
    m = _DOI_RE.search(ref or "")
    return m.group(0).rstrip(".,);]") if m else ""


def verify_source(ref: str) -> Dict[str, Any]:
    ref = (ref or "").strip()
    if not ref:
        return {"verified": False, "how": "empty"}
    now = time.time()
    cached = _CACHE.get(ref)
    if cached and now - cached[0] < _TTL:
        return cached[1]

    res: Dict[str, Any]
    if ref.startswith(("cluster:", "case:", "run:", "scenario:")):
        res = {"verified": True, "how": "internal"}
    else:
        doi = _doi(ref)
        if doi:
            if crossref and crossref.exists_doi(doi):
                res = {"verified": True, "how": "crossref", "doi": doi}
            elif openalex and openalex.exists_doi(doi):
                res = {"verified": True, "how": "openalex", "doi": doi}
            else:
                res = {"verified": False, "how": "doi_not_found", "doi": doi}
        elif ref.startswith("http") and _TRUSTED.search(ref):
            res = {"verified": True, "how": "trusted_host"}
        else:
            res = {"verified": False, "how": "unresolved"}

    _CACHE[ref] = (now, res)
    return res
