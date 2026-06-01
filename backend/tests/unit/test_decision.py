"""Unit tests for the decision service."""
from app.services.decision_service import authorize_decision
from app.services.simulation_service import run_simulation


class TestDecisionService:
    def test_authorize_decision(self, repos):
        # First run simulation to get a sim_id
        sim = run_simulation(repos, "INC-ZARQA-2026-05", "INT-A")
        sim_id = sim["sim_id"]

        result = authorize_decision(
            repos,
            incident_id="INC-ZARQA-2026-05",
            intervention_id="INT-A",
            sim_id=sim_id,
            justification="Critical pipe burst",
            officer="commander",
        )
        assert result["status"] == "authorized"

    def test_decision_persists(self, repos):
        sim = run_simulation(repos, "INC-ZARQA-2026-05", "INT-A")
        sim_id = sim["sim_id"]

        result = authorize_decision(
            repos,
            incident_id="INC-ZARQA-2026-05",
            intervention_id="INT-A",
            sim_id=sim_id,
            justification="Test persist",
            officer="commander",
        )
        dec_id = result["decision_id"]
        stored = repos.decisions.get(dec_id)
        assert stored is not None
        assert stored["status"] == "authorized"

    def test_decision_includes_audit_fields(self, repos):
        sim = run_simulation(repos, "INC-ZARQA-2026-05", "INT-B")
        sim_id = sim["sim_id"]

        result = authorize_decision(
            repos,
            incident_id="INC-ZARQA-2026-05",
            intervention_id="INT-B",
            sim_id=sim_id,
            justification="Audit test",
            officer="ops-lead",
        )
        assert "authorized_by" in result
        assert "justification" in result
        assert "authorized_at" in result
        assert "audit_path" in result
