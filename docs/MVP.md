# MVP Specification — Crisis-Solving Brain

**Minimum viable build · the dashboard wizard walkthrough · full stack · API · PostgreSQL schema · 2026-05-31**

The MVP delivers **one end-to-end loop** — ingest → graph → correlate → root-cause → generate solution → simulate-validate → authorize — operated through a **guided dashboard wizard**, demonstrated on the Zarqa water-pipe cascade. Full stack: **React + FastAPI (Python) + PostgreSQL** (with AGE/pgvector/PostGIS/TimescaleDB). See `TECH_STACK.md` for the complete stack and `SYSTEM_REQUIREMENTS.pdf` for the deep requirements.

---

## 1. MVP Scope & the Dashboard Wizard Walkthrough

The MVP is **one end-to-end loop, fully wired, on one Domain Pack**. A duty officer opens the **Zarqa** case and walks the wizard from raw signals to an *authorized* intervention. The brain must surface `PIPE-ZN-44` as the causal apex — not the loud 911/hospital symptoms — and prove the fix by re-simulation. The engine, the LangGraph swarm, and the React wizard are real; everything domain-specific lives in the Zarqa pack (ontology, propagation rules, WNTR/EPANET adapter, intervention library).

### 1.1 In / Out for v1

| IN (v1) | OUT (deferred) |
|---|---|
| Single seeded case (Zarqa water cascade) replayed from a fixture | Live external connectors (SCADA, 911 CAD, traffic APIs) |
| Full loop: Ingest→Resolve→Correlate→Root-Cause→Risk→Generate→Validate→Recommend→Learn | Multi-domain packs (power, epidemic) — engine stays pack-agnostic so they slot later |
| LangGraph swarm with real nodes; deterministic Zarqa outputs | Auto-execution of interventions (we stop at *authorize*) |
| PostgreSQL 16 + **AGE** (incident graph), **pgvector** (signal embeddings), **PostGIS** (geo), **TimescaleDB** (signal series) | Multi-tenant RBAC beyond one `duty_officer` + one `commander` role |
| WNTR/EPANET re-sim for before/after risk | OR-Tools full intervention optimization (v1 = library + ranking) |
| 7-step wizard, React Flow graph, MapLibre map, WS streaming | Mobile layout, i18n, offline |
| Audit trail of the decision to S3/MinIO | Grafana/Loki dashboards (OTel hooks stubbed) |

### 1.2 Architecture at a glance

```
 React 18 + Vite + Tailwind + shadcn/ui
 ├─ TanStack Query (REST)  Zustand (wizard step state)
 ├─ React Flow (incident graph)   MapLibre GL (Zarqa map)
 └─ native WS  ── /ws/cases/{id} ──┐
                                   ▼
        FastAPI (REST + WS)  ── Arq + Redis (run the loop async)
                │                    │
                ▼                    ▼
        LangGraph swarm  ───►  PostgreSQL 16
   ingest→resolve→correlate→        AGE | pgvector | PostGIS | Timescale
   rootcause→risk→generate→         S3/MinIO (sim artifacts, audit)
   validate→recommend→learn
```

`POST /api/cases/{id}/run` enqueues an Arq job; each LangGraph node emits a `case.step` event over `/ws/cases/{id}`; the wizard advances as steps complete.

### 1.3 Wizard Walkthrough — the Zarqa demo script

The officer logs in, sees the **National Crisis Cockpit** (risk index spiking for Zarqa North), clicks **"Open Case ZARQA-2025-08"**. The wizard overlay launches at Step 1.

**Step 1 — Signals (live feed).** The Signal Explorer streams the seeded fixture over WS. The officer sees a TimescaleDB-backed feed: `911_call_volume` +320%, `hospital_ed_occupancy` 94%, `traffic_congestion` on Highway 35, `scada_pressure` on `PIPE-ZN-44` dropping to 0.4 bar.
```json
{"ts":"2025-08-14T09:42:11Z","source":"SCADA","entity":"PIPE-ZN-44",
 "metric":"pressure_bar","value":0.4,"z":-6.1,"embedding_id":"vec_8831"}
```
PyOD flags the pressure z-score. Click **Next →** to stitch.

**Step 2 — Stitched Incident (graph).** Splink resolves duplicate entities (3 "Zarqa General Hospital" spellings → one node). The **Incident Graph** renders from AGE via React Flow: nodes (pipe, hospital, junction, dispatch zone), edges = propagation links. The officer drags nodes, hovers an edge to see `supplies_water_to (lag=12m)`. The graph already *looks* like the rupture feeds everything downstream, but nothing is asserted yet.

**Step 3 — Root Cause (causal apex + evidence).** The Root-Cause Panel runs DoWhy/PyRCA over the graph. It ranks candidates by causal score, demoting high-volume symptoms:

| Rank | Node | Causal score | Why |
|---|---|---|---|
| 1 | **PIPE-ZN-44** | 0.91 | upstream apex; pressure drop precedes all downstream spikes |
| 2 | Zarqa Gen. Hospital | 0.22 | symptom — strain *follows* supply loss |
| 3 | 911 Dispatch Z-North | 0.08 | loudest signal, lowest causal score |

The apex card highlights `PIPE-ZN-44` with an evidence trail (time-lag, propagation path, anomaly). Officer clicks **Accept Root Cause**.

**Step 4 — Candidate Solutions.** The Solution/Intervention Review pulls from the Zarqa pack's intervention library. Three candidates, scored:

| # | Intervention | Est. risk ↓ | ETA | Cost |
|---|---|---|---|---|
| A | **Isolate ZN-44 + bypass via ZN-12 + 4 tankers** | high | 35m | med |
| B | Isolate only | med | 15m | low |
| C | Tankers only | low | 50m | high |

Officer selects **A**, clicks **Validate**.

**Step 5 — Validation / Simulation (before/after).** The Simulation Console fires a WNTR/EPANET re-sim via Arq. Recharts shows before/after: predicted 911 volume returns toward baseline, hospital occupancy −18 pts, network pressure restored. Artifact (sim run JSON, hydraulic plot) saved to MinIO and linked.

```
Risk index  BEFORE ████████████ 0.87
            AFTER  ███           0.21   ✓ validated
```

**Step 6 — Decide & Authorize (human gate).** The Decision Hub presents the validated plan, evidence, and sim diff. The officer (role `commander`) types a justification and clicks **Authorize**. A signed `decision` row is written; the audit bundle exports to S3/MinIO. *No execution happens* — v1 stops here.

**Step 7 — Outcome / Learn.** The Learn node records the case (root cause, chosen intervention, sim-predicted vs. logged outcome) back into Postgres and the pgvector store, so similar future signal patterns retrieve this resolution. Wizard shows the closed-loop summary and a **"Replay this case"** button.

### 1.4 MVP Acceptance Test

```gherkin
Scenario: Zarqa cascade resolves to PIPE-ZN-44 with a validated fix
  Given the seeded case "ZARQA-2025-08" with a +320% 911 surge
  When I run the full loop via POST /api/cases/ZARQA-2025-08/run
  Then the root_cause node id == "PIPE-ZN-44"
   And its causal_score > every symptom node (hospital, 911 zone)
   And the recommended intervention == "isolate+bypass+tanker"
   And the post-sim risk_index < 0.30 and < 0.5 * pre_sim risk_index
   And a "decision" row exists with status="authorized"
   And an audit artifact is persisted to S3/MinIO
```

This is the single demoable, CI-gated truth condition for v1: **right root cause, validated fix, authorized — proven by re-simulation.**

---

## 2. Full-Stack Architecture (MVP)

The MVP is a four-tier system: a **React/TS SPA** talks to a **FastAPI** edge over REST (commands/queries) and one WebSocket (live case stream). FastAPI dispatches long work to a **LangGraph engine/swarm** running under **Arq workers**, which read/write a single **PostgreSQL 16** instance (AGE graph, pgvector embeddings, PostGIS geo, TimescaleDB signal hypertables). **Redis** is cache, Arq queue, and the pub/sub bus that fans engine events back out to the WebSocket. The engine + swarm are domain-agnostic; the Zarqa **Water Domain Pack** plugs in ontology, propagation rules, the WNTR/EPANET simulator adapter, and an OR-Tools intervention library.

### 2.1 Component / Deployment Diagram

```
┌──────────────────────── Browser (React 18 + TS, Vite) ────────────────────────┐
│ Cockpit · Signal Explorer · Incident Graph(React Flow) · Root-Cause · Sim      │
│ Decision Hub · Wizard overlay   |  TanStack Query (server)  Zustand (UI)       │
│ MapLibre GL (PostGIS tiles) · visx/Recharts · Motion                           │
└──────────────┬───────────────────────────────────────────┬────────────────────┘
        REST (JSON, /api/v1)                          WS  /ws/case/{id}
               │                                            │ (live frames)
┌──────────────▼────────────────────────────────────────────▼────────────────────┐
│                         FastAPI (Pydantic v2, OAuth2/OIDC + RBAC)               │
│  routers: signals · incidents · rootcause · solutions · sim · decisions        │
│  WS hub  ◄── subscribes Redis pubsub `case:{id}:events`                         │
└───────┬──────────────────────────────┬────────────────────────────┬────────────┘
   enqueue jobs (Arq)            sync reads/writes              publish events
        │                              │ (SQLAlchemy 2)               │
┌───────▼──────────────┐    ┌──────────▼───────────┐      ┌──────────▼──────────┐
│  Arq Workers         │    │  PostgreSQL 16        │      │  Redis              │
│  ┌─ LangGraph swarm ─┐│    │  • AGE  (Cypher graph)│      │  cache · queue ·    │
│  │ Ingest→Resolve→   ││◄──►│  • pgvector (embeds)  │      │  pub/sub bus        │
│  │ Correlate→RootCause│    │  • PostGIS (geo)      │      └─────────────────────┘
│  │ →Risk→Solve→       ││    │  • TimescaleDB (TS)   │      ┌─────────────────────┐
│  │ Validate→Recommend ││    └───────────────────────┘      │  S3 / MinIO         │
│  └────────────────────┘│         engine libs:               │  sim runs · audit   │
│  networkx/rustworkx,   │   Splink · PyRCA/DoWhy · PyOD       └─────────────────────┘
│  WNTR/EPANET, OR-Tools │
└────────────────────────┘     docker-compose (dev) · k8s-ready · OTel→Grafana/Loki
```

### 2.2 Request Lifecycle — One Zarqa Case

| # | Stage | Trigger / Path | Service · Lib | Store written |
|---|-------|----------------|---------------|---------------|
| 1 | **Ingest** | `POST /api/v1/signals` (911 surge, SCADA pressure-drop on `PIPE-ZN-44`) | FastAPI validates (Pydantic) → Arq job | TimescaleDB `signal` hypertable; raw → S3 |
| 2 | **Resolve** | LangGraph `resolve` node | Splink dedupe maps "Zarqa New, blk-7" ↔ `ZONE-ZN-7` | AGE entities, pgvector embeddings |
| 3 | **Correlate** | `correlate` node | PyOD anomaly + spatio-temporal join (PostGIS + Timescale) clusters 911/hospital/traffic spikes into one incident | AGE `(:Incident)` + edges |
| 4 | **Graph update** | each node commits | rustworkx in-memory ↔ AGE Cypher `MERGE` | AGE; event → Redis `case:Z1:events` → WS |
| 5 | **Root-Cause** | `rootcause` node | PyRCA/DoWhy walks causal apex; ranks `PIPE-ZN-44` rupture above loud 911/hospital symptoms | AGE `root_cause` flag + scores |
| 6 | **Risk** | `risk` node | propagation rules (Water Pack) score cascade severity | `risk_snapshot` (JSONB) |
| 7 | **Generate-Solution** | `solve` node | OR-Tools selects isolate + bypass + tanker stopgap from intervention library | `solution` rows |
| 8 | **Validate (sim)** | `POST /api/v1/sim/run` → `validate` node | WNTR/EPANET re-simulates network with valves closed; before/after risk delta | sim artifact → S3; `sim_run` |
| 9 | **Recommend** | `recommend` node | ranked solutions + evidence pushed to Decision Hub | `recommendation` |
| 10 | **Decide (human gate)** | `POST /api/v1/decisions/{id}/authorize` | FastAPI RBAC checks duty-officer scope; writes audit | `decision`, `audit_log` |
| 11 | **Learn** | post-decision | outcome embedded (pgvector) for retrieval on future cases | pgvector, AGE |

Every node emits a frame to `case:Z1:events`; the FastAPI WS hub relays it so the Wizard advances Step 1→7 in real time. Frame shape:

```json
{ "case_id": "Z1", "stage": "rootcause", "status": "done",
  "apex": {"id": "PIPE-ZN-44", "type": "TrunkMain", "score": 0.91},
  "demoted": ["SIG-911-surge", "HOSP-strain"], "ts": "2026-05-31T09:14:22Z" }
```

### 2.3 Full Stack

| Layer | Tech | Role |
|-------|------|------|
| UI framework | React 18 + TypeScript, Vite, Tailwind, shadcn/ui (Radix) | SPA, key screens + Wizard overlay |
| Graph canvas | React Flow | Incident dependency graph |
| Geo / charts | MapLibre GL (OSM/PostGIS tiles), visx/Recharts | Map of Zarqa zones; risk/time-series |
| State / realtime | TanStack Query, Zustand, native WebSocket, Motion | Server+UI state, live frames, animation |
| API edge | FastAPI, Pydantic v2, OAuth2/OIDC + RBAC | REST + WS, validation, authz, human gate |
| Orchestration | LangGraph + Arq workers, Celery-optional | Deer-flow swarm; async job execution |
| Engine libs | networkx/rustworkx, Splink/dedupe, PyRCA/DoWhy/causal-learn, PyOD/river, OR-Tools | graph, resolution, root-cause, anomaly, optimization |
| Sim adapter | Mesa/PySD, **WNTR/EPANET** (Water Pack) | Re-simulation / validation |
| ORM / migrations | SQLAlchemy 2, Alembic | Schema + data access |
| Primary store | PostgreSQL 16 + AGE / pgvector / PostGIS / TimescaleDB | Graph, embeddings, geo, signal hypertables |
| Cache / bus / queue | Redis | Cache, Arq queue, pub/sub WS fan-out |
| Artifacts | S3 / MinIO | Sim runs, audit exports |
| Infra / obs | Docker + docker-compose (k8s-ready), GitHub Actions, OpenTelemetry → Grafana/Loki | Deploy, CI, tracing/logs |

---

## 3. API Surface & Contracts (MVP)

The backend is **FastAPI** (Python 3.12, Pydantic v2) over **PostgreSQL 16** (AGE/pgvector/PostGIS/Timescale). All REST lives under `/api/v1`; realtime under `/ws`. The React+TS client consumes REST via TanStack Query and subscribes to WebSocket channels for live signal/risk pushes.

### 3.1 Conventions

- **Auth:** OAuth2/OIDC password+code flow → JWT bearer. `Authorization: Bearer <jwt>` on every call (REST + WS via `?token=`). Claims carry `sub`, `roles` (`duty_officer`, `analyst`, `commander`), `exp`. RBAC enforced per-route; `decisions.authorize` requires `commander`.
- **IDs:** ULIDs (`sig_…`, `inc_…`, `sol_…`, `sim_…`, `dec_…`). Times are ISO-8601 UTC.
- **Pagination:** cursor-based. `?limit=50&cursor=<opaque>` → `{ "items": [...], "next_cursor": "…"|null }`. Max `limit` 200.
- **Errors:** RFC-7807-style envelope, consistent across the surface.

```json
{ "type": "https://errors.crisis.io/validation",
  "title": "Invalid signal payload", "status": 422,
  "detail": "geom.lon out of range", "instance": "/api/v1/signals",
  "errors": [{ "field": "geom.lon", "msg": "must be -180..180" }],
  "trace_id": "otel-9f2c…" }
```

Common codes: `401` (missing/expired JWT), `403` (RBAC), `404`, `409` (state conflict, e.g. authorizing a stale decision), `422` (validation), `429` (rate limit), `503` (engine/sim node down).

### 3.2 Endpoint table

| Method | Path | Purpose | Role |
|---|---|---|---|
| `POST` | `/auth/token` | OAuth2 token (password/code) → JWT | — |
| `GET` | `/signals` | List/stream-replay signals (filter `?source=&since=&bbox=&type=`) | analyst+ |
| `POST` | `/signals` | Ingest a raw signal (also via connectors) | analyst+ |
| `GET` | `/signals/{id}` | Single signal + resolved entities | analyst+ |
| `GET` | `/incidents` | List stitched incidents (`?status=&risk_gte=`) | analyst+ |
| `GET` | `/incidents/{id}` | Incident header + KPIs + member signals | analyst+ |
| `GET` | `/incidents/{id}/graph` | Dependency graph (AGE/Cypher → React Flow nodes/edges) | analyst+ |
| `GET` | `/incidents/{id}/root-cause` | Causal apex + ranked evidence (PyRCA/DoWhy) | analyst+ |
| `GET` | `/incidents/{id}/solutions` | Candidate interventions (OR-Tools ranked) | analyst+ |
| `POST` | `/incidents/{id}/solutions:generate` | Trigger generation (async job) | analyst+ |
| `POST` | `/simulations` | Run before/after sim for a solution (async, WNTR/EPANET) | analyst+ |
| `GET` | `/simulations/{id}` | Sim status + before/after risk artifact | analyst+ |
| `POST` | `/decisions` | Record a decision (propose/reject) | duty_officer+ |
| `POST` | `/decisions/{id}:authorize` | Human gate — authorize intervention | commander |
| `GET` | `/incidents/{id}/wizard` | Get wizard state (current step, gates) | duty_officer+ |
| `PUT` | `/incidents/{id}/wizard` | Advance/set wizard step | duty_officer+ |

Long-running ops (`solutions:generate`, `simulations`) return `202 Accepted` + `{ "job_id", "status_url" }`; clients poll the `GET` resource or watch the WS `incident` channel.

### 3.3 WebSocket channels

Single endpoint `wss://…/ws?token=<jwt>`. Client sends `{ "op": "subscribe", "channel": "<name>", "incident_id?": "…" }`. Server frames: `{ "channel", "event", "data", "ts" }`.

| Channel | Events | Payload |
|---|---|---|
| `signals` | `signal.new`, `signal.resolved` | Signal as in REST; firehose for Signal Explorer |
| `incident:{id}` | `incident.updated`, `graph.delta`, `rootcause.ready`, `solution.ready`, `sim.progress`, `sim.done`, `wizard.step`, `decision.authorized` | Partial deltas matching the REST shape |
| `risk` | `risk.index` | National cockpit gauge: `{ "national_index": 0.71, "by_governorate": {…} }` |

### 3.4 Worked examples (Zarqa)

**Ingest the 911 surge signal** — `POST /api/v1/signals`

```json
{ "source": "911-CAD", "type": "call_volume_anomaly",
  "ts": "2026-05-31T08:42:00Z",
  "geom": { "lon": 36.0876, "lat": 32.0728 },
  "metrics": { "baseline": 100, "current": 420, "delta_pct": 320 },
  "raw": { "text": "no water multiple blocks Zarqa New district" } }
```

→ `201 Created`

```json
{ "id": "sig_01J8Z911SURGE",
  "type": "call_volume_anomaly", "severity": 0.82,
  "embedding_id": "vec_91f0", "resolved_entities": ["zone:ZN", "facility:HOSP-ZN-CENTRAL"],
  "incident_id": "inc_01J8ZARQACASCADE" }
```

**Root cause** — `GET /api/v1/incidents/inc_01J8ZARQACASCADE/root-cause`

```json
{ "incident_id": "inc_01J8ZARQACASCADE",
  "apex": { "node_id": "asset:PIPE-ZN-44", "label": "Trunk-main rupture PIPE-ZN-44",
            "kind": "water.pipe", "confidence": 0.91 },
  "method": "PyRCA+DoWhy",
  "ranked_causes": [
    { "node_id": "asset:PIPE-ZN-44", "score": 0.91, "is_apex": true },
    { "node_id": "facility:HOSP-ZN-CENTRAL", "score": 0.34, "is_apex": false },
    { "node_id": "signal:911-surge", "score": 0.12, "is_apex": false }],
  "evidence": [
    { "type": "graph_path", "path": ["asset:PIPE-ZN-44","zone:ZN","facility:HOSP-ZN-CENTRAL","signal:911-surge"] },
    { "type": "timeseries", "metric": "pressure_kpa", "asset": "PIPE-ZN-44",
      "drop": { "from": 380, "to": 40, "at": "2026-05-31T08:31:00Z" } }],
  "note": "Loud 911/hospital symptoms ranked below the pressure-loss apex." }
```

**Authorize the fix** — `POST /api/v1/decisions/dec_01J8ZBYPASS:authorize`

```json
{ "rationale": "Sim shows risk 0.86→0.21; isolate + bypass + 6 tankers approved.",
  "valves": ["VLV-ZN-12","VLV-ZN-13"], "sim_id": "sim_01J8ZSIMRUN" }
```

→ `200 OK`

```json
{ "id": "dec_01J8ZBYPASS", "status": "authorized",
  "intervention": "isolate+bypass+tanker_stopgap",
  "authorized_by": "user_cmdr_07", "authorized_at": "2026-05-31T09:05:00Z",
  "wizard_step": 7, "projected_risk": { "before": 0.86, "after": 0.21 } }
```

A `409` is returned if `sim_id` is stale or the decision was already actioned, guarding the human gate against race conditions.

---

## 4. Data Model — PostgreSQL Schema (MVP)

PostgreSQL 16 is the single primary store. Four extensions divide the labor: **TimescaleDB** for signal time-series, **Apache AGE** for the dependency graph, **PostGIS** for geo, **pgvector** for embeddings. One database, one transaction boundary, one backup — the engine reads/writes everything through SQLAlchemy 2.

```sql
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS age;
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;
LOAD 'age'; SET search_path = ag_catalog, public;
```

### 4.1 Provenance convention

Every fact-bearing row carries `provenance provenance_t NOT NULL` and `run_id UUID`. `live` rows come from connectors; `sim` rows are written by the simulator under a `run_id`. This is the single mechanism that lets before/after re-simulation coexist with reality in one schema — the UI filters `WHERE provenance='live'` for the cockpit, `WHERE run_id=:sim` for the Simulation Console.

```sql
CREATE TYPE provenance_t AS ENUM ('live','sim');
```

### 4.2 Core relational tables

```sql
-- Physical/logical entities: assets, services, locations (one table, typed)
CREATE TABLE nodes (
  id          TEXT PRIMARY KEY,                 -- 'PIPE-ZN-44', 'HOSP-ZN-01'
  kind        TEXT NOT NULL,                    -- pipe|pump|hospital|road|psap
  domain      TEXT NOT NULL DEFAULT 'water',
  label       TEXT NOT NULL,
  geom        geometry(Geometry,4326),          -- point or linestring
  attrs       JSONB NOT NULL DEFAULT '{}',       -- diameter_mm, beds, capacity
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX nodes_geom_gix ON nodes USING GIST (geom);     -- PostGIS GiST
CREATE INDEX nodes_attrs_gin ON nodes USING GIN (attrs);

-- Signals: TimescaleDB hypertable, partitioned on time
CREATE TABLE signals (
  ts          TIMESTAMPTZ NOT NULL,
  node_id     TEXT REFERENCES nodes(id),
  metric      TEXT NOT NULL,                    -- pressure_psi, calls_per_min
  value       DOUBLE PRECISION NOT NULL,
  source      TEXT NOT NULL,                    -- scada|psap|traffic|hospital
  provenance  provenance_t NOT NULL DEFAULT 'live',
  run_id      UUID,
  raw         JSONB
);
SELECT create_hypertable('signals','ts', chunk_time_interval => INTERVAL '1 day');
CREATE INDEX signals_node_metric_ts ON signals (node_id, metric, ts DESC);
SELECT add_retention_policy('signals', INTERVAL '90 days');
```

`incidents` is the stitched case; `root_causes`, `interventions`, `simulations`, `decisions` hang off it. `evidence JSONB` arrays and `confidence` columns carry the swarm's reasoning trail.

```sql
CREATE TABLE incidents (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title       TEXT NOT NULL,
  status      TEXT NOT NULL DEFAULT 'open',     -- open|resolved|closed
  severity    INT  NOT NULL DEFAULT 3,
  risk_index  NUMERIC(5,2),                     -- 0–100, drives cockpit
  opened_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  graph_snap  JSONB                             -- frozen subgraph for replay
);

CREATE TABLE root_causes (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  incident_id UUID REFERENCES incidents(id) ON DELETE CASCADE,
  node_id     TEXT REFERENCES nodes(id),        -- the causal APEX
  method      TEXT NOT NULL,                    -- pyrca|dowhy|propagation
  confidence  NUMERIC(4,3) NOT NULL,
  evidence    JSONB NOT NULL,                   -- paths, counterfactuals
  is_apex     BOOLEAN NOT NULL DEFAULT true
);

CREATE TABLE interventions (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  incident_id UUID REFERENCES incidents(id) ON DELETE CASCADE,
  action      TEXT NOT NULL,                    -- isolate|bypass|tanker
  target_node TEXT REFERENCES nodes(id),
  params      JSONB NOT NULL DEFAULT '{}',
  cost        NUMERIC, est_eta_min INT,
  rank        INT
);

CREATE TABLE simulations (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  incident_id UUID REFERENCES incidents(id) ON DELETE CASCADE,
  intervention_id UUID REFERENCES interventions(id),
  adapter     TEXT NOT NULL,                    -- wntr|mesa
  risk_before NUMERIC(5,2), risk_after NUMERIC(5,2),
  run_id      UUID NOT NULL,                    -- ties to signals(run_id)
  artifact_s3 TEXT,                             -- MinIO key for full run
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE decisions (                        -- human gate + immutable audit
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  incident_id UUID REFERENCES incidents(id),
  intervention_id UUID REFERENCES interventions(id),
  actor       TEXT NOT NULL,                    -- OIDC subject
  verdict     TEXT NOT NULL,                    -- authorize|reject|hold
  rationale   TEXT,
  decided_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 4.3 Embeddings (pgvector)

Signal-window and incident-text embeddings power dedup ("have we seen this 911 pattern?") and case retrieval. ivfflat index for ANN search.

```sql
CREATE TABLE embeddings (
  id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ref_type  TEXT NOT NULL,                      -- incident|signal_window
  ref_id    TEXT NOT NULL,
  embedding vector(768) NOT NULL
);
CREATE INDEX embeddings_ivf ON embeddings
  USING ivfflat (embedding vector_cosine_ops) WITH (lists=100);
```

### 4.4 Dependency graph (Apache AGE)

**Recommendation: AGE, not adjacency tables.** Root-cause traversal is "walk upstream until no `FEEDS` predecessor anomalous" — a variable-length path query Cypher expresses natively (`*1..6`), whereas adjacency tables force recursive CTEs the agents would hand-build. AGE stores vertices/edges in the same DB, so a graph query joins to `signals`/`nodes` by id. Vertex/edge labels mirror `nodes.kind`; `nodes` remains the relational source of truth (geo, attrs), the graph holds topology.

```sql
SELECT create_graph('crisis');
-- vertices keyed by the same id used in nodes.id
SELECT * FROM cypher('crisis', $$
  CREATE (:pipe   {id:'PIPE-ZN-44'}),
         (:hospital {id:'HOSP-ZN-01'}),
         (:psap   {id:'PSAP-ZN'}),
         (:road   {id:'ROAD-ZN-7'})
$$) AS (v agtype);
-- directed FEEDS / STRAINS edges = propagation paths
SELECT * FROM cypher('crisis', $$
  MATCH (p:pipe {id:'PIPE-ZN-44'}), (h:hospital {id:'HOSP-ZN-01'})
  CREATE (p)-[:FEEDS {weight:0.9}]->(h)
$$) AS (e agtype);
```

Upstream root-cause walk from a loud symptom:

```sql
SELECT * FROM cypher('crisis', $$
  MATCH path = (apex)-[:FEEDS|STRAINS*1..6]->(s:psap {id:'PSAP-ZN'})
  RETURN apex.id, length(path) ORDER BY length(path) DESC LIMIT 1
$$) AS (apex agtype, hops agtype);
```

### 4.5 Zarqa population

```
nodes:   PIPE-ZN-44 (pipe, linestring, diameter_mm=600)
         HOSP-ZN-01 (hospital, point, beds=180)
         PSAP-ZN (psap), ROAD-ZN-7 (road)
graph:   PIPE-ZN-44 -FEEDS-> HOSP-ZN-01 -STRAINS-> PSAP-ZN
         PIPE-ZN-44 -FEEDS-> ROAD-ZN-7  -STRAINS-> PSAP-ZN
signals: PIPE-ZN-44 pressure_psi 62→8 (provenance=live)
         PSAP-ZN   calls_per_min +320%  (live)   ← loud symptom
incident:"Zarqa North water cascade", risk_index=84
root_cause: node_id=PIPE-ZN-44, method=pyrca, confidence=0.91, is_apex=true
intervention: isolate(PIPE-ZN-44)+bypass+tanker, rank=1
simulation:   risk_before=84 risk_after=22, run_id=… (sim signals show 62psi)
decision:     verdict=authorize, actor=duty.officer@zarqa
```

The apex query returns `PIPE-ZN-44`, never `PSAP-ZN`, because the +320% call surge is a graph *leaf*, not a source — the schema makes "loud ≠ causal" a structural fact.

---
