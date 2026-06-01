from fastapi import APIRouter, Request

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("")
async def list_signals(request: Request, since: float | None = None):
    repos = request.app.state.repos
    sigs = repos.signals.list(since=since)
    return [
        {
            "id": s.id, "observes": s.observes, "metric": s.metric,
            "value": s.value, "baseline": s.baseline,
            "t_offset_s": s.t_offset_s, "severity_raw": s.severity_raw,
        }
        for s in sigs
    ]


@router.post("")
async def ingest_signal(request: Request, body: dict):
    """Ingest a new signal (simplified for v1)."""
    from app.engine.types import Signal
    repos = request.app.state.repos
    sig = Signal(
        id=body["id"],
        observes=body["observes"],
        metric=body["metric"],
        value=body["value"],
        baseline=body["baseline"],
        t_offset_s=body.get("t_offset_s", 0),
        severity_raw=body.get("severity_raw", "low"),
    )
    repos.signals.add(sig)
    return {"status": "ingested", "signal_id": sig.id}
