"""Swarm node: validate — run before/after simulation."""
from app.swarm.state import CaseState
from app.swarm.emit import emit
from app.services.simulation_service import run_simulation


def validate_node(state: CaseState, *, repos) -> dict:
    # Pick top-ranked solution
    if state.solutions:
        intervention_id = state.solutions[0]["id"]
    else:
        intervention_id = "INT-A"
    sim = run_simulation(repos, state.case_id, intervention_id)
    emit(state.case_id, "validate", "done", {
        "risk_before": sim["risk_before"], "risk_after": sim["risk_after"]
    })
    return {"sim": sim, "step": "validate",
            "trace": state.trace + [{"step": "validate",
                                     "risk_before": sim["risk_before"],
                                     "risk_after": sim["risk_after"]}]}
