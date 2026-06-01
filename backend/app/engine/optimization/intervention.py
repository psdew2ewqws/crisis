from app.engine.types import Intervention


def rank_interventions(
    library: list[dict], incident_risk: float
) -> list[Intervention]:
    """Rank interventions by projected risk reduction (v1 = weighted rank)."""
    reduction_map = {"high": 0.9, "medium": 0.5, "low": 0.2}
    cost_penalty = {"low": 0.0, "medium": 0.1, "high": 0.25}

    ranked: list[Intervention] = []
    for item in library:
        red = reduction_map.get(item["risk_reduction"], 0.3)
        cost_pen = cost_penalty.get(item["cost"], 0.1)
        score = red - cost_pen - (item["eta_min"] / 200.0)
        ranked.append(Intervention(
            id=item["id"],
            title=item["title"],
            actions=item["actions"],
            cost=item["cost"],
            eta_min=item["eta_min"],
            risk_reduction=item["risk_reduction"],
            score=round(score, 3),
        ))
    ranked.sort(key=lambda x: -x.score)
    return ranked
