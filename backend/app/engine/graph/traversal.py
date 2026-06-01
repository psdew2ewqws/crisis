import heapq
from app.engine.graph.store import CDG
from app.engine.types import CausalPath


def k_shortest_causal_paths(
    g: CDG, symptom: str, candidate: str,
    K: int = 1, max_hops: int = 6, min_pw: float = 0.05,
) -> list[CausalPath]:
    """Walk UPSTREAM from symptom toward candidate (Tech Spec §1.3 pseudocode).
    Returns CausalPath list, non-increasing path_weight (R2)."""
    heap: list[tuple[float, float, list[str]]] = [(-1.0, 0.0, [symptom])]
    out: list[CausalPath] = []
    best_at: dict[str, float] = {}
    while heap and len(out) < K:
        neg_pw, lag, path = heapq.heappop(heap)
        pw, node = -neg_pw, path[-1]
        if node == candidate:
            out.append(CausalPath(path=path, path_weight=pw, path_lag=lag))
            continue
        if len(path) - 1 >= max_hops:
            continue
        for e in g.in_edges(node):  # u --rel--> node : u is upstream cause
            if e.src in path:       # simple paths only
                continue
            npw = pw * e.w
            if npw < min_pw:        # prune (weight only shrinks)
                continue
            if npw <= best_at.get(e.src, 0.0):  # cycle-damping
                continue
            best_at[e.src] = npw
            heapq.heappush(heap, (-npw, lag + e.lag_s, path + [e.src]))
    return out


def ancestors(g: CDG, n: str, max_hops: int = 6, min_pw: float = 0.05) -> set[str]:
    """All upstream nodes reachable within max_hops with path weight >= min_pw."""
    seen: set[str] = set()
    heap: list[tuple[float, list[str]]] = [(-1.0, [n])]
    while heap:
        neg_pw, path = heapq.heappop(heap)
        pw, node = -neg_pw, path[-1]
        if len(path) - 1 >= max_hops:
            continue
        for e in g.in_edges(node):
            npw = pw * e.w
            if npw < min_pw or e.src in path:
                continue
            if e.src not in seen:
                seen.add(e.src)
            heapq.heappush(heap, (-npw, path + [e.src]))
    return seen
