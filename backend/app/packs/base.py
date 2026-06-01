"""Domain Pack ABC — the contract all domain packs implement."""
from abc import ABC, abstractmethod


class DomainPack(ABC):
    @property
    @abstractmethod
    def domain_key(self) -> str: ...

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def get_ontology(self) -> dict:
        """Return node/edge type definitions for this domain."""
        ...

    @abstractmethod
    def get_propagation_rules(self) -> list[dict]:
        """Return propagation rules (relationship weights, lags)."""
        ...

    @abstractmethod
    def get_intervention_library(self) -> list[dict]:
        """Return available interventions for this domain."""
        ...

    @abstractmethod
    def get_seed_data(self) -> dict:
        """Return seed scenario data."""
        ...
