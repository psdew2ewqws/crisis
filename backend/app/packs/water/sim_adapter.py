"""Water pack simulation adapter — deterministic before/after model for v1."""
from app.engine.types import SimResult


class WaterSimAdapter:
    """Implements SimAdapter for the Water domain.
    In v1: deterministic risk reduction based on intervention type.
    Later: WNTR/EPANET hydraulic simulation."""

    def run(self, scenario: dict) -> SimResult:
        intervention_id = scenario.get("intervention_id", "INT-A")
        risk_before = scenario.get("risk_before", 84)

        reduction_map = {"INT-A": 0.74, "INT-B": 0.50, "INT-C": 0.20}
        reduction = reduction_map.get(intervention_id, 0.40)
        risk_after = round(risk_before * (1 - reduction))

        series = []
        steps = 5
        for i in range(steps):
            t = i * 15
            before_val = risk_before + (i * 2 if i < 3 else -1)
            after_val = risk_before - int((risk_before - risk_after) * (i / (steps - 1)))
            series.append({"t": t, "before": before_val, "after": after_val})

        return SimResult(
            risk_before=risk_before,
            risk_after=risk_after,
            series=series,
        )
