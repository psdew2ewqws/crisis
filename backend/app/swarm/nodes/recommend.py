"""Swarm node: recommend — select the top intervention for authorization."""
from app.swarm.state import CaseState
from app.swarm.emit import emit


def recommend_node(state: CaseState, *, repos) -> dict:
    recommendation = None
    if state.solutions and state.sim:
        recommendation = {
            "intervention": state.solutions[0],
            "sim_id": state.sim.get("sim_id"),
            "risk_before": state.sim.get("risk_before"),
            "risk_after": state.sim.get("risk_after"),
            "status": "pending_authorization",
        }
    emit(state.case_id, "recommend", "done", recommendation or {})
    return {"recommendation": recommendation, "step": "recommend",
            "trace": state.trace + [{"step": "recommend"}]}
