"""Swarm node: rootcause — engine computes causal apex."""
from app.swarm.state import CaseState
from app.swarm.emit import emit
from app.services.incident_service import get_root_cause


def rootcause_node(state: CaseState, *, repos) -> dict:
    rc = get_root_cause(repos)
    repos.root_causes.save(state.case_id, rc)
    emit(state.case_id, "rootcause", "done", rc)
    return {"root_cause": rc, "step": "rootcause",
            "trace": state.trace + [{"step": "rootcause", "apex": rc["likely_cause"]}]}
