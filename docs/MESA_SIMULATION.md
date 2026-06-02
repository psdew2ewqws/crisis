# Mesa Simulation — Complaint / Sentiment Propagation ABM over the voc360 Service Graph

This document is the authoritative write-up of the **Mesa agent-based simulation (ABM)**
inside the AEGIS crisis brain: what Mesa is, the exact Mesa APIs we lean on
(`Model` / `Agent` / `AgentSet` / `NetworkGrid` / `DataCollector`), and **exactly how**
we built a complaint-propagation model over the live **voc360** service graph, how the
**intervention experiment** (before/after a fix) works, and how the **`POST /api/simulate`**
endpoint serves it to the reactflow frontend.

Everything here is grounded in the real voc360 schema (the `the_data` /
`ril_*` tables described below) and the existing backend
(`backend/app/graph_builder.py`, `rootcause.py`, `db.py`, `main.py`). Where the live
endpoint currently ships a lightweight closed-form curve, this document is the design
and reference implementation for the **Mesa-backed** version that replaces it; the Mesa
code in this file is real, runnable, and import-safe with graceful fallbacks if `mesa`
is not installed.

---

## 1. The data source: voc360 (what we are simulating *on*)

The simulation runs **on top of** the live graph the rest of the system already builds
from voc360 — a Voice-of-Customer 360 platform for Jordanian public services
(PostgreSQL 16, `<VOC_HOST>:5432/voc360`, `sslmode=require`, **READ-ONLY** at the
session level via `-c default_transaction_read_only=on`, see `db.py`).

The simulation is grounded in three real layers (exact table / column names):

### 1.1 `the_data` — the SIGNAL / data-source layer (22,882 rows)
One row per citizen signal. Columns we use:

| column | role in the ABM |
|---|---|
| `record_id`, `source_record_id` | signal identity |
| `source_type` | the **Source** node (`app_review` 18.6k, `social_media_sentiment` 1.6k, `employee_complaint`, `qr/ces/csat_survey`, `complaint`, plus Arabic types `فساد_إداري`/admin-corruption, `سوء_الخدمة`/poor-service, `عدم_الرد`/no-response) |
| `service_id` | the **Service** node (`Sanad` 15.8k, `Amman Bus` 2k, `Bekhedmetkom`, `نقل_عام`/transit, `طرق_وبنية_تحتية`/roads, `مراكز_الخدمة`, `جوازات_السفر`/passports, `الخدمات_الإلكترونية`, …) |
| `governorate` | the **Governorate** node (mostly **NULL**; materialized values: `الزرقاء`/Zarqa, `إربد`/Irbid, `العقبة`/Aqaba, `السلط`/Salt, `المفرق`, `جرش`) |
| `severity` | seeds agent `severity` (`low` 2258 / `medium` 786 / `high` 812 / `critical` 395; **NULL for app_reviews**) |
| `sentiment_label` | seeds agent `sentiment` (`negative` / `positive` / `neutral_citizen_sentiment` / `high_severity_complaint`) |
| `confidence`, `rating`, `signal_value` | weighting / tie-breaks |
| `duplicate_flag`, `spam_flag` | filtered out before the graph is built |

### 1.2 RIL — the ROOT-CAUSE layer
- `ril_text_segments` (2,001): extracted problem segments. Cols `segment_id, record_id, segment_text, segment_type('problem'), confidence, language('ar'), embedding_vector, metadata_json`. **Caveat: `record_id` here does NOT join to `the_data.record_id`** — RIL ran on a separate snapshot; the two layers are parallel.
- `ril_cluster_members` (903): `segment_id → cluster_id` (+ `distance_to_centroid`).
- `ril_problem_clusters` (21; 20 with members): the root-cause clusters. Cols `cluster_id, canonical_label_ar` (real Arabic problem text, e.g. `تأخير دعم صندوق المعونة`/National-Aid-Fund delays, `الباص السريع`/BRT bus, `رسوم الخدمة المستعجلة`/urgent-service fees, `منصة تكافل`/Takaful platform), `canonical_label_en, description, parent_cluster_id` (hierarchy field, currently **flat NULL**), `entity_id, service_id, member_count` (top: 551, 69, 64, 55, 52, 23, 18, 9, 9, 9, 8, 7), `severity_avg, centroid_vector, status('active'), first_seen/last_seen`.

### 1.3 The live graph the ABM seats agents on
The signal graph (built by `graph_builder.build_graph`):

```
Source(source_type) --count--> Service(service_id) --count--> Governorate
        each signal carries severity + sentiment
```

and the root-cause graph:

```
Segment --member_of--> ProblemCluster --part_of--> parent   (currently flat: parent NULL)
ROOT CAUSE = dominant ProblemCluster(s)  ranked by  member_count × severity_avg
```

bridged **only at the Service level** (RIL ↔ `the_data` don't join by `record_id`),
via the Arabic keyword heuristic in `graph_builder._KW`
(الباص/سريع/BRT→Amman Bus, معونة/صندوق→National Aid, تكافل→Takaful,
الكتروني/منصة/sanad→Sanad, شارع/حفريات→طرق_وبنية_تحتية).

**A CASE** is one of: a `service:<service_id>`, a `gov:<governorate>`, or a
`cluster:<cluster_id>`. The simulation always builds the graph for that case first,
then propagates over it.

---

## 2. What Mesa is

[Mesa](https://github.com/projectmesa/mesa) is a Python framework for **agent-based
modeling (ABM)**: you define autonomous **agents**, place them in a **space**, and a
**model** advances time in discrete **ticks**, activating agents in some order each tick.
A **DataCollector** snapshots model- and agent-level metrics every tick into pandas
DataFrames — that is our time series.

We pin **`mesa>=3.1,<4`** (Python 3.12). This matters:

- Mesa 3 removed schedulers (`RandomActivation` etc.); activation is now done on the
  **AgentSet** `model.agents` (`agents.shuffle_do("step")`).
- `mesa.Agent.__init__` takes **no `unique_id`** — `super().__init__(model)` auto-assigns
  an id and auto-registers the agent into `model.agents`.
- `mesa.Model.__init__(seed=...)` is **mandatory** and seeds `self.random` / `self.rng`,
  initializes `model.agents`, `model.steps = 0`, `model.running = True`. Pass `seed`
  **or** `rng`, never both.
- **Mesa 4 alpha** changes `Model.__init__` to a `scenario=`/`rng=` signature, drops
  `batch_run`, and rewrites graph space — it breaks everything below. Do **not** use
  `--pre`.

### 2.1 The four APIs we use

**`mesa.Model`** — the world. Holds the graph, RNG, the agent set, the datacollector.
We subclass it as `PropagationModel`. `model.step()` is what we call once per tick.

**`mesa.Agent`** — one sentiment carrier per graph node. We subclass it as `NodeAgent`.
`agent.step()` is **not** auto-called; the model drives activation. `agent.pos` is the
node id once the agent is placed on the grid.

**`AgentSet` (`model.agents`)** — the live, ordered, query-able collection of all agents.
Key ops we use:
- `model.agents.shuffle_do("step")` — random-order activation each tick (our scheduler).
- `model.agents.select(lambda a: a.is_root_cause)` — pick the inflow / intervention targets.
- `model.agents.get(["node_id", "kind", "sentiment"])` — stream node state to reactflow.
- `model.agents.groupby("kind")` / `.agg(...)` — per-governorate / per-service rollups.

**`NetworkGrid`** (`mesa.space.NetworkGrid`) — graph space, **one agent per node**.
Wraps a networkx graph; `place_agent(agent, node)` sets `agent.pos = node` and stores the
agent under `G.nodes[node]['agent']`. `get_neighbors(pos, include_center=False)` returns
the neighbor agents along the graph edges — this is the channel sentiment spreads along.
(We use legacy `mesa.space.NetworkGrid` for headless stability; the modern
`mesa.discrete_space.Network` is the actively-developed path and is noted where relevant.)

**`DataCollector`** (`mesa.datacollection.DataCollector`) — per-tick metric snapshots.
`model_reporters` accept an attribute-name string, a `lambda m: ...`, a method, or
`[fn, [params]]`; `agent_reporters` likewise. `collect(self)` raises `AttributeError`
if any agent lacks a reported attribute — so **every agent is initialized with
`sentiment` and `severity` defaults** even when the voc360 `severity` is NULL
(app_reviews). `tables=` adds an event log (we use it to record the intervention tick).
`get_model_vars_dataframe()` / `get_agent_vars_dataframe()` return the time series.

---

## 3. The complaint-propagation model (exactly how we built it)

### 3.1 Node set (Mesa agents — one per graph node)

Stable, hashable ids, shared verbatim across networkx, Mesa (`agent.pos`) and reactflow:

| id form | `kind` | source |
|---|---|---|
| `svc:<service_id>` | `service` | `the_data.service_id` (Sanad, Amman Bus, نقل_عام, جوازات_السفر…) |
| `gov:<governorate>` | `governorate` | `the_data.governorate` (only materialized, non-NULL govs) |
| `src:<source_type>` | `source` | `the_data.source_type` (app_review, سوء_الخدمة…) |
| `cluster:<cluster_id>` | `cluster` | `ril_problem_clusters` (20 populated) |

Edges carry `weight = count`; direction is `src → svc → gov`; a root-cause edge attaches
`cluster:<id> → svc:<service_id>` via the keyword bridge. Each node carries
`sentiment∈[0,1]` (0 = happy, 1 = furious), `severity∈[0,1]` (NULL→0.0), `volume` (signal
count), and `label_ar`.

> The graph builder in `graph_builder.py` emits `src::`/`svc::`/`gov::`/`cl::` prefixed
> ids for the **reactflow** payload. The simulation uses the single-colon
> `src:`/`svc:`/`gov:`/`cluster:` Mesa id convention from the D-mesa contract.
> `build_graph_for_case` below produces the Mesa-side networkx graph directly so node
> attributes (`sentiment`, `severity`, `volume`) are attached for the agents.

### 3.2 Agent dynamics — `NodeAgent.step()`

Each tick, every agent:

1. **inflow** (only if it is a root-cause node): a constant `inflow` is added — the root
   cause keeps generating fresh complaints until it is fixed.
2. **weighted contagion**: it drifts toward the edge-weighted average sentiment of its
   neighbors, scaled by the `spread_rate` lever. Weighting by edge `weight` (the signal
   count) means high-volume channels (e.g. app_review → Sanad, 15.8k signals) dominate
   propagation — exactly the real-world dynamic where a heavily-used service spreads
   sentiment fastest.
3. **decay**: sentiment is multiplied by `decay` (< 1) — anger fades absent fresh inflow.

This is computed two-phase-safe (read neighbors, then write `self.sentiment`), and clamped
to `[0, 1]`.

### 3.3 Model dynamics — `PropagationModel.step()`

```
model.step():
    model.agents.shuffle_do("step")     # random-order activation
    model.datacollector.collect(model)  # one row per tick
```

`__init__` seats one `NodeAgent` per graph node (seeded from node attrs), marks the
`root_cause_nodes` set, applies the one-shot intervention damp on `intervention_node`
(scaling its sentiment by `1 - intervention_strength` and logging an `Events` row),
and builds the `DataCollector`. We **never** call `model.run_model()` in a request (it
blocks `while self.running`); we step manually for a fixed number of ticks.

### 3.4 DataCollector reporters (the three required series)

| reporter | definition |
|---|---|
| `mean_negativity` | `mean(a.sentiment for a in model.agents)` — global negativity curve |
| `complaint_volume` | `Σ a.sentiment × a.volume` — volume-weighted complaint pressure |
| `n_critical` | `count(a.sentiment > 0.7)` — number of nodes in the red |
| `step` | the `"steps"` attribute (tick index) |

Plus agent reporters `sentiment`, `kind`, and an `Events` table
(`{tick, node, action}`) logging the intervention.

### 3.5 Reference implementation (import-safe)

```python
# backend/app/mesa_sim.py
"""Mesa ABM: complaint / sentiment propagation over the voc360 service graph.

Import-safe: if `mesa` or `networkx` is missing, MESA_AVAILABLE is False and a pure-Python
fallback (`_run_simulation_fallback`) produces the same SimResult shape so /api/simulate
keeps working. Grounded in the real voc360 schema (the_data / ril_problem_clusters)."""
from __future__ import annotations

import random
from dataclasses import dataclass, field, asdict
from typing import Any

# ---- optional deps, graceful fallback ------------------------------------
try:
    import networkx as nx  # type: ignore
    NX_AVAILABLE = True
except Exception:  # pragma: no cover
    nx = None  # type: ignore
    NX_AVAILABLE = False

try:
    import mesa  # type: ignore
    from mesa.space import NetworkGrid  # type: ignore
    from mesa.datacollection import DataCollector  # type: ignore
    MESA_AVAILABLE = True
except Exception:  # pragma: no cover
    mesa = None  # type: ignore
    NetworkGrid = object  # type: ignore
    DataCollector = object  # type: ignore
    MESA_AVAILABLE = False


# ---- 1. graph from voc360 ------------------------------------------------
def build_graph_for_case(case: str | None, db) -> "nx.DiGraph":
    """Build the Mesa-side networkx DiGraph for a CASE from the live voc360 graph.

    `db` is backend.app.db (read-only voc360). Reuses graph_builder.build_graph so the
    Mesa graph and the reactflow graph share the same SQL-grounded topology, then
    re-keys nodes to the Mesa `src:`/`svc:`/`gov:`/`cluster:` convention and attaches
    `sentiment` / `severity` / `volume` agent attributes."""
    if not NX_AVAILABLE:
        raise RuntimeError("networkx is required to build the simulation graph")

    from . import graph_builder  # local import to avoid cycles
    g = graph_builder.build_graph(case)

    # render-tone -> sentiment seed (0..1). alert/warn/calm/neutral from graph_builder.
    tone_to_sent = {"alert": 0.85, "warn": 0.55, "calm": 0.25, "neutral": 0.40}
    # render-tone -> severity seed (NULL severity -> 0.0 via 'neutral'/'calm')
    tone_to_sev = {"alert": 0.8, "warn": 0.5, "calm": 0.2, "neutral": 0.0}
    remap = {"src": "src", "svc": "svc", "gov": "gov", "cl": "cluster"}

    G = nx.DiGraph()
    root_cause_nodes: set[str] = set()

    def mesa_id(nid: str) -> str:
        # graph_builder ids look like 'src::app_review' / 'svc::Sanad' / 'cl::b39d06f6'
        if "::" in nid:
            pre, rest = nid.split("::", 1)
            return f"{remap.get(pre, pre)}:{rest}"
        return nid  # 'rchub', 'case::all'

    for n in g["nodes"]:
        if n["type"] in ("case", "rchub"):
            continue  # structural hubs are not propagation agents
        nid = mesa_id(n["id"])
        tone = n.get("severity", "neutral")
        G.add_node(
            nid,
            kind={"source": "source", "service": "service",
                  "governorate": "governorate", "cluster": "cluster"}[n["type"]],
            sentiment=tone_to_sent.get(tone, 0.40),
            severity=tone_to_sev.get(tone, 0.0),
            volume=int(n.get("value", 0) or 0),
            label_ar=n.get("label_ar") or n.get("label", ""),
        )
        if n["type"] == "cluster":
            root_cause_nodes.add(nid)

    for e in g["edges"]:
        if e["kind"] in ("channel", "diagnoses", "cluster"):
            continue  # case/rchub structural edges are not propagation channels
        s, t = mesa_id(e["source"]), mesa_id(e["target"])
        if s in G and t in G:
            G.add_edge(s, t, weight=int(e.get("weight", 1) or 1))

    # stash for the model; root_cause edges (cluster->svc) make clusters the inflow source
    G.graph["root_cause_nodes"] = sorted(root_cause_nodes)
    return G


# ---- 2. agent + model ----------------------------------------------------
if MESA_AVAILABLE:

    class NodeAgent(mesa.Agent):
        """One sentiment carrier per voc360 graph node."""

        def __init__(self, model, node_id, kind="service", sentiment=0.0,
                     severity=0.0, volume=0, is_root_cause=False):
            super().__init__(model)            # Mesa 3: no unique_id; auto-registers
            self.node_id = node_id             # == self.pos once placed
            self.kind = kind
            self.sentiment = float(sentiment)
            self.severity = float(severity)
            self.volume = int(volume)
            self.is_root_cause = bool(is_root_cause)

        def step(self):
            m = self.model
            # 1. inflow: root causes keep generating fresh complaints
            if self.is_root_cause:
                self.sentiment += m.inflow * (1.0 + self.severity)
            # 2. weighted contagion along graph edges
            nbrs = m.grid.get_neighbors(self.pos, include_center=False)
            if nbrs:
                wsum = 0.0
                acc = 0.0
                for a in nbrs:
                    w = m.edge_weight(self.pos, a.pos)
                    acc += w * a.sentiment
                    wsum += w
                if wsum > 0:
                    avg = acc / wsum
                    self.sentiment += m.spread_rate * (avg - self.sentiment)
            # 3. decay + clamp
            self.sentiment = max(0.0, min(1.0, self.sentiment * m.decay))


    class PropagationModel(mesa.Model):
        """Complaint/sentiment propagation over a voc360 case graph."""

        def __init__(self, graph, spread_rate=0.30, decay=0.985, inflow=0.05,
                     root_cause_nodes=None, intervention_node=None,
                     intervention_strength=0.0, seed=42):
            super().__init__(seed=seed)        # MANDATORY: seeds rng, agents, steps=0
            self.spread_rate = spread_rate
            self.decay = decay
            self.inflow = inflow
            self._graph = graph
            self.grid = NetworkGrid(graph)     # one agent per node

            rc = set(root_cause_nodes or graph.graph.get("root_cause_nodes", []))

            for node, data in graph.nodes(data=True):
                agent = NodeAgent(
                    self, node_id=node, kind=data.get("kind", "service"),
                    sentiment=data.get("sentiment", 0.0),
                    severity=data.get("severity", 0.0),
                    volume=data.get("volume", 0),
                    is_root_cause=(node in rc),
                )
                self.grid.place_agent(agent, node)   # sets agent.pos = node

            self.datacollector = DataCollector(
                model_reporters={
                    "step": "steps",
                    "mean_negativity": lambda m: (
                        sum(a.sentiment for a in m.agents) / len(m.agents)
                        if len(m.agents) else 0.0),
                    "complaint_volume": lambda m: sum(
                        a.sentiment * a.volume for a in m.agents),
                    "n_critical": lambda m: sum(
                        1 for a in m.agents if a.sentiment > 0.7),
                },
                agent_reporters={"sentiment": "sentiment", "kind": "kind"},
                tables={"Events": ["step", "node", "action"]},
            )

            # one-shot intervention damp at tick 0
            if intervention_node is not None and intervention_node in graph:
                for a in self.grid.get_cell_list_contents([intervention_node]):
                    a.sentiment *= (1.0 - intervention_strength)
                    a.is_root_cause = False    # the fix stops the inflow
                self.datacollector.add_table_row(
                    "Events",
                    {"step": 0, "node": intervention_node,
                     "action": f"intervention -{intervention_strength:.2f}"})

            self.datacollector.collect(self)   # tick-0 snapshot

        # edge weight lookup tolerant of DiGraph direction
        def edge_weight(self, u, v) -> float:
            g = self._graph
            if g.has_edge(u, v):
                return float(g[u][v].get("weight", 1.0))
            if g.has_edge(v, u):
                return float(g[v][u].get("weight", 1.0))
            return 1.0

        def step(self):
            self.agents.shuffle_do("step")     # random-order activation
            self.datacollector.collect(self)
```

> **Modern-API note.** For new code / SolaraViz the recommended path is
> `mesa.discrete_space.Network(graph, capacity=1, random=self.random)` with
> `FixedAgent` subclasses (`cell.neighborhood.agents` for neighbors). The dynamics are
> identical; we keep legacy `NetworkGrid` here because it is the most stable for the
> headless FastAPI runner and matches the `agent.pos` / `get_neighbors` calls above.

---

## 4. The headless runner and result schemas

### 4.1 `run_simulation` → `SimResult`

```python
@dataclass
class SimResult:
    series: list[dict]               # [{step, mean_negativity, complaint_volume, n_critical}]
    final_by_node: dict[str, float]  # node_id -> final sentiment (reactflow node color)
    critical_nodes: list[str]        # nodes with final sentiment > 0.7
    params: dict[str, Any]
    events: list[dict]               # intervention log

    def to_dict(self) -> dict:
        return asdict(self)


def run_simulation(graph, steps=50, spread_rate=0.30, decay=0.985, inflow=0.05,
                   intervention_node=None, intervention_strength=0.0,
                   seed=42) -> SimResult:
    """Construct a FRESH model per call (stateful, not thread-safe), step manually."""
    if not MESA_AVAILABLE or not NX_AVAILABLE:
        return _run_simulation_fallback(
            graph, steps, spread_rate, decay, inflow,
            intervention_node, intervention_strength, seed)

    model = PropagationModel(
        graph, spread_rate=spread_rate, decay=decay, inflow=inflow,
        intervention_node=intervention_node,
        intervention_strength=intervention_strength, seed=seed)
    for _ in range(steps):
        model.step()                 # NEVER model.run_model() (blocks while running)

    mdf = model.datacollector.get_model_vars_dataframe().reset_index(drop=True)
    series = mdf[["step", "mean_negativity", "complaint_volume", "n_critical"]] \
        .to_dict(orient="records")
    final = {a.node_id: round(float(a.sentiment), 4) for a in model.agents}
    critical = sorted(n for n, s in final.items() if s > 0.7)
    events = model.datacollector.get_table_dataframe("Events").to_dict(orient="records")
    return SimResult(
        series=series, final_by_node=final, critical_nodes=critical,
        params={"steps": steps, "spread_rate": spread_rate, "decay": decay,
                "inflow": inflow, "intervention_node": intervention_node,
                "intervention_strength": intervention_strength, "seed": seed},
        events=events)
```

- A **fresh model per request** (cheap; Mesa models are stateful and **not** thread-safe —
  never share one across threads).
- Same `seed` ⇒ identical replay (audit trail).

### 4.2 The intervention experiment — `run_before_after` → `BeforeAfter`

The experiment answers: *if we fix the dominant root cause, how much better does the
case get, and how fast does it settle?* We run the **same** graph and seed twice — once
with no intervention, once damping the root-cause node — and diff the curves.

```python
@dataclass
class BeforeAfter:
    before: dict                     # SimResult.to_dict() with intervention_strength=0
    after: dict                      # SimResult.to_dict() with the fix applied
    delta: dict                      # mean_negativity_final, n_critical_final, ...
    root_cause: dict                 # {cluster_id, canonical_label_ar, member_count, ...}

    def to_dict(self) -> dict:
        return asdict(self)


def _settle_tick(series, eps=0.01) -> int:
    """First tick after which mean_negativity changes by < eps for the rest of the run."""
    for i in range(1, len(series)):
        if all(abs(series[j]["mean_negativity"] - series[j - 1]["mean_negativity"]) < eps
               for j in range(i, len(series))):
            return series[i]["step"]
    return series[-1]["step"] if series else 0


def run_before_after(graph, *, intervention_node, intervention_strength=0.6,
                     root_cause=None, steps=50, spread_rate=0.30, decay=0.985,
                     inflow=0.05, seed=42) -> BeforeAfter:
    common = dict(steps=steps, spread_rate=spread_rate, decay=decay,
                  inflow=inflow, seed=seed)
    before = run_simulation(graph, intervention_node=None,
                            intervention_strength=0.0, **common)
    after = run_simulation(graph, intervention_node=intervention_node,
                           intervention_strength=intervention_strength, **common)

    def fin(sr, key):
        return sr.series[-1][key] if sr.series else 0.0

    def peak(sr):
        return max((p["mean_negativity"] for p in sr.series), default=0.0)

    delta = {
        "mean_negativity_final": round(
            fin(before, "mean_negativity") - fin(after, "mean_negativity"), 4),
        "n_critical_final": int(
            fin(before, "n_critical") - fin(after, "n_critical")),
        "peak_mean_negativity": round(peak(before) - peak(after), 4),
        "ticks_to_settle": _settle_tick(after.series) - _settle_tick(before.series),
    }
    return BeforeAfter(before=before.to_dict(), after=after.to_dict(),
                       delta=delta, root_cause=root_cause or {})
```

`delta` reports how much the fix lowered final negativity, how many nodes left the red,
how much it shaved the peak, and the change in ticks-to-settle.

### 4.3 Import-safe fallback (no Mesa installed)

If `mesa` / `networkx` are unavailable, `_run_simulation_fallback` reproduces the same
`SimResult` shape with a pure-Python neighbor-averaging loop, so the endpoint never 500s
on a thin deployment:

```python
def _run_simulation_fallback(graph, steps, spread_rate, decay, inflow,
                             intervention_node, intervention_strength, seed) -> SimResult:
    rng = random.Random(seed)
    # graph may be an nx graph or a plain {nodes, edges} dict
    if NX_AVAILABLE and hasattr(graph, "nodes"):
        nodes = {n: dict(d) for n, d in graph.nodes(data=True)}
        adj: dict[str, list[tuple[str, float]]] = {n: [] for n in nodes}
        for u, v, d in graph.edges(data=True):
            w = float(d.get("weight", 1.0))
            adj[u].append((v, w)); adj[v].append((u, w))
        rc = set(graph.graph.get("root_cause_nodes", []))
    else:  # dict form
        nodes = {n["id"]: n for n in graph.get("nodes", [])}
        adj = {nid: [] for nid in nodes}
        for e in graph.get("edges", []):
            s, t, w = e["source"], e["target"], float(e.get("weight", 1.0))
            if s in adj and t in adj:
                adj[s].append((t, w)); adj[t].append((s, w))
        rc = {nid for nid, n in nodes.items() if n.get("kind") == "cluster"}

    sent = {n: float(d.get("sentiment", 0.0)) for n, d in nodes.items()}
    sev = {n: float(d.get("severity", 0.0)) for n, d in nodes.items()}
    vol = {n: int(d.get("volume", 0) or 0) for n, d in nodes.items()}
    events = []
    if intervention_node in sent:
        sent[intervention_node] *= (1.0 - intervention_strength)
        rc.discard(intervention_node)
        events.append({"step": 0, "node": intervention_node,
                       "action": f"intervention -{intervention_strength:.2f}"})

    def snapshot(step):
        vals = list(sent.values()) or [0.0]
        return {"step": step,
                "mean_negativity": round(sum(vals) / len(vals), 4),
                "complaint_volume": round(sum(sent[n] * vol[n] for n in sent), 2),
                "n_critical": sum(1 for v in vals if v > 0.7)}

    series = [snapshot(0)]
    for t in range(1, steps + 1):
        order = list(sent); rng.shuffle(order)
        nxt = dict(sent)
        for n in order:
            s = sent[n]
            if n in rc:
                s += inflow * (1.0 + sev[n])
            if adj[n]:
                wsum = sum(w for _, w in adj[n])
                avg = sum(w * sent[m] for m, w in adj[n]) / wsum if wsum else 0.0
                s += spread_rate * (avg - s)
            nxt[n] = max(0.0, min(1.0, s * decay))
        sent = nxt
        series.append(snapshot(t))

    final = {n: round(v, 4) for n, v in sent.items()}
    return SimResult(
        series=series, final_by_node=final,
        critical_nodes=sorted(n for n, v in final.items() if v > 0.7),
        params={"steps": steps, "spread_rate": spread_rate, "decay": decay,
                "inflow": inflow, "intervention_node": intervention_node,
                "intervention_strength": intervention_strength, "seed": seed,
                "engine": "fallback"},
        events=events)
```

---

## 5. Root-cause targeting (what gets fixed)

The intervention node is the **dominant root-cause cluster**, ranked exactly as the rest
of the system ranks root causes (`rootcause.rank_root_causes`,
`backend/app/rootcause.py`):

```sql
select cluster_id, canonical_label_ar, canonical_label_en,
       coalesce(member_count,0) member_count,
       coalesce(severity_avg,0) severity_avg,
       coalesce(member_count,0) * (0.5 + coalesce(severity_avg,0)) as score
from ril_problem_clusters
where coalesce(member_count,0) > 1
order by score desc limit %(lim)s
```

The `0.5 +` floor matters: `severity_avg` is effectively flat (~0.40) across clusters, so
without the floor the score would collapse to `member_count` alone — the floor keeps
severity a tie-breaker, not the sole driver. With this ranking the top cluster is
`رسوم الخدمة المستعجلة` (urgent-service fees, 551 members) followed by the
National-Aid-Fund / BRT / Takaful clusters.

If the caller does not pass an `intervention_node`, `/api/simulate` **auto-targets the
top-ranked cluster**, resolving it to the Mesa node id `cluster:<cluster_id>`, and the
`BeforeAfter.root_cause` field carries `{cluster_id, canonical_label_ar, member_count,
severity_avg, score}` so the frontend and report can name the real Arabic problem.

---

## 6. Serving it: `POST /api/simulate`

The endpoint is registered in `backend/app/main.py`. It currently ships a lightweight
closed-form risk curve (a placeholder noted in code as *"Mesa version arrives via
workflow"*). This section is the Mesa-backed replacement.

### 6.1 Request / response contract

```
POST /api/simulate
SimRequest {
  case_id: str                       # service:<id> | gov:<governorate> | cluster:<id>
  steps: int = 50                    # 4..500
  spread_rate: float = 0.30
  decay: float = 0.985
  inflow: float = 0.05
  intervention_node: str | None      # None -> auto-target top cluster
  intervention_strength: float = 0.6
  seed: int = 42
}
-> BeforeAfter JSON  (ensure_ascii=False — Arabic-safe)
```

### 6.2 Why the DB pull happens *before* the threadpool

A Mesa run is **synchronous, CPU-bound** work — it must not run directly in an
`async def` (it would block the event loop). We offload it with
`run_in_threadpool`. But psycopg connections are **not** thread-safe to share, so we
**pull voc360 and build the graph and rank the root causes first, on the event loop**,
and pass the finished networkx graph (plus the resolved intervention target) into the
threadpool. Nothing touches the DB inside the worker thread.

### 6.3 Reference endpoint

```python
# backend/app/main.py  (Mesa-backed /api/simulate)
from fastapi import Body
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import db, rootcause, mesa_sim


class SimRequest(BaseModel):
    case_id: str | None = None
    steps: int = Field(default=50, ge=4, le=500)
    spread_rate: float = Field(default=0.30, ge=0.0, le=1.0)
    decay: float = Field(default=0.985, ge=0.80, le=1.0)
    inflow: float = Field(default=0.05, ge=0.0, le=0.5)
    intervention_node: str | None = None
    intervention_strength: float = Field(default=0.6, ge=0.0, le=1.0)
    seed: int = 42


@app.post("/api/simulate")
async def simulate(req: SimRequest = Body(default_factory=SimRequest)):
    # 1. DB work + graph build + root-cause ranking — ON THE EVENT LOOP (psycopg here)
    graph = mesa_sim.build_graph_for_case(req.case_id, db)
    ranked = rootcause.rank_root_causes(limit=1)
    top = ranked[0] if ranked else None

    # 2. resolve the intervention target (auto-target the top cluster if not given)
    intervention_node = req.intervention_node
    if intervention_node is None and top is not None:
        candidate = f"cluster:{top['cluster_id']}"
        if candidate in graph:
            intervention_node = candidate

    root_cause = None
    if top is not None:
        root_cause = {
            "cluster_id": top["cluster_id"],
            "canonical_label_ar": top["label_ar"],
            "member_count": top["members"],
            "severity_avg": top["severity_avg"],
            "score": top["score"],
        }

    # 3. CPU-bound Mesa run — OFF the event loop, no DB access inside
    result = await run_in_threadpool(
        mesa_sim.run_before_after, graph,
        intervention_node=intervention_node,
        intervention_strength=req.intervention_strength,
        root_cause=root_cause, steps=req.steps,
        spread_rate=req.spread_rate, decay=req.decay,
        inflow=req.inflow, seed=req.seed)

    # 4. Arabic-safe JSON (ensure_ascii=False for canonical_label_ar)
    return JSONResponse(content=json.loads(
        json.dumps(result.to_dict(), ensure_ascii=False)))
```

`ensure_ascii=False` everywhere is load-bearing: `canonical_label_ar` and `label_ar`
carry real Arabic (`رسوم الخدمة المستعجلة`, `تأخير دعم صندوق المعونة`) that must not be
mangled into `\uXXXX` escapes for the RTL frontend.

### 6.4 Frontend consumer

The reactflow frontend reads `BeforeAfter`:
- `before.series` / `after.series` → two risk/negativity curves in a recharts chart
  (the only new frontend consumer of `/api/simulate`, per the D-frontend gap).
- `after.final_by_node` → recolor reactflow nodes by final sentiment.
- `delta` → headline numbers ("−N nodes critical", "peak −X").
- `root_cause.canonical_label_ar` → name the fixed problem in Arabic.

For a **live** per-tick stream to reactflow, step the model manually and emit each tick
instead of calling `run_before_after` (never `model.run_model()`):

```python
model = mesa_sim.PropagationModel(graph, seed=req.seed)
for t in range(req.steps):
    model.step()
    await ws.send_json({"step": t,
        "nodes": model.agents.get(["node_id", "kind", "sentiment"])})
```

---

## 7. Intervention sweeps (`batch_run`) — testing many levers

To compare interventions across a parameter grid (e.g. spread × strength, with
Monte-Carlo repeats), use Mesa's own `mesa.batch_run`. Inside FastAPI we run it with
`number_processes=1` (parallel spawn calls `multiprocessing.set_start_method("spawn")`,
which needs an `if __name__ == "__main__":` guard — unsafe in the async server). It
requires `self.datacollector` + `collect()` in `step()` + a `seed=`/`rng=` kwarg, all of
which `PropagationModel` has.

```python
import pandas as pd
results = mesa.batch_run(
    mesa_sim.PropagationModel,
    parameters={"graph": graph,
                "spread_rate": [0.1, 0.3, 0.5],
                "intervention_strength": [0.0, 0.6]},  # full factorial
    rng=[None] * 5,            # 5 Monte-Carlo repeats (iterations= is DEPRECATED)
    max_steps=50, number_processes=1,
    data_collection_period=1)  # 1 = every step (trajectories); -1 = final only
df = pd.DataFrame(results)     # RunId, iteration, Step, <params>, seed, <reporters>, AgentID
```

`batch_run` is **not** exported in Mesa 4 alpha — another reason for the `mesa<4` pin.

---

## 8. Where this slots into the Deer Graph flow

In the deer-flow LangGraph state graph the simulation is a `simulate_node` scheduled
**after** `root_cause` (and downstream of the human-review gate, so an operator has
approved the investigation first). It:

1. reads `state["root_causes"][0]`, resolves `cluster:<cluster_id>` as `intervention_node`,
2. builds the graph from voc360, runs `run_before_after`,
3. writes `state["mesa_results"]`,
4. streams `sim_step` / `graph_edge` SSE frames to the same reactflow canvas
   (frames `json.dumps(..., ensure_ascii=False)`),
5. returns `Command(goto="report")`,

and the `BeforeAfter` result folds into the report's *"recommended interventions"*
section, naming the real Arabic root cause and the projected drop in complaint volume.

---

## 9. Pins, invariants, and load-bearing gotchas

- **`mesa>=3.1,<4`** — Mesa 4 alpha changes `Model.__init__`, drops `batch_run`, rewrites
  graph space.
- **`super().__init__(seed=seed)` is mandatory** in the model; pass `seed` **xor** `rng`.
- **No `unique_id`** arg on agents (auto-assigned); agents auto-register into `model.agents`
  — there is no scheduler object.
- `model.steps` auto-increments and `model.running` defaults `True` — don't manage them.
- **Never `model.run_model()` in a request** — it blocks `while self.running`. Step
  manually for a fixed count.
- **Initialize every agent with `sentiment` and `severity`** (defaults `0.0`) — the
  voc360 `severity` is NULL for all 18.6k app_reviews, and `DataCollector.collect`
  `AttributeError`s on a missing reported attribute.
- **Pull DB / build the graph BEFORE `run_in_threadpool`** — psycopg connections aren't
  thread-safe to share; nothing touches the DB inside the worker thread.
- **Fresh model per request** — Mesa models are stateful and not thread-safe.
- **Node ids stable & hashable** across networkx (`G.nodes`), Mesa (`agent.pos`) and
  reactflow — `src:` / `svc:` / `gov:` / `cluster:`.
- **`ensure_ascii=False`** on every JSON / SSE frame for Arabic labels.
- **RIL ↔ `the_data` don't join by `record_id`** — clusters bridge to services only via
  the keyword heuristic, so a cluster's propagation edge into the graph exists only when
  the bridge fires (e.g. الباص→Amman Bus, الكتروني/منصة→Sanad).
- `parent_cluster_id` is flat NULL — the root-cause "tree" is one level; clusters are
  pure inflow sources with no parent propagation.
- The simulation module is **import-safe**: missing `mesa`/`networkx` falls back to the
  pure-Python runner producing the identical `SimResult` / `BeforeAfter` shape, so
  `/api/simulate` stays up on a thin deployment.
