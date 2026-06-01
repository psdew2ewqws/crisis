from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/simulations", tags=["simulations"])


class SimRequest(BaseModel):
    incident_id: str
    intervention_id: str


@router.post("")
async def create_simulation(body: SimRequest, request: Request):
    from app.services.simulation_service import run_simulation
    repos = request.app.state.repos
    inc = repos.incidents.get(body.incident_id)
    if not inc:
        raise HTTPException(404, f"Incident {body.incident_id} not found")
    result = run_simulation(repos, body.incident_id, body.intervention_id)
    return result


@router.get("/{sim_id}")
async def get_simulation(sim_id: str, request: Request):
    repos = request.app.state.repos
    sim = repos.simulations.get(sim_id)
    if not sim:
        raise HTTPException(404, f"Simulation {sim_id} not found")
    return sim
