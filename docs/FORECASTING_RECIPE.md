# TimesFM in FastAPI (voc360) — Embedding Recipe + Statistical Fallback

## Verified environment (ran in `backend/`)
- INSTALLED: numpy 2.4.4, pandas 3.0.3, statsmodels 0.14.6
- NOT installed: torch, timesfm
=> TimesFM must be **optional + lazy-imported** (gated on env `TIMESFM_MODEL`); the
fallback runs **today** on statsmodels. Never `import timesfm`/`import torch` at module
top — it crashes the backend on import, breaking the graceful-degrade pattern `main.py`
already uses for `deer_flow`/`mesa_sim` (main.py:24-35).

## Two supported TimesFM APIs
**2.5 (current, recommended)** — no `freq` argument:
```python
model = timesfm.TimesFM_2p5_200M_torch.from_pretrained("google/timesfm-2.5-200m-pytorch")
model.compile(timesfm.ForecastConfig(
    max_context=1024, max_horizon=256, normalize_inputs=True,
    use_continuous_quantile_head=True, force_flip_invariance=True,
    infer_is_positive=True, fix_quantile_crossing=True))
point, quant = model.forecast(horizon=H, inputs=[np.float32_array, ...])
# point.shape (B,H); quant.shape (B,H,10) = mean, then 10th..90th deciles
# -> lo = quant[i][:,1] (10th), hi = quant[i][:,9] (90th)
```
**2.0/1.x (legacy)** — uses `freq`:
```python
tfm = timesfm.TimesFm(
    hparams=timesfm.TimesFmHparams(backend="cpu", per_core_batch_size=32,
        horizon_len=H, context_len=512, num_layers=50),  # context_len mult of 32
    checkpoint=timesfm.TimesFmCheckpoint(huggingface_repo_id="google/timesfm-2.0-500m-pytorch"))
point, quant = tfm.forecast(inputs_list, freq=[0])   # 0=daily,1=weekly/monthly,2=quarterly+
# or, all series at once from a long-format df:
fc = tfm.forecast_on_df(inputs=df[["unique_id","ds","y"]], freq="D", value_name="y", num_jobs=-1)
```
Checkpoints: `google/timesfm-2.5-200m-pytorch`, `google/timesfm-2.0-500m-pytorch`,
`google/timesfm-1.0-200m-pytorch`. 2.0 context up to 2048, 2.5 up to ~16k.

## forecaster.py (drop in backend/app/)
```python
from __future__ import annotations
import os
import numpy as np

_MODEL = None      # cached TimesFM model (loaded once)
_BACKEND = None    # '2.5' | '2.0' | 'stat'
_LOAD_ERR = None

def _try_load():
    """Load TimesFM ONCE, lazily, only if TIMESFM_MODEL is set. Never hard-depend on torch."""
    global _MODEL, _BACKEND, _LOAD_ERR
    if _MODEL is not None or _BACKEND == 'stat':
        return
    ckpt = os.environ.get('TIMESFM_MODEL')   # e.g. google/timesfm-2.5-200m-pytorch
    if not ckpt:
        _BACKEND = 'stat'; return
    try:
        import timesfm                        # lazy: torch is heavy/optional
        if 'TimesFM_2p5' in dir(timesfm) and '2.5' in ckpt:
            m = timesfm.TimesFM_2p5_200M_torch.from_pretrained(ckpt)
            m.compile(timesfm.ForecastConfig(
                max_context=1024, max_horizon=256, normalize_inputs=True,
                use_continuous_quantile_head=True, force_flip_invariance=True,
                infer_is_positive=True, fix_quantile_crossing=True))
            _MODEL, _BACKEND = m, '2.5'
        else:                                  # older 2.0 / 1.x checkpoints
            m = timesfm.TimesFm(
                hparams=timesfm.TimesFmHparams(
                    backend='cpu', per_core_batch_size=32,
                    horizon_len=int(os.environ.get('TIMESFM_HORIZON', 30)),
                    context_len=512, num_layers=50),
                checkpoint=timesfm.TimesFmCheckpoint(huggingface_repo_id=ckpt))
            _MODEL, _BACKEND = m, '2.0'
    except Exception as e:                     # any failure -> statistical fallback
        _LOAD_ERR, _BACKEND = str(e), 'stat'

def forecast_series(y, horizon=30, season=7):
    """y = chronological daily values (volume or sentiment) for ONE service/cluster."""
    _try_load()
    hist = np.asarray(y, dtype=np.float32)
    if _BACKEND == '2.5':
        pt, q = _MODEL.forecast(horizon=horizon, inputs=[hist])
        return {'source': 'timesfm-2.5', 'mean': pt[0].tolist(),
                'lo': q[0][:, 1].tolist(), 'hi': q[0][:, 9].tolist()}  # 10th & 90th deciles
    if _BACKEND == '2.0':
        pt, q = _MODEL.forecast([hist], freq=[0])   # 0 = daily / high-freq
        return {'source': 'timesfm-2.0', 'mean': pt[0].tolist(),
                'lo': q[0][:, 0].tolist(), 'hi': q[0][:, -1].tolist()}
    return _stat_forecast(hist, horizon, season)

def _stat_forecast(hist, horizon, season):
    """Holt-Winters via statsmodels (installed). Needs >= 2 full seasons."""
    if len(hist) >= 2 * season:
        try:
            from statsmodels.tsa.holtwinters import ExponentialSmoothing
            fit = ExponentialSmoothing(hist, trend='add', seasonal='add',
                                       seasonal_periods=season,
                                       initialization_method='estimated').fit()
            mean = np.clip(np.asarray(fit.forecast(horizon), dtype=float), 0, None)
            sd = float(np.nanstd(hist - fit.fittedvalues)) or 1.0
            return {'source': 'holt-winters', 'mean': mean.tolist(),
                    'lo': np.clip(mean - 1.28 * sd, 0, None).tolist(),  # ~80% band
                    'hi': (mean + 1.28 * sd).tolist()}
        except Exception:
            pass
    return _seasonal_naive(hist, horizon, season)

def _seasonal_naive(hist, horizon, season):
    """Zero-dependency safety net: seasonal-naive + EWMA drift (pure numpy)."""
    n = len(hist)
    if n == 0:
        z = [0.0] * horizon
        return {'source': 'empty', 'mean': z, 'lo': z, 'hi': z}
    season = min(season, n)
    last = hist[-season:]
    def ewma(a, al):
        o = a[0]
        for v in a[1:]:
            o = al * v + (1 - al) * o
        return o
    drift = (ewma(hist, 0.5) - ewma(hist, 0.1)) / max(season, 1)  # short minus long EWMA
    sd = float(np.std(hist[-min(n, 4 * season):])) or 1.0
    mean = np.asarray([max(0.0, last[h % season] + drift * (h + 1)) for h in range(horizon)])
    return {'source': 'seasonal-naive', 'mean': mean.tolist(),
            'lo': np.clip(mean - 1.28 * sd, 0, None).tolist(),
            'hi': (mean + 1.28 * sd).tolist()}
```

## api_v3.py (load once at startup, forecast per request)
```python
from fastapi import APIRouter, Query
from . import db, forecaster

router = APIRouter()

@router.on_event('startup')
def _warm():
    forecaster._try_load()     # heavy load happens once at boot, off the request hot path

def _daily_volume(service_id):
    rows = db.fetchall(
        """select date_trunc('day', coalesce(observed_at, date::timestamp)) d, count(*) v
           from the_data where service_id = %s
             and coalesce(observed_at, date::timestamp) is not null
           group by 1 order by 1""", (service_id,))
    return [float(r['v']) for r in rows]   # dense-fill gaps to 0 in production

@router.get('/api/forecast')
def forecast(service: str = Query(...), horizon: int = Query(30, ge=1, le=120)):
    y = _daily_volume(service)
    return {'service': service, 'history_points': len(y),
            **forecaster.forecast_series(y, horizon=horizon)}

@router.get('/api/forecast/status')
def status():
    forecaster._try_load()
    return {'backend': forecaster._BACKEND, 'model_loaded': forecaster._MODEL is not None,
            'load_error': forecaster._LOAD_ERR}
# main.py: app.include_router(api_v3.router)  # same pattern as main_v2.router (main.py:46-50)
```

## Notes
- Build per-service/cluster daily series from `the_data` and **dense-fill missing days to 0**
  (both TimesFM and Holt-Winters need evenly-spaced series). Feasible: Sanad ~1702 days,
  Amman Bus ~1151, Bekhedmetkom ~580. `season=7` matches day_of_week/is_weekend weekly cycle.
- Sentiment forecast: feed daily mean of `sentiment_label` mapped to {-1,0,+1} or the
  negative-share ratio instead of counts.
- Escalation / "which problem grows": rank services/clusters by forecast mean slope, or by
  forecast-window mean vs trailing-history mean.
- Keep `timesfm`/`torch` OUT of requirements.txt (or in an extras group); install via
  `pip install -e .[torch]`. Checkpoint downloads from HuggingFace on first `from_pretrained`
  (set `HF_HOME` to cache). Oct-2025 model card: 2.5 was updated for QKV fusion — pin/refresh.

## Sources
- github.com/google-research/timesfm (README quickstart, 2.5 API)
- huggingface.co/google/timesfm-2.5-200m-pytorch (model card)
- pypi.org/project/timesfm (2.0 TimesFmHparams/TimesFmCheckpoint, forecast freq, forecast_on_df)
- statsmodels.org tsa.holtwinters.ExponentialSmoothing (fallback)
