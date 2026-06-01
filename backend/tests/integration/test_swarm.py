"""Integration tests for the LangGraph 9-step swarm."""
from app.swarm.graph import run_case, run_case_async

INCIDENT_ID = "INC-ZARQA-2026-05"


class TestSwarmSync:
    def test_run_case_completes(self, repos):
        """Sync run_case produces a valid final state."""
        result = run_case(repos, INCIDENT_ID)
        assert result.case_id == INCIDENT_ID
        assert result.root_cause is not None
        assert result.risk is not None

    def test_run_case_identifies_pipe(self, repos):
        """Root cause is PIPE-ZN-44."""
        result = run_case(repos, INCIDENT_ID)
        assert result.root_cause["likely_cause"] == "PIPE-ZN-44"

    def test_run_case_has_solutions(self, repos):
        """Swarm generates solutions."""
        result = run_case(repos, INCIDENT_ID)
        assert len(result.solutions) >= 1

    def test_run_case_risk_decreases(self, repos):
        """Risk after recommended intervention < initial risk."""
        result = run_case(repos, INCIDENT_ID)
        assert result.risk["national"] > 0
        if result.sim is not None:
            assert result.sim["risk_after"] < result.sim["risk_before"]


class TestSwarmAsync:
    async def test_run_case_async_completes(self, repos):
        """Async ainvoke produces same result as sync."""
        result = await run_case_async(repos, INCIDENT_ID)
        assert result.case_id == INCIDENT_ID
        assert result.root_cause["likely_cause"] == "PIPE-ZN-44"

    async def test_run_case_async_risk(self, repos):
        result = await run_case_async(repos, INCIDENT_ID)
        assert result.risk is not None
        assert result.risk["national"] > 0
