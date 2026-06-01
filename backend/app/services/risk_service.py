from app.engine.risk.base_risk import base_risk
from app.engine.risk.propagation import propagate
from app.engine.risk.index import national_index


def get_national_risk(repos) -> dict:
    """Compute national risk index from current signals."""
    cdg = repos.store.cdg
    sigs = repos.signals.list()

    # Compute base risk for each node
    source_risks: dict[str, float] = {}
    for nid, node in cdg.nodes.items():
        criticality = node.attrs.get("criticality", 0.5)
        r = base_risk(nid, sigs, criticality=criticality)
        if r > 0:
            source_risks[nid] = r

    # Propagate through graph
    all_risks = propagate(cdg, source_risks)

    # Aggregate to national index
    return national_index(all_risks)
