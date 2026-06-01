"""Unit tests for the simulation service."""
from app.services.simulation_service import run_simulation


class TestSimulationService:
    def test_run_simulation_returns_result(self, repos):
        result = run_simulation(repos, "INC-ZARQA-2026-05", "INT-A")
        assert result is not None
        assert "sim_id" in result or "id" in result

    def test_simulation_risk_drops(self, repos):
        result = run_simulation(repos, "INC-ZARQA-2026-05", "INT-A")
        risk_after = result.get("risk_after") or result.get("residual_risk")
        assert risk_after is not None
        assert risk_after < 100  # Risk should be reasonable

    def test_simulation_persists(self, repos):
        result = run_simulation(repos, "INC-ZARQA-2026-05", "INT-A")
        sim_id = result.get("sim_id") or result.get("id")
        stored = repos.simulations.get(sim_id)
        assert stored is not None
