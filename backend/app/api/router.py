from fastapi import APIRouter
from app.api.v1 import incidents, signals, risk, solutions, simulations, decisions, sources

router = APIRouter(prefix="/api/v1")
router.include_router(incidents.router)
router.include_router(signals.router)
router.include_router(risk.router)
router.include_router(solutions.router)
router.include_router(simulations.router)
router.include_router(decisions.router)
router.include_router(sources.router)
