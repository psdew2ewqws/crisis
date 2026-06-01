"""Build the LangGraph state graph for the 9-step crisis loop."""
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from app.swarm.state import CaseState
from app.swarm.nodes import (
    ingest_node, resolve_node, correlate_node, rootcause_node,
    risk_node, generate_node, validate_node, recommend_node, learn_node,
)


NODE_MAP = {
    "ingest": ingest_node,
    "resolve": resolve_node,
    "correlate": correlate_node,
    "rootcause": rootcause_node,
    "risk": risk_node,
    "generate": generate_node,
    "validate": validate_node,
    "recommend": recommend_node,
    "learn": learn_node,
}

ORDER = list(NODE_MAP.keys())


def build_graph(repos):
    """Build and compile the LangGraph state machine."""
    g = StateGraph(CaseState)

    for name, fn in NODE_MAP.items():
        # Wrap to inject repos
        def make_node(node_fn):
            def wrapped(state: CaseState) -> dict:
                return node_fn(state, repos=repos)
            return wrapped
        g.add_node(name, make_node(fn))

    g.add_edge(START, "ingest")
    for a, b in zip(ORDER, ORDER[1:]):
        g.add_edge(a, b)
    g.add_edge("learn", END)

    return g.compile(checkpointer=MemorySaver())


async def run_case_async(repos, case_id: str) -> CaseState:
    """Run the full 9-step loop for a case asynchronously. Returns final state."""
    graph = build_graph(repos)
    initial = CaseState(case_id=case_id)
    config = {"configurable": {"thread_id": case_id}}
    result = await graph.ainvoke(initial, config=config)
    return CaseState.model_validate(result)


def run_case(repos, case_id: str) -> CaseState:
    """Run the full 9-step loop synchronously (for scripts/tests)."""
    graph = build_graph(repos)
    initial = CaseState(case_id=case_id)
    config = {"configurable": {"thread_id": case_id}}
    result = graph.invoke(initial, config=config)
    return CaseState.model_validate(result)
