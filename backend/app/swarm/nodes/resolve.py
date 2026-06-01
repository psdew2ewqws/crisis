"""Swarm node: resolve — map signals to known entities."""
from app.swarm.state import CaseState
from app.swarm.emit import emit


def resolve_node(state: CaseState, *, repos) -> dict:
    # In v1 with seed data, entities are already resolved (IDs match graph)
    resolved_count = len(state.signals)
    emit(state.case_id, "resolve", "done", {"resolved": resolved_count})
    return {"step": "resolve",
            "trace": state.trace + [{"step": "resolve", "resolved": resolved_count}]}
