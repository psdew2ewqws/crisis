import json
import os
from datetime import datetime, timezone


def authorize_decision(
    repos, incident_id: str, intervention_id: str, sim_id: str,
    justification: str, officer: str = "duty_officer",
) -> dict:
    """Create an authorized decision record + audit bundle."""
    # Verify sim exists and matches
    sim = repos.simulations.get(sim_id)
    if not sim:
        raise ValueError(f"Simulation {sim_id} not found")
    if sim.get("intervention_id") != intervention_id:
        raise ValueError("Simulation does not match intervention (409 stale)")

    decision_id = f"DEC-{incident_id}-{int(datetime.now(timezone.utc).timestamp())}"
    decision = {
        "decision_id": decision_id,
        "incident_id": incident_id,
        "intervention_id": intervention_id,
        "sim_id": sim_id,
        "status": "authorized",
        "justification": justification,
        "authorized_by": officer,
        "authorized_at": datetime.now(timezone.utc).isoformat(),
    }

    repos.decisions.save(decision_id, decision)

    # Write audit bundle
    artifacts_dir = os.environ.get("ARTIFACTS_DIR", "./data/artifacts")
    os.makedirs(artifacts_dir, exist_ok=True)
    audit_path = os.path.join(artifacts_dir, f"audit-{decision_id}.json")
    audit_bundle = {
        "decision": decision,
        "simulation": sim,
        "incident": repos.incidents.get(incident_id),
    }
    with open(audit_path, "w") as f:
        json.dump(audit_bundle, f, indent=2)

    decision["audit_path"] = audit_path
    return decision
