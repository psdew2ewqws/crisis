"""AEGIS Deer Graph — in-memory decision log (Track 2 "Decisions" console page).

A thread-safe-ish, process-local audit trail of operator decisions made on top
of the voc360 root-cause clusters: "we authorized countermeasure X against
root-cause cluster Y". This is deliberately ephemeral (no DB writes — voc360 is
READ-ONLY) and resets on process restart; it exists so the Decisions page and
the /api/decisions routes have something real to read and append to.

Public surface (mirrors the existing module style — plain JSON-serializable,
Arabic-safe dicts; callers dump with ensure_ascii=False):
  - list_decisions()              -> list[dict]   newest-first snapshot
  - create_decision(payload)      -> dict          the created record
  - get_decision(decision_id)     -> dict | None
  - update_status(decision_id, s) -> dict | None
  - clear_decisions()             -> int           (test/util) rows removed
  - stats()                       -> dict          counts by status

A decision record:
  {
    "id":            "dec_00001",          # stable, monotonic
    "ts":            "2026-06-01T10:30:00Z",
    "cluster_id":    "b39d06f6-...",       # ril_problem_clusters.cluster_id
    "label":         "رسوم الخدمة المستعجلة",  # optional human label (ar/en)
    "action":        "Route to owning agency and cap urgent-service fees",
    "authorized_by": "Operations Lead",
    "status":        "proposed",           # proposed|authorized|in_progress|done|rejected
    "rationale":     "...",                # optional free text
    "expected_impact": "...",              # optional
  }

Import-safety: pure stdlib, no optional deps, no DB calls at import time — so
`from . import decisions` never fails and a missing voc360 connection cannot
break the Decisions page.
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# --------------------------------------------------------------------------- #
# Module state. A single lock guards the append-only list + id counter so the  #
# FastAPI threadpool can't interleave two create_decision() calls.            #
# --------------------------------------------------------------------------- #

_LOCK = threading.RLock()
_DECISIONS: List[Dict[str, Any]] = []
_SEQ = 0

# Allowed lifecycle states; first is the default for a freshly proposed action.
VALID_STATUSES = ("proposed", "authorized", "in_progress", "done", "rejected")
DEFAULT_STATUS = VALID_STATUSES[0]


# --------------------------------------------------------------------------- #
# Helpers.                                                                     #
# --------------------------------------------------------------------------- #

def _now_iso() -> str:
    """UTC timestamp, ISO-8601 with a trailing Z (no microseconds)."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _coerce_str(value: Any, default: str = "") -> str:
    """Best-effort string coercion that never raises (Arabic-safe)."""
    if value is None:
        return default
    try:
        s = str(value).strip()
    except Exception:
        return default
    return s or default


def _normalize_status(value: Any) -> str:
    """Map an arbitrary status input to a known state, else the default."""
    s = _coerce_str(value).lower()
    return s if s in VALID_STATUSES else DEFAULT_STATUS


# --------------------------------------------------------------------------- #
# Public API.                                                                  #
# --------------------------------------------------------------------------- #

def list_decisions() -> List[Dict[str, Any]]:
    """Return a newest-first snapshot copy of the decision log.

    Copies are shallow dicts so callers can't mutate the stored records.
    """
    with _LOCK:
        return [dict(d) for d in reversed(_DECISIONS)]


def create_decision(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Append a decision to the log and return the stored record.

    Accepts a loose payload (dict-like or None) and fills sensible defaults so a
    minimal `{"cluster_id": ..., "action": ...}` body is enough. Unknown keys in
    `payload` are ignored; recognised optional keys (label, rationale,
    expected_impact) are carried through. `status` is normalised to a known
    lifecycle state, defaulting to "proposed".

    Required-ish fields degrade rather than raise: a missing cluster_id/action
    becomes "" so the route can validate at the edge without this ever throwing.
    """
    global _SEQ
    p: Dict[str, Any] = payload if isinstance(payload, dict) else {}

    with _LOCK:
        _SEQ += 1
        record: Dict[str, Any] = {
            "id": f"dec_{_SEQ:05d}",
            "ts": _now_iso(),
            "cluster_id": _coerce_str(p.get("cluster_id")),
            "label": _coerce_str(p.get("label")),
            "action": _coerce_str(p.get("action")),
            "authorized_by": _coerce_str(p.get("authorized_by"), default="operator"),
            "status": _normalize_status(p.get("status")),
            "rationale": _coerce_str(p.get("rationale")),
            "expected_impact": _coerce_str(p.get("expected_impact")),
        }
        _DECISIONS.append(record)
        return dict(record)


def get_decision(decision_id: str) -> Optional[Dict[str, Any]]:
    """Return a copy of the decision with `decision_id`, or None."""
    key = _coerce_str(decision_id)
    if not key:
        return None
    with _LOCK:
        for d in _DECISIONS:
            if d["id"] == key:
                return dict(d)
    return None


def update_status(decision_id: str, status: Any) -> Optional[Dict[str, Any]]:
    """Transition a decision to a new lifecycle status; return it, or None.

    Unknown statuses are coerced to the default rather than rejected, keeping the
    route handler trivial.
    """
    key = _coerce_str(decision_id)
    new_status = _normalize_status(status)
    if not key:
        return None
    with _LOCK:
        for d in _DECISIONS:
            if d["id"] == key:
                d["status"] = new_status
                return dict(d)
    return None


def clear_decisions() -> int:
    """Empty the log (test/reset utility). Returns the number removed."""
    global _SEQ
    with _LOCK:
        n = len(_DECISIONS)
        _DECISIONS.clear()
        _SEQ = 0
        return n


def stats() -> Dict[str, Any]:
    """Aggregate counts: total + per-status breakdown (all states present)."""
    by_status: Dict[str, int] = {s: 0 for s in VALID_STATUSES}
    with _LOCK:
        for d in _DECISIONS:
            by_status[d.get("status", DEFAULT_STATUS)] = by_status.get(d.get("status", DEFAULT_STATUS), 0) + 1
        total = len(_DECISIONS)
    return {"total": total, "by_status": by_status}


# --------------------------------------------------------------------------- #
# Self-test (offline, no DB needed).                                          #
# --------------------------------------------------------------------------- #

if __name__ == "__main__":  # pragma: no cover
    import json

    clear_decisions()
    a = create_decision({
        "cluster_id": "b39d06f6-aaaa-bbbb-cccc-ddddeeeeffff",
        "label": "رسوم الخدمة المستعجلة",
        "action": "Cap urgent-service fees on Sanad and route to owning agency",
        "authorized_by": "Operations Lead",
        "expected_impact": "−15% complaint volume on the fees cluster within 30 days",
    })
    create_decision({"cluster_id": "a1c2e3f4", "action": "Audit National-Aid-Fund delays"})
    update_status(a["id"], "authorized")

    print("decisions:", json.dumps(list_decisions(), ensure_ascii=False, indent=2))
    print("stats:", json.dumps(stats(), ensure_ascii=False))
