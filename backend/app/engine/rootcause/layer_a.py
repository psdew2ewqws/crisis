from statistics import mean
from app.engine.graph.store import CDG
from app.engine.graph.traversal import ancestors, k_shortest_causal_paths
from app.engine.types import Signal, RankedCause, RootCauseResult, CausalPath

W_COV, W_PATH, W_TEMP, W_CORR = 0.30, 0.25, 0.20, 0.25  # §4.1 defaults
TAU = 0.5  # ±50% temporal tolerance


def _temporal_ok(expected_lag: float, t_cause: float, t_symptom: float) -> int:
    observed = t_symptom - t_cause
    if observed < 0:
        return 0
    return 1 if abs(observed - expected_lag) <= TAU * max(expected_lag, 1) else 0


def rank_root_causes(g: CDG, signals: list[Signal]) -> RootCauseResult:
    sigma = [(s.observes, s.t_offset_s, s) for s in signals]
    candidates: set[str] = set()
    paths: dict[tuple[str, str], CausalPath] = {}
    for sym, _t, _s in sigma:
        for c in ancestors(g, sym):
            candidates.add(c)
            kp = k_shortest_causal_paths(g, sym, c, K=1)
            if kp:
                paths[(c, sym)] = kp[0]

    # direct corroboration: a signal whose `observes` is the candidate or its direct child
    def corroboration(c: str) -> float:
        for s in signals:
            if s.observes == c:
                return 1.0
            if any(e.src == c for e in g.in_edges(s.observes)):
                return 0.8
        return 0.0

    ranked: list[RankedCause] = []
    for c in candidates:
        reached = [(sym, t) for (sym, t, _s) in sigma if (c, sym) in paths]
        if not reached:
            continue
        cov = len(reached) / len(sigma)
        path_strength = mean(paths[(c, sym)].path_weight for sym, _ in reached)
        temp = mean(
            _temporal_ok(paths[(c, sym)].path_lag, 0.0, t) for sym, t in reached
        )
        corr = corroboration(c)
        score = W_COV * cov + W_PATH * path_strength + W_TEMP * temp + W_CORR * corr
        ranked.append(RankedCause(node_id=c, score=round(score, 3), covers=len(reached)))
    ranked.sort(key=lambda r: -r.score)
    if ranked:
        ranked[0].is_apex = True
    conf = _confidence(ranked)
    return RootCauseResult(
        likely_cause=ranked[0].node_id if ranked else "",
        confidence=conf,
        hypotheses=ranked,
        supporting=[f"path strength {ranked[0].score}"] if ranked else [],
        conflicting=["loudest signal resolves to a downstream symptom, not the cause"],
        missing=["acoustic/leak sensor on apex (none deployed)"],
    )


def _confidence(ranked: list[RankedCause]) -> float:
    if not ranked:
        return 0.0
    if len(ranked) == 1:
        return round(ranked[0].score, 2)
    margin = ranked[0].score - ranked[1].score
    return round(min(0.95, ranked[0].score * (0.6 + 0.4 * min(margin / 0.15, 1.0))), 2)
