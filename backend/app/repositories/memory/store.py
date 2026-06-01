from app.engine.graph.store import CDG
from app.engine.types import Signal


class MemoryStore:
    def __init__(self):
        self.cdg: CDG | None = None
        self.signals: list[Signal] = []
        self.incidents: dict[str, dict] = {}
        self.root_causes: dict[str, dict] = {}
        self.interventions: list[dict] = []
        self.simulations: dict[str, dict] = {}
        self.decisions: dict[str, dict] = {}
        self.wizard: dict[str, dict] = {}
        self.sources: dict[str, dict] = {}
