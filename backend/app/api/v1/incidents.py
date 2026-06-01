from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.get("")
async def list_incidents(request: Request):
    repos = request.app.state.repos
    return repos.incidents.list_all()


@router.get("/{incident_id}")
async def get_incident(incident_id: str, request: Request):
    repos = request.app.state.repos
    inc = repos.incidents.get(incident_id)
    if not inc:
        raise HTTPException(404, f"Incident {incident_id} not found")
    return inc


@router.get("/{incident_id}/graph")
async def get_incident_graph(incident_id: str, request: Request):
    from app.services.incident_service import get_graph
    repos = request.app.state.repos
    inc = repos.incidents.get(incident_id)
    if not inc:
        raise HTTPException(404, f"Incident {incident_id} not found")
    return get_graph(repos)


@router.get("/{incident_id}/root-cause")
async def get_root_cause(incident_id: str, request: Request):
    from app.services.incident_service import get_root_cause
    repos = request.app.state.repos
    inc = repos.incidents.get(incident_id)
    if not inc:
        raise HTTPException(404, f"Incident {incident_id} not found")
    return get_root_cause(repos)


@router.post("/{incident_id}/run")
async def run_case(incident_id: str, request: Request):
    """Trigger the full loop for an incident."""
    from app.services.incident_service import get_root_cause
    from app.services.risk_service import get_national_risk
    from app.services.solution_service import generate_solutions
    repos = request.app.state.repos
    inc = repos.incidents.get(incident_id)
    if not inc:
        raise HTTPException(404, f"Incident {incident_id} not found")

    rc = get_root_cause(repos)
    repos.root_causes.save(incident_id, rc)
    risk = get_national_risk(repos)
    solutions = generate_solutions(repos, incident_id)

    return {
        "status": "completed",
        "incident_id": incident_id,
        "root_cause": rc,
        "risk": risk,
        "solutions": solutions,
    }
