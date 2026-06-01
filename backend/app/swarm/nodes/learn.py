"""Swarm node: learn — record outcome for future retrieval."""
from app.swarm.state import CaseState
from app.swarm.emit import emit


def learn_node(state: CaseState, *, repos) -> dict:
    # In v1: record the case summary in the wizard state for future retrieval
    summary = {
        "case_id": state.case_id,
        "root_cause": state.root_cause.get("likely_cause") if state.root_cause else None,
        "intervention": state.solutions[0]["id"] if state.solutions else None,
        "risk_before": state.sim.get("risk_before") if state.sim else None,
        "risk_after": state.sim.get("risk_after") if state.sim else None,
        "status": "learned",
    }
    repos.wizard.save(state.case_id, {"step": "complete", "summary": summary})
    emit(state.case_id, "learn", "done", summary)
    return {"step": "learn",
            "trace": state.trace + [{"step": "learn", "status": "complete"}]}
