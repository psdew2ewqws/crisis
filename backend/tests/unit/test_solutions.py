"""Unit tests for the solution generation engine."""
from app.services.solution_service import generate_solutions


class TestSolutionGeneration:
    def test_generates_solutions_for_incident(self, repos):
        solutions = generate_solutions(repos, "INC-ZARQA-2026-05")
        assert isinstance(solutions, list)
        assert len(solutions) >= 1

    def test_solution_has_required_fields(self, repos):
        solutions = generate_solutions(repos, "INC-ZARQA-2026-05")
        for sol in solutions:
            assert "id" in sol
            assert "title" in sol or "actions" in sol
