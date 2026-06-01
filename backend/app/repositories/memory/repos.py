from app.repositories.memory.store import MemoryStore


class MemoryIncidentRepo:
    def __init__(self, store: MemoryStore):
        self._store = store

    def get(self, incident_id: str) -> dict | None:
        return self._store.incidents.get(incident_id)

    def list_all(self) -> list[dict]:
        return list(self._store.incidents.values())

    def update(self, incident_id: str, data: dict) -> None:
        if incident_id in self._store.incidents:
            self._store.incidents[incident_id].update(data)
        else:
            self._store.incidents[incident_id] = data


class MemoryRootCauseRepo:
    def __init__(self, store: MemoryStore):
        self._store = store

    def get(self, incident_id: str) -> dict | None:
        return self._store.root_causes.get(incident_id)

    def save(self, incident_id: str, data: dict) -> None:
        self._store.root_causes[incident_id] = data


class MemoryInterventionRepo:
    def __init__(self, store: MemoryStore):
        self._store = store

    def list_for_incident(self, incident_id: str) -> list[dict]:
        return self._store.interventions

    def get_library(self) -> list[dict]:
        return self._store.interventions


class MemorySimulationRepo:
    def __init__(self, store: MemoryStore):
        self._store = store

    def get(self, sim_id: str) -> dict | None:
        return self._store.simulations.get(sim_id)

    def save(self, sim_id: str, data: dict) -> None:
        self._store.simulations[sim_id] = data

    def list_for_incident(self, incident_id: str) -> list[dict]:
        return [s for s in self._store.simulations.values()
                if s.get("incident_id") == incident_id]


class MemoryDecisionRepo:
    def __init__(self, store: MemoryStore):
        self._store = store

    def get(self, decision_id: str) -> dict | None:
        return self._store.decisions.get(decision_id)

    def save(self, decision_id: str, data: dict) -> None:
        self._store.decisions[decision_id] = data

    def list_for_incident(self, incident_id: str) -> list[dict]:
        return [d for d in self._store.decisions.values()
                if d.get("incident_id") == incident_id]


class MemoryWizardRepo:
    def __init__(self, store: MemoryStore):
        self._store = store

    def get(self, incident_id: str) -> dict | None:
        return self._store.wizard.get(incident_id)

    def save(self, incident_id: str, data: dict) -> None:
        self._store.wizard[incident_id] = data


class MemorySourceRepo:
    def __init__(self, store: MemoryStore):
        self._store = store

    def get(self, source_id: str) -> dict | None:
        return self._store.sources.get(source_id)

    def list_all(self) -> list[dict]:
        return list(self._store.sources.values())

    def save(self, source_id: str, data: dict) -> None:
        self._store.sources[source_id] = data

    def delete(self, source_id: str) -> None:
        self._store.sources.pop(source_id, None)
