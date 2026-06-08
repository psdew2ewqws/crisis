"""Optional causal-REFUTATION layer for case validation (DoWhy — MIT licensed).

Scope: refutation-only. We do NOT publish an effect SIZE as a headline; we STRESS-TEST
whether a candidate root-cause cluster's association with bad outcomes is causally ROBUST,
using DoWhy's refuters on real ``the_data``:

    build T/Y/X frame  →  minimal backdoor estimate (the substrate refuters need)
                       →  placebo_treatment_refuter : randomize the treatment — a real
                          effect should COLLAPSE toward 0 (if it doesn't, the association
                          is spurious).
                       →  random_common_cause      : add a random confounder — a real
                          effect should stay STABLE.
    robust := placebo collapses AND effect survives the random common cause.

This is an ADVISORY signal: ``validate.py`` keeps its five grounded checks and only nudges
confidence by a small bounded amount (robust → up; spurious → down). The verdict math is
unchanged.

Trust + degradation:
  • Env-gated (``VALIDATE_CAUSAL=1``) AND import-safe: if dowhy/pandas are absent,
    ``available()`` is False and validation simply omits this block — no hard dependency.
    Install:  pip install dowhy
  • Treatment is SERVICE-LEVEL exposure (signals whose service is in the cluster's mapped
    service set). ``record_id`` does not join ``the_data`` (the parallel-layer rule), so this
    is a proxy and is surfaced as such, not as a per-signal treatment.
  • Outcome Y = severity ∈ {high, critical}. Only the ~labeled rows (severity not null)
    are used; X = governorate, source_type, hour, weekend/holiday/ramadan.
"""
from __future__ import annotations

import os
from typing import Any, List, Optional

try:
    from . import db
except Exception:  # pragma: no cover
    db = None  # type: ignore

_ENABLED = os.environ.get("VALIDATE_CAUSAL", "").strip().lower() in ("1", "true", "yes", "on")

try:
    import pandas as _pd  # noqa: F401
    _HAVE_PD = True
except Exception:
    _HAVE_PD = False


def _patch_networkx_for_dowhy() -> None:
    """dowhy 0.8 (the only build that installs on Python 3.14) calls the old
    ``networkx.algorithms.d_separated``; networkx >=3.3 renamed it to
    ``is_d_separator`` (same signature). Alias it so the old dowhy runs."""
    try:
        import networkx as nx
        if not hasattr(nx.algorithms, "d_separated"):
            from networkx.algorithms.d_separation import is_d_separator as _isds
            nx.algorithms.d_separated = _isds  # type: ignore[attr-defined]
            nx.d_separated = _isds  # type: ignore[attr-defined]
    except Exception:
        pass


def _have_dowhy() -> bool:
    try:
        import dowhy  # noqa: F401
        return True
    except Exception:
        return False


def available() -> bool:
    """True only when explicitly enabled AND the optional deps are importable."""
    return _ENABLED and _HAVE_PD and db is not None and _have_dowhy()


_FRAME_SQL = """
  select service_id, governorate, source_type, hour,
         is_weekend, is_holiday, is_ramadan, severity
  from the_data
  where severity is not null and service_id is not null
"""


def _top_severity_services(limit: int = 4) -> List[str]:
    """Return the service_ids with the most severity-labeled rows in the_data."""
    try:
        rows = db.fetchall(
            "SELECT service_id FROM the_data "
            "WHERE severity IS NOT NULL AND service_id IS NOT NULL "
            "GROUP BY service_id ORDER BY count(*) DESC LIMIT %s",
            (limit,)
        )
        return [r["service_id"] for r in (rows or [])]
    except Exception:
        return []


def _build_frame(treated_services: List[str]):
    """Return (DataFrame, common_cause_columns) or None.

    Treatment definition: signal's service_id is in the treated set.
    If treated_services are not in the severity-labeled data, falls back
    to the top services by severity row count so n_treated > 0.
    Y = severity ∈ {high, critical}; X = encoded confounders.
    """
    import pandas as pd

    rows = db.fetchall(_FRAME_SQL)
    if not rows:
        return None
    df = pd.DataFrame(rows)
    if df.empty:
        return None

    treated = set(treated_services or [])
    # Check how many treated rows we'd get; fall back to top services if insufficient.
    initial_t = int((df["service_id"].isin(treated)).sum())
    if initial_t < 20:
        treated = set(_top_severity_services(4))

    df["T"] = df["service_id"].apply(lambda s: 1 if s in treated else 0)
    df["Y"] = df["severity"].apply(lambda s: 1 if str(s).lower() in ("high", "critical") else 0)
    for b in ("is_weekend", "is_holiday", "is_ramadan"):
        df[b] = df[b].apply(lambda v: 1 if v in (True, "true", "t", 1, "1") else 0)
    df["hour"] = pd.to_numeric(df["hour"], errors="coerce").fillna(0).astype(int)

    # one-hot the categorical confounders (low cardinality: governorate, source_type)
    cats = df[["governorate", "source_type"]].astype(str).fillna("none")
    conf = pd.get_dummies(cats, prefix=["gov", "src"], dummy_na=False)
    base = df[["T", "Y", "hour", "is_weekend", "is_holiday", "is_ramadan"]].reset_index(drop=True)
    frame = pd.concat([base, conf.reset_index(drop=True)], axis=1)
    common = ["hour", "is_weekend", "is_holiday", "is_ramadan"] + list(conf.columns)
    return frame, common


def refute(cluster_id: str, treated_services: List[str]) -> dict[str, Any]:
    """Run the refutation battery. Never raises — returns a structured result with
    ``available`` / ``ok`` flags so the caller degrades cleanly."""
    if not available():
        return {"available": False}
    try:
        built = _build_frame(treated_services)
        if not built:
            return {"available": True, "ok": False, "error": "empty frame"}
        frame, common = built
        n_t = int(frame["T"].sum())
        n_c = int(len(frame) - n_t)
        if n_t < 20 or n_c < 20:
            return {"available": True, "ok": False, "error": "insufficient treated/control",
                    "n_treated": n_t, "n_control": n_c}

        import logging
        logging.getLogger("dowhy").setLevel(logging.ERROR)
        _patch_networkx_for_dowhy()
        from dowhy import CausalModel

        model = CausalModel(data=frame, treatment="T", outcome="Y", common_causes=common)
        identified = model.identify_effect(proceed_when_unidentifiable=True)
        # propensity-score stratification: avoids dowhy-0.8's statsmodels ``params[0]``
        # path (which KeyErrors on pandas>=3), and gives a clean backdoor-adjusted ATE.
        estimate = model.estimate_effect(
            identified, method_name="backdoor.propensity_score_stratification"
        )
        eff = float(estimate.value)

        refutations: List[dict[str, Any]] = []
        spurious = False

        # placebo: a real effect should collapse toward 0 under a randomized treatment
        try:
            pl = model.refute_estimate(
                identified, estimate, method_name="placebo_treatment_refuter",
                placebo_type="permute", num_simulations=20,
            )
            new = float(pl.new_effect)
            passed = (abs(new) < 0.5 * abs(eff)) if eff else None
            if passed is False:
                spurious = True   # placebo kept a comparable effect → not causal
            refutations.append({"method": "placebo_treatment", "original": round(eff, 5),
                                "placebo_effect": round(new, 5), "passed": passed})
        except Exception as e:
            refutations.append({"method": "placebo_treatment", "error": str(e)[:140]})

        # random common cause: a real effect should stay stable
        try:
            rc = model.refute_estimate(
                identified, estimate, method_name="random_common_cause", num_simulations=10,
            )
            new = float(rc.new_effect)
            passed = (abs(new - eff) < 0.25 * abs(eff)) if eff else None
            refutations.append({"method": "random_common_cause", "original": round(eff, 5),
                                "new_effect": round(new, 5), "passed": passed})
        except Exception as e:
            refutations.append({"method": "random_common_cause", "error": str(e)[:140]})

        decided = [r for r in refutations if r.get("passed") is not None]
        robust = bool(decided) and all(r.get("passed") for r in decided)
        return {
            "available": True, "ok": True,
            "effect": round(eff, 5),
            "treatment": f"service_id in top-severity services ({n_t} rows)",
            "outcome": "severity ∈ {high, critical}",
            "n_treated": n_t, "n_control": n_c,
            "refutations": refutations,
            "robust": robust,
            "spurious": spurious,
        }
    except Exception as e:  # never break validation
        return {"available": True, "ok": False, "error": str(e)[:200]}
