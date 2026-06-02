# Deer Graph System — voc360 → Live Graph → Root Cause

End-to-end documentation for the **Deer Graph** subsystem of the AEGIS crisis brain: how a
user gives a **CASE** (a Jordanian public service, a governorate, or an emerging problem
cluster) and watches the system connect to the live **voc360** Voice-of-Customer database,
pull the real citizen signals, build a live dependency graph, rank the **root-cause problem
clusters**, simulate how the problem propagates and how an intervention would damp it, and
render the whole thing as a live visual graph in the browser.

It fuses two upstream patterns onto the real voc360 schema:

- **deer-flow** — an orchestrated, multi-step **LangGraph** state-graph flow
  (`ingest → plan → [human review gate] → segment/cluster → build-graph → root-cause →
  recommend → report`).
- **Mesa** — an **agent-based simulation** of how a complaint / sentiment wave spreads across
  services and governorates, used to test interventions before they are recommended.

Everything is grounded in the **real voc360 schema** (exact table and column names below) and
in the **real backend code** that already ships in `backend/app/` and `frontend/src/`.

---

## 0. The one-paragraph mental model

> A **CASE** is a question about Jordanian public services. The system answers it by walking a
> three-layer chain that lives in voc360:
> **`the_data` (22,882 raw citizen signals) → the live graph (Source → Service → Governorate)
> → `ril_problem_clusters` (the 20 populated root-cause clusters)**.
> The dominant root cause is the cluster with the highest `member_count × severity_avg`. The
> live graph and the ranked root causes are streamed to a React + reactflow canvas as they are
> computed, and a Mesa simulation shows the projected risk curve with and without an
> intervention on the top cluster.

---

## 1. The data source: voc360 (PostgreSQL 16, READ-ONLY)

```
postgresql://<user>@<VOC_HOST>:5432/voc360?sslmode=require
```

- voc360 is a **live** Voice-of-Customer 360 platform for Jordanian public services. We are a
  **read-only** consumer. The backend never writes to it.
- Read-only is enforced **at the session level** on every connection
  (`options="-c default_transaction_read_only=on"`, see `backend/app/db.py`) so a stray
  `INSERT`/`UPDATE` would be rejected by Postgres itself, not just by convention.
- The DSN lives **only** in `backend/.env` as `VOC_DSN` — never hard-coded, never logged.
- **LangGraph checkpoints must go to a *separate, writable* Postgres** — never voc360. voc360
  is read-only and cannot host the `interrupt()` checkpointer (see §6).

### 1.1 The three real tables that form the chain

| Layer | Table | Rows | Role |
|------|-------|-----:|------|
| **Signal** | `the_data` | **22,882** | raw citizen signals (the data-source layer) |
| **Segment** | `ril_text_segments` | **2,001** | extracted Arabic "problem" segments |
| **Membership** | `ril_cluster_members` | **903** | `segment_id → cluster_id` (+ `distance_to_centroid`) |
| **Root cause** | `ril_problem_clusters` | **21** (20 with members) | the canonical problem clusters |

#### `the_data` — the SIGNAL layer (22,882 rows)

Key columns used by the graph:

- `record_id`, `source_record_id`
- `source_type` — the channel kind. Real distribution: `app_review` **≈18.6k**,
  `social_media_sentiment` **≈1.6k**, plus `employee_complaint`, `qr_survey` / `ces_survey` /
  `csat_survey`, `complaint`, and Arabic types `فساد_إداري` (admin-corruption),
  `سوء_الخدمة` (poor-service), `عدم_الرد` (no-response).
- `source_platform`, `source_channel`, `entity_id`
- `service_id` — the public service. Real volumes: **Sanad ≈15.8k**, **Amman Bus ≈2k**,
  `Bekhedmetkom`, `نقل_عام` (public transit), `طرق_وبنية_تحتية` (roads/infrastructure),
  `مراكز_الخدمة` (service centres), `جوازات_السفر` (passports), `الخدمات_الإلكترونية`
  (e-services), …
- `governorate` — **mostly NULL**; materialized Arabic values include `الزرقاء` (Zarqa),
  `إربد` (Irbid), `العقبة` (Aqaba), `السلط` (Salt), `المفرق`, `جرش`.
- `district`, `text` / `text_clean` (Arabic)
- `observed_at` / `date` / `hour` / `day_of_week` / `is_weekend` / `is_ramadan`
- `rating`, `signal_value`
- `sentiment_label` — `negative` / `positive` / `neutral_citizen_sentiment` /
  `high_severity_complaint`
- `confidence`
- `severity` — **`low` 2258 / `medium` 786 / `high` 812 / `critical` 395; NULL for app_reviews.**
- `duplicate_flag`, `spam_flag` — filtered out of the signal counts.

#### `ril_text_segments` — extracted problem segments (2,001 rows)

`segment_id`, `record_id`, `segment_text`, `segment_type` (`'problem'`), `confidence`,
`language` (`'ar'`), `embedding_vector` (text JSON array), `metadata_json`.

> **Load-bearing caveat:** `ril_text_segments.record_id` does **NOT** join to `the_data` ids —
> RIL ran on a **separate snapshot**. The signal layer and the cluster layer are **parallel**;
> they are bridged only at the **service level** (see §3.3).

#### `ril_cluster_members` — membership (903 rows)

`segment_id → cluster_id`, plus `distance_to_centroid`.

#### `ril_problem_clusters` — the ROOT-CAUSE layer (21 clusters; 20 populated)

`cluster_id`, `canonical_label_ar` (**real Arabic problem text**), `canonical_label_en`
(often empty → fall back to AR), `description`, `parent_cluster_id` (hierarchy field —
**currently flat NULL** for all 21, so the cluster tree is one level deep), `entity_id`,
`service_id`, `member_count`, `severity_avg`, `centroid_vector`, `status` (`'active'`),
`first_seen` / `last_seen`.

**Real `member_count` distribution (top clusters):**
`551, 69, 64, 55, 52, 23, 18, 9, 9, 9, 8, 7, …`

**The real top problem clusters** (from `canonical_label_ar`):

| `canonical_label_ar` | gloss | ~members |
|---|---|---:|
| `رسوم الخدمة المستعجلة` | urgent-service fees | **551** (dominant) |
| `تأخير دعم صندوق المعونة` | National-Aid-Fund support delays | high |
| `الباص السريع` | BRT bus | high |
| `منصة تكافل` | Takaful platform | mid |

> Because `canonical_label_en` is frequently empty, **all** rendering and reporting falls back
> to `canonical_label_ar`, and **all** JSON/SSE must be emitted with `ensure_ascii=False` so
> Arabic survives the wire intact.

### 1.2 Other voc360 tables (available, not yet in the core graph)

`pm_gam_calls` (≈126k municipality call logs), `pm_bkhidmatkom_complaints` (≈4k),
`pm_mol_complaints` (MoL), `pm_moh_complaints` (MoH),
`social_sentiment_signals` / `telegram` / `tiktok`, `google_review_data`, `youtube_data`,
`pm_surveys`, `pm_kpi_summary`, `forecast_questions`, `jordan_public`.

---

## 2. What a CASE is

A **CASE** is one opaque selector string. Three kinds:

| Kind | Example | Resolves to |
|------|---------|-------------|
| **Service** | `Sanad`, `Amman Bus`, `نقل_عام`, `جوازات_السفر` | filter `the_data.service_id` |
| **Governorate** | `الزرقاء`, `إربد` | filter `the_data.governorate` |
| **Problem cluster** | a `cluster_id` | an emerging `ril_problem_clusters` row |
| **`all` / empty** | (default) | the whole platform, top-16 services |

In the current backend the case is a plain service id (or `all`); the graph builder passes it
straight into the parameterized SQL as `%(svc)s` (NULL ⇒ "all services"). Only the **service**
kind can bridge both subgraphs, because that is the only join key shared by `the_data` and the
RIL tables.

---

## 3. The live graph model

The graph is **two parallel subgraphs**, bridged at the service level.

### 3.1 Signal subgraph (from `the_data`)

```
Case ──channel──▶ Source(source_type) ──reports──▶ Service(service_id) ──affects──▶ Governorate
```

- Every edge weight is a **count** of rows in `the_data`.
- Each Service node carries a **render tone** computed from its severity mix:
  `alert` if `≥30%` of severity-rated signals are `high`/`critical`, `warn` if `≥10%`, else
  `calm`. (app_review rows have NULL severity and so do not push a service toward `alert`.)

### 3.2 Cluster subgraph (from the RIL tables)

```
Case ──diagnoses──▶ "Root Causes" hub ──cluster──▶ ProblemCluster(cluster_id)
ProblemCluster ──part_of──▶ parent      (only when parent_cluster_id ≠ NULL — currently never)
```

- Cluster node `value` = `member_count`; tone from `severity_avg`.

### 3.3 The bridge (`root_cause` edges)

Because RIL ↔ `the_data` do **not** join by `record_id`, a cluster is linked back to the
service it concerns by a **first-hit Arabic keyword heuristic** on `canonical_label_ar`
(only emitted if that service node exists in the current graph):

| Keyword(s) in `canonical_label_ar` | bridges to service |
|---|---|
| `باص` / `الباص` / `brt` / `نقل` / `مواقف` / `دوار` | `Amman Bus` |
| `الكتروني` / `إلكترون` / `منصة` / `تطبيق` / `sanad` | `Sanad` |
| `شارع` / `طريق` / `بنية` / `حفر` | `طرق_وبنية_تحتية` |
| `معونة` / `تكافل` / `دعم` / `صندوق` | National Aid (no top service node ⇒ no edge yet) |

### 3.4 Node / edge contract (shared across networkx, Mesa, reactflow)

Node ids are **stable, hashable keys** used identically by the backend networkx graph, the
Mesa `NetworkGrid`, and the reactflow canvas:

```
case::<case>     src::<source_type>   svc::<service_id>
gov::<governorate>   rchub   cl::<cluster_id[:8]>
```

**`GraphNode`** `{ id, type, label, value, severity, x, y, label_ar?, members?, severity_avg? }`
where `type ∈ {case, source, service, governorate, rchub, cluster}`, `value` → node size,
`severity ∈ {alert, warn, calm, neutral}` → colour, `x/y` → **server-side layered layout**
(the client honours them; no client-side dagre).

**`GraphEdge`** `{ source, target, weight, kind }` where
`kind ∈ {channel, reports, affects, diagnoses, cluster, root_cause}`. `weight` → stroke width
(`log10`-scaled). `root_cause` / `cluster` / `diagnoses` edges render **animated + danger-red**.

The whole response is `Graph = { case, nodes, edges, stats:{signals, services, sources, clusters} }`.

This contract is implemented verbatim in **`backend/app/graph_builder.py`** and consumed by
**`frontend/src/lib/voc.ts`** + **`frontend/src/components/LiveGraph.tsx`**.

---

## 4. The root-cause ranking

The root cause is **deterministic** — no LLM, fully auditable. Ranked directly in SQL against
`ril_problem_clusters`:

```sql
select cluster_id, canonical_label_ar, canonical_label_en,
       coalesce(member_count,0)  as member_count,
       coalesce(severity_avg,0)  as severity_avg,
       coalesce(member_count,0) * (0.5 + coalesce(severity_avg,0)) as score
from ril_problem_clusters
where coalesce(member_count,0) > 1
order by score desc
limit %(lim)s;
```

> **Why `0.5 +`?** `severity_avg` in the live data is nearly flat (≈`0.40`) across clusters, so
> a bare `member_count × severity_avg` would be a near-monotone function of `member_count`. The
> `0.5 +` floor keeps `member_count` the dominant signal while still letting severity break
> ties — i.e. the top cluster `رسوم الخدمة المستعجلة` (551 members) wins decisively.

**Evidence** for each ranked cause comes from real DB rows, joining membership to segment text:

```sql
select s.segment_text
from ril_cluster_members m
join ril_text_segments  s on s.segment_id = m.segment_id
where m.cluster_id = %(cid)s
limit 3;
```

This is implemented in **`backend/app/rootcause.py`** (`rank_root_causes(limit)` +
`recommend(top)`).

---

## 5. The simulation (Mesa agent-based propagation)

Mesa models how a **complaint/sentiment wave** spreads across the service graph, and how
**damping the top root-cause cluster** changes the trajectory. It answers: *"if we fix the
National-Aid-Fund / urgent-fees cluster on its owning service, how much does platform-wide
negativity drop, and how fast?"*

> The backend ships a **lightweight analytic stand-in** for the simulation today
> (`POST /api/simulate` in `backend/app/main.py`): it seeds risk from the share of `alert`
> service nodes and returns two risk curves (`no_action`, `with_intervention`). The Mesa
> version below is the drop-in replacement wired through the same endpoint and the same node
> ids. **Both are import-safe**: Mesa is an *optional* dependency and the system degrades to
> the analytic curve if Mesa is absent.

### 5.1 The Mesa model (one agent per graph node)

```python
import mesa
import networkx as nx
from mesa.space import NetworkGrid
from mesa.datacollection import DataCollector


class NodeAgent(mesa.Agent):
    """One sentiment carrier per service/governorate/source/cluster node."""
    def __init__(self, model, sentiment=0.0, severity=0.0, volume=0,
                 kind="service", is_root_cause=False):
        super().__init__(model)              # Mesa 3: NO unique_id; auto-registers
        self.sentiment = sentiment           # 0..1 negativity, seeded from the_data
        self.severity = severity             # severity_avg / critical+high load, NULL→0.0
        self.volume = volume
        self.kind = kind
        self.is_root_cause = is_root_cause

    @property
    def node_id(self):
        return self.pos                      # pos == the stable graph key

    def step(self):
        if self.is_root_cause:
            self.sentiment = min(1.0, self.sentiment + self.model.inflow)   # keeps re-seeding pressure
        nbrs = self.model.grid.get_neighbors(self.pos, include_center=False)
        if nbrs:
            avg = sum(a.sentiment for a in nbrs) / len(nbrs)
            self.sentiment += self.model.spread_rate * (avg - self.sentiment)  # contagion
        self.sentiment = min(1.0, self.sentiment * self.model.decay)           # decay


class PropagationModel(mesa.Model):
    def __init__(self, graph, spread_rate=0.30, decay=0.985, inflow=0.05,
                 root_cause_nodes=None, intervention_node=None,
                 intervention_strength=0.0, seed=None):
        super().__init__(seed=seed)          # MANDATORY: seeds rng, agents, running, steps
        self.spread_rate, self.decay, self.inflow = spread_rate, decay, inflow
        self.grid = NetworkGrid(graph)
        root_cause_nodes = set(root_cause_nodes or [])

        for node, data in graph.nodes(data=True):
            a = NodeAgent(
                self,
                sentiment=float(data.get("sentiment", 0.0)),
                severity=float(data.get("severity", 0.0)),   # NULL-safe default
                volume=int(data.get("volume", 0)),
                kind=data.get("kind", "service"),
                is_root_cause=(node in root_cause_nodes),
            )
            self.grid.place_agent(a, node)

        # INTERVENTION: damp one node (e.g. fix the top cluster on Sanad)
        if intervention_node is not None and intervention_node in graph:
            for a in self.grid.get_cell_list_contents([intervention_node]):
                a.sentiment *= (1 - intervention_strength)
                a.is_root_cause = False      # stop re-seeding the fixed cluster

        self.datacollector = DataCollector(
            model_reporters={
                "step":             "steps",
                "mean_negativity":  lambda m: sum(a.sentiment for a in m.agents) / len(m.agents),
                "complaint_volume": lambda m: sum(a.sentiment * a.volume for a in m.agents),
                "n_critical":       lambda m: sum(1 for a in m.agents if a.sentiment > 0.7),
            },
            agent_reporters={"sentiment": "sentiment", "kind": "kind"},
            tables={"Events": ["step", "node", "action"]},
        )
        self.datacollector.collect(self)     # tick-0 snapshot

    def step(self):
        self.agents.shuffle_do("step")       # random-order activation (no scheduler in Mesa 3)
        self.datacollector.collect(self)
```

### 5.2 Headless runner + before/after A-B

```python
from dataclasses import dataclass, asdict


@dataclass
class SimResult:
    series: list          # [{step, mean_negativity, complaint_volume, n_critical}]
    final_by_node: dict   # {node_id: sentiment}
    critical_nodes: list  # node_ids with sentiment > 0.7 at the end
    params: dict
    events: list


def run_simulation(graph, steps=50, spread_rate=0.30, decay=0.985, inflow=0.05,
                   root_cause_nodes=None, intervention_node=None,
                   intervention_strength=0.0, seed=42) -> SimResult:
    model = PropagationModel(
        graph, spread_rate=spread_rate, decay=decay, inflow=inflow,
        root_cause_nodes=root_cause_nodes, intervention_node=intervention_node,
        intervention_strength=intervention_strength, seed=seed,
    )
    for _ in range(steps):                   # manual loop — never model.run_model() in a request
        model.step()
    mdf = model.datacollector.get_model_vars_dataframe()
    adf = model.datacollector.get_agent_vars_dataframe()
    final = adf.xs(steps, level="Step")["sentiment"].to_dict()
    return SimResult(
        series=mdf.to_dict(orient="records"),
        final_by_node=final,
        critical_nodes=[n for n, v in final.items() if v > 0.7],
        params={"steps": steps, "spread_rate": spread_rate, "decay": decay,
                "inflow": inflow, "intervention_node": intervention_node,
                "intervention_strength": intervention_strength, "seed": seed},
        events=model.datacollector.get_table_dataframe("Events").to_dict("records"),
    )


def run_before_after(graph, *, intervention_node, intervention_strength=0.6,
                     root_cause_nodes=None, **kw) -> dict:
    before = run_simulation(graph, root_cause_nodes=root_cause_nodes, **kw)
    after  = run_simulation(graph, root_cause_nodes=root_cause_nodes,
                            intervention_node=intervention_node,
                            intervention_strength=intervention_strength, **kw)
    b, a = before.series[-1], after.series[-1]
    return {
        "before": asdict(before), "after": asdict(after),
        "delta": {
            "mean_negativity_final": round(b["mean_negativity"] - a["mean_negativity"], 4),
            "n_critical_final": b["n_critical"] - a["n_critical"],
            "peak_mean_negativity": round(max(s["mean_negativity"] for s in before.series), 4),
        },
    }
```

**Mesa gotchas baked into the design:**

- Pin `mesa>=3.1,<4` (Mesa 4 alpha changes `Model.__init__` and drops `batch_run`).
- `super().__init__(seed=seed)` is **mandatory**; pass `seed` **xor** `rng`, never both.
- **No `unique_id`** on agents (auto-assigned); no scheduler — use `self.agents.shuffle_do(...)`.
- Every agent must be initialised with `sentiment`/`severity` defaults so `DataCollector` never
  hits a missing attribute (app_review `severity` is NULL → default `0.0`).
- A Mesa run is **synchronous CPU work**: build the graph from voc360 **before** the threadpool,
  then run inside `run_in_threadpool(...)`. Fresh model per request; never share across threads.
- Same `seed` ⇒ identical replay (audit trail).
- For intervention sweeps use `mesa.batch_run(..., number_processes=1)` inside FastAPI.

---

## 6. The deer-flow flow (LangGraph state graph)

deer-flow gives the orchestrated, operator-gated multi-step flow. **Keep the deer-flow `State`
+ `interrupt()` + `Command(goto)` + `astream` / `Command(resume)` skeleton verbatim; change only
the node set and the `goto` targets.** Pin deer-flow at the v1 line (commit `2e010a4619` /
branch `main-1.x`) — `main` is a v2 rewrite with no `src/graph`.

### 6.1 Node map (deer-flow → AEGIS)

| deer-flow node | AEGIS node | role | data touch |
|---|---|---|---|
| `coordinator` | `case_intake` | resolve CASE + locale `ar` | none |
| `background_investigator` | `ingest` | `SELECT the_data` filtered by case, drop spam/dup → `signals` | voc360 |
| `planner` | `planner` | emit typed `Plan`; `has_enough_context` short-circuits to `report` | LLM |
| `human_feedback` | `human_feedback` | **review gate — copy verbatim** (`interrupt()`) | — |
| `research_team` | `research_team` | no-op router | — |
| `researcher` | `segment_cluster` | pull `ril_text_segments` / `ril_cluster_members` / `ril_problem_clusters` | voc360 |
| `coder` | `build_graph` | networkx two-subgraph build → `graph_json` | — |
| `analyst` | `root_cause` | rank `member_count × (0.5+severity_avg)` | voc360 |
| (new lane) | `simulate` | Mesa before/after on the top cluster | — |
| `reporter` | `report` | synthesize ranked causes + recommendation → `final_report` | LLM |

`StepType` is reused verbatim: `RESEARCH` → ingest / segment-cluster, `PROCESSING` →
build-graph + Mesa, `ANALYSIS` → rank / diagnose.

### 6.2 The graph wiring

```
START → case_intake → ingest → planner → [human gate]
        → research_team ⇄ { segment_cluster | build_graph | root_cause }
        → (drain) → simulate → recommend → critic → report → END
```

The dispatcher `continue_to_running_research_team` is **deer-flow-verbatim** (only the return
targets change): it walks the typed `Plan.steps`, routes each unfinished step by `step_type` to
the matching lane, and drains to `recommend` once every step has an `execution_res`.

Compile with a **`PostgresSaver` on a separate writable DB** (never voc360); set
`recursion_limit ≥ 40` so the human-gate pause does not trip the cap.

### 6.3 The human review gate (copy verbatim, localize the prompt)

```python
def human_feedback_node(state, config) -> Command[Literal["planner","research_team","report","__end__"]]:
    if not state.get("auto_accepted_plan", False):
        feedback = interrupt("يرجى مراجعة خطة تحليل السبب الجذري")  # pauses; persists by thread_id
        fb = str(feedback).strip().upper()
        if fb.startswith("[EDIT_PLAN]"):
            return Command(update={"messages": [HumanMessage(content=feedback, name="feedback")]},
                           goto="planner")
        elif fb.startswith("[ACCEPTED]"):
            pass
        else:
            return Command(goto="planner")
    plan = Plan.model_validate(json.loads(repair_json_output(state["current_plan"])))
    return Command(update={"current_plan": plan,
                           "plan_iterations": state.get("plan_iterations", 0) + 1},
                   goto="research_team")
```

- `interrupt()` is a **no-op / infinite loop without a checkpointer** — compiling with one is
  mandatory.
- The gate sits **upstream of `recommend`**, so the operator approves the *investigation* before
  any recommendation is produced.
- `[EDIT_PLAN]` examples that drive a re-rank: `focus on صندوق المعونة`, `drop spam_flag rows`,
  `weight severity higher`.

### 6.4 State (`CaseState`)

```python
class CaseState(MessagesState):
    locale: str = "ar"
    case: str = ""                  # service_id | governorate | cluster_id
    signals: list[dict] = []        # rows from the_data
    signal_stats: dict = {}
    segments: list = []             # ril_text_segments / ril_cluster_members
    clusters: list[dict] = []       # ril_problem_clusters
    graph_json: dict | None = None  # networkx node-link → reactflow
    root_causes: list[dict] = []    # {cluster_id, canonical_label_ar, member_count, severity_avg, score, rank}
    mesa_results: dict | None = None
    recommendation: str = ""
    citations: list[dict] = []      # real DB rows, appended LAST
    current_plan: "Plan | str" = ""
    plan_iterations: int = 0
    auto_accepted_plan: bool = False
    final_report: str = ""
```

### 6.5 Tools (`tools/voc360.py`, `@tool @log_io`, psycopg READ-ONLY @ `$VOC360_DSN`)

`voc360_pull_signals(case, limit)`, `voc360_signal_stats(case)`,
`voc360_clusters_for_service(service_id)`, `voc360_cluster_members(cluster_ids)`,
`voc360_segments(cluster_ids)`, `voc360_rank_root_causes(service_id)`.

### 6.6 Wiring Mesa into the flow

`simulate_node` runs **after** `root_cause`: it reads `state["root_causes"][0]`, resolves
`cluster:<id>` as the `intervention_node`, calls `run_before_after(...)`, writes
`state["mesa_results"]`, streams `sim_step` / `graph_edge` SSE frames to the same reactflow
canvas, and returns `Command(goto="recommend")`. Its result folds into the report's
"recommended interventions" section.

---

## 7. The API (FastAPI, reading voc360)

All endpoints are in **`backend/app/main.py`**. Cross-cutting rules: psycopg connections opened
**read-only**; every JSON/SSE frame uses `ensure_ascii=False` for Arabic; CORS allows the Vite
dev origin.

| Method · Route | Purpose | Returns |
|---|---|---|
| `GET /api/health` | DB connectivity | `{ ok, connected, database, server }` |
| `GET /api/stats` | voc360 row counts | `{ signals~22882, services, sources, governorates, clusters, segments }` |
| `GET /api/cases` | selectable cases | `{ services[], top_root_causes[] }` |
| `GET /api/graph?case=` | the live dependency graph | `Graph` (§3.4) |
| `GET /api/rootcause?limit=` | ranked root causes | `{ root_causes:[RootCause], recommendation }` |
| `POST /api/flow/run?case=` | stream the Deer Graph flow | **NDJSON** of `FlowEvent` |
| `POST /api/simulate?case=&steps=` | propagation sim (before/after) | `{ case, no_action[], with_intervention[], risk_before, risk_after, note }` |

### 7.1 `POST /api/flow/run` — the staged, streamed flow

The endpoint streams **NDJSON**, one `FlowEvent` per line:

```json
{"stage": "...", "status": "running|done", "detail": "...", "data": {...}}
```

The five stages, in order, exactly as the backend emits them:

1. **`connect`** — "Connecting to voc360 (read-only)…" → done with `db.health()`.
2. **`ingest`** — pull citizen signals → `"<N> signals across <M> services"`.
3. **`graph`** — build the dependency graph → `"<nodes> nodes · <edges> edges"`.
4. **`rootcause`** — rank the RIL clusters → top cause's report count.
5. **`recommend`** — draft the recommendation; the final frame carries the full
   `{ graph, root_causes }` payload so the canvas paints the completed graph.

The frontend parses this with the existing `runFlow()` async-generator (`lib/voc.ts`). In the
full deer-flow version this becomes an SSE stream with extra event types (`graph_node`,
`graph_edge`, `signal_count`, `root_cause`, `interrupt`, `message_chunk`, `report`, `error`,
`done`); **resume** = re-POST the same `thread_id` with `interrupt_feedback` →
`Command(resume="[ACCEPTED]" | "[EDIT_PLAN] …")`.

### 7.2 `POST /api/simulate`

Build the graph from voc360 **before** running the simulation; in the Mesa version this is
`run_in_threadpool(run_before_after, ...)` with `intervention_node` auto-targeted to the top
ranked cluster (`cluster:<id>`) when the caller does not specify one. Returns the two risk
curves and `risk_before` / `risk_after`.

---

## 8. The frontend live graph (React + reactflow)

The live graph is **`frontend/src/components/LiveGraph.tsx`**, talking to the API through
**`frontend/src/lib/voc.ts`**. It owns state + fetch and renders three regions: a header
(health pill + "Run Deer Graph Flow" button), the reactflow `GraphCanvas`, and a 360° right
aside (flow stages, recommendation card, ranked root-cause list).

### 8.1 What the user sees

1. **On load** it calls `getHealth()`, `getGraph()`, `getRootCause()` in parallel — the canvas
   paints the default (`all`) graph and the right rail fills with ranked causes. The header
   shows `voc360 connected · 22,882 signals · N services · M root causes`.
2. **Press "Run Deer Graph Flow"** → `runFlow()` streams the five stages; each `FlowEvent`
   updates a checklist (spinner → green check) and the recommendation card.
3. **The graph itself**: case (blue) → sources (grey) → services (severity-coloured) →
   governorates (grey); separately, the case → red **Root Causes** hub → cluster nodes, with
   animated red `root_cause` bridges from a service to its dominant cluster. Arabic labels
   render RTL via `isAr = s => /[؀-ۿ]/.test(s)`.

### 8.2 Rendering contract (already implemented)

- **Severity → colour:** `{ alert:#F04359, warn:#FBBF24, calm:#34D399, neutral:#8B8D96 }`.
  Structural overrides: case → blue `#3B82F6`, rchub → danger red, source/governorate → muted.
- **Node size:** `w = min(230, 96 + sqrt(value) * 5)`; severity-tinted glow via `boxShadow`.
- **Edge stroke:** `min(4, 0.6 + log10(weight+1) * 1.3)`; `root_cause` / `cluster` / `diagnoses`
  edges are **animated** and red.
- **Layout is server-side** (nodes carry `x/y`); reactflow uses `fitView padding 0.18`,
  `minZoom 0.15`, `nodesConnectable={false}`, `elementsSelectable={false}`, with `Background`
  dots, `MiniMap` (colour = node colour), and `Controls`.
- Tailwind tokens: bg `#0A0A0B`, card `#131417`, border `#212228`, txt `#ECEDEE`,
  muted `#8B8D96`.

### 8.3 The one open gap (Mesa chart)

`POST /api/simulate` currently has **no frontend consumer**. To close the loop:

1. Add a `Simulation` type + `runSimulate(case)` to `lib/voc.ts`.
2. Add `sim` + `case` state, a `CaseSelect` (from `/api/cases`), and a `SimChart`
   (recharts — `recharts@3.8` is already a dep; mirror `SignalVolume.tsx`) to `LiveGraph.tsx`.
3. Fire `runSimulate(case)` after the `recommend.done` event and plot `no_action` vs
   `with_intervention` so the operator sees the projected risk curve with and without the fix.

---

## 9. End-to-end walkthrough — a single CASE

> **CASE = `Amman Bus`** (≈2k signals; the `الباص السريع` / BRT cluster is a known hotspot).

1. **User** selects `Amman Bus` and presses **Run Deer Graph Flow**.
2. **`connect`** — backend opens a read-only psycopg session to voc360 and confirms
   `current_database() = voc360`.
3. **`ingest`** — `SELECT … from the_data where service_id = 'Amman Bus' and spam_flag is not
   true and duplicate_flag is not true`; emits e.g. *"~2k signals across N services"*.
4. **`graph`** — builds Source → Service → Governorate from `the_data` counts and the Root-Cause
   hub → cluster subgraph from RIL; the keyword bridge (`باص`/`brt`/`نقل`) draws an animated
   `root_cause` edge `svc::Amman Bus → cl::<BRT cluster>`. The reactflow canvas paints it live.
5. **`rootcause`** — ranks `ril_problem_clusters` by `member_count × (0.5 + severity_avg)`; the
   BRT cluster `الباص السريع` surfaces near the top with three real `segment_text` evidence
   snippets pulled from `ril_text_segments`.
6. **`simulate`** (Mesa) — seeds one `NodeAgent` per graph node from the_data volumes/severity,
   marks the BRT cluster `is_root_cause`, and runs `run_before_after(intervention_node="cluster:
   <BRT id>", intervention_strength=0.6)`. The `SimChart` shows platform `mean_negativity`
   climbing under **no action** and bending down once the BRT cluster is damped.
7. **`recommend`** — *"Prioritise the root cause 'الباص السريع' (N citizen reports, severity X).
   Route to the owning agency, brief the relevant service team, and track whether complaint
   volume on this cluster falls after action."*
8. **(deer-flow full version)** the **human gate** lets the operator `[ACCEPTED]` or
   `[EDIT_PLAN] weight severity higher` before the recommendation is finalized into the report,
   with real DB rows appended LAST as citations.

---

## 10. Setup & run

### 10.1 Backend

```bash
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt        # fastapi, uvicorn, psycopg[binary], networkx, …
                                        # langgraph + mesa are OPTIONAL (graceful fallback)
cp .env.example .env                    # set VOC_DSN=postgresql://…@<VOC_HOST>:5432/voc360?sslmode=require
uvicorn app.main:app --reload --port 8000
```

`requirements.txt` (real):

```
fastapi==0.115.6
uvicorn[standard]==0.34.0
psycopg[binary]==3.2.4
python-dotenv==1.0.1
networkx==3.4.2
pydantic==2.10.4
# optional — the Deer Graph flow & Mesa simulation degrade gracefully if absent
langgraph==0.2.60
mesa==3.1.1
```

### 10.2 Frontend

```bash
cd frontend
npm install
npm run dev        # Vite dev server on http://localhost:5173 → calls VITE_API (default :8000)
```

### 10.3 Graceful degradation (import-safe)

- **No `VOC_DSN`** → `db._connect()` raises a clear `RuntimeError`; `/api/health` returns
  `{ ok: false, error: … }` and the frontend shows a red "db offline" pill instead of crashing.
- **No `mesa`** → `/api/simulate` falls back to the lightweight analytic risk curve already in
  `main.py` (`import mesa` is guarded; the Mesa runner is only used when present).
- **No `langgraph`** → `/api/flow/run` still streams the staged NDJSON flow (the staged
  generator in `main.py` does not require LangGraph); the full multi-agent flow with the human
  gate is the optional upgrade.

This keeps the core **data → graph → root-cause** loop runnable with only `fastapi` + `psycopg`
+ `networkx` installed; deer-flow and Mesa are additive.

---

## 11. Load-bearing caveats (do not forget these)

1. **RIL ↔ `the_data` do not join by `record_id`** — they are parallel snapshots, bridged only
   at the **service level** via the Arabic keyword heuristic.
2. **`governorate` is mostly NULL** — the Service → Governorate layer is sparse; never assume a
   governorate for a signal.
3. **`severity` is NULL for app_reviews** — always default to `0.0` / `low` in Mesa and never
   let a NULL push a service to `alert`.
4. **`parent_cluster_id` is flat NULL** — the cluster hierarchy is one level deep; `part_of`
   edges are reserved but never emitted yet.
5. **`canonical_label_en` is frequently empty** — always fall back to `canonical_label_ar`.
6. **Arabic everywhere** — every JSON/SSE/NDJSON frame must use `ensure_ascii=False`; the
   frontend detects RTL with `/[؀-ۿ]/`.
7. **voc360 is READ-ONLY** — LangGraph checkpoints go to a *separate writable* Postgres.
8. **Node ids are stable & hashable** across networkx, Mesa (`agent.pos`), and reactflow — use
   the `src::` / `svc::` / `gov::` / `cl::` / `case::` / `rchub` keys directly.
9. **The ranking `0.5 +` floor matters** — `severity_avg` is nearly flat (~0.40), so it keeps
   `member_count` dominant while letting severity break ties.
