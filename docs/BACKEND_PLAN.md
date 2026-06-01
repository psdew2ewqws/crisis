# Backend Engineering Plan — Crisis-Solving Brain

**How the backend is built: architecture, layering, folder/file layout, data, engine, swarm, sources, API, jobs, security, testing, and a phased build order · 2026-06-01**

This plan is authoritative for the backend. It reconciles two horizons:

- **MVP horizon** (`MVP.md`) — one end-to-end loop on the **Zarqa water cascade**: `ingest → resolve → correlate → root-cause → risk → generate → validate → recommend → learn`, surfaced through the 7-step wizard, proving `PIPE-ZN-44` is the apex (not the loud 911/hospital symptoms) and validating the fix by re-simulation.
- **Full horizon** (`scope_spec_clean.md`) — the 4-layer national platform: Source Layer → Integration/Control → Intelligence Core → Experience Layer, with ≥5 source types, ≥3 domains, dynamic source onboarding, 3 simulations + 1 wicked problem, and a production-transition path.

The architecture below is **built for the full horizon but delivered MVP-first**: every seam the full scope needs (pluggable sources, pluggable domain packs, provenance-scoped sim/live data) exists from day one, but only the Zarqa Water Pack and its synthetic sources are wired for v1.

---

## 1. Architectural principles

1. **Strict layering with a one-way dependency rule.** `api → services → {engine, repositories, swarm} → db`. The **engine never imports FastAPI, SQLAlchemy, or Redis** — it is pure, in-memory, deterministic algorithm code that takes plain dataclasses/Pydantic in and returns results out. This is what makes the algorithms in the Technical Spec unit-testable against the Zarqa fixtures with zero infrastructure.
2. **Everything domain-specific is a plug-in.** The engine + swarm + storage are domain-agnostic. A **Domain Pack** (`packs/water/…`) contributes ontology, propagation rules, an intervention library, a simulation adapter, and seed data. Adding "power" or "epidemic" later means adding a folder, not touching the core. (Per memory: *"engine + swarm + storage never change; Domain Packs plug in."*)
3. **Sources are registry-driven, not hard-coded.** Layer 1/2 (ingestion) goes through a `SourceConnector` contract + a runtime **source registry** so a new synthetic or live feed is onboarded (register → discover schema → map fields → validate → activate) without a redeploy of the core. This directly satisfies the "dynamic source onboarding" acceptance criterion.
4. **One Postgres, many extensions; one transaction boundary.** AGE (graph), pgvector (embeddings), PostGIS (geo), TimescaleDB (signal series) live in **one PostgreSQL 16**. A single commit can write the resolved entity, its embedding, its geometry, its time-series, and its graph edge atomically — a correctness feature for a crisis system where graph, signal, and geo must always agree.
5. **Provenance is a first-class column, not an afterthought.** Every fact-bearing row carries `provenance ('live'|'sim')` + `run_id`. This is the single mechanism that lets before/after re-simulation coexist with reality, lets the Simulation Console read `WHERE run_id=:sim`, and makes **simulation rollback/cleanup** a `DELETE WHERE run_id=:sim` instead of a saga.
6. **Async by default for heavy work; realtime via pub/sub.** REST is for commands/queries; long work (`run loop`, `run sim`, `generate solutions`) is enqueued to **Arq** workers. Each swarm node publishes a frame to Redis `case:{id}:events`; the FastAPI WS hub fans it out so the wizard advances in real time. The API process stays responsive.
7. **Explainability is structured data, not prose.** Root cause, risk, and recommendations each carry machine-readable `evidence`/`factors`/`confidence` so the Experience Layer can render *what changed, why, contributing factors, dominant risks*.

---

## 2. Tech stack (pinned for THIS build)

Runtime **Python 3.12** · **FastAPI** (REST + WS) · **Pydantic v2** · **Arq** on **Redis 7** · **LangGraph** (+ **langchain-ollama**) swarm · engine libs **rustworkx/networkx, Splink/dedupe, PyRCA/DoWhy/causal-learn, PyOD/river, WNTR/EPANET, OR-Tools** · **TimesFM** (time-series foundation model, forecasting) · **MinIO/S3** artifacts · **Authlib** OIDC + app-level RBAC · **OpenTelemetry** hooks · **pytest + httpx + schemathesis**.

### 2.1 Three decisions that override `TECH_STACK.md` for this build

1. **LLM = local Ollama, model `gemma4:26B`, for everything — including the LangGraph swarm.** No cloud LLM. Ollama is already running at `http://localhost:11434` and `gemma4:26B` is pulled and responding. Embeddings use **`nomic-embed-text`** (already pulled), which returns **768-dim** vectors — exactly the `vector(768)` the schema expects. All LLM access goes through one module, `app/llm/`, wrapping `langchain-ollama`'s `ChatOllama` (chat/reasoning in swarm nodes) and `OllamaEmbeddings` (the `learn`/retrieval path). The base URL and model name are config, never hard-coded in node files.

2. **Forecasting = TimesFM** (`google-research/timesfm`). The prediction engine (forecast incident growth, resource depletion, service overload, recovery ETA, and the "what happens next" series that feed risk) uses TimesFM as a zero-shot time-series foundation model. It loads a HuggingFace checkpoint once at worker startup (singleton) and is hidden behind a `Forecaster` Protocol so it is swappable and so the heavy model never loads inside request handlers. **Install is required** (`pip install timesfm` + checkpoint download) — see the Execution Guide.

3. **The database is DEFERRED.** The user will connect Postgres later. Therefore the system runs *now* on **in-memory repositories seeded from `data/seeds/zarqa.json`**, and switching to PostgreSQL later is a **config flip + migration run, with zero changes to services, engine, or swarm**. This works because every service depends only on a **repository interface** (`repositories/base.py` Protocols), never on SQL. Two implementations live side by side: `repositories/memory/` (active now) and `repositories/postgres/` (scaffolded, left as `NotImplementedError` stubs for later). A top-level **`data/`** folder holds the seed fixtures now and is the reserved mount point for the future DB. The `app/db/` package (SQLAlchemy engine, Alembic migrations) is written but **inert** until `REPO_BACKEND=postgres`.

A single `Settings` object (pydantic-settings) drives all wiring — `OLLAMA_BASE_URL`, `OLLAMA_CHAT_MODEL=gemma4:26B`, `OLLAMA_EMBED_MODEL=nomic-embed-text`, `TIMESFM_CHECKPOINT`, `REPO_BACKEND=memory`, `REDIS_URL`, `S3_*`. Flip `REPO_BACKEND` to `postgres` when the DB is ready; nothing else moves.

---

## 3. High-level topology

```
React SPA ──REST /api/v1──┐        ┌──WS /ws (token in query)──┐
                          ▼        ▼                            │
                  ┌──────────────────────────────────────────┐ │
                  │ FastAPI (app/api)  Pydantic v2 · OIDC/RBAC│ │
                  │  routers + WS hub (subscribes Redis)      │◄┘
                  └───┬───────────────┬──────────────┬────────┘
            enqueue   │   repo iface  │      publish  │
            (Arq)     ▼               ▼               ▼
        ┌─────────────────┐   ┌──────────────────┐  ┌──────────┐
        │ Arq workers     │   │ repositories/    │  │ Redis    │
        │  LangGraph swarm│◄─►│  base (Protocols)│  │ cache·   │
        │  (9 nodes)      │   │   ├ memory  ◄ NOW │  │ queue·   │
        │   ↑ uses        │   │   └ postgres ◄LATR│  │ pub/sub  │
        │  app/engine +   │   └────────┬─────────┘  └──────────┘
        │  app/packs/water│            │ seeded from
        │  app/llm(Ollama)│      ┌──────────────┐  ┌──────────┐
        │  TimesFM        │      │ data/seeds/  │  │ MinIO/S3 │
        └────────┬────────┘      │ zarqa.json   │  │ sim·audit│
                 │ HTTP          └──────────────┘  └──────────┘
        ┌────────▼────────┐   ┌──────────────────────────────┐
        │ Ollama :11434   │   │ (PostgreSQL 16 + AGE/pgvector │
        │ gemma4:26B      │   │  /PostGIS/TSDB) — DEFERRED,   │
        │ nomic-embed-text│   │  plugs in behind repo iface  │
        └─────────────────┘   └──────────────────────────────┘
```

Two processes share one codebase: the **API process** (`uvicorn app.main:app`) and the **worker process** (`arq app.workers.arq_worker.WorkerSettings`). They talk only through the repository layer + Redis — never in-process — so workers scale independently of the API. **Today the repository layer is in-memory** (seeded from `data/seeds/zarqa.json`); the boxed Postgres stack is the deferred drop-in. LLM and embeddings are local Ollama calls over HTTP; TimesFM runs in-process inside the worker.

---

## 4. Folder & file architecture

The backend lives in a new top-level **`crisis/backend/`** (sibling to `crisis/frontend/`). Layout:

```
crisis/backend/
├── pyproject.toml                # deps, tool config (ruff, mypy, pytest)
├── alembic.ini
├── Dockerfile                    # api + worker share one image, different CMD
├── docker-compose.yml            # postgres(+exts), redis, minio, api, worker
├── .env.example
├── README.md                     # "one compose up" runbook
│
├── app/
│   ├── main.py                   # create_app(); lifespan: db pool, redis, otel, registries
│   ├── __init__.py
│   │
│   ├── core/                     # cross-cutting, no domain logic
│   │   ├── config.py             # Settings (pydantic-settings); env-driven
│   │   ├── logging.py            # structlog config
│   │   ├── telemetry.py          # OpenTelemetry tracer/meter setup
│   │   ├── security.py           # JWT verify, OIDC (Authlib), RBAC dependency
│   │   ├── ids.py                # ULID mint/parse: sig_/inc_/sol_/sim_/dec_
│   │   ├── errors.py             # RFC-7807 envelope + exception handlers
│   │   ├── pagination.py         # cursor encode/decode, Page[T]
│   │   └── time.py               # UTC helpers, ISO-8601
│   │
│   ├── llm/                      # ALL model access — local Ollama, one place
│   │   ├── client.py             # build_chat()→ChatOllama(gemma4:26B), build_embeddings()
│   │   ├── prompts.py            # system/user templates for swarm nodes
│   │   └── json_mode.py          # structured-output helper (parse/validate JSON from gemma)
│   │
│   ├── db/                       # DEFERRED — written but inert until REPO_BACKEND=postgres
│   │   ├── session.py            # async engine, async_sessionmaker, get_session()
│   │   ├── base.py               # DeclarativeBase + naming convention
│   │   ├── uow.py                # UnitOfWork (one txn spanning all 4 modalities)
│   │   ├── extensions.sql        # CREATE EXTENSION timescaledb/age/postgis/vector
│   │   └── age.py                # AGE session bootstrap (LOAD 'age', search_path)
│   │
│   ├── models/                   # SQLAlchemy ORM = relational source of truth
│   │   ├── node.py               # nodes (PostGIS geom, attrs JSONB)
│   │   ├── signal.py             # signals hypertable (Timescale)
│   │   ├── incident.py
│   │   ├── root_cause.py
│   │   ├── intervention.py
│   │   ├── simulation.py
│   │   ├── decision.py           # human gate + immutable audit
│   │   ├── embedding.py          # pgvector(768)
│   │   ├── source.py             # source registry (Layer 2)
│   │   ├── wizard.py             # per-incident wizard state/gates
│   │   └── enums.py              # provenance_t, severity, verdict, source_status
│   │
│   ├── schemas/                  # Pydantic v2 DTOs = the API/WS contract
│   │   ├── common.py             # Page[T], Problem, GeoPoint, ULID types
│   │   ├── signal.py             # SignalIn / SignalOut
│   │   ├── incident.py           # IncidentOut, GraphOut (nodes/edges → React Flow)
│   │   ├── rootcause.py          # RootCauseOut (apex, ranked_causes, evidence)
│   │   ├── solution.py
│   │   ├── simulation.py         # SimRunIn / SimOut (risk_before/after, series)
│   │   ├── decision.py           # DecisionIn / AuthorizeIn / DecisionOut
│   │   ├── source.py             # SourceRegisterIn, SourceOut, MappingSpec
│   │   ├── wizard.py             # WizardState
│   │   └── ws.py                 # WSFrame{channel,event,data,ts}, SubscribeOp
│   │
│   ├── api/
│   │   ├── deps.py               # get_session, current_user, require_role(...)
│   │   ├── router.py             # mounts /api/v1
│   │   ├── v1/
│   │   │   ├── auth.py           # POST /auth/token (OIDC password/code → JWT)
│   │   │   ├── signals.py        # GET/POST /signals, GET /signals/{id}
│   │   │   ├── incidents.py      # GET /incidents, /{id}, /{id}/graph
│   │   │   ├── rootcause.py      # GET /incidents/{id}/root-cause
│   │   │   ├── solutions.py      # GET + POST :generate
│   │   │   ├── simulations.py    # POST /simulations, GET /simulations/{id}
│   │   │   ├── decisions.py      # POST /decisions, POST /{id}:authorize (commander)
│   │   │   ├── wizard.py         # GET/PUT /incidents/{id}/wizard
│   │   │   ├── risk.py           # GET /risk (national index + by_governorate)
│   │   │   └── sources.py        # source registry CRUD + :activate (Layer 2)
│   │   └── ws/
│   │       ├── router.py         # /ws endpoint; auth via ?token=
│   │       ├── hub.py            # ConnectionManager: subscriptions, fan-out
│   │       └── relay.py          # Redis pubsub → WS frame bridge (started in lifespan)
│   │
│   ├── repositories/             # data access behind interfaces — DB swappable
│   │   ├── base.py               # Protocols: NodeRepo, SignalRepo, GraphRepo,
│   │   │                         #   IncidentRepo, RootCauseRepo, InterventionRepo,
│   │   │                         #   SimulationRepo, DecisionRepo, EmbeddingRepo,
│   │   │                         #   SourceRepo, WizardRepo  (+ a RepoBundle facade)
│   │   ├── factory.py            # get_repos(settings) → memory or postgres bundle
│   │   ├── memory/               # ◄ ACTIVE NOW — in-memory, seeded from data/seeds
│   │   │   ├── store.py          # MemoryStore: dict tables + rustworkx graph
│   │   │   ├── nodes.py  signals.py  graph.py  incidents.py
│   │   │   ├── root_causes.py  interventions.py  simulations.py
│   │   │   ├── decisions.py  embeddings.py  sources.py  wizard.py
│   │   │   └── seed_loader.py    # load data/seeds/zarqa.json → MemoryStore
│   │   └── postgres/             # ◄ LATER — same Protocols, raw SQL/Cypher; stubs now
│   │       ├── nodes.py  signals_ts.py  graph_age.py  incidents.py
│   │       ├── root_causes.py  interventions.py  simulations.py
│   │       └── decisions.py  embeddings.py  sources.py  wizard.py
│   │
│   ├── services/                 # application/use-case layer (orchestration)
│   │   ├── ingestion.py          # validate → normalize → resolve → persist → enqueue
│   │   ├── incident_service.py   # headers, KPIs, graph projection for React Flow
│   │   ├── rootcause_service.py  # engine.rootcause + repo read/write
│   │   ├── solution_service.py   # engine.optimization + intervention library (pack)
│   │   ├── simulation_service.py # spawn sim job; assemble before/after artifact
│   │   ├── decision_service.py   # human gate, 409 on stale sim, audit + S3 export
│   │   ├── risk_service.py       # National Risk Index aggregation + explainability
│   │   ├── wizard_service.py     # step gating; which gates are satisfied
│   │   └── source_service.py     # onboarding state machine (register→...→activate)
│   │
│   ├── engine/                   # PURE domain-agnostic intelligence core (no I/O)
│   │   ├── types.py              # frozen dataclasses: Node, Edge, SignalPoint, ...
│   │   ├── graph/
│   │   │   ├── store.py          # rustworkx in-mem graph; build from edges
│   │   │   └── traversal.py      # paths, centrality, upstream-anomalous walk (§1.3)
│   │   ├── resolution/
│   │   │   └── resolver.py       # Splink/dedupe: signal → entity (§2.5)
│   │   ├── correlation/
│   │   │   └── stitch.py         # dim scores, pairwise link, stitching (§3)
│   │   ├── anomaly/
│   │   │   ├── batch.py          # PyOD z-score/outlier on signal windows
│   │   │   └── stream.py         # river online anomaly (future live feed)
│   │   ├── rootcause/
│   │   │   ├── layer_a.py        # cross-symptom causal apex (PyRCA/DoWhy) (§4.1)
│   │   │   └── layer_b.py        # intra-asset failure causation (§4.2)
│   │   ├── risk/
│   │   │   ├── base_risk.py      # per-node r(n) (§5.2)
│   │   │   ├── propagation.py    # cascade propagation (§5.3)
│   │   │   └── index.py          # National Risk Index + factor attribution (§5.1/5.6)
│   │   ├── prediction/
│   │   │   ├── base.py           # Forecaster Protocol: forecast(series, horizon)->Forecast
│   │   │   └── timesfm_forecaster.py  # TimesFM impl (singleton, lazy checkpoint load)
│   │   ├── optimization/
│   │   │   └── intervention.py   # OR-Tools select isolate+bypass+tanker (ranking v1)
│   │   └── simulation/
│   │       ├── adapter.py        # SimAdapter Protocol (run(scenario)->SimResult)
│   │       └── runner.py         # generic before/after harness, risk delta
│   │
│   ├── swarm/                    # LangGraph orchestration of the 9-step loop
│   │   ├── state.py              # CaseState (Pydantic) — the shared channel
│   │   ├── graph.py              # build StateGraph; node wiring; entrypoint run_case()
│   │   ├── checkpoint.py         # Postgres checkpointer (resumable mid-flow)
│   │   ├── emit.py               # publish case.step frame → Redis
│   │   └── nodes/
│   │       ├── ingest.py  resolve.py  correlate.py  rootcause.py
│   │       ├── risk.py    generate.py  validate.py  recommend.py
│   │       └── learn.py          # embed outcome (pgvector) for future retrieval
│   │
│   ├── packs/                    # Domain Packs (pluggable)
│   │   ├── base.py               # DomainPack ABC: ontology, rules, interventions, sim, seed
│   │   ├── registry.py           # discovery + lookup by domain key
│   │   └── water/
│   │       ├── __init__.py       # WaterPack(DomainPack)
│   │       ├── ontology.py       # node/edge kinds: pipe,pump,hospital,road,psap
│   │       ├── propagation.py    # FEEDS/STRAINS weights, lags (Water rules)
│   │       ├── interventions.py  # isolate / bypass / tanker library + costs/ETA
│   │       ├── sim_adapter.py    # WNTR/EPANET adapter implementing SimAdapter
│   │       └── seed/zarqa.py     # the reference scenario (exact IDs from spec §0.3)
│   │
│   ├── sources/                  # Layer 1+2: connectors & dynamic onboarding
│   │   ├── base.py               # SourceConnector Protocol: discover/poll/normalize
│   │   ├── registry.py           # runtime registry; activation lifecycle
│   │   ├── mapping.py            # field-mapping + schema validation + quality score
│   │   ├── health.py             # freshness/availability monitor
│   │   ├── synthetic/            # the sandbox feeds (≥5 types)
│   │   │   ├── scada.py          # pressure on PIPE-ZN-44
│   │   │   ├── psap_911.py       # call-volume surge (loud symptom)
│   │   │   ├── hospital.py       # ED occupancy
│   │   │   ├── traffic.py        # congestion Highway 35
│   │   │   └── weather.py        # the "advanced/external signal" source
│   │   └── adapters/             # future live connectors (stubs, same Protocol)
│   │       └── __init__.py
│   │
│   ├── workers/
│   │   ├── arq_worker.py         # WorkerSettings: redis, functions, startup/shutdown
│   │   ├── tasks.py              # run_case_loop, run_simulation, generate_solutions,
│   │   │                         #   replay_source, cleanup_sim_run
│   │   └── events.py             # typed Redis publisher (case/signal/risk channels)
│   │
│   ├── bus/
│   │   ├── redis.py              # async redis client factory
│   │   └── pubsub.py             # publish/subscribe helpers, channel names
│   │
│   └── storage/
│       └── artifacts.py          # MinIO/S3: put sim-run JSON, audit bundle; presign
│
├── data/                         # ◄ DATA HOME — fixtures now, DB mount point later
│   ├── seeds/
│   │   └── zarqa.json            # canonical fixture: nodes, edges, signal replay
│   ├── timesfm/                  # downloaded TimesFM checkpoint cache (gitignored)
│   └── README.md                 # "DB plugs in here later; see REPO_BACKEND"
│
├── migrations/                   # Alembic — DEFERRED, written, run only when DB connected
│   ├── env.py                    # runs extensions.sql first, then versions
│   └── versions/                 # 0001_init, 0002_hypertable, 0003_age_graph, ...
│
├── scripts/
│   ├── seed_db.py                # load Water Pack seed into Postgres+AGE
│   ├── run_demo.py               # drive the full Zarqa loop headless (CI gate)
│   └── replay_signals.py         # stream the fixture over time for Step-1 feed
│
└── tests/
    ├── conftest.py               # pg/redis testcontainers, seeded Zarqa fixtures
    ├── unit/                     # engine algorithms vs spec worked examples
    │   ├── test_traversal.py     # §1.3 upstream walk → PIPE-ZN-44
    │   ├── test_rootcause.py     # §4 apex > every symptom
    │   ├── test_risk.py          # §5.4 cascade numbers
    │   └── test_resolution.py    # §2.5 3 hospital spellings → 1 node
    ├── integration/              # service + repo against real Postgres
    │   ├── test_ingestion.py
    │   ├── test_swarm_loop.py    # run_case() end-to-end → authorized
    │   └── test_sim_rollback.py  # DELETE WHERE run_id cleans up
    └── contract/
        └── test_openapi.py       # schemathesis fuzz over /api/v1
```

### Why this shape

- **`engine/` is the crown jewel and is deliberately I/O-free.** The Technical Spec's algorithms (§1–§5) map 1:1 to files here and are tested directly against the spec's worked Zarqa numbers — no DB, no network. If the apex math is wrong, `tests/unit/test_rootcause.py` fails in milliseconds.
- **`repositories/` is the only place raw SQL/Cypher lives.** Services and engine never see a connection string. Swapping `signals_ts.py` for a different store, or adding a read replica, touches one file.
- **`swarm/` is thin glue.** Each node = (read via repo) → (call engine) → (write via repo) → (emit frame). LangGraph owns control flow + checkpointing; it owns no algorithm.
- **`packs/` + `sources/` are the two extension points** the full scope demands. New domain = new pack folder; new feed = new connector class registered at runtime.

---

## 5. Data layer

> **Status: DEFERRED behind the repository interface.** Everything in this section is the *target* once the DB is connected. **Right now the active store is `repositories/memory/`**, seeded from `data/seeds/zarqa.json` into dict "tables" + a rustworkx graph. Services/engine/swarm call **`repositories/base.py` Protocols only**, so the cutover is `REPO_BACKEND=postgres` + `alembic upgrade head` + seed import — no logic changes. The `repositories/base.py` Protocol method signatures below are the contract both backends honor.

When the DB is connected, the schema in `MVP.md §4` is adopted as-is. Migration ordering matters with these extensions:

1. **`0001_extensions`** — `CREATE EXTENSION` timescaledb, age, postgis, vector; `provenance_t` enum.
2. **`0002_core`** — `nodes` (+GIST geom, GIN attrs), `incidents`, `root_causes`, `interventions`, `simulations`, `decisions`, `embeddings` (+ivfflat), `sources`, `wizard_state`.
3. **`0003_signals_hypertable`** — create `signals`, then `create_hypertable('signals','ts')`, add `(node_id,metric,ts DESC)` index + 90-day retention policy. (Hypertable conversion must follow table creation, so it gets its own migration.)
4. **`0004_age_graph`** — `SELECT create_graph('crisis')`; vertex/edge labels mirror `nodes.kind`. AGE DDL runs outside Alembic's autogenerate (raw `op.execute`).

**The Unit of Work** (`db/uow.py`) opens one async transaction and exposes the repositories bound to that session, so a swarm node that resolves an entity, writes its embedding, updates the graph edge, and appends a signal commits **atomically** — principle #4 made concrete.

**Graph store duality.** `repositories/graph_age.py` is the durable truth (Cypher over AGE, joinable to `nodes` by id). `engine/graph/store.py` builds a transient **rustworkx** graph from edge rows for fast traversal/centrality during a single loop run. The swarm hydrates rustworkx at loop start and MERGEs deltas back to AGE — the spec's "rustworkx in-memory ↔ AGE Cypher" pattern.

---

## 6. The intelligence engine (`engine/`)

Each module is a pure function family keyed to a spec section:

| Module | Spec | Input → Output | MVP behavior |
|---|---|---|---|
| `graph/traversal` | §1.3 | edges + anomaly flags → ranked upstream apex | upstream walk stops at non-anomalous predecessor |
| `resolution/resolver` | §2.5 | raw signal → canonical `node_id` | Splink scores 3 "Zarqa General Hospital" spellings → one node |
| `correlation/stitch` | §3 | signal set → incident clusters | spatio-temporal + dim scores stitch 911/hospital/traffic into one incident |
| `anomaly/batch` | §2 | signal window → z-scores | PyOD flags pressure z = −6.1 |
| `rootcause/layer_a` | §4.1 | graph + series → ranked causes + evidence | `PIPE-ZN-44` 0.91 > hospital 0.34 > 911 0.12 |
| `risk/index` + `propagation` | §5 | node risks + topology → cascade + national index | risk_before 0.84/84; factor attribution |
| `optimization/intervention` | §7 | candidates + constraints → ranked plan | isolate+bypass+tanker ranked #1 |
| `prediction/timesfm_forecaster` | scope §9 | historical signal series + horizon → point + quantile forecast | **TimesFM** zero-shot forecast of 911/pressure/occupancy → "what happens next"; feeds risk + recovery ETA |
| `simulation/runner` | §8 | scenario + adapter → before/after `SimResult` | drives WNTR via Water Pack adapter |

**LLM usage is confined to the swarm, not the engine.** The pure `engine/` stays deterministic and model-free (so its unit tests are reproducible). The `gemma4:26B` model is called only from `swarm/` nodes via `app/llm` — for narrative evidence summaries, the `resolve` node's fuzzy tie-breaks, conflicting-evidence notes, and the `recommend` node's human-readable rationale. Numeric truth (apex score, risk index, forecast) always comes from `engine/`, never from the LLM; the LLM explains and narrates, it does not compute the verdict.

The `SimAdapter` Protocol (`engine/simulation/adapter.py`) is the boundary: the engine knows *"run a scenario, get risk_before/after + a time series + an artifact blob"*; only `packs/water/sim_adapter.py` knows EPANET. A Mesa/PySD pack later implements the same Protocol with zero engine changes.

---

## 7. The LangGraph swarm (`swarm/`)

- **`state.py` — `CaseState`** (Pydantic): the single channel — `case_id`, `signals`, `entities`, `incident`, `graph_delta`, `root_cause`, `risk`, `solutions`, `sim`, `recommendation`, `decision`, plus a `trace[]` of per-node evidence. Pydantic so it serializes into the checkpointer and into WS frames unchanged.
- **`graph.py`** wires nodes in the loop order `ingest→resolve→correlate→rootcause→risk→generate→validate→recommend→learn`. `validate` may loop back to `generate` if no candidate clears the risk threshold.
- **LLM nodes use `gemma4:26B` via `app/llm`.** Nodes that reason in language (`resolve` tie-breaks, `rootcause`/`risk` evidence prose, `recommend` rationale) call `build_chat()` → `ChatOllama(model="gemma4:26B", base_url=settings.OLLAMA_BASE_URL, format="json")` and validate the JSON against a Pydantic schema (`llm/json_mode.py`) before it touches `CaseState`. A bad/garbled LLM reply is caught and the node falls back to the deterministic engine output — the loop never blocks on the model.
- **`checkpoint.py`** persists `CaseState` after each node so a case is **resumable mid-flow** and `"Replay this case"` re-runs from any checkpoint (scope §17). **While the DB is deferred, the checkpointer uses LangGraph's `MemorySaver`**; it swaps to the Postgres checkpointer when `REPO_BACKEND=postgres`.
- **`emit.py`** publishes the frame `{case_id, stage, status, ...}` to `case:{id}:events` after each node. The `validate` node additionally emits `sim.progress`/`sim.done`.
- **Each node file** is ~30 lines: pull what it needs from `CaseState` + repos, call one `engine` function, write results via repo (inside the UoW), update `CaseState`, emit. **No algorithm lives here.**

`run_case_loop` (an Arq task) instantiates the graph for the incident's Domain Pack and streams it to completion; the acceptance test (`MVP.md §1.4`) asserts `root_cause.node_id == "PIPE-ZN-44"`, post-sim risk `< 0.30` and `< 0.5×` pre-sim, and a `decision` row `status="authorized"`.

---

## 8. Source layer & dynamic onboarding (`sources/`)

Satisfies scope §5/§6 and the "add a source without rebuilding the core" criterion.

- **`SourceConnector` Protocol** — `discover_schema()`, `poll()→raw envelopes`, `normalize(raw)→SignalIn`. Synthetic feeds and (future) live connectors implement the same interface.
- **`registry.py`** holds the onboarding state machine, persisted in the `sources` table: `registered → schema_discovered → mapped → validated → active → decommissioned`. `source_service.py` drives transitions; `api/v1/sources.py` exposes them.
- **`mapping.py`** maps an arbitrary source schema onto the **canonical model** (scope §7) and computes a data-quality score (missing fields, duplicates, freshness).
- **`synthetic/`** ships the **≥5 source types** for the sandbox (SCADA, 911/PSAP, hospital, traffic, weather) generating the *difficult* data the scope wants: missing fields, delayed/duplicate events, conflicting signals, misleading symptoms. `weather.py` doubles as the **advanced/external signal** source — onboarded *after* the core demo to prove it shifts risk/sim/recommendations (the §6 minimum demonstration).
- **`health.py`** feeds source freshness/availability into the Source Management Console.

Replay for the demo: `scripts/replay_signals.py` + the `replay_source` Arq task push the Zarqa fixture through the *real* ingestion path over time, so Step-1's live feed is genuine ingestion, not a canned stream.

---

## 9. API & realtime mapping

- **REST** — every row of `MVP.md §3.2` maps to exactly one handler in `api/v1/*`. Conventions enforced centrally: ULIDs (`core/ids`), RFC-7807 errors (`core/errors`), cursor pagination (`core/pagination`), JWT+RBAC (`core/security` + `api/deps.require_role`). `decisions:authorize` is gated to `commander`; a stale `sim_id` returns **409** (guards the human gate against races).
- **Long ops return `202 + {job_id, status_url}`** (`solutions:generate`, `simulations`); clients poll the resource or watch WS.
- **WebSocket** — one endpoint `/ws?token=<jwt>`. `ws/hub.py` tracks per-connection channel subscriptions (`signals`, `incident:{id}`, `risk`); `ws/relay.py` (started in the app lifespan) subscribes Redis `case:*:events` + `signals` + `risk` and fans frames to subscribed sockets. The frontend's current static `zarqa.ts` is replaced by a thin API/WS client; **the backend serves the `MVP.md` contract verbatim** and a small adapter maps snake_case DTOs to the frontend's `types.ts` (camelCase) — documented in the frontend integration note, not leaked into the backend.

---

## 10. Async, security, artifacts, observability

- **Arq workers** (`workers/arq_worker.py`) run the swarm and sims. `cleanup_sim_run(run_id)` implements **simulation cleanup/rollback** as a scoped delete across `signals`/`simulations` by `run_id` — safe because of the provenance design (#5). `scenario expiration` is a periodic Arq cron task purging expired `run_id`s.
- **Auth** — Authlib OIDC password/code → JWT; claims `sub`, `roles`, `exp`. RBAC is a FastAPI dependency. WS authenticates via `?token=`. v1 roles: `duty_officer`, `analyst`, `commander`.
- **Artifacts** (`storage/artifacts.py`) — sim-run JSON + hydraulic plots and the **audit bundle** (decision + evidence + sim diff) are written to MinIO; the `decisions` row stores the S3 key. Audit rows are append-only.
- **Observability** — OpenTelemetry spans thread `api → service → swarm node → engine`; `case_id` is a span attribute so a whole loop is one trace. Logs are structured (structlog) → Loki; OTel hooks are wired but Grafana dashboards are deferred per MVP out-scope.

---

## 11. Config & environments

`core/config.Settings` (pydantic-settings) reads `.env`. The keys that matter for *this* build:

```
APP_ENV=dev
REPO_BACKEND=memory                       # ◄ flip to "postgres" when DB is ready
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_CHAT_MODEL=gemma4:26B
OLLAMA_EMBED_MODEL=nomic-embed-text
OLLAMA_REQUEST_TIMEOUT=120
TIMESFM_CHECKPOINT=google/timesfm-2.0-500m-pytorch
TIMESFM_BACKEND=cpu                       # mac: cpu/mps; no CUDA
SEED_PATH=./data/seeds/zarqa.json
REDIS_URL=redis://localhost:6379/0        # used by Arq + WS pub/sub
S3_ENDPOINT=... S3_BUCKET=... (MinIO; optional in dev — artifacts can write to ./data/artifacts)
# DATABASE_URL=...  ← commented out until DB is connected
```

For dev, **only Ollama (already up) and Redis are required**; Postgres and MinIO are optional/deferred (artifacts fall back to `./data/artifacts`, the store falls back to memory). A `docker-compose.yml` is provided that brings up redis (and, when you want them, postgres-with-extensions + minio), but the demo runs today against local Ollama + in-memory repos with at most a local Redis. The same image is k8s-ready (worker as a separately-scaled Deployment) for later.

---

## 12. Testing strategy

| Layer | Tooling | What it proves |
|---|---|---|
| Engine unit | pytest, fixtures from `seeds/zarqa.json` | spec worked examples (§1.3, §4, §5.4, §2.5) reproduce exactly — fast, no infra |
| Service/repo integration | pytest + testcontainers (pg+exts, redis) | ingestion, swarm loop, sim rollback against real Postgres |
| API contract | httpx + **schemathesis** over the OpenAPI | every `/api/v1` route conforms to its schema; error envelope is consistent |
| End-to-end CI gate | `scripts/run_demo.py` | the `MVP.md §1.4` Gherkin: right apex, validated fix, authorized — the one CI-gated truth condition |

CI (GitHub Actions): ruff + mypy → unit → integration (services in compose) → contract → the demo gate → build & push image.

---

## 13. Build order (phased, each phase demoable)

0. **Bootstrap** — `crisis/backend/` scaffold, venv, `pip install` (incl. `langchain-ollama`, `timesfm`), `Settings`, `app/llm` wired to Ollama, `data/seeds/zarqa.json`, `repositories/base.py` Protocols + `repositories/memory/` seeded store + `factory.py`. *Exit:* `python scripts/check_env.py` prints gemma4:26B OK, embed dim=768, seed loaded (N nodes / M edges), TimesFM checkpoint resolves.
1. **Engine core (pure, no infra)** — `graph`, `resolution`, `correlation`, `anomaly`, `rootcause`, `risk`, `prediction/timesfm`. *Exit:* all `tests/unit` green against the spec's worked Zarqa numbers. **Highest-value phase.**
2. **Repositories(memory) + services + REST (read paths)** — `GET /incidents/{id}`, `/graph`, `/root-cause`, `/risk`, `/signals`, served from the in-memory store. *Exit:* frontend renders cockpit/graph/root-cause from the API.
3. **Sources + ingestion + WS** — `SourceConnector`s, registry, `POST /signals` (writes to memory store), Redis pub/sub, WS hub + relay, signal replay. *Exit:* Step-1 live feed is genuine ingestion over WS.
4. **Swarm + Arq (Ollama-driven)** — `CaseState`, 9 LangGraph nodes using `gemma4:26B` for narration, `MemorySaver` checkpoint, `run_case_loop`. *Exit:* `POST /incidents/{id}/run` drives Steps 1→7 via WS frames; apex == `PIPE-ZN-44`.
5. **Solutions + simulation + decision gate** — OR-Tools ranking, WNTR adapter, `POST /simulations`, before/after artifact (to `./data/artifacts`), `decisions:authorize` (commander, 409 guard), audit bundle. *Exit:* the `MVP.md §1.4` acceptance test passes via `scripts/run_demo.py`.
6. **Dynamic onboarding + advanced signal + cleanup** — onboard `weather` source post-demo; show it shifts risk/sim/recommendations; `cleanup_sim_run` (`del by run_id`); scenario expiration. *Exit:* scope §6/§16 criteria met.
7. **DB cutover (LATER, when user connects Postgres)** — implement `repositories/postgres/*`, run `app/db` + Alembic `0001–0004`, swap checkpointer + artifact store, set `REPO_BACKEND=postgres`. *Exit:* same tests pass against Postgres with `REPO_BACKEND=postgres`; zero changes to services/engine/swarm.
8. **Hardening** — OTel traces, RBAC polish, schemathesis in CI, k8s manifests, production-transition notes.

Phases 0–5 deliver the MVP **on memory + Ollama, no database**; phase 6 reaches the national-platform criteria; phase 7 is the deferred DB drop-in.

---

## 14. Cross-cutting conventions (quick reference)

- **IDs:** ULIDs, type-prefixed (`sig_`, `inc_`, `sol_`, `sim_`, `dec_`); times ISO-8601 UTC.
- **Errors:** RFC-7807 envelope everywhere; `401/403/404/409/422/429/503` as in `MVP.md §3.1`.
- **Provenance:** every fact row carries `provenance` + `run_id`; cockpit reads `live`, Sim Console reads `run_id`.
- **Dependency rule:** `engine` imports nothing from `app.*` infra; `services` never write raw SQL; `api` never calls `engine` directly (always via a service).
- **Extension points:** new domain → `packs/<name>/`; new feed → a `SourceConnector` in `sources/`; both register at runtime, no core edits.
```
