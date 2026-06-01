"""Deer Graph — the deer-flow LangGraph orchestration for the AEGIS crisis brain.

This module implements the "Deer Graph": a LangGraph ``StateGraph`` that drives a
voc360 CASE through the full investigation chain

    DATA-SOURCE (voc360)  ->  GRAPH  ->  ROOT-CAUSE  ->  RECOMMEND

following the deer-flow pattern (a typed ``State``, node functions that return
``Command(goto=...)``, conditional edges, a compiled graph, and a streaming
runner).  Every node is grounded in the REAL voc360 schema via the project's
own read-only data layer:

  * ``db``            — psycopg READ-ONLY session against voc360 (host from env).
  * ``graph_builder`` — Source(source_type) -> Service(service_id) -> Governorate
                        signal graph + the RIL Problem-Cluster root-cause layer
                        (``the_data`` / ``ril_problem_clusters``).
  * ``rootcause``     — ranks ``ril_problem_clusters`` by
                        ``member_count * (0.5 + severity_avg)``.

LangGraph is an *optional* dependency.  If ``import langgraph`` fails (or any
import error occurs), this module degrades to a pure-Python fallback runner that
walks the identical stages, so the FastAPI ``/api/flow/run`` endpoint keeps
working with zero extra deps.  Either way the public surface is the same:

    run_flow(case)        -> generator of FlowEvent dicts (the stage updates)
    stream_flow(case)     -> generator of NDJSON-ready dicts (main.py consumes this)
    run_flow_stream(case) -> alias of stream_flow

All Arabic text (``canonical_label_ar`` / ``text_clean``) flows through
untouched; serialization is left to the caller with ``ensure_ascii=False``.
"""
from __future__ import annotations

import time
from typing import Any, Dict, Iterator, List, Optional

# --- ground in the real voc360 data layer ---------------------------------
# Support both "package" execution (app.deer_flow) and flat imports so the
# module is import-safe in either layout.
try:  # pragma: no cover - import shim
    from . import db, graph_builder, rootcause
except Exception:  # pragma: no cover
    import db  # type: ignore
    import graph_builder  # type: ignore
    import rootcause  # type: ignore


# ===========================================================================
# Optional LangGraph — detected once, never required.
# ===========================================================================
try:  # pragma: no cover - exercised only where langgraph is installed
    from langgraph.graph import StateGraph, START, END
    from langgraph.types import Command

    _HAS_LANGGRAPH = True
except Exception:  # pragma: no cover - the common case in this environment
    StateGraph = None  # type: ignore
    START = "__start__"  # type: ignore
    END = "__end__"  # type: ignore
    Command = None  # type: ignore
    _HAS_LANGGRAPH = False

try:
    from typing import TypedDict, Literal
except Exception:  # pragma: no cover - py<3.8 safety
    TypedDict = dict  # type: ignore
    Literal = None  # type: ignore


# ===========================================================================
# State — the Deer Graph working memory (grounded in the D-deerflow contract).
# ===========================================================================
class DeerState(TypedDict, total=False):
    """The investigation state threaded through every node.

    Mirrors the D-deerflow ``CaseState`` contract, narrowed to the fields the
    deterministic data->graph->root-cause->recommend chain actually reads and
    writes (no LLM plan loop is required for the live pipeline).
    """

    locale: str  # "ar" — Arabic-first VOC platform
    case: Optional[str]  # service_id | governorate | cluster_id | None/"all"
    # --- signal layer (the_data) ---
    signals: List[Dict[str, Any]]  # source->service->gov edge rows
    signal_stats: Dict[str, Any]  # {signals, services, sources, clusters}
    # --- graph layer (networkx node-link / reactflow) ---
    graph_json: Optional[Dict[str, Any]]
    # --- root-cause layer (ril_problem_clusters) ---
    root_causes: List[Dict[str, Any]]
    # --- output ---
    recommendation: str
    observations: List[str]
    error: Optional[str]


# Stage identifiers — the FlowEvent.stage values the frontend's runFlow() reads.
STAGE_CONNECT = "connect"
STAGE_INGEST = "ingest"
STAGE_GRAPH = "graph"
STAGE_ROOTCAUSE = "rootcause"
STAGE_RECOMMEND = "recommend"
STAGE_ERROR = "error"

# Small inter-stage delay so the live reactflow canvas can animate each layer
# appearing.  Kept tiny; set DEER_FLOW_TICK=0 to disable.
import os as _os

_TICK = float(_os.environ.get("DEER_FLOW_TICK", "0.12") or 0.0)


def _ev(stage: str, status: str, detail: str, data: Any = None) -> Dict[str, Any]:
    """Build a FlowEvent frame: {stage, status, detail, data?}."""
    frame: Dict[str, Any] = {"stage": stage, "status": status, "detail": detail}
    if data is not None:
        frame["data"] = data
    return frame


def _normalize_case(case: Optional[str]) -> Optional[str]:
    """Collapse 'all'/'' to the all-services view (None for graph_builder)."""
    if not case or case == "all":
        return None
    return case


# ===========================================================================
# Node functions.
#
# Each node performs one stage of the chain by calling the real data layer,
# records a list of FlowEvent frames under ``state['observations']`` (used by
# the streaming runner), mutates ``state`` in place, and — under LangGraph —
# returns a ``Command(update=..., goto=...)`` so the StateGraph advances.
#
# To keep one body usable in BOTH worlds, each node is written as a plain
# function that mutates state and returns the next node name; a thin
# ``_lg_node`` adapter wraps it into a ``Command`` for LangGraph.
# ===========================================================================
def _emit(state: DeerState, frame: Dict[str, Any]) -> None:
    state.setdefault("observations", []).append(frame)  # type: ignore[arg-type]


def case_intake(state: DeerState) -> str:
    """Resolve the CASE + locale and open the read-only voc360 session."""
    state.setdefault("locale", "ar")
    case = _normalize_case(state.get("case"))
    state["case"] = case
    _emit(state, _ev(STAGE_CONNECT, "running", "Connecting to voc360 (read-only)…"))
    try:
        h = db.health()
        label = h.get("database", "voc360")
        _emit(state, _ev(STAGE_CONNECT, "done", f"Connected · {label}", h))
        return "ingest_node"
    except Exception as e:  # DB down — abort the flow cleanly.
        state["error"] = f"DB connect failed: {e}"
        _emit(state, _ev(STAGE_CONNECT, STAGE_ERROR, state["error"]))
        return "report_node"


def ingest_node(state: DeerState) -> str:
    """Pull citizen signals for the case from ``the_data`` (spam/dup excluded
    by graph_builder's top-service CTE) and stash the signal stats.

    graph_builder already runs the column-grounded SELECTs against ``the_data``
    (source_type / service_id / governorate / severity), so we build once here
    and carry the result forward to the graph stage.
    """
    _emit(state, _ev(STAGE_INGEST, "running", "Pulling citizen signals for the case…"))
    try:
        g = graph_builder.build_graph(state.get("case"))
    except Exception as e:
        state["error"] = f"ingest failed: {e}"
        _emit(state, _ev(STAGE_INGEST, STAGE_ERROR, state["error"]))
        return "report_node"
    stats = g.get("stats", {})
    state["graph_json"] = g  # reused by build_graph_node (avoid a 2nd query)
    state["signal_stats"] = stats
    state["signals"] = g.get("edges", [])
    detail = (
        f"{stats.get('signals', 0)} signals across "
        f"{stats.get('services', 0)} services, {stats.get('sources', 0)} sources"
    )
    _emit(state, _ev(STAGE_INGEST, "done", detail, stats))
    return "build_graph_node"


def build_graph_node(state: DeerState) -> str:
    """Materialize the live dependency graph (node-link → reactflow).

    Two bridged subgraphs (per the voc360 caveats): the signal graph
    Source(source_type)→Service(service_id)→Governorate weighted by count, and
    the RIL cluster graph Segment→ProblemCluster, joined only at the service
    level by the keyword heuristic.  ``graph_builder`` produced this in
    ``ingest_node``; here we publish it as a discrete stage so the frontend can
    render the graph LIVE before the diagnosis lands.
    """
    _emit(state, _ev(STAGE_GRAPH, "running", "Building the dependency graph…"))
    g = state.get("graph_json")
    if not g:
        try:
            g = graph_builder.build_graph(state.get("case"))
            state["graph_json"] = g
        except Exception as e:
            state["error"] = f"graph build failed: {e}"
            _emit(state, _ev(STAGE_GRAPH, STAGE_ERROR, state["error"]))
            return "report_node"
    n_nodes = len(g.get("nodes", []))
    n_edges = len(g.get("edges", []))
    _emit(
        state,
        _ev(
            STAGE_GRAPH,
            "done",
            f"{n_nodes} nodes · {n_edges} edges",
            {"nodes": n_nodes, "edges": n_edges, "graph": g},
        ),
    )
    return "root_cause_node"


def root_cause_node(state: DeerState) -> str:
    """Rank the RIL Problem Clusters as root causes.

    Pure, deterministic reasoning over ``ril_problem_clusters`` ordered by
    ``member_count * (0.5 + severity_avg)`` (the 0.5 floor matters because
    ``severity_avg`` is near-flat ~0.40).  Real DB rows + Arabic
    ``canonical_label_ar`` + sample evidence segments come back untouched.
    """
    _emit(
        state,
        _ev(STAGE_ROOTCAUSE, "running", "Ranking root-cause problem clusters (RIL)…"),
    )
    try:
        rc = rootcause.rank_root_causes(8)
    except Exception as e:
        state["error"] = f"root-cause ranking failed: {e}"
        _emit(state, _ev(STAGE_ROOTCAUSE, STAGE_ERROR, state["error"]))
        return "report_node"
    state["root_causes"] = rc
    if rc:
        top = rc[0]
        detail = f"Top cause: {top.get('label_ar')} · {top.get('members')} reports"
    else:
        detail = "no clusters"
    _emit(state, _ev(STAGE_ROOTCAUSE, "done", detail, rc[:5]))
    return "recommend_node"


def recommend_node(state: DeerState) -> str:
    """Draft the operator recommendation from the dominant cluster."""
    _emit(state, _ev(STAGE_RECOMMEND, "running", "Drafting recommendation…"))
    rc = state.get("root_causes") or []
    try:
        rec = rootcause.recommend(rc[0]) if rc else "No root cause found."
    except Exception as e:
        rec = f"Recommendation unavailable: {e}"
    state["recommendation"] = rec
    _emit(
        state,
        _ev(
            STAGE_RECOMMEND,
            "done",
            rec,
            {"graph": state.get("graph_json"), "root_causes": rc},
        ),
    )
    return "report_node"


def report_node(state: DeerState) -> str:
    """Terminal node — the flow is complete (or aborted via ``error``)."""
    return END


# Ordered chain used by the fallback runner and to assert the LangGraph wiring.
_CHAIN = {
    "case_intake": case_intake,
    "ingest_node": ingest_node,
    "build_graph_node": build_graph_node,
    "root_cause_node": root_cause_node,
    "recommend_node": recommend_node,
    "report_node": report_node,
}


# ===========================================================================
# LangGraph StateGraph (compiled once, lazily).
# ===========================================================================
def _lg_node(fn):
    """Wrap a plain (state)->next_name node into a LangGraph node that returns
    ``Command(update=state, goto=next)``.  The node bodies mutate ``state`` in
    place, so we hand the whole dict back as the update."""

    def _wrapped(state: DeerState):  # pragma: no cover - needs langgraph
        nxt = fn(state)
        goto = END if nxt in (END, "report_node") and fn is report_node else nxt
        # report_node returns END; everything else returns a node name.
        if nxt == END:
            return Command(update=dict(state), goto=END)
        return Command(update=dict(state), goto=nxt)

    _wrapped.__name__ = getattr(fn, "__name__", "deer_node")
    return _wrapped


_COMPILED = None
_COMPILE_FAILED = False


def build_deer_graph():
    """Construct and compile the Deer Graph StateGraph.

    START → case_intake → ingest → build_graph → root_cause → recommend → report → END,
    with conditional edges so any node can short-circuit to ``report`` on error.
    Returns the compiled graph, or ``None`` if LangGraph is unavailable.
    """
    if not _HAS_LANGGRAPH:
        return None

    builder = StateGraph(DeerState)  # type: ignore[call-arg]

    builder.add_node("case_intake", _lg_node(case_intake))
    builder.add_node("ingest_node", _lg_node(ingest_node))
    builder.add_node("build_graph_node", _lg_node(build_graph_node))
    builder.add_node("root_cause_node", _lg_node(root_cause_node))
    builder.add_node("recommend_node", _lg_node(recommend_node))
    builder.add_node("report_node", _lg_node(report_node))

    builder.add_edge(START, "case_intake")
    # Linear edges are expressed via the Command(goto=...) the nodes return, but
    # we also declare them so the graph validates and renders correctly.
    builder.add_edge("recommend_node", "report_node")
    builder.add_edge("report_node", END)
    # recursion_limit must clear the (short) chain comfortably.
    return builder.compile()


def _get_compiled():
    """Lazily compile + cache the StateGraph; tolerate compile errors."""
    global _COMPILED, _COMPILE_FAILED
    if _COMPILED is not None or _COMPILE_FAILED:
        return _COMPILED
    try:
        _COMPILED = build_deer_graph()
    except Exception:
        _COMPILE_FAILED = True
        _COMPILED = None
    return _COMPILED


# Expose the compiled graph at import time (None where langgraph is absent) so
# callers / tests can introspect it without triggering a run.
graph = _get_compiled()


# ===========================================================================
# Runners.
# ===========================================================================
def _fallback_run_flow(case: Optional[str]) -> Iterator[Dict[str, Any]]:
    """Minimal pure-Python runner — identical stages, no LangGraph required.

    Walks the node chain in order, draining each node's emitted FlowEvent
    frames as it goes, so the consumer receives the exact same stage stream as
    the LangGraph path (connect → ingest → graph → rootcause → recommend).
    """
    state: DeerState = {"case": case, "locale": "ar", "observations": []}
    drained = 0
    current = "case_intake"
    visited = 0
    while current not in (END, "report_node") and visited < 32:
        visited += 1
        node = _CHAIN.get(current)
        if node is None:
            break
        nxt = node(state)
        obs = state.get("observations", [])
        # yield any frames emitted during this node, then pace the stages
        while drained < len(obs):
            frame = obs[drained]
            drained += 1
            yield frame
            if _TICK and frame.get("status") == "done":
                time.sleep(_TICK)
        if state.get("error"):
            break
        current = nxt
    # drain any trailing frames (e.g. an error emitted by report transition)
    obs = state.get("observations", [])
    while drained < len(obs):
        yield obs[drained]
        drained += 1


def _langgraph_run_flow(case: Optional[str]) -> Iterator[Dict[str, Any]]:
    """Drive the compiled StateGraph and surface each node's FlowEvent frames.

    LangGraph streams *state updates*; the per-stage FlowEvents we care about
    are accumulated under ``state['observations']`` by the node bodies, so we
    diff the observation list across updates and yield the new frames in order
    (preserving the live, stage-by-stage cadence the frontend expects).
    """
    compiled = _get_compiled()
    if compiled is None:  # pragma: no cover - defensive
        yield from _fallback_run_flow(case)
        return
    init: DeerState = {"case": case, "locale": "ar", "observations": []}
    seen = 0
    try:  # pragma: no cover - needs langgraph installed
        config = {"recursion_limit": 50}
        for update in compiled.stream(init, config=config, stream_mode="values"):
            obs = (update or {}).get("observations", []) or []
            while seen < len(obs):
                frame = obs[seen]
                seen += 1
                yield frame
                if _TICK and frame.get("status") == "done":
                    time.sleep(_TICK)
    except Exception as e:
        # Surface, then fall back so the operator still gets a result.
        yield _ev(
            STAGE_ERROR,
            STAGE_ERROR,
            f"Deer Graph (LangGraph) failed, using fallback runner: {e}",
        )
        yield from _fallback_run_flow(case)


def run_flow(case: Optional[str] = None) -> Iterator[Dict[str, Any]]:
    """Run the Deer Graph for ``case`` and yield FlowEvent stage updates.

    This is THE public generator: it walks
    ``ingest → graph → rootcause → recommend`` (preceded by ``connect``),
    yielding ``{stage, status, detail, data?}`` dicts. Uses the compiled
    LangGraph StateGraph when available, else the equivalent fallback runner.

    Example::

        for ev in run_flow("Sanad"):
            print(ev["stage"], ev["status"], ev["detail"])
    """
    case = _normalize_case(case)
    if _HAS_LANGGRAPH and _get_compiled() is not None:
        yield from _langgraph_run_flow(case)
    else:
        yield from _fallback_run_flow(case)


def stream_flow(case: Optional[str] = None) -> Iterator[Dict[str, Any]]:
    """Alias consumed by ``main.py`` (``getattr(deer_flow, 'stream_flow')``).

    Yields the same FlowEvent dicts as :func:`run_flow`; ``main.py`` serializes
    them to NDJSON with ``ensure_ascii=False`` so Arabic labels survive.
    """
    yield from run_flow(case)


# Back-compat alias — main.py also probes ``run_flow_stream``.
run_flow_stream = stream_flow


__all__ = [
    "DeerState",
    "build_deer_graph",
    "graph",
    "run_flow",
    "stream_flow",
    "run_flow_stream",
    "case_intake",
    "ingest_node",
    "build_graph_node",
    "root_cause_node",
    "recommend_node",
    "report_node",
    "_HAS_LANGGRAPH",
]


# ===========================================================================
# Manual smoke test (won't touch the DB unless VOC_DSN is set & reachable).
# ===========================================================================
if __name__ == "__main__":  # pragma: no cover
    import json

    print(f"LangGraph available: {_HAS_LANGGRAPH}; compiled graph: {graph!r}")
    for frame in run_flow(None):
        print(json.dumps(frame, ensure_ascii=False))
