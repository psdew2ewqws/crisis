"""deliberation_jobs.py — run the agent-swarm deliberation as a BACKGROUND job.

Unlike the request-bound NDJSON stream (report_swarm.deliberate), a job runs in a daemon
thread server-side, so it KEEPS RUNNING even if the operator closes the report modal,
navigates away, or the browser disconnects. Progress (each agent turn, the convergence
votes, the iteration/round count) accumulates live and is pollable; on completion the full
solution (argument transcript + report) is persisted to the saved-solutions HISTORY.

Endpoints:
    POST /api/scenario/deliberate/start            {scenario payload} -> {job_id}
    GET  /api/scenario/deliberate/status/{jid}?since=N  incremental snapshot (events from N)
    GET  /api/scenario/deliberate/active           running/recent jobs (to re-attach the UI)
"""
from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Body, Path, Query

try:
    from . import report_swarm
except Exception:  # pragma: no cover
    report_swarm = None  # type: ignore
try:
    from . import saved_solutions
except Exception:  # pragma: no cover
    saved_solutions = None  # type: ignore

router = APIRouter(tags=["deliberation"])

_JOBS: Dict[str, Dict[str, Any]] = {}
_LOCK = threading.Lock()
_MAX_JOBS = 40  # keep memory bounded; oldest finished jobs are evicted


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _job_id(scenario: str, ts: str) -> str:
    return "job:" + hashlib.sha256(f"{scenario}|{ts}".encode("utf-8")).hexdigest()[:16]


def _run(job_id: str, payload: Dict[str, Any]) -> None:
    job = _JOBS[job_id]
    try:
        for raw in report_swarm.deliberate(payload):
            try:
                ev = json.loads(raw.decode("utf-8"))
            except Exception:
                continue
            stage = ev.get("stage")
            with _LOCK:
                if stage == "agent":
                    job["events"].append(ev)
                    job["turns"] += 1
                    if ev.get("round"):
                        job["iteration"] = max(job["iteration"], int(ev["round"]))
                elif stage == "tally":
                    job["events"].append(ev)
                    job["tallies"].append(ev)
                    job["iteration"] = max(job["iteration"], int(ev.get("round") or 0))
                elif stage == "report":
                    job["report"] = {
                        "ok": True, "sections": ev.get("sections"),
                        "key_figures": ev.get("key_figures"), "references": ev.get("references"),
                        "deliberated": ev.get("deliberated"),
                    }
                    job["events"].append({"stage": "report", "deliberated": ev.get("deliberated")})
                elif stage in ("preflight", "fallback", "synthesis", "section", "done"):
                    job["events"].append(ev)
                job["updated"] = _now_iso()
        with _LOCK:
            job["status"] = "done"
            job["updated"] = _now_iso()
    except Exception as e:  # surface, don't crash the thread silently
        with _LOCK:
            job["status"] = "error"
            job["error"] = str(e)
    # Persist the finished solution to the history (downloadable later).
    if saved_solutions is not None and job.get("report"):
        try:
            sol = saved_solutions.save({
                "scenario": job["scenario"],
                "transcript": [e for e in job["events"] if e.get("stage") == "agent"],
                "tallies": job["tallies"],
                "report": job["report"],
                "meta": {"deliberated": True, "iterations": job["iteration"], "job_id": job_id},
            })
            with _LOCK:
                job["saved"] = True
                job["solution_id"] = sol.get("id")
        except Exception:
            pass


def start(payload: Dict[str, Any]) -> str:
    scenario = str(payload.get("text") or payload.get("scenario") or "").strip()
    ts = _now_iso()
    jid = _job_id(scenario, ts)
    with _LOCK:
        _JOBS[jid] = {
            "id": jid, "status": "running", "scenario": scenario,
            "events": [], "turns": 0, "tallies": [], "iteration": 0,
            "report": None, "started": ts, "updated": ts, "saved": False,
        }
        if len(_JOBS) > _MAX_JOBS:
            finished = sorted((j for j in _JOBS.values() if j["status"] != "running"),
                              key=lambda j: j["started"])
            for j in finished[: len(_JOBS) - _MAX_JOBS]:
                _JOBS.pop(j["id"], None)
    threading.Thread(target=_run, args=(jid, payload), daemon=True).start()
    return jid


@router.post("/api/scenario/deliberate/start")
def deliberate_start(body: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
    if report_swarm is None:
        return {"ok": False, "error": "unavailable"}
    return {"ok": True, "job_id": start(body)}


@router.get("/api/scenario/deliberate/status/{jid}")
def deliberate_status(jid: str = Path(...), since: int = Query(0, ge=0)) -> Dict[str, Any]:
    with _LOCK:
        job = _JOBS.get(jid)
        if not job:
            return {"ok": False, "error": "not_found"}
        return {
            "ok": True, "status": job["status"], "iteration": job["iteration"],
            "turns": job["turns"], "events": job["events"][since:], "total_events": len(job["events"]),
            "report": job["report"], "scenario": job["scenario"],
            "saved": job.get("saved", False), "solution_id": job.get("solution_id"),
            "error": job.get("error"),
        }


@router.get("/api/scenario/deliberate/active")
def deliberate_active() -> Dict[str, Any]:
    with _LOCK:
        jobs = sorted(_JOBS.values(), key=lambda x: x["started"], reverse=True)[:20]
        return {"jobs": [{"job_id": j["id"], "scenario": j["scenario"], "status": j["status"],
                          "iteration": j["iteration"], "turns": j["turns"], "started": j["started"],
                          "solution_id": j.get("solution_id")} for j in jobs]}
