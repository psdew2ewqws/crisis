"""Swarm node: correlate — stitch signals into an incident."""
from app.swarm.state import CaseState
from app.swarm.emit import emit
from app.services.incident_service import get_graph


def correlate_node(state: CaseState, *, repos) -> dict:
    graph_data = get_graph(repos)
    incident = {
        "id": state.case_id,
        "nodes": len(graph_data["nodes"]),
        "edges": len(graph_data["edges"]),
        "graph": graph_data,
    }
    emit(state.case_id, "correlate", "done", {"nodes": incident["nodes"], "edges": incident["edges"]})
    return {"incident": incident, "step": "correlate",
            "trace": state.trace + [{"step": "correlate", "nodes": incident["nodes"]}]}
