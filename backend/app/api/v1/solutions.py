from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/solutions", tags=["solutions"])


@router.get("/{incident_id}")
async def list_solutions(incident_id: str, request: Request):
    from app.services.solution_service import generate_solutions
    repos = request.app.state.repos
    inc = repos.incidents.get(incident_id)
    if not inc:
        raise HTTPException(404, f"Incident {incident_id} not found")
    return generate_solutions(repos, incident_id)


@router.post("/{incident_id}/generate")
async def generate(incident_id: str, request: Request):
    from app.services.solution_service import generate_solutions
    repos = request.app.state.repos
    inc = repos.incidents.get(incident_id)
    if not inc:
        raise HTTPException(404, f"Incident {incident_id} not found")
    return generate_solutions(repos, incident_id)
