# Tech Stack — Crisis-Solving Brain

**The complete, explicit stack across every layer · React + Python + PostgreSQL · 2026-05-31**

The authoritative technology stack for the system: frontend, backend/API, the deer-flow-style agent swarm, the engine libraries, the single-PostgreSQL data layer, infrastructure, security, observability, and testing — each with its role and (where applicable) the verified open-source repo it maps to.

---

## Full Tech Stack

The single, authoritative stack for the crisis-solving brain. Versions are the targeted/pinned majors as of build start (2026-Q2); "maturity" flags production-readiness for that role. Repo slugs are GitHub `owner/name`. The rule is: **engine + swarm + storage never change; Domain Packs plug in.**

### High-level topology

```
 React/Vite SPA ──WS+REST──> FastAPI (Uvicorn) ──> LangGraph swarm
   (wizard, graph,             │   │   │                │
    map, sim console)          │   │   │        engine libs (graph/ER/RCA/anomaly/sim/opt)
                               │   │   └──> Arq workers (Redis) — long sim/optimize jobs
                               │   └──> Redis (cache / pub-sub / queue)
                               └──> PostgreSQL 16  [ AGE | pgvector | PostGIS | TimescaleDB ]
                                          └──> S3/MinIO (sim runs, audit exports)
```

### Frontend

| Tech | Version | Role | Repo |
|---|---|---|---|
| React + TypeScript | 18.3 / 5.x | SPA UI, wizard Steps 1–7 | `facebook/react` |
| Vite | 5.x | Dev server, bundler, HMR | `vitejs/vite` |
| Tailwind CSS | 3.4 | Utility styling, design tokens | `tailwindlabs/tailwindcss` |
| shadcn/ui (+ Radix) | latest / 1.x | Accessible primitives (dialog, command, sheet) | `shadcn-ui/ui` |
| TanStack Query | 5.x | Server-state cache for case/signal/sim REST | `TanStack/query` |
| Zustand | 4.x | Local UI state (wizard step, selections) | `pmndrs/zustand` |
| React Flow | 12.x | Incident dependency-graph canvas (Step 2/3) | `xyflow/xyflow` |
| Recharts / visx | 2.x / 3.x | Risk-index, 911-surge, before/after charts | `recharts/recharts`, `airbnb/visx` |
| MapLibre GL JS | 4.x | Geospatial cockpit, OSM tiles, Zarqa zones | `maplibre/maplibre-gl-js` |
| Motion (Framer Motion) | 11.x | Wizard transitions, node-pulse animation | `framer/motion` |
| Native WebSocket | — | Realtime signal/sim push (no socket lib) | — |
| Vitest / Playwright | 2.x / 1.x | Unit + E2E (wizard walkthrough) | `vitest-dev/vitest`, `microsoft/playwright` |

### Backend / API

| Tech | Version | Role | Repo |
|---|---|---|---|
| Python | 3.12 | Runtime for API, swarm, engine | `python/cpython` |
| FastAPI | 0.11x | REST + WebSocket endpoints | `fastapi/fastapi` |
| Uvicorn | 0.3x | ASGI server | `encode/uvicorn` |
| Pydantic | 2.x | Request/response + case-state schemas | `pydantic/pydantic` |
| SQLAlchemy + Alembic | 2.0 / 1.13 | ORM + migrations (one Postgres) | `sqlalchemy/sqlalchemy` |
| Arq | 0.26 | Async job queue on Redis (sim/optimize) | `samuelcolvin/arq` |

### Agent swarm (LangGraph / deer-flow)

| Tech | Version | Role | Repo |
|---|---|---|---|
| LangGraph | 0.2.x | Graph-of-agents orchestration, the 9-step loop as nodes | `langchain-ai/langgraph` |
| deer-flow (pattern) | ref | Supervisor + worker flow blueprint | `bytedance/deer-flow` |
| LangChain core | 0.3.x | LLM/tool bindings for agent nodes | `langchain-ai/langchain` |

Nodes map 1:1 to the loop: `ingest → resolve → correlate → root_cause → risk → generate → validate → recommend → learn`. Shared `CaseState` (Pydantic) is the channel; checkpointer persists to Postgres so a case is resumable mid-flow.

### Engine libraries

| Concern | Tech | Version | Role | Repo |
|---|---|---|---|---|
| Graph | NetworkX | 3.x | Topology, paths, centrality on incident graph | `networkx/networkx` |
| Graph (perf) | rustworkx | 0.15 | Fast propagation/centrality at scale | `Qiskit/rustworkx` |
| Entity resolution | Splink | 4.x | Probabilistic linkage of signals→entities | `moj-analytical-services/splink` |
| Entity resolution | dedupe | 3.x | Fallback fuzzy dedup | `dedupeio/dedupe` |
| Root cause | PyRCA | latest | Causal-apex detection on metric graph | `salesforce/PyRCA` |
| Root cause | DoWhy | 0.11 | Causal effect estimation / refutation | `py-why/dowhy` |
| Root cause | causal-learn | 0.1.x | Structure discovery (PC/GES) | `py-why/causal-learn` |
| Anomaly | PyOD | 1.1 | Batch outlier scoring on signals | `yzhao062/pyod` |
| Anomaly | river | 0.21 | Streaming anomaly on live feed | `online-ml/river` |
| Simulation (water) | WNTR / EPANET | 1.x / 2.2 | Hydraulic re-sim of `PIPE-ZN-44` | `USEPA/WNTR`, `OpenWaterAnalytics/EPANET` |
| Simulation (sys) | Mesa / PySD | 2.x / 3.x | Agent-based / system-dynamics packs | `projectmesa/mesa`, `SDXorg/pysd` |
| Optimization | OR-Tools | 9.x | Intervention selection (isolate+bypass+tanker) | `google/or-tools` |

### Data

| Tech | Version | Role | Repo |
|---|---|---|---|
| PostgreSQL | 16.x | Single primary store (relational truth) | `postgres/postgres` |
| Apache AGE | 1.5 (PG16) | Property graph + openCypher over the incident graph | `apache/age` |
| pgvector | 0.7 | Signal/text embeddings, similarity recall | `pgvector/pgvector` |
| PostGIS | 3.4 | Geo: zones, pipe geometry, hospital catchments | `postgis/postgis` |
| TimescaleDB | 2.15 | Hypertables for signal time-series (911 rate, pressure) | `timescale/timescaledb` |
| Redis | 7.x | Cache, Arq queue, WS pub/sub | `redis/redis` |
| MinIO (S3 API) | latest | Artifacts: sim-run dumps, audit exports | `minio/minio` |

Cypher over AGE finds the causal apex behind the loud symptoms:

```cypher
-- Apex = node that reaches the symptoms but nothing upstream reaches it
MATCH (root)-[:CAUSES*1..4]->(sym:Symptom {case:'ZARQA-2026-05'})
WHERE NOT (:Entity)-[:CAUSES]->(root)
RETURN root.id, count(DISTINCT sym) AS reach
ORDER BY reach DESC LIMIT 1;   -- => PIPE-ZN-44
```

Timescale keeps the symptom that must NOT be mistaken for the cause:

```sql
SELECT time_bucket('5 min', ts) AS b, avg(value)
FROM signal_ts
WHERE entity_id = 'DISPATCH-911-ZARQA' AND metric = 'call_rate'
GROUP BY b ORDER BY b;          -- the +320% surge (a symptom, not root)
```

### Infra / DevOps

| Tech | Version | Role | Repo |
|---|---|---|---|
| Docker / Compose | 26 / v2 | Dev parity, all services one `up` | `moby/moby` |
| Kubernetes (target) | 1.30 | Prod deploy, HPA on workers | `kubernetes/kubernetes` |
| GitHub Actions | — | CI: lint, test, build, image push | `actions/runner` |

### Auth / Security

| Tech | Version | Role | Repo |
|---|---|---|---|
| OAuth2 / OIDC | — | Duty-officer SSO | — |
| Authlib | 1.3 | OIDC client in FastAPI | `lepture/authlib` |
| RBAC | app-level | Roles: viewer / analyst / authorizer (Step 6 gate) | — |

### Observability

| Tech | Version | Role | Repo |
|---|---|---|---|
| OpenTelemetry | 1.x | Traces across API → swarm → engine | `open-telemetry/opentelemetry-python` |
| Grafana / Loki | 11 / 3 | Dashboards + log aggregation | `grafana/grafana`, `grafana/loki` |

### Testing

| Layer | Tech | Role |
|---|---|---|
| Backend unit/integration | pytest (`pytest-dev/pytest`) | Engine nodes, ER, RCA-on-Zarqa fixtures |
| API contract | httpx + schemathesis | REST/WS schema conformance |
| Frontend unit | Vitest | Components, store reducers |
| E2E | Playwright | Full wizard Step 1→7 on the demo case |

### Rationale

**React + Python + PostgreSQL core.** React/TS with React Flow and MapLibre is the only mainstream stack that natively delivers both an interactive dependency-graph canvas and live geospatial overlays — the two hardest UI surfaces here — with a deep, hireable talent pool. Python is non-negotiable for the engine: every required library for entity resolution, causal root-cause, anomaly detection, and hydraulic simulation (Splink, DoWhy, PyRCA, PyOD/river, WNTR/EPANET, OR-Tools) is first-class Python, and LangGraph's deer-flow swarm lives there too, so the API, orchestration, and analytics share one language and one `CaseState` model with no FFI seams. **"One Postgres, many extensions"** collapses what would otherwise be four stores — a graph DB, a vector DB, a geo DB, and a time-series DB — into a single PostgreSQL 16 instance via AGE, pgvector, PostGIS, and TimescaleDB. That means one connection pool, one backup, one transaction boundary, and one consistency model: a single commit can write the resolved entity, its embedding, its geometry, its time-series, and its graph edge atomically. For a crisis system where the incident graph, the signal feed, and the geo picture must agree at every instant, that transactional unity is a correctness feature, not just an ops convenience — and it keeps the dev `docker-compose` small enough to run the entire Zarqa demo on a laptop.

---
