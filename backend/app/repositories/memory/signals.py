from app.engine.types import Signal
from app.repositories.memory.store import MemoryStore


class MemorySignalRepo:
    def __init__(self, store: MemoryStore):
        self._store = store

    def list(self, since: float | None = None) -> list[Signal]:
        if since is None:
            return list(self._store.signals)
        return [s for s in self._store.signals if s.t_offset_s >= since]

    def add(self, sig: Signal) -> None:
        self._store.signals.append(sig)
