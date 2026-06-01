from __future__ import annotations
from dataclasses import dataclass
from functools import lru_cache
from app.core.config import get_settings


@dataclass
class Forecast:
    point: list[float]
    lower: list[float]
    upper: list[float]
    backend: str


@lru_cache
def _load_timesfm():
    """Load the TimesFM checkpoint once (singleton). Returns the model or None."""
    s = get_settings()
    try:
        import timesfm
        tfm = timesfm.TimesFm(
            hparams=timesfm.TimesFmHparams(
                backend=s.TIMESFM_BACKEND,
                per_core_batch_size=32,
                horizon_len=128,
                context_len=512,
            ),
            checkpoint=timesfm.TimesFmCheckpoint(
                huggingface_repo_id=s.TIMESFM_CHECKPOINT,
            ),
        )
        return tfm
    except Exception as exc:
        print(f"[timesfm] load failed, using naive fallback: {exc}")
        return None


def forecast(series: list[float], horizon: int = 24) -> Forecast:
    """Forecast `horizon` steps ahead. Uses TimesFM if available, else naive drift."""
    tfm = _load_timesfm()
    if tfm is not None:
        try:
            point, quant = tfm.forecast([series], freq=[0])
            p = list(point[0][:horizon])
            lo = [v * 0.85 for v in p]
            hi = [v * 1.15 for v in p]
            return Forecast(point=p, lower=lo, upper=hi, backend="timesfm")
        except Exception as exc:
            print(f"[timesfm] forecast failed, fallback: {exc}")
    # naive fallback: last value + linear drift of last step
    last = series[-1] if series else 0.0
    drift = (series[-1] - series[-2]) if len(series) >= 2 else 0.0
    p = [last + drift * (i + 1) for i in range(horizon)]
    return Forecast(
        point=p,
        lower=[v * 0.8 for v in p],
        upper=[v * 1.2 for v in p],
        backend="naive",
    )
