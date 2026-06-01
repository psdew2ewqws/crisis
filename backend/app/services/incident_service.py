from app.engine.rootcause.layer_a import rank_root_causes


def get_graph(repos) -> dict:
    """Return incident graph shaped for React Flow: {nodes: [...], edges: [...]}."""
    nodes = repos.graph.get_nodes()
    edges = repos.graph.get_edges()
    return {
        "nodes": [
            {
                "id": n.id, "type": n.type, "kind": n.kind,
                "label": n.label, "location_ref": n.location_ref,
                "attrs": n.attrs,
            }
            for n in nodes
        ],
        "edges": [
            {
                "id": f"{e.src}->{e.dst}",
                "source": e.src, "target": e.dst,
                "relation": e.rel, "weight": e.w, "lag_s": e.lag_s,
            }
            for e in edges
        ],
    }


def get_root_cause(repos) -> dict:
    """Run root-cause analysis and return result."""
    cdg = repos.store.cdg
    sigs = repos.signals.list()
    res = rank_root_causes(cdg, sigs)
    return {
        "likely_cause": res.likely_cause,
        "confidence": res.confidence,
        "hypotheses": [
            {"node_id": h.node_id, "score": h.score, "covers": h.covers, "is_apex": h.is_apex}
            for h in res.hypotheses
        ],
        "supporting": res.supporting,
        "conflicting": res.conflicting,
        "missing": res.missing,
    }
