"""saved_solutions.py — persist a deliberated crisis SOLUTION (the agents' argument +
the final report) so the operator can re-open and DOWNLOAD it later.

A "solution" = the scenario text + the live swarm transcript (each persona's argument,
the convergence votes) + the synthesized report (sections, key figures, references).
Stored as JSON in the gitignored data dir (pattern: scenario_runs.py); also rendered to
Markdown on demand for a one-click download.

Endpoints:
    POST /api/scenario/solution/save        {scenario, transcript[], tallies[], report, meta}
    GET  /api/scenario/solutions            list (lightweight)
    GET  /api/scenario/solution/{sid}        full record
    GET  /api/scenario/solution/{sid}.md     downloadable Markdown (argument + report)
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Path
from fastapi.responses import PlainTextResponse

router = APIRouter(tags=["solutions"])

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_JSON = os.path.join(_DATA_DIR, "saved_solutions.json")
_MAX = 200


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load() -> List[Dict[str, Any]]:
    try:
        with open(_JSON, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_all(rows: List[Dict[str, Any]]) -> None:
    os.makedirs(_DATA_DIR, exist_ok=True)
    with open(_JSON, "w", encoding="utf-8") as fh:
        json.dump(rows[:_MAX], fh, ensure_ascii=False, indent=1)


def save(payload: Dict[str, Any]) -> Dict[str, Any]:
    scenario = str(payload.get("scenario") or "").strip()
    ts = _now_iso()
    sid = "sol:" + hashlib.sha256(f"{scenario}|{ts}".encode("utf-8")).hexdigest()[:16]
    transcript = payload.get("transcript") or []
    report = payload.get("report") or {}
    title = ((report.get("meta") or {}).get("title_ar")) or "تقرير حلّ — مداولة الوكلاء"
    rec = {
        "id": sid,
        "ts": ts,
        "scenario": scenario[:600],
        "title_ar": title,
        "deliberated": bool((payload.get("meta") or {}).get("deliberated") or transcript),
        "n_turns": len(transcript),
        "transcript": transcript,
        "tallies": payload.get("tallies") or [],
        "report": report,
        "meta": payload.get("meta") or {},
    }
    rows = _load()
    rows.insert(0, rec)
    _save_all(rows)
    return {"ok": True, "id": sid, "message_ar": "حُفِظ الحلّ. يمكنك تنزيله متى شئت."}


def get(sid: str) -> Optional[Dict[str, Any]]:
    return next((r for r in _load() if r.get("id") == sid), None)


def list_light() -> List[Dict[str, Any]]:
    return [{"id": r.get("id"), "ts": r.get("ts"), "scenario": r.get("scenario"),
             "title_ar": r.get("title_ar"), "deliberated": r.get("deliberated"),
             "n_turns": r.get("n_turns")} for r in _load()]


_PHASE_AR = {"analysis": "تحليل", "negotiation": "تفاوض", "vote": "تصويت"}


def to_markdown(sol: Dict[str, Any]) -> str:
    out: List[str] = []
    out.append(f"# {sol.get('title_ar') or 'تقرير حلّ — AEGIS'}")
    out.append("")
    out.append(f"**السيناريو:** {sol.get('scenario','')}")
    out.append(f"**التاريخ:** {sol.get('ts','')}")
    out.append("")
    transcript = sol.get("transcript") or []
    if transcript:
        out.append("## مداولة الوكلاء (المحضر)")
        out.append("")
        for t in transcript:
            phase = _PHASE_AR.get(str(t.get("phase") or ""), str(t.get("phase") or ""))
            rnd = t.get("round")
            head = f"### {t.get('persona','')} — {phase}" + (f" · جولة {rnd}" if rnd else "")
            out.append(head)
            out.append(str(t.get("text") or "").strip())
            out.append("")
        for v in (sol.get("tallies") or []):
            conv = "توافق ✓" if v.get("converged") else "لم يكتمل التوافق"
            out.append(f"> تصويت جولة {v.get('round')}: {v.get('ready')}/{v.get('total')} جاهز — {conv}")
        out.append("")
    report = sol.get("report") or {}
    kf = report.get("key_figures") or []
    if kf:
        out.append("## الأرقام الرئيسية")
        out.append("")
        for r in kf:
            out.append(f"- **{r.get('label','')}:** {r.get('value','')}"
                       + (f"  _( {r.get('source')} )_" if r.get("source") else ""))
        out.append("")
    for sec in (report.get("sections") or []):
        out.append(f"## {sec.get('title_ar') or sec.get('title_en') or ''}")
        out.append("")
        for p in (sec.get("paragraphs") or []):
            out.append(str(p).strip())
            out.append("")
    refs = report.get("references") or {}
    peer = refs.get("peer_reviewed") or []
    inst = refs.get("institutional") or []
    if peer or inst:
        out.append("## المراجع")
        out.append("")
        for e in peer:
            doi = f" https://doi.org/{e.get('doi')}" if e.get("doi") else ""
            out.append(f"- {e.get('title','')}" + (f" ({e.get('year')})" if e.get("year") else "") + doi)
        for r in inst:
            out.append(f"- {r.get('name','')}" + (f" — {r.get('url')}" if r.get("url") else ""))
        out.append("")
    out.append("---")
    out.append("AEGIS Crisis Console · لدعم القرار فقط — لا توقّع للواقع.")
    return "\n".join(out)


@router.post("/api/scenario/solution/save")
def solution_save(body: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    if not str(body.get("scenario") or "").strip():
        return {"ok": False, "error": "no_scenario", "message_ar": "لا يوجد سيناريو لحفظه."}
    return save(body)


@router.get("/api/scenario/solutions")
def solutions_list() -> Dict[str, Any]:
    return {"solutions": list_light()}


@router.get("/api/scenario/solution/{sid}.md")
def solution_markdown(sid: str = Path(...)) -> PlainTextResponse:
    sol = get(sid)
    if not sol:
        return PlainTextResponse("الحلّ غير موجود.", status_code=404)
    fname = f"AEGIS-Solution-{sid.replace('sol:', '')}.md"
    return PlainTextResponse(
        to_markdown(sol), media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'})


@router.get("/api/scenario/solution/{sid}")
def solution_get(sid: str = Path(...)) -> Dict[str, Any]:
    sol = get(sid)
    return sol or {"ok": False, "error": "not_found"}
