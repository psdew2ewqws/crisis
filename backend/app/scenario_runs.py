"""Scenario run-history — every simulation iteration is recorded, for two roles:

  • RECALL (this module): a clean JSON history of past runs, surfaced at the top of a
    new run ("سبق أن حاكيت موقفًا مشابهًا" + how it turned out).
  • LEARN (driven from scenario.py): each run is ALSO fed back into the lessons RAG as a
    LOW-WEIGHT provisional precedent (confidence ~0.2, risk_source='run', deterministic
    id 'run:<hash>') so retrieval improves over time. Low confidence keeps provisional
    runs ranked BELOW validated lessons, and the 'run:' prefix keeps them prunable.

The history file lives in the gitignored data dir and is capped so it can't grow without
bound; re-running the same scenario overwrites its record (deterministic id).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_RUNS_JSON = os.path.join(_DATA_DIR, "scenario_runs.json")
_MAX_RUNS = 500


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run_id(text: str, service: str = "", location: str = "") -> str:
    """Deterministic id so re-running the same scenario overwrites its record."""
    key = f"{(text or '').strip().lower()}|{service or ''}|{location or ''}"
    return "run:" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def _load() -> List[Dict[str, Any]]:
    try:
        with open(_RUNS_JSON, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save(rows: List[Dict[str, Any]]) -> None:
    os.makedirs(_DATA_DIR, exist_ok=True)
    with open(_RUNS_JSON, "w", encoding="utf-8") as fh:
        json.dump(rows[:_MAX_RUNS], fh, ensure_ascii=False, indent=1)


def _tokens(text: str) -> set:
    return {t for t in re.split(r"\W+", (text or "").lower()) if len(t) > 2}


def save_run(*, text: str, domain: str, service: str, location: str,
             verdict: Dict[str, Any], sim: Dict[str, Any]) -> Dict[str, Any]:
    """Append (or overwrite) this run in the history. Returns the stored record."""
    rid = run_id(text, service, location)
    det = (verdict or {}).get("detection") or {}
    pred = (verdict or {}).get("prediction") or {}
    conf = (verdict or {}).get("confidence") or {}
    rec = {
        "id": rid,
        "ts": _now_iso(),
        "text": (text or "").strip()[:400],
        "domain": domain,
        "service": service or None,
        "location": location or None,
        "severity": det.get("severity"),
        "severity_ar": det.get("severity_ar"),
        "escalating": bool(det.get("escalating")),
        "likely_outcome_ar": pred.get("likely_outcome_ar"),
        "confidence_band_ar": conf.get("band_ar"),
        "risk_before": (sim or {}).get("risk_before"),
        "risk_after": (sim or {}).get("risk_after"),
    }
    rows = [r for r in _load() if r.get("id") != rid]
    rows.insert(0, rec)
    _save(rows)
    return rec


def recall_similar(text: str, domain: str = "", limit: int = 3) -> List[Dict[str, Any]]:
    """Past runs most similar to this scenario (same domain and/or keyword overlap),
    newest-first on ties. Excludes nothing destructively — purely advisory."""
    rows = _load()
    if not rows:
        return []
    qt = _tokens(text)
    scored: List[tuple] = []
    for r in rows:
        overlap = len(qt & _tokens(r.get("text", ""))) if qt else 0
        dom = 1 if (domain and r.get("domain") == domain) else 0
        score = overlap + 0.5 * dom
        if score > 0:
            scored.append((score, r))
    scored.sort(key=lambda x: -x[0])
    return [r for _, r in scored[:limit]]


def stats() -> Dict[str, Any]:
    rows = _load()
    return {"total_runs": len(rows)}
