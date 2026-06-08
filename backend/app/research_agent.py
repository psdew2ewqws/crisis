"""Research agent — OpenAlex discovery + Sci-Hub full-text resolution.

Plan-Execute pipeline over free scholarly + open-data APIs:
    plan -> search (OpenAlex, Jordan-scoped + global) -> dedupe -> RRF rank
         -> verify existence (provenance.verify_source) -> cited evidence.

DETERMINISTIC + urllib-only + DEGRADE-SAFE: any source offline/4xx disables only that
source; if nothing VERIFIES, the agent ABSTAINS ('لا توجد أدلة كافية موثّقة') rather than
fabricating a reference. Runs with Ollama DOWN. Exposed as POST /api/research/run (NDJSON)
and as ``gather()`` for the scenario engine's optional 'evidence' stage.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Iterator, List

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

try:
    from .scholar import openalex, fusion
except Exception:  # pragma: no cover
    openalex = fusion = None  # type: ignore
from . import provenance

try:
    from . import scihub as _scihub
except Exception:  # pragma: no cover
    _scihub = None  # type: ignore

router = APIRouter()
NDJSON = "application/x-ndjson"


class ResearchIn(BaseModel):
    query: str = ""
    jordan: bool = True
    limit: int = 8


def _ev(stage: str, **data: Any) -> bytes:
    return (json.dumps({"stage": stage, **data}, ensure_ascii=False) + "\n").encode("utf-8")


def _evidence_row(it: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "source": it.get("source"),
        "title": it.get("title"),
        "year": it.get("year"),
        "doi": it.get("doi") or None,
        "url": it.get("pdf_url") or it.get("oa_url") or it.get("landing_url") or it.get("id"),
        "oa_status": it.get("oa_status"),
        "license": it.get("license"),
        "cited_by": it.get("cited_by"),
        "snippet": (it.get("abstract") or "")[:500],
        "verified": it.get("verified"),
        "verify_how": it.get("verify_how"),
        "scihub_url": it.get("scihub_url"),     # resolved by scihub.enrich_evidence()
    }


def gather(query: str, *, jordan: bool = True, limit: int = 8) -> Dict[str, Any]:
    """Deterministic search -> dedupe -> RRF -> verify. Returns verified evidence only;
    ``abstained`` True when nothing verifies."""
    q = (query or "").strip()
    if len(q) < 4 or openalex is None:
        return {"evidence": [], "considered": 0, "abstained": True}

    lists: List[List[Dict[str, Any]]] = []
    try:
        if jordan:
            lists.append(openalex.search(q, jordan=True, limit=limit))
        lists.append(openalex.search(q, jordan=False, limit=limit))   # global fallback
    except Exception:
        pass
    lists = [l for l in lists if l]
    merged = fusion.rrf(lists) if (fusion and lists) else [x for l in lists for x in l]
    merged = fusion.dedupe(merged) if fusion else merged

    out: List[Dict[str, Any]] = []
    for it in merged[: max(1, min(int(limit), 20))]:
        ref = it.get("doi") or it.get("oa_url") or it.get("landing_url") or it.get("id") or ""
        v = provenance.verify_source(ref)
        it["verified"] = bool(v.get("verified"))
        it["verify_how"] = v.get("how")
        out.append(_evidence_row(it))
    verified = [e for e in out if e.get("verified")]

    # Sci-Hub enrichment: resolve full-text PDF URLs for closed/bronze papers
    if _scihub is not None and verified:
        verified = _scihub.enrich_evidence(verified)

    return {"evidence": verified, "considered": len(out), "abstained": len(verified) == 0}


def run(body: ResearchIn) -> Iterator[bytes]:
    q = (body.query or "").strip()
    yield _ev("planning", query=q, jordan=body.jordan)
    if len(q) < 4:
        yield _ev("done", abstained=True, reason="empty_query")
        return
    yield _ev("searching", sources=["openalex"])
    res = gather(q, jordan=body.jordan, limit=body.limit)
    yield _ev("ranked", considered=res["considered"])
    if res["abstained"]:
        yield _ev("abstain", message_ar="لا توجد أدلة كافية موثّقة من مصادر مفتوحة لهذا الموضوع.")
    else:
        yield _ev("evidence", items=res["evidence"], count=len(res["evidence"]))
    yield _ev("done", abstained=res["abstained"])


@router.post("/api/research/run")
def research_run(body: ResearchIn) -> StreamingResponse:
    return StreamingResponse(run(body), media_type=NDJSON)
