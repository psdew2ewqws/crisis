from app.repositories.memory.store import MemoryStore
from app.repositories.memory.graph import MemoryGraphRepo
from app.repositories.memory.signals import MemorySignalRepo
from app.repositories.memory.repos import (
    MemoryIncidentRepo, MemoryRootCauseRepo, MemoryInterventionRepo,
    MemorySimulationRepo, MemoryDecisionRepo, MemoryWizardRepo, MemorySourceRepo,
)


class MemoryBundle:
    def __init__(self, store: MemoryStore):
        self._store = store
        self.graph = MemoryGraphRepo(store)
        self.signals = MemorySignalRepo(store)
        self.incidents = MemoryIncidentRepo(store)
        self.root_causes = MemoryRootCauseRepo(store)
        self.interventions = MemoryInterventionRepo(store)
        self.simulations = MemorySimulationRepo(store)
        self.decisions = MemoryDecisionRepo(store)
        self.wizard = MemoryWizardRepo(store)
        self.sources = MemorySourceRepo(store)

    @property
    def store(self) -> MemoryStore:
        return self._store
