from fastapi import APIRouter, Request

router = APIRouter(prefix="/risk", tags=["risk"])


@router.get("")
async def get_risk(request: Request):
    from app.services.risk_service import get_national_risk
    repos = request.app.state.repos
    return get_national_risk(repos)
