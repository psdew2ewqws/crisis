from __future__ import annotations
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Node:
    id: str
    type: str           # Asset|Service|Location|PopulationSegment|...
    kind: str           # pipe|pump|hospital|...
    label: str = ""
    location_ref: str | None = None
    attrs: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Edge:
    src: str
    dst: str
    rel: str
    w: float
    lag_s: float


@dataclass(frozen=True)
class Signal:
    id: str
    observes: str
    metric: str
    value: float
    baseline: float
    t_offset_s: float
    severity_raw: str = "low"


@dataclass
class CausalPath:
    path: list[str]     # symptom ... cause (upstream order)
    path_weight: float
    path_lag: float


@dataclass
class RankedCause:
    node_id: str
    score: float
    covers: int
    is_apex: bool = False


@dataclass
class RootCauseResult:
    likely_cause: str
    confidence: float
    hypotheses: list[RankedCause]
    supporting: list[str] = field(default_factory=list)
    conflicting: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)


@dataclass
class SimResult:
    risk_before: float
    risk_after: float
    series: list[dict] = field(default_factory=list)
    artifact_path: str | None = None


@dataclass
class Intervention:
    id: str
    title: str
    actions: list[str]
    cost: str
    eta_min: int
    risk_reduction: str
    score: float = 0.0
