from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/decisions", tags=["decisions"])


class AuthorizeRequest(BaseModel):
    incident_id: str
    intervention_id: str
    sim_id: str
    justification: str
    officer: str = "commander"


@router.post("")
async def create_decision(body: AuthorizeRequest, request: Request):
    from app.services.decision_service import authorize_decision
    repos = request.app.state.repos
    try:
        result = authorize_decision(
            repos,
            incident_id=body.incident_id,
            intervention_id=body.intervention_id,
            sim_id=body.sim_id,
            justification=body.justification,
            officer=body.officer,
        )
        return result
    except ValueError as e:
        raise HTTPException(409, str(e))


@router.get("/{decision_id}")
async def get_decision(decision_id: str, request: Request):
    repos = request.app.state.repos
    dec = repos.decisions.get(decision_id)
    if not dec:
        raise HTTPException(404, f"Decision {decision_id} not found")
    return dec
