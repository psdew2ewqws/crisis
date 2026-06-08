"""True agent-based crisis simulation for Jordan (the "Agent-Based" tab).

Unlike ``mesa_sim.py`` — which despite its name runs a single identical diffusion
update on every node — this is a genuine agent-based model: heterogeneous,
autonomous agents that observe their local world and *decide*. Four archetypes
are seated on the SAME voc360 graph that ``mesa_sim.build_graph_for_case`` builds:

  • CitizenCohort  (one per governorate, population-weighted) — perceives the
    quality of the services it depends on, blends in peer sentiment and media
    awareness, and DECIDES whether to complain when its grievance crosses a
    per-cohort tolerance threshold (heterogeneous, seeded).
  • ServiceAgent   (one per service) — has finite capacity; degrades under
    complaint load and recovers when the operator allocates resourcing.
  • OperatorAgent  (one) — observes a LAGGED view of the crisis, detects it only
    after ``detection_lag`` ticks, deliberates for ``decision_lag`` ticks, then
    RAMPS an intervention up over ``ramp_ticks`` (never instant — this fixes the
    step-0 optimism of the old before/after model).
  • MediaAgent     (one) — amplifies the number of critical cohorts into a global
    awareness level that feeds back into citizen sentiment.

Two-phase contract: Phase 1 runs the society with the operator DISABLED (the
"do nothing" problem trajectory); Phase 2 re-runs from the same seed with the
operator ENABLED (the solution). The output extends mesa_sim's SimResult /
BeforeAfter so the existing charts render it unchanged, plus additive ABM fields
(agent populations, per-archetype series, intervention timeline, lags).

Import-safe: reuses Mesa when present (engine label only — the agent behaviour is
identical either way) and never requires it. Deterministic: a single seeded RNG
drives every stochastic choice, and both phases share the seed so the only
difference between them is the operator's intervention (a clean A/B).
"""
from __future__ import annotations

import math
import random
from typing import Any, Dict, List, Optional, Tuple

# Reuse the existing graph builder, helpers, constants and escalation readout so
# the ABM is seeded by — and reports in the same units as — the rest of AEGIS.
from . import mesa_sim
from .mesa_sim import (  # noqa: F401  (re-exported flags used in engine_notes)
    _HAVE_NX,
    _HAVE_NUMPY,
    _HAVE_MESA,
    CRITICAL_THRESHOLD,
    DEFAULT_STEPS,
    DEFAULT_SEED,
    DEFAULT_INTERVENTION_STRENGTH,
    seir_readout,
    build_graph_for_case,
)

if _HAVE_NX:
    import networkx as nx  # type: ignore

# ── Behaviour constants (calibratable; documented in the plan) ────────────────
DEGRADE = 0.35            # service-quality loss per unit of complaint pressure
RECOVER = 0.45            # service-quality gain per unit of operator resourcing
DETECT_THRESHOLD = 0.30   # mean negativity the operator must SEE before acting
DEFAULT_SHOCK = 0.45      # scenario severity → initial citizen grievance floor
DEFAULT_DETECTION_LAG = 4 # ticks before the crisis is observed at all
DEFAULT_DECISION_LAG = 3  # ticks of deliberation after detection
DEFAULT_RAMP_TICKS = 6    # ticks for the intervention to reach full strength
DEFAULT_BUDGET = 2        # number of services the operator can resource at once

_GRIEVANCE_W = 0.55       # weight of own service experience in target sentiment
_PEER_W = 0.30            # weight of peer (social contagion) sentiment
_MEDIA_W = 0.15           # weight of media awareness
DEFAULT_SPREAD = 0.30     # how fast a cohort moves toward its target sentiment
DEFAULT_DECAY = 0.985     # natural decay of sentiment toward calm
_MEDIA_AMP = 0.6          # media amplification factor
_MEDIA_DECAY = 0.9        # media awareness decay per tick


# ── Edge extraction (mirror _FallbackModel lines 850-854) ─────────────────────
def _edges(graph) -> List[Tuple[str, str, float]]:
    if _HAVE_NX and isinstance(graph, nx.DiGraph):  # type: ignore[arg-type]
        return [(u, v, float(d.get("weight", 1.0))) for u, v, d in graph.edges(data=True)]
    return [(u, v, float(w)) for (u, v, w) in graph["edges"]]


def _coupling(w: float) -> float:
    """Log-compressed edge weight — identical to mesa_sim's contagion coupling."""
    return math.log10(float(w) + 1.0) + 1.0


# ── Agents ────────────────────────────────────────────────────────────────────
class CitizenCohort:
    """One per governorate. Population-weighted, heterogeneous complaint threshold."""
    kind = "citizen"

    def __init__(self, nid: str, pop: float, sentiment0: float,
                 tolerance: float, media_susceptibility: float):
        self.nid = nid
        self.pop = max(1.0, pop)
        self.sentiment = float(max(0.0, min(1.0, sentiment0)))
        self.tolerance = tolerance               # complaint threshold
        self.media_susceptibility = media_susceptibility
        self.complaint_rate = 0.0                # emitted this tick → service load

    def step(self, m: "CrisisABM") -> None:
        svc_quality = m.mean_service_quality(self.nid)   # 0..1 (1 = good)
        grievance = 1.0 - svc_quality
        peer = m.peer_sentiment(self.nid)
        media = m.media_awareness * self.media_susceptibility
        target = min(1.0, _GRIEVANCE_W * grievance + _PEER_W * peer + _MEDIA_W * media)
        # autonomous move toward target, then decay toward calm
        self.sentiment += m.spread_rate * (target - self.sentiment)
        self.sentiment = max(0.0, min(1.0, self.sentiment * m.decay))
        # DECIDE: complaint INTENSITY in [0,1] past a personal tolerance threshold
        self.complaint_rate = max(0.0, self.sentiment - self.tolerance)


class ServiceAgent:
    """One per service. Capacity-limited; degrades under load, recovers when resourced."""
    kind = "service"

    def __init__(self, nid: str, capacity: float, quality0: float, severity: float):
        self.nid = nid
        self.capacity = max(1.0, capacity)
        self.quality = float(max(0.0, min(1.0, quality0)))  # 1 = good
        self.severity = float(max(0.0, min(1.0, severity)))
        self.load = 0.0
        self.resourcing = 0.0                                # 0..1, set by operator

    def step(self, m: "CrisisABM") -> None:
        # load is a normalized [0,1] complaint-pressure (pop-weighted mean intensity)
        self.load = m.incoming_complaints(self.nid)
        self.quality += (-DEGRADE * self.load * (0.5 + self.severity)
                         + RECOVER * self.resourcing)
        self.quality = max(0.0, min(1.0, self.quality))


class OperatorAgent:
    """Government/operator. Detects late, deliberates, then ramps an intervention."""
    kind = "operator"

    def __init__(self, *, enabled: bool, budget: int, detection_lag: int,
                 decision_lag: int, ramp_ticks: int, effect_size: float):
        self.enabled = enabled
        self.budget = max(1, int(budget))
        self.detection_lag = max(0, int(detection_lag))
        self.decision_lag = max(0, int(decision_lag))
        self.ramp_ticks = max(1, int(ramp_ticks))
        self.effect_size = float(max(0.0, min(1.0, effect_size)))
        self._detected_at: Optional[int] = None
        self._committed_at: Optional[int] = None
        self.targets: List[str] = []
        self.timeline: List[Dict[str, Any]] = []

    def step(self, m: "CrisisABM") -> None:
        if not self.enabled:
            return
        obs = m.lagged_mean_negativity(self.detection_lag)
        if self._detected_at is None and obs > DETECT_THRESHOLD:
            self._detected_at = m.tick
            self.timeline.append({"tick": m.tick, "event": "detected", "obs": round(obs, 4)})
        if (self._detected_at is not None and self._committed_at is None
                and m.tick >= self._detected_at + self.decision_lag):
            self._committed_at = m.tick
            self.targets = m.pick_targets(self.budget)
            self.timeline.append({"tick": m.tick, "event": "intervene",
                                  "targets": list(self.targets),
                                  "effect_size": round(self.effect_size, 3)})
        if self._committed_at is not None:
            ramp = min(1.0, (m.tick - self._committed_at + 1) / self.ramp_ticks)
            alloc = self.effect_size * ramp
            for nid in self.targets:
                svc = m.service_by_nid.get(nid)
                if svc is not None:
                    svc.resourcing = alloc
            if ramp >= 1.0 and not any(e.get("event") == "ramp_full" for e in self.timeline):
                self.timeline.append({"tick": m.tick, "event": "ramp_full"})


class MediaAgent:
    """Amplifies the count of critical cohorts into a global awareness level."""
    kind = "media"

    def step(self, m: "CrisisABM") -> None:
        n_crit = m.n_critical()
        spike = _MEDIA_AMP * (n_crit / max(1, m.n_citizens))
        m.media_awareness = min(1.0, m.media_awareness * _MEDIA_DECAY + spike)


# ── The model ────────────────────────────────────────────────────────────────
class CrisisABM:
    """Builds the agent society from a voc360 graph and steps it deterministically.

    Scheduler order each tick: media → citizens → services → operator, so the
    operator's lever lands AFTER it has observed the freshly-updated world.
    """

    def __init__(self, graph, *, steps: int = DEFAULT_STEPS, seed: int = DEFAULT_SEED,
                 intervene: bool = False, effect_size: float = DEFAULT_INTERVENTION_STRENGTH,
                 spread_rate: float = DEFAULT_SPREAD, decay: float = DEFAULT_DECAY,
                 shock: float = DEFAULT_SHOCK,
                 detection_lag: int = DEFAULT_DETECTION_LAG,
                 decision_lag: int = DEFAULT_DECISION_LAG,
                 ramp_ticks: int = DEFAULT_RAMP_TICKS, budget: int = DEFAULT_BUDGET):
        self.rng = random.Random(seed)
        self.spread_rate = float(spread_rate)
        self.decay = float(decay)
        self.shock = float(max(0.0, min(1.0, shock)))
        self.tick = 0
        self.media_awareness = 0.0

        nodes = mesa_sim._g_nodes(graph)
        attrs = {nid: a for nid, a in nodes}

        # adjacency (undirected): service ↔ governorate, service ↔ cluster
        self._svc_of_gov: Dict[str, List[str]] = {}
        self._gov_of_svc: Dict[str, List[str]] = {}
        self._rootcluster_of_svc: Dict[str, List[str]] = {}
        for u, v, _w in _edges(graph):
            ku, kv = attrs.get(u, {}).get("kind"), attrs.get(v, {}).get("kind")
            svc, other, okind = None, None, None
            if ku == "service":
                svc, other, okind = u, v, kv
            elif kv == "service":
                svc, other, okind = v, u, ku
            if svc is None:
                continue
            if okind == "governorate":
                self._svc_of_gov.setdefault(other, []).append(svc)
                self._gov_of_svc.setdefault(svc, []).append(other)
            elif okind == "cluster" and attrs.get(other, {}).get("is_root_cause"):
                self._rootcluster_of_svc.setdefault(svc, []).append(other)

        # build agents
        self.citizens: List[CitizenCohort] = []
        self.services: List[ServiceAgent] = []
        self.service_by_nid: Dict[str, ServiceAgent] = {}
        for nid, a in nodes:
            kind = a.get("kind")
            if kind == "governorate":
                tol = min(0.55, max(0.15, self.rng.gauss(0.35, 0.10)))
                ms = self.rng.uniform(0.2, 0.8)
                # seed grievance at the scenario shock floor (a crisis IS happening)
                s0 = max(float(a.get("sentiment", 0.0)), self.shock)
                self.citizens.append(CitizenCohort(
                    nid, pop=float(a.get("volume", 0) or 0),
                    sentiment0=s0, tolerance=tol, media_susceptibility=ms))
            elif kind == "service":
                # Shock degrades services proportionally to crisis severity.
                # At shock=0, services start at their voc360 baseline.
                # At shock=0.45, a service that was at 75% quality starts at 75%*(1-0.45)=41%.
                # This ensures the grievance loop can sustain and escalate the crisis.
                base_quality = 1.0 - float(a.get("sentiment", 0.0))
                degraded_quality = max(0.05, base_quality * (1.0 - self.shock))
                svc = ServiceAgent(
                    nid, capacity=float(a.get("volume", 0) or 0),
                    quality0=degraded_quality,
                    severity=float(a.get("severity", 0.0)))
                self.services.append(svc)
                self.service_by_nid[nid] = svc

        # Governorate signals in voc360 are mostly NULL → if no citizen cohorts were
        # seeded, synthesize one cohort per service's catchment so the society is alive.
        if not self.citizens and self.services:
            for svc in self.services:
                gid = f"gov:_catchment_{svc.nid}"
                self._svc_of_gov[gid] = [svc.nid]
                self._gov_of_svc[svc.nid] = [gid]
                tol = min(0.55, max(0.15, self.rng.gauss(0.35, 0.10)))
                s0 = max(svc.shock if hasattr(svc, 'shock') else (1.0 - svc.quality), self.shock)
                self.citizens.append(CitizenCohort(
                    gid, pop=svc.capacity, sentiment0=s0,
                    tolerance=tol, media_susceptibility=self.rng.uniform(0.2, 0.8)))

        self.n_citizens = max(1, len(self.citizens))
        self._total_pop = sum(c.pop for c in self.citizens) or 1.0

        self.operator = OperatorAgent(
            enabled=intervene, budget=budget, detection_lag=detection_lag,
            decision_lag=decision_lag, ramp_ticks=ramp_ticks, effect_size=effect_size)
        self.media = MediaAgent()

        self._neg_history: List[float] = []
        self._series: List[Dict[str, Any]] = []
        self._arch_series: List[Dict[str, float]] = []
        self._collect()

    # ── queries the agents use ──
    def mean_service_quality(self, gov_nid: str) -> float:
        svcs = self._svc_of_gov.get(gov_nid, [])
        qs = [self.service_by_nid[s].quality for s in svcs if s in self.service_by_nid]
        return sum(qs) / len(qs) if qs else 0.6

    def peer_sentiment(self, gov_nid: str) -> float:
        num = den = 0.0
        for c in self.citizens:
            if c.nid == gov_nid:
                continue
            num += c.sentiment * c.pop
            den += c.pop
        return (num / den) if den else 0.0

    def incoming_complaints(self, svc_nid: str) -> float:
        """Pop-weighted mean complaint intensity (0..1) over connected cohorts."""
        num = den = 0.0
        for gid in self._gov_of_svc.get(svc_nid, []):
            cohort = self._citizen_by_nid.get(gid)
            if cohort is None:
                continue
            num += cohort.complaint_rate * cohort.pop
            den += cohort.pop
        return (num / den) if den else 0.0

    def lagged_mean_negativity(self, lag: int) -> float:
        if not self._neg_history:
            return 0.0
        idx = max(0, len(self._neg_history) - 1 - lag)
        return self._neg_history[idx]

    def pick_targets(self, budget: int) -> List[str]:
        """Target the services that will actually relieve citizens: those a citizen
        cohort depends on, ranked by worst quality × citizen reach, root-cause first."""
        def reach(nid: str) -> float:
            return sum(self._citizen_by_nid[g].pop
                       for g in self._gov_of_svc.get(nid, [])
                       if g in self._citizen_by_nid)
        # only services citizens actually perceive can relieve grievance
        connected = [s for s in self.services if reach(s.nid) > 0]
        pool = connected or list(self.services)
        pool = sorted(
            pool,
            key=lambda s: (
                0 if self._rootcluster_of_svc.get(s.nid) else 1,   # root-cause first
                -reach(s.nid) * (1.0 - s.quality),                 # most relief first
            ),
        )
        return [s.nid for s in pool[:budget]]

    def n_critical(self) -> int:
        return sum(1 for c in self.citizens if c.sentiment > CRITICAL_THRESHOLD)

    # ── reporters (same keys as mesa_sim so seir_readout works unchanged) ──
    def _mean_negativity(self) -> float:
        return sum(c.sentiment * c.pop for c in self.citizens) / self._total_pop

    def _complaint_volume(self) -> float:
        return sum(c.sentiment * c.pop for c in self.citizens)

    def _mean_service_quality(self) -> float:
        return (sum(s.quality for s in self.services) / len(self.services)
                if self.services else 0.0)

    def _collect(self) -> None:
        mn = self._mean_negativity()
        self._neg_history.append(mn)
        self._series.append({
            "step": self.tick,
            "mean_negativity": round(mn, 6),
            "complaint_volume": round(self._complaint_volume(), 4),
            "n_critical": self.n_critical(),
        })
        self._arch_series.append({
            "step": self.tick,
            "citizen": round(mn, 6),
            "service_quality": round(self._mean_service_quality(), 6),
            "media_awareness": round(self.media_awareness, 6),
        })

    # lazily-built nid→cohort index (citizens list is stable after __init__)
    @property
    def _citizen_by_nid(self) -> Dict[str, CitizenCohort]:
        cache = getattr(self, "_cbn", None)
        if cache is None:
            cache = {c.nid: c for c in self.citizens}
            self._cbn = cache
        return cache

    def step(self) -> None:
        self.media.step(self)
        order = list(self.citizens)
        self.rng.shuffle(order)              # seeded staged activation
        for c in order:
            c.step(self)
        for s in self.services:
            s.step(self)
        self.operator.step(self)
        self.tick += 1
        self._collect()

    # ── SimResult-shaped accessors ──
    def series(self) -> List[Dict[str, Any]]:
        return list(self._series)

    def arch_series(self) -> List[Dict[str, float]]:
        return list(self._arch_series)

    def final_by_node(self) -> Dict[str, float]:
        out: Dict[str, float] = {}
        for c in self.citizens:
            out[c.nid] = round(c.sentiment, 6)
        for s in self.services:
            out[s.nid] = round(1.0 - s.quality, 6)   # report service STRESS
        return out


# ── Runner ──────────────────────────────────────────────────────────────────────
def run_two_phase(graph, *, steps: int = DEFAULT_STEPS, seed: int = DEFAULT_SEED,
                  effect_size: Optional[float] = None,
                  calib: Optional[Dict[str, Any]] = None,
                  lags: Optional[Dict[str, int]] = None,
                  shock: float = DEFAULT_SHOCK) -> Dict[str, Any]:
    """Phase 1 = problem (operator OFF); Phase 2 = solution (operator ON, lagged).

    Returns an EXTENDED BeforeAfter / simulate contract: every key the existing
    ScenarioCharts reads (risk_before/after, series_before/after, seir_*), plus
    additive ABM fields (agent_populations, per_archetype_series, timeline, lags).
    """
    steps = max(1, int(steps))
    calib = calib or {}
    eff = effect_size if effect_size is not None else float(
        calib.get("effect_size", DEFAULT_INTERVENTION_STRENGTH))
    # Bound calibrated params so extreme values don't prevent crisis escalation.
    # Decay < 0.96 combined with high spread_rate causes instant self-resolution.
    spread = float(min(0.30, calib.get("spread_rate", DEFAULT_SPREAD)))
    decay = float(max(0.975, calib.get("decay", DEFAULT_DECAY)))
    lags = lags or {
        "detection_lag": DEFAULT_DETECTION_LAG,
        "decision_lag": DEFAULT_DECISION_LAG,
        "ramp_ticks": DEFAULT_RAMP_TICKS,
    }

    def _mk(intervene: bool) -> CrisisABM:
        m = CrisisABM(graph, steps=steps, seed=seed, intervene=intervene,
                      effect_size=eff, spread_rate=spread, decay=decay,
                      shock=shock, **lags)
        for _ in range(steps):
            m.step()
        return m

    m_before = _mk(False)
    m_after = _mk(True)

    n_nodes = len(m_after.citizens) + len(m_after.services)
    series_before = m_before.series()
    series_after = m_after.series()
    seir_before = seir_readout(series_before, n_nodes)
    seir_after = seir_readout(series_after, n_nodes)
    risk_before = round(seir_before["peak_negativity"] * 100, 1)
    risk_after = round(seir_after["peak_negativity"] * 100, 1)

    def _compact(series: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [{"step": int(p["step"]),
                 "mean_negativity": round(float(p["mean_negativity"]), 4),
                 "n_critical": int(p["n_critical"])} for p in series]

    target = m_after.operator.targets[0] if m_after.operator.targets else None

    return {
        "available": True,
        "engine": "abm",
        "n_nodes": n_nodes,
        "intervention_node": target,
        "intervention_strength": round(eff, 3),
        "risk_before": risk_before,
        "risk_after": risk_after,
        "risk_reduction": round(risk_before - risk_after, 1),
        "seir_before": seir_before,
        "seir_after": seir_after,
        "escalation": {
            "source": "simulation",
            "escalating": bool(seir_before.get("escalating")),
            "ticks_to_settle": seir_after.get("ticks_to_settle"),
            "note": "إشارة تصعيد من المحاكاة (خطوات نسبية، لا أيام)",
        },
        "series_before": _compact(series_before),
        "series_after": _compact(series_after),
        # ── additive ABM fields ──
        "agent_populations": m_after._run_populations(),
        "per_archetype_series": {
            "problem": m_before.arch_series(),
            "solution": m_after.arch_series(),
        },
        "intervention_timeline": list(m_after.operator.timeline),
        "lags": dict(lags),
        "engine_notes": {"mesa": bool(_HAVE_MESA), "numpy": bool(_HAVE_NUMPY)},
    }


# small helper so run_two_phase can read populations off a model instance
def _run_populations(self: CrisisABM) -> Dict[str, Any]:
    return {
        "citizens": len(self.citizens),
        "services": len(self.services),
        "operators": 1,
        "media": 1,
        "citizen_pop_total": int(self._total_pop),
    }


CrisisABM._run_populations = _run_populations  # type: ignore[attr-defined]
