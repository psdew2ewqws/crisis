from typing import Protocol
from app.engine.types import SimResult


class SimAdapter(Protocol):
    """Simulation adapter boundary (run(scenario) -> SimResult)."""

    def run(self, scenario: dict) -> SimResult: ...
