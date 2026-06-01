"""Swarm node: risk — compute national risk index."""
from app.swarm.state import CaseState
from app.swarm.emit import emit
from app.services.risk_service import get_national_risk


def risk_node(state: CaseState, *, repos) -> dict:
    risk_data = get_national_risk(repos)
    emit(state.case_id, "risk", "done", risk_data)
    return {"risk": risk_data, "step": "risk",
            "trace": state.trace + [{"step": "risk", "national": risk_data["national"]}]}
