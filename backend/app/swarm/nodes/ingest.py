"""Swarm node: ingest — load signals from repo into state."""
from app.swarm.state import CaseState
from app.swarm.emit import emit


def ingest_node(state: CaseState, *, repos) -> dict:
    sigs = repos.signals.list()
    signals_data = [
        {"id": s.id, "observes": s.observes, "metric": s.metric,
         "value": s.value, "baseline": s.baseline, "t_offset_s": s.t_offset_s,
         "severity_raw": s.severity_raw}
        for s in sigs
    ]
    emit(state.case_id, "ingest", "done", {"count": len(signals_data)})
    return {"signals": signals_data, "step": "ingest",
            "trace": state.trace + [{"step": "ingest", "count": len(signals_data)}]}
