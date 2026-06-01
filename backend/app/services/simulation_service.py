import json
import os
from datetime import datetime, timezone


def run_simulation(repos, incident_id: str, intervention_id: str) -> dict:
    """Run a deterministic before/after simulation for the selected intervention."""
    incident = repos.incidents.get(incident_id)
    risk_before = incident.get("risk_index", 84) if incident else 84

    # Deterministic model keyed off intervention type
    reduction_map = {"INT-A": 0.74, "INT-B": 0.50, "INT-C": 0.20}
    reduction = reduction_map.get(intervention_id, 0.40)
    risk_after = round(risk_before * (1 - reduction))

    # Generate time-series
    series = []
    steps = 5
    for i in range(steps):
        t = i * 15
        # Before: risk stays high or slightly rises
        before_val = risk_before + (i * 2 if i < 3 else -1)
        # After: risk drops as intervention takes effect
        after_val = risk_before - int((risk_before - risk_after) * (i / (steps - 1)))
        series.append({"t": t, "before": before_val, "after": after_val})

    sim_id = f"SIM-{incident_id}-{intervention_id}-{int(datetime.now(timezone.utc).timestamp())}"

    result = {
        "sim_id": sim_id,
        "incident_id": incident_id,
        "intervention_id": intervention_id,
        "risk_before": risk_before,
        "risk_after": risk_after,
        "series": series,
        "status": "completed",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # Save artifact
    artifacts_dir = os.environ.get("ARTIFACTS_DIR", "./data/artifacts")
    os.makedirs(artifacts_dir, exist_ok=True)
    artifact_path = os.path.join(artifacts_dir, f"{sim_id}.json")
    with open(artifact_path, "w") as f:
        json.dump(result, f, indent=2)
    result["artifact_path"] = artifact_path

    # Persist in repo
    repos.simulations.save(sim_id, result)
    return result
