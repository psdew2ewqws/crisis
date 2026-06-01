"""Swarm node: generate — produce candidate solutions."""
from app.swarm.state import CaseState
from app.swarm.emit import emit
from app.services.solution_service import generate_solutions


def generate_node(state: CaseState, *, repos) -> dict:
    solutions = generate_solutions(repos, state.case_id)
    emit(state.case_id, "generate", "done", {"count": len(solutions)})
    return {"solutions": solutions, "step": "generate",
            "trace": state.trace + [{"step": "generate", "count": len(solutions)}]}
