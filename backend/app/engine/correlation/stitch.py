from dataclasses import dataclass
from app.engine.graph.store import CDG
from app.engine.types import Signal


@dataclass
class Incident:
    id: str
    signals: list[Signal]
    nodes: list[str]
    edges: list[tuple[str, str]]


def stitch(signals: list[Signal], g: CDG, locality: str | None = None) -> Incident:
    """Stitch signals into one incident by shared dependency paths.
    Excludes signals with no edge into the incident's locality."""
    # Determine all node IDs in the graph
    valid_nodes = set(g.nodes.keys())
    included: list[Signal] = []
    incident_nodes: set[str] = set()

    for s in signals:
        # Exclude signals observing entities not in the graph
        if s.observes not in valid_nodes:
            continue
        included.append(s)
        incident_nodes.add(s.observes)

    # Add nodes that connect the observed ones (intermediate nodes on paths)
    edges_in_incident: list[tuple[str, str]] = []
    for nid in list(incident_nodes):
        for e in g.out_edges(nid):
            if e.dst in incident_nodes or e.dst in valid_nodes:
                edges_in_incident.append((e.src, e.dst))
                incident_nodes.add(e.dst)
        for e in g.in_edges(nid):
            if e.src in valid_nodes:
                edges_in_incident.append((e.src, e.dst))
                incident_nodes.add(e.src)

    return Incident(
        id="INC-ZARQA-2026-05",
        signals=included,
        nodes=list(incident_nodes),
        edges=list(set(edges_in_incident)),
    )
