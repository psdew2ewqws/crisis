from app.engine.graph.store import CDG


def propagate(
    g: CDG, source_risks: dict[str, float], decay: float = 0.7
) -> dict[str, float]:
    """Cascade propagation from source risks downstream (§5.3).
    Each downstream node accumulates: parent_risk * edge_weight * decay."""
    risks = dict(source_risks)
    visited: set[str] = set()
    queue = list(source_risks.keys())

    while queue:
        node = queue.pop(0)
        if node in visited:
            continue
        visited.add(node)
        nr = risks.get(node, 0.0)
        for e in g.out_edges(node):
            prop_risk = nr * e.w * decay
            current = risks.get(e.dst, 0.0)
            if prop_risk > current:
                risks[e.dst] = round(prop_risk, 4)
                queue.append(e.dst)
    return risks
