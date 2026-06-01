from app.engine.optimization.intervention import rank_interventions


def generate_solutions(repos, incident_id: str) -> list[dict]:
    """Generate and rank candidate solutions from the intervention library."""
    library = repos.interventions.get_library()
    incident = repos.incidents.get(incident_id)
    risk = incident.get("risk_index", 80) if incident else 80
    ranked = rank_interventions(library, risk)
    result = [
        {
            "id": i.id, "title": i.title, "actions": i.actions,
            "cost": i.cost, "eta_min": i.eta_min,
            "risk_reduction": i.risk_reduction, "score": i.score,
        }
        for i in ranked
    ]
    return result
