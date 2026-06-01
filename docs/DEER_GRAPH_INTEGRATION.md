# Deer Graph Integration — adapting deer-flow's LangGraph flow onto voc360

**Component of the AEGIS crisis brain.** This document is the authoritative write-up of how
[ByteDance **deer-flow**](https://github.com/bytedance/deer-flow)'s multi-agent LangGraph flow is
re-targeted into the **Deer Graph**: a live pipeline that takes a *CASE* (a service, a governorate,
or an emerging problem cluster), pulls real Voice-of-Customer signals out of the **voc360** PostgreSQL
database, builds a dependency graph, ranks the root-cause problem clusters behind the case, passes
through a **human review gate**, and renders the whole thing as a live `reactflow` graph.

It covers, in order:

1. What deer-flow is and how its graph is wired.
2. The exact node-by-node mapping (deer-flow → Deer Graph), grounded in the real voc360 schema.
3. The shared `CaseState`.
4. The voc360 query each node runs (real table and column names).
5. The human-review interrupt gate.
6. How the LangGraph flow co-exists with the already-shipped staged backend (`backend/app/`).
7. How to run it, end to end.

> **Pin.** Use deer-flow **v1** (commit `2e010a4619`, the `main-1.x`-era tree that still ships
> `src/graph`). The current `main` is a v2 *SuperAgent* rewrite with **no `src/graph`** — do **not**
> build against it. We keep deer-flow's `State` + `interrupt()` + `Command(goto=…)` + `astream` /
> `Command(resume=…)` skeleton **verbatim** and change only the node bodies and the `goto` targets.

---

## 1. What deer-flow is

deer-flow is an open "Deep Research" agent framework. It is, concretely, a **LangGraph `StateGraph`**
of role-named nodes that pass a single shared `State` dict around, with a typed multi-step `Plan`
and a **human-in-the-loop approval gate** between planning and execution.

### 1.1 deer-flow's own node set

| deer-flow node | role |
|---|---|
| `coordinator` | entry point; resolves the user's request and hands off to the planner via a `handoff_to_planner` tool call. Does no research itself. |
| `background_investigator` | optional pre-search (Tavily) that seeds the planner with context before it writes the plan. |
| `planner` | a reasoning LLM that emits a **typed `Plan`** — a list of `Step`s, each tagged with a `StepType` (`RESEARCH`, `PROCESSING`, `ANALYSIS`). Has a `has_enough_context` short-circuit straight to the reporter. |
| `human_feedback` | **the review gate.** Calls LangGraph `interrupt()`, pauses, and resumes on `[ACCEPTED]` / `[EDIT_PLAN] …`. |
| `research_team` | a **no-op router**; the actual routing lives in a conditional edge (`continue_to_running_research_team`) that dispatches the next un-executed step by its `StepType`. |
| `researcher` | executes `RESEARCH` steps (web/RAG tools) as a ReAct agent. |
| `coder` | executes `PROCESSING` steps in a Python REPL / sandbox. |
| `reporter` | a basic LLM that synthesizes all `observations` into the final report. |

### 1.2 deer-flow's graph shape (verbatim wiring we keep)

```
START → coordinator → background_investigator → planner → human_feedback
        ┌──────────────────────────────────────────────┘
        ▼
     research_team ⇄ { researcher | coder }   (loop until every Step has execution_res)
        │
        ▼
     reporter → END
```

The two load-bearing pieces of machinery we **reuse unchanged**:

- **The plan/step loop.** `research_team` is re-entered after every step; the conditional edge
  `continue_to_running_research_team` looks at `state["current_plan"].steps`, finds the first step with
  no `execution_res`, and routes by its `StepType`. When all steps are done it routes back to
  `planner` (which, seeing `has_enough_context`, ends).
- **The interrupt gate.** `human_feedback` uses `interrupt()`, which **requires a checkpointer** to
  work — without one it is a no-op / infinite loop. The thread is keyed by `thread_id`; resuming the
  same `thread_id` with `Command(resume="[ACCEPTED]")` continues exactly where it paused.

This is everything we need. The adaptation is purely a re-skin: same skeleton, voc360-flavoured nodes.

---

## 2. The Deer Graph — node-by-node mapping

We rename the four canonical deer-flow roles to their voc360 jobs and remap the three `StepType`s to
the three stages of the *data → graph → root-cause* chain. **We do not invent new control flow.**

### 2.1 Role mapping (the four canonical roles)

| deer-flow role | Deer Graph node | what it does on voc360 | LLM? |
|---|---|---|---|
| **coordinator** | `case_intake` | resolve the CASE string (`service:<id>` / `gov:<governorate>` / `cluster:<id>`) + locale (`ar`); hand off to planner. **No DB.** | no |
| **background_investigator** | `ingest` | psycopg READ-ONLY `SELECT … FROM the_data` filtered by the case → `signals` + `signal_stats`. The voc360 analogue of Tavily — it seeds the planner with real numbers. | no |
| **planner** | `planner` | reasoning LLM; emits the typed `Plan`. `has_enough_context` → straight to `report`. | yes (reasoning) |
| **(gate)** | `human_feedback` | **the review gate — copied verbatim.** `interrupt()`, then `[ACCEPTED]` / `[EDIT_PLAN]`. | no |
| **research_team** | `research_team` | no-op router (`pass`); dispatching lives in the conditional edge. | no |
| **researcher** (`RESEARCH`) | `segment_cluster` | pull the RIL layer: `ril_text_segments`, `ril_cluster_members`, `ril_problem_clusters`. | no (deterministic) |
| **coder** (`PROCESSING`) | `build_graph` | build the two-subgraph networkx graph → `graph_json` (node-link, reactflow-ready); optionally hand off to Mesa. | no (deterministic) |
| *(analysis lane)* | `root_cause` | rank `ril_problem_clusters` by `member_count * (0.5 + severity_avg)`; attach `evidence`. | no (deterministic) |
| **reporter** | `report` | basic LLM; synthesize ranked root causes + recommendation → `final_report`, with real DB rows appended LAST as citations. | yes (basic) |

> **`StepType` remap (reuse the enum verbatim — do not rename it):**
> `RESEARCH` → ingest / segment-cluster (pull data), `PROCESSING` → build-graph (+ Mesa),
> `ANALYSIS` → rank / diagnose. The planner emits steps in these three types; the existing
> dispatcher routes them to the three lanes with no change beyond the target node names.

### 2.2 The Deer Graph shape

```
START
  │
  ▼
case_intake ──► ingest ──► planner ──► human_feedback   ◄── interrupt() gate
   (coord.)    (bg inv.)   (reason)         │
                                            │  [ACCEPTED]
                                            ▼
                                      research_team ⇄ { segment_cluster | build_graph | root_cause }
                                            │  (loop until every Step.execution_res is set)
                                            ▼
                                          report ──► END
                                         (reporter)
```

The conditional edge out of `research_team` is deer-flow's `continue_to_running_research_team`
**verbatim** — only the three return targets changed:

```python
from src.prompts.planner_model import StepType   # reused unchanged

def continue_to_running_research_team(state: "CaseState"):
    plan = state.get("current_plan")
    if not plan or not getattr(plan, "steps", None):
        return "planner"
    if all(s.execution_res for s in plan.steps):
        return "planner"                                  # all steps done → planner ends
    step = next((s for s in plan.steps if not s.execution_res), None)
    if not step:
        return "planner"
    if step.step_type == StepType.RESEARCH:   return "segment_cluster"   # was "researcher"
    if step.step_type == StepType.PROCESSING: return "build_graph"       # was "coder"
    if step.step_type == StepType.ANALYSIS:   return "root_cause"        # (analysis lane)
    return "planner"
```

### 2.3 Mapping onto the real *data → graph → root-cause* chain

The voc360 data has three physical layers; each maps to a lane:

```
 the_data (22,882 rows)            ── SIGNAL layer  ──►  ingest (RESEARCH)
   Source(source_type) → Service(service_id) → Governorate
   each signal carries severity + sentiment

 ril_text_segments (2,001)         ── PROBLEM layer ──►  segment_cluster (RESEARCH)
   + ril_cluster_members (903)
   Segment ── member_of ──► ProblemCluster

 ril_problem_clusters (21; 20 pop.) ── ROOT-CAUSE layer ──►  root_cause (ANALYSIS)
   ProblemCluster ── part_of ──► parent   (hierarchy currently flat: parent_cluster_id all NULL)

 ROOT CAUSE = dominant ProblemCluster(s) by member_count × severity_avg
```

`build_graph` (PROCESSING) stitches the SIGNAL layer and the PROBLEM/ROOT-CAUSE layer into one
`graph_json`. **Critical caveat:** `ril_*` does **not** join `the_data` on `record_id` (the RIL
pipeline ran on a separate snapshot), so the graph is **two parallel subgraphs** bridged only at the
**Service / `entity_id`** level via an Arabic-keyword heuristic — never at the row level.

---

## 3. The shared State — `CaseState`

deer-flow's `State` extends LangGraph's `MessagesState` (so `messages` has a built-in reducer). We
keep every plan-loop field deer-flow relies on (`current_plan`, `plan_iterations`,
`auto_accepted_plan`, `observations`, `goto`) and add the voc360 payload fields. One file,
`src/graph/types.py`:

```python
from __future__ import annotations
from dataclasses import field
from typing import Optional
from langgraph.graph import MessagesState
from src.prompts.planner_model import Plan   # deer-flow's typed Plan/Step/StepType — reused verbatim


class CaseState(MessagesState):
    # ----- deer-flow plan-loop fields (kept verbatim) -----
    locale: str = "ar"
    current_plan: Optional[Plan | str] = None
    plan_iterations: int = 0
    auto_accepted_plan: bool = False
    observations: list[str] = field(default_factory=list)   # accumulator → report
    goto: str = "planner"

    # ----- the CASE (replaces deer-flow's research_topic) -----
    # one opaque string: "service:<id>" | "gov:<governorate>" | "cluster:<id>"
    case: str = ""

    # ----- SIGNAL layer (the_data) -----
    signals: list[dict] = field(default_factory=list)       # rows from the_data
    signal_stats: dict = field(default_factory=dict)        # by_source_type / by_severity / by_sentiment

    # ----- PROBLEM layer (RIL) -----
    segments: list[dict] = field(default_factory=list)      # ril_text_segments
    cluster_members: list[dict] = field(default_factory=list)  # ril_cluster_members
    clusters: list[dict] = field(default_factory=list)      # ril_problem_clusters

    # ----- graph + diagnosis -----
    graph_json: Optional[dict] = None                       # networkx node-link → reactflow
    root_causes: list[dict] = field(default_factory=list)   # ranked clusters {cluster_id, canonical_label_ar, member_count, severity_avg, score, rank, evidence_record_ids}
    mesa_results: Optional[dict] = None                     # populated by the Mesa simulate lane (see MESA_SIMULATION.md)
    recommendation: str = ""
    critic_verdict: dict = field(default_factory=dict)
    citations: list[dict] = field(default_factory=list)     # REAL DB rows, appended LAST
    final_report: str = ""
```

Every node has the same signature:

```python
from langgraph.types import Command
from langchain_core.runnables import RunnableConfig
from typing import Literal

def some_node(state: CaseState, config: RunnableConfig) -> Command[Literal[...]]:
    ...
    return Command(update={...}, goto="<next-node>")
```

`case:` parsing is shared across the whole stack (one helper) so node ids stay stable across
networkx, Mesa, and reactflow:

```python
def parse_case(case: str) -> tuple[str, str | None]:
    """'service:Sanad' -> ('service','Sanad'); '' -> ('all', None)."""
    if not case or case == "all":
        return "all", None
    kind, _, value = case.partition(":")
    return kind, (value or None)
```

Stable, hashable node-id keys used everywhere: `src:<source_type>`, `svc:<service_id>`,
`gov:<governorate>`, `cluster:<cluster_id>`, `seg:<segment_id>`.

---

## 4. The voc360 queries each node runs

All queries are **READ-ONLY**, parameterised (`%(name)s`), and run against the live voc360 DB
(`postgresql://…@<VOC_HOST>:5432/voc360?sslmode=require`). They live in `src/tools/voc360.py`
as `@tool @log_io` functions and are also called directly by the deterministic nodes. The connection
helper mirrors the already-shipped `backend/app/db.py`:

```python
import os, psycopg
DSN = os.environ["VOC360_DSN"]   # in .env ONLY; referenced from conf.yaml as $VOC360_DSN

def fetchall(sql, params=None):
    # session-level read-only — this service never writes
    with psycopg.connect(DSN, options="-c default_transaction_read_only=on") as conn, conn.cursor() as cur:
        cur.execute(sql, params or {})
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
```

### 4.1 `case_intake` (coordinator) — no DB

Resolves and validates the case string, sets `locale="ar"`, emits a hand-off message, and routes to
`ingest`. No query.

### 4.2 `ingest` (background_investigator) — pull the SIGNAL layer

`voc360_pull_signals(case, limit)` — drops spam/duplicates, scopes to the case:

```sql
-- the_data is the SIGNAL / data-source layer (22,882 rows)
SELECT record_id, source_type, source_platform, source_channel,
       service_id, entity_id, governorate, district,
       text_clean, observed_at, rating, signal_value,
       sentiment_label, confidence, severity
FROM the_data
WHERE coalesce(spam_flag, false) = false
  AND coalesce(duplicate_flag, false) = false
  AND ( %(svc)s::text IS NULL OR service_id   = %(svc)s::text )   -- service:<id> case
  AND ( %(gov)s::text IS NULL OR governorate  = %(gov)s::text )   -- gov:<governorate> case
ORDER BY observed_at DESC NULLS LAST
LIMIT %(limit)s;
```

`voc360_signal_stats(case)` — the headline distributions the planner reasons over:

```sql
SELECT
  count(*)                                                                  AS signals,
  count(*) FILTER (WHERE severity IN ('high','critical'))                   AS high_severity,
  count(*) FILTER (WHERE sentiment_label LIKE 'negative%'
                      OR sentiment_label = 'high_severity_complaint')       AS negative,
  count(DISTINCT service_id)   FILTER (WHERE service_id IS NOT NULL)        AS services,
  count(DISTINCT source_type)                                               AS sources,
  count(DISTINCT governorate)  FILTER (WHERE governorate IS NOT NULL)       AS governorates
FROM the_data
WHERE coalesce(spam_flag,false)=false AND coalesce(duplicate_flag,false)=false
  AND ( %(svc)s::text IS NULL OR service_id  = %(svc)s::text )
  AND ( %(gov)s::text IS NULL OR governorate = %(gov)s::text );
```

Writes `signals`, `signal_stats`; routes to `planner`.

> **Schema reality used here:** `source_type` is dominated by `app_review` (18.6k) and
> `social_media_sentiment` (1.6k), with Arabic types like `سوء_الخدمة` / `فساد_إداري` / `عدم_الرد`.
> `service_id` is led by `Sanad` (15.8k) and `Amman Bus` (2k). `severity` is **NULL for every
> app_review**, so all severity gating uses `FILTER (WHERE …)` (NULL-safe) — never a bare comparison.
> `governorate` is mostly NULL (the non-NULL values are Arabic: `الزرقاء`, `إربد`, `العقبة`, …).

### 4.3 `planner` (planner) — no DB

Reads `signal_stats`, emits the typed `Plan`. No query. Routes to `human_feedback` unless
`has_enough_context` (→ `report`) or `plan_iterations >= max_plan_iterations` (→ `report`).

### 4.4 `segment_cluster` (researcher / `RESEARCH`) — pull the PROBLEM layer

`voc360_clusters_for_service(service_id)` — the populated problem clusters (RIL ran on a separate
snapshot, so these are bridged at the service/entity level, not by `record_id`):

```sql
-- ril_problem_clusters is the ROOT-CAUSE layer (21 clusters; 20 with members)
SELECT cluster_id, canonical_label_ar, canonical_label_en, description,
       coalesce(member_count,0) AS member_count,
       coalesce(severity_avg,0) AS severity_avg,
       entity_id, service_id, status, parent_cluster_id
FROM ril_problem_clusters
WHERE coalesce(member_count,0) > 1
  AND ( %(svc)s::text IS NULL OR service_id = %(svc)s::text )
ORDER BY member_count DESC;
```

`voc360_cluster_members(cluster_ids)` and `voc360_segments(cluster_ids)` — the extracted Arabic
problem segments that populate each cluster:

```sql
SELECT m.cluster_id, m.segment_id, m.distance_to_centroid,
       s.segment_text, s.segment_type, s.confidence, s.language
FROM ril_cluster_members m
JOIN ril_text_segments  s ON s.segment_id = m.segment_id
WHERE m.cluster_id = ANY(%(cluster_ids)s)
ORDER BY m.distance_to_centroid ASC;       -- closest-to-centroid = most representative
```

Writes `clusters`, `cluster_members`, `segments`; sets the step's `execution_res`; routes to
`research_team`.

### 4.5 `build_graph` (coder / `PROCESSING`) — build the two-subgraph graph

No new query — it consumes `signals` + `clusters`. It builds the **signal subgraph**
(`Source(source_type) → Service(service_id) → Governorate`, edge `weight = count`, nodes carrying
severity tone + sentiment) and the **cluster subgraph** (`Segment → ProblemCluster → parent`),
bridged at the Service level by the Arabic-keyword heuristic. The exact builder already exists and is
reused verbatim — `backend/app/graph_builder.py::build_graph(case)` — producing
`{case, nodes, edges, stats}`. The node-by-node SQL it issues (the count rollups) is:

```sql
-- Source → Service counts (gated on the top-16 services by volume)
WITH top_svc AS (
  SELECT service_id FROM the_data WHERE service_id IS NOT NULL
    AND ( %(svc)s::text IS NULL OR service_id = %(svc)s::text )
  GROUP BY 1 ORDER BY count(*) DESC LIMIT 16
)
SELECT source_type, service_id, count(*) AS c
FROM the_data
WHERE service_id IN (SELECT service_id FROM top_svc) AND source_type IS NOT NULL
GROUP BY 1,2 ORDER BY c DESC;

-- Service → Governorate counts (governorate non-NULL only — it is mostly NULL)
WITH top_svc AS (SELECT service_id FROM the_data WHERE service_id IS NOT NULL
                 GROUP BY 1 ORDER BY count(*) DESC LIMIT 16)
SELECT service_id, governorate, count(*) AS c
FROM the_data
WHERE governorate IS NOT NULL AND service_id IN (SELECT service_id FROM top_svc)
  AND ( %(svc)s::text IS NULL OR service_id = %(svc)s::text )
GROUP BY 1,2 ORDER BY c DESC LIMIT 18;
```

The Arabic-keyword bridge (`canonical_label_ar` lowered, first hit, edge added only if the service
node exists) — e.g. `باص`/`brt`/`نقل` → **Amman Bus**, `معونة`/`صندوق`/`تكافل` → National Aid /
Takaful, `الكتروني`/`منصة`/`sanad` → **Sanad**, `شارع`/`طريق`/`حفر` → `طرق_وبنية_تحتية`.

Writes `graph_json`; streams `graph_node` / `graph_edge` SSE frames so reactflow renders LIVE;
routes to `research_team`.

### 4.6 `root_cause` (analysis / `ANALYSIS`) — rank the ROOT-CAUSE layer

`voc360_rank_root_causes(service_id)` — the dominant problem clusters, scored:

```sql
-- ROOT CAUSE = dominant ProblemCluster(s) by member_count × severity.
-- The "0.5 +" floor matters because severity_avg is a flat ~0.40 across clusters.
SELECT cluster_id, canonical_label_ar, canonical_label_en,
       coalesce(member_count,0) AS member_count,
       coalesce(severity_avg,0) AS severity_avg,
       coalesce(member_count,0) * (0.5 + coalesce(severity_avg,0)) AS score
FROM ril_problem_clusters
WHERE coalesce(member_count,0) > 1
  AND ( %(svc)s::text IS NULL OR service_id = %(svc)s::text )
ORDER BY score DESC
LIMIT %(limit)s;
```

Plus real evidence per cluster (closest segments — appended to citations LAST so the LLM can't
fabricate Arabic labels):

```sql
SELECT s.segment_text
FROM ril_cluster_members m
JOIN ril_text_segments  s ON s.segment_id = m.segment_id
WHERE m.cluster_id = %(cid)s
LIMIT 3;
```

The top cluster on the live data is `رسوم الخدمة المستعجلة` (urgent-service fees, **551 members,
score ≈ 495.9**), ahead of `الباص السريع` (BRT), `تأخير دعم صندوق المعونة` (National-Aid-Fund delays)
and `منصة تكافل` (Takaful platform). This is the exact ranking
`backend/app/rootcause.py::rank_root_causes()` already produces and the doc grounds the LLM in it.

Writes `root_causes`; routes to `research_team` (which, all steps done, returns to `planner` → end).

### 4.7 `report` (reporter) — synthesize

Basic LLM. Reads `root_causes`, `recommendation`, `graph_json`, `mesa_results`. Renders the Arabic
crisis brief. **Citations = real DB rows** (`cluster_id`, `canonical_label_ar`, `member_count`,
`severity_avg`, sample `segment_text`, sample `record_id`) appended **LAST**, after the LLM text, so
the model cannot invent Arabic labels or record ids. Writes `final_report`; routes to `END`.

---

## 5. The human review gate

This is the heart of the deer-flow pattern and the one node we copy **verbatim** (only the prompt is
localized to Arabic). It sits **between `planner` and `research_team`** — i.e. the operator approves
the *investigation plan* before any clustering, graph-building, or diagnosis runs, and therefore
before any recommendation is produced.

```python
import json
from langchain_core.messages import HumanMessage
from langgraph.types import Command, interrupt
from src.prompts.planner_model import Plan
from src.utils.json_utils import repair_json_output

def human_feedback_node(state: CaseState, config) \
        -> Command[Literal["planner", "research_team", "report", "__end__"]]:
    if not state.get("auto_accepted_plan", False):
        feedback = interrupt("يرجى مراجعة خطة تحليل السبب الجذري قبل التنفيذ")  # PAUSE — persists by thread_id
        fb = str(feedback).strip().upper()
        if fb.startswith("[EDIT_PLAN]"):
            return Command(
                update={"messages": [HumanMessage(content=feedback, name="feedback")]},
                goto="planner",
            )
        elif fb.startswith("[ACCEPTED]"):
            pass
        else:
            return Command(goto="planner")        # any other reply → re-plan

    plan = Plan.model_validate(json.loads(repair_json_output(state["current_plan"])))
    return Command(
        update={"current_plan": plan, "plan_iterations": state.get("plan_iterations", 0) + 1},
        goto="research_team",
    )
```

**Rules (all load-bearing):**

- `interrupt()` is a **no-op / infinite loop without a checkpointer** — compiling with one is
  **mandatory** (see §6).
- Resume = re-POST the same `thread_id` with `interrupt_feedback`; the server turns it into
  `Command(resume=f"[{interrupt_feedback}]")`.
- `[ACCEPTED]` proceeds; `[EDIT_PLAN] …` re-plans with the operator's note as a `HumanMessage`.
  Edit examples that drive a re-rank: `[EDIT_PLAN] focus on صندوق المعونة`,
  `[EDIT_PLAN] drop spam_flag rows`, `[EDIT_PLAN] weight severity higher`.
- `auto_accepted_plan=true` skips the pause (used by `/api/flow/run` smoke tests and the staged
  fallback).

---

## 6. Building, compiling & checkpointing the graph

`src/graph/builder.py` — deer-flow's `_build_base_graph` with node bodies swapped:

```python
from langgraph.graph import StateGraph, START, END
from .types import CaseState
from . import nodes

def _build_base_graph() -> StateGraph:
    b = StateGraph(CaseState)
    b.add_edge(START, "case_intake")
    b.add_node("case_intake",     nodes.case_intake_node)      # was coordinator
    b.add_node("ingest",          nodes.ingest_node)           # was background_investigator
    b.add_node("planner",         nodes.planner_node)
    b.add_node("human_feedback",  nodes.human_feedback_node)   # verbatim gate
    b.add_node("research_team",   nodes.research_team_node)    # no-op router
    b.add_node("segment_cluster", nodes.segment_cluster_node)  # RESEARCH lane (was researcher)
    b.add_node("build_graph",     nodes.build_graph_node)      # PROCESSING lane (was coder)
    b.add_node("root_cause",      nodes.root_cause_node)       # ANALYSIS lane
    b.add_node("report",          nodes.report_node)           # was reporter
    b.add_edge("ingest", "planner")
    b.add_conditional_edges(
        "research_team",
        nodes.continue_to_running_research_team,
        ["planner", "segment_cluster", "build_graph", "root_cause"],
    )
    b.add_edge("report", END)
    return b
```

```python
import os

def build_deer_graph():
    """Compile with a PostgresSaver on a SEPARATE WRITABLE db (never voc360).
    Falls back to an in-memory saver / staged flow when deps or checkpoint db are absent."""
    builder = _build_base_graph()
    ckpt_url = os.environ.get("LANGGRAPH_CHECKPOINT_DB_URL")
    if ckpt_url and os.environ.get("LANGGRAPH_CHECKPOINT_SAVER", "").lower() == "true":
        from langgraph.checkpoint.postgres import PostgresSaver   # langgraph-checkpoint-postgres
        saver = PostgresSaver.from_conn_string(ckpt_url)          # writable, NOT read-only voc360
        saver.setup()
        return builder.compile(checkpointer=saver)
    # dev fallback — interrupt() still works in a single process with an in-memory saver
    from langgraph.checkpoint.memory import MemorySaver
    return builder.compile(checkpointer=MemorySaver())
```

**Checkpointer rules:**

- The checkpoint DB **must be a separate writable Postgres** — voc360 is opened READ-ONLY and the
  flow would fail to persist state there. Set in `.env`:
  `LANGGRAPH_CHECKPOINT_SAVER=true` and `LANGGRAPH_CHECKPOINT_DB_URL=postgresql://…/aegis_state`.
- `MemorySaver` is fine for local dev (the interrupt still pauses within one process) but loses state
  across restarts — never use it in prod.
- Raise the recursion limit above 30 (`recursion_limit ≥ 40–50`) so the human-gate pause + the
  per-step research loop don't trip the cap.

---

## 7. Co-existence with the already-shipped staged backend

A working **staged** version of this exact chain already ships in `backend/app/` and powers the
current frontend. The LangGraph flow is **import-safe and additive**: when `langgraph` (or the
checkpoint extras) are missing, or no checkpoint DB is configured, the API serves the staged
generator instead, so nothing breaks.

| concern | staged backend (always available) | LangGraph Deer Graph (when deps present) |
|---|---|---|
| connect | `db.health()` | `case_intake` |
| ingest | `graph_builder.build_graph(case)` | `ingest` + `voc360_pull_signals/_signal_stats` |
| graph | same `build_graph(case)` → `graph_json` | `build_graph` node (same builder) |
| root cause | `rootcause.rank_root_causes()` | `root_cause` node (same SQL/score) |
| human gate | *(skipped; `auto_accepted_plan=true`)* | `human_feedback` `interrupt()` |
| recommend | `rootcause.recommend(top)` | `report` (LLM) |
| transport | `POST /api/flow/run` → NDJSON | `POST /api/flow/run` → SSE w/ `interrupt` frames |

The deterministic nodes (`ingest`, `build_graph`, `root_cause`) call the **same**
`graph_builder` / `rootcause` functions, so the two paths produce identical graphs and rankings —
the LangGraph path only adds the **plan loop + human gate + LLM narration** on top. Wire the LLM path
behind a feature flag:

```python
try:
    from src.graph.builder import build_deer_graph
    DEER = build_deer_graph()          # None if langgraph/checkpointer unavailable
except Exception:
    DEER = None                        # fall back to the staged _flow() generator
```

> **Note.** The staged `_flow()` generator in `backend/app/main.py` emits stages
> `connect → ingest → graph → rootcause → recommend` (no `human_feedback`, since it runs
> `auto_accepted_plan`). The LangGraph path adds the interrupt frame; the frontend's `runFlow()`
> async-generator already tolerates extra/unknown stages.

### 7.1 SSE / streaming for reactflow (Arabic-safe)

Mirror deer-flow's `_astream_workflow_generator`. The two non-negotiables:

```python
from fastapi.responses import StreamingResponse

async def stream_case(case_id: str, thread_id: str, resume: str | None = None):
    workflow_input = ({"case": case_id, "auto_accepted_plan": False}
                      if resume is None else Command(resume=f"[{resume}]"))
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 50}

    async for agent, _, event in DEER.astream(
            workflow_input, config=config,
            stream_mode=["messages", "updates"], subgraphs=True):
        if isinstance(event, dict) and "__interrupt__" in event:
            intr = event["__interrupt__"][0]
            yield _sse("interrupt", {"thread_id": thread_id, "content": intr.value,
                                     "options": [{"text": "Accept", "value": "accepted"},
                                                 {"text": "Edit",   "value": "edit_plan"}]})
        # push graph_json on every build_graph update so reactflow renders LIVE:
        # yield _sse("graph_node", …) / _sse("graph_edge", …) / _sse("root_cause", …)

def _sse(kind: str, data: dict) -> str:
    # ensure_ascii=False is MANDATORY for text_clean / canonical_label_ar
    return f"event: {kind}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
```

1. `subgraphs=True` + `stream_mode=["messages","updates"]` so you see both LLM token chunks and node
   state updates (and the `__interrupt__` sentinel).
2. **Every** frame uses `json.dumps(…, ensure_ascii=False)` — Arabic `text_clean` and
   `canonical_label_ar` must not be `\uXXXX`-escaped or the RTL frontend renders mojibake.

The frontend (`frontend/src/components/LiveGraph.tsx`) already consumes this: it lays out nodes by
`{x,y}`, colours by `severity` tone, animates `root_cause`/`cluster`/`diagnoses` edges in danger-red,
renders Arabic labels RTL via `isAr()`, and walks the flow stages in the right panel.

---

## 8. How to run it

### 8.1 Configuration

`backend/.env` (voc360 DSN lives here **only**; never commit it):

```bash
# READ-ONLY voc360 data source
VOC_DSN=postgresql://<user>:<pass>@<VOC_HOST>:5432/voc360?sslmode=require
VOC360_DSN=postgresql://<user>:<pass>@<VOC_HOST>:5432/voc360?sslmode=require

# SEPARATE WRITABLE Postgres for LangGraph checkpoints (NOT voc360)
LANGGRAPH_CHECKPOINT_SAVER=true
LANGGRAPH_CHECKPOINT_DB_URL=postgresql://<user>:<pass>@localhost:5432/aegis_state

# LLMs (deer-flow conf.yaml references these; node→type map below)
#   reasoning  → planner + (gate prompts)      e.g. ChatDeepSeek
#   basic      → root-cause explainer + report  (set token_limit, e.g. 128000)
```

`conf.yaml` maps node LLM types and references `$VOC360_DSN`. **Set `token_limit` on `BASIC_MODEL`**
(e.g. `128000`) — context compression is off when unset and the 551-member top cluster plus its
segments will overflow the report context.

### 8.2 Install (deps degrade gracefully)

```bash
python -m venv backend/.venv && source backend/.venv/bin/activate
pip install -r backend/requirements.txt          # fastapi, psycopg, networkx, langgraph, mesa
# for the persistent human-gate checkpointer:
pip install "langgraph-checkpoint-postgres>=2.0"
```

`backend/requirements.txt` already pins the optional deps and the README notes them as optional —
the Deer Graph flow and Mesa simulation **degrade gracefully if absent** (the staged `_flow()` runs
instead). `mesa` must be pinned `>=3.1,<4` (Mesa 4 alpha breaks `Model.__init__` and drops
`batch_run`).

### 8.3 Start

```bash
# backend
source backend/.venv/bin/activate
uvicorn app.main:app --reload --app-dir backend --port 8000

# frontend
cd frontend && npm install && npm run dev      # http://localhost:5173 (CORS already allows it)
```

### 8.4 Drive the flow

```bash
# health / data sanity
curl -s localhost:8000/api/health
curl -s localhost:8000/api/stats          # ~22,882 signals · 21 clusters · 2,001 segments
curl -s localhost:8000/api/cases          # selectable services + top root causes

# the live graph for a case
curl -s 'localhost:8000/api/graph?case=service:Sanad' | jq '.stats'
curl -s 'localhost:8000/api/rootcause?limit=8'        # ranked clusters + recommendation

# the staged flow (NDJSON, no gate) — always available
curl -sN -X POST 'localhost:8000/api/flow/run?case=service:Sanad'
```

**LangGraph path with the human gate** — start a case, it pauses at `human_feedback`, then resume:

```bash
# 1) start → streams until the interrupt frame (thread_id is yours to choose)
curl -sN -X POST localhost:8000/api/case/stream \
  -H 'content-type: application/json' \
  -d '{"case":"service:Sanad","thread_id":"case-sanad-001"}'
#    … event: interrupt  data: {"content":"يرجى مراجعة خطة تحليل السبب الجذري…", "options":[…]}

# 2) approve (same thread_id) → resumes through research_team → report → END
curl -sN -X POST localhost:8000/api/case/stream \
  -H 'content-type: application/json' \
  -d '{"thread_id":"case-sanad-001","interrupt_feedback":"ACCEPTED"}'

# 2b) or edit the plan instead:
#  -d '{"thread_id":"case-sanad-001","interrupt_feedback":"EDIT_PLAN focus on صندوق المعونة"}'
```

In the UI, click **Run Deer Graph Flow**: the stages light up
(`connect → ingest → graph → rootcause → recommend`), nodes stream onto the reactflow canvas, and the
ranked root causes appear in the right panel with their Arabic labels and `members × severity` bars.

---

## 9. Load-bearing caveats (do not regress)

- **RIL ↔ the_data do NOT join on `record_id`.** They are parallel snapshots. `build_graph` makes
  **two subgraphs** (signal: `source→service→governorate`; cluster: `segment→cluster→parent`) bridged
  **only at the Service / `entity_id`** level via the Arabic-keyword heuristic.
- **NULLs are everywhere.** `governorate` is mostly NULL (and Arabic when present); `severity` is NULL
  for every `app_review`; `canonical_label_en` is frequently empty → fall back to `canonical_label_ar`.
  Use `coalesce(…)` / `FILTER (WHERE …)`, never bare comparisons.
- **`parent_cluster_id` is flat NULL** across all 21 clusters → the root-cause "tree" is one level for
  now; the `part_of` edge is emitted only when `parent_cluster_id` is non-NULL (currently never).
- **`severity_avg` is a flat ~0.40**, so the ranking score keeps the `member_count * (0.5 + severity_avg)`
  floor — without the `0.5 +`, low-severity-but-high-volume clusters (the real signal) get suppressed.
- **Arabic safety:** every JSON / SSE frame uses `ensure_ascii=False`; the frontend renders RTL via
  `isAr()`.
- **Checkpointer ≠ voc360.** The interrupt gate needs a writable checkpoint DB; voc360 is READ-ONLY.
- **Citations = real DB rows, appended LAST** in the report so the LLM cannot fabricate Arabic labels
  or `record_id`s.
- **Mesa is not part of deer-flow.** It is an additional `simulate` lane scheduled after `root_cause`
  (it reads `root_causes[0]`, resolves `cluster:<id>` as the intervention node, writes `mesa_results`,
  streams `sim_step`/`graph_edge` frames, and folds into the report's interventions section). See
  `docs/MESA_SIMULATION.md` for the agent-based model.

---

## 10. File map

| file | role |
|---|---|
| `src/graph/types.py` | `CaseState` (§3) — extends `MessagesState`, reuses deer-flow `Plan/Step/StepType`. |
| `src/graph/nodes.py` | the 9 nodes (§2); `human_feedback_node` verbatim; `continue_to_running_research_team` verbatim-but-retargeted. |
| `src/graph/builder.py` | `_build_base_graph` + `build_deer_graph` with `PostgresSaver` / graceful fallback (§6). |
| `src/tools/voc360.py` | `@tool @log_io` READ-ONLY psycopg queries (§4) against `$VOC360_DSN`. |
| `backend/app/db.py` | shipped READ-ONLY voc360 connection helper (reused). |
| `backend/app/graph_builder.py` | shipped two-subgraph builder → `graph_json` (reused by `build_graph` node). |
| `backend/app/rootcause.py` | shipped cluster ranking + evidence + recommendation (reused by `root_cause` node). |
| `backend/app/main.py` | FastAPI; staged `_flow()` fallback + LangGraph stream/resume endpoints. |
| `frontend/src/components/LiveGraph.tsx` | reactflow live graph + flow-stage panel + ranked root causes. |
| `frontend/src/lib/voc.ts` | typed client: `getGraph`, `getRootCause`, `runFlow`, `runSimulate`. |
| `conf.yaml` / `.env` | LLM-type map + `$VOC360_DSN` + checkpoint DB (§8.1). |
