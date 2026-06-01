"""Run the full Zarqa crisis loop end-to-end (headless).
This is the MVP acceptance gate."""
import sys
import os
import argparse

# Ensure we run from backend/
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ".")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true", help="Run full loop including authorization")
    args = parser.parse_args()

    from app.repositories.factory import get_repos
    from app.swarm.graph import run_case
    from app.services.decision_service import authorize_decision

    repos = get_repos()
    case_id = "INC-ZARQA-2026-05"

    print(f"Running full loop for {case_id}...")
    state = run_case(repos, case_id)

    # Assertions from MVP.md §1.4
    assert state.root_cause is not None, "No root cause produced"
    assert state.root_cause["likely_cause"] == "PIPE-ZN-44", \
        f"Expected PIPE-ZN-44, got {state.root_cause['likely_cause']}"
    print(f"  ✓ Root cause: {state.root_cause['likely_cause']} (confidence: {state.root_cause['confidence']})")

    assert state.sim is not None, "No simulation produced"
    assert state.sim["risk_after"] < 30, \
        f"Expected risk_after < 30, got {state.sim['risk_after']}"
    assert state.sim["risk_after"] < 0.5 * state.sim["risk_before"], \
        f"Expected risk_after < 50% of risk_before"
    print(f"  ✓ Simulation: risk {state.sim['risk_before']} → {state.sim['risk_after']}")

    assert len(state.solutions) > 0, "No solutions generated"
    print(f"  ✓ Solutions: {len(state.solutions)} candidates, top = {state.solutions[0]['title']}")

    if args.full:
        # Authorize decision
        sim_id = state.sim["sim_id"]
        intervention_id = state.solutions[0]["id"]
        decision = authorize_decision(
            repos, case_id, intervention_id, sim_id,
            justification="Validated fix: isolate+bypass+tanker restores service.",
            officer="commander",
        )
        assert decision["status"] == "authorized"
        print(f"  ✓ Decision authorized: {decision['decision_id']}")

        # Verify artifact exists
        audit_path = decision.get("audit_path")
        assert audit_path and os.path.exists(audit_path), "Audit artifact not found"
        print(f"  ✓ Audit artifact: {audit_path}")

    print("\n  ALL ASSERTIONS PASSED — MVP acceptance test green.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
