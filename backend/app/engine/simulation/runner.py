from app.engine.simulation.adapter import SimAdapter
from app.engine.types import SimResult


def run_before_after(adapter: SimAdapter, scenario: dict) -> SimResult:
    """Run the simulation and compute risk delta."""
    return adapter.run(scenario)
