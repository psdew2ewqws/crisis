# AEGIS — General Crisis-Solving Brain

> A graph-based, deer-flow-style multi-agent system that takes **any** crisis case, connects every signal in a dependency graph, finds the **root cause**, and produces a **validated solution** — demonstrated end-to-end on the *Jordan Crisis Management Simulation Engine* scope, with a working React command-center dashboard.

This repository contains the full body of work: a specification gap analysis, a domain-agnostic system blueprint, a technical engine spec, a deep System Requirements document, an MVP definition, and a **running frontend** — the **AEGIS Crisis Console** dashboard.

---

## The dashboard (live MVP UI)

The **AEGIS Crisis Console** is the operator dashboard: a left command rail (operations + active cases), at-a-glance KPI cards, a live signal-volume chart, and a tabbed signals / incidents / solutions table — all driven by the Zarqa demo case (no backend required).

![AEGIS Crisis Console](screenshots/dashboard.png)

- **KPIs** — National Risk (84, ▲ +12, critical), Apex Confidence (0.91, PyRCA — `PIPE-ZN-44` isolated, loud symptoms demoted), Projected Risk (22, ▼ −62, validated fix holds), Time to Mitigate (35 min — isolate + bypass + tanker).
- **Signal Volume** — 911 call rate & pressure anomalies for Zarqa North: a flat baseline ramping into the cascade onset.
- **Signals table** — per-entity observations with severity, Δ value, Z-score and time. The quiet `PIPE-ZN-44` pressure drop is the true root cause behind the loud 911/hospital spikes.

![Signals table](screenshots/dashboard-table.png)

---

## Live Deer Graph — connected to a real database (voc360)

Beyond the demo dashboard, the system connects to a **live PostgreSQL database** — `voc360`, a real Jordanian government Voice-of-Customer platform — and runs the full **data source → graph → root cause** flow on real data. The **Incident Graph** view renders it live: 22k+ citizen signals across 150+ services are wired into a dependency graph, and the RIL problem-cluster pipeline surfaces the real **root causes** (urgent-service fees · the BRT bus · National Aid Fund delays · the Takaful platform · class sizes of 50 students…).

![Live Deer Graph](screenshots/live-graph.png)

The **Deer Graph flow** (a deer-flow-style staged pipeline) runs live and streams to the UI: `connect → ingest → graph → root-cause → recommend`. A Python / FastAPI backend (`backend/`) reads voc360 **read-only**, builds the graph from the real `the_data` + `ril_problem_clusters` tables, and ranks root causes by `member_count × severity`.

**Run the backend:**

```bash
cd backend
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
cp .env.example .env          # add your voc360 DSN (never commit it)
./.venv/bin/uvicorn app.main:app --reload --port 8000
```

Endpoints: `/api/health` · `/api/stats` · `/api/graph` · `/api/rootcause` · `/api/flow/run` (streamed NDJSON) · `/api/simulate`. The frontend **Incident Graph** view consumes them. Schema: [`docs/VOC360_SCHEMA.md`](docs/VOC360_SCHEMA.md).

---

## Run the frontend

```bash
cd frontend
npm install
npm run dev
# open http://localhost:5173
```

Built with **React 18 + TypeScript · Vite · Tailwind CSS · Recharts · lucide-react**. No backend needed — it ships with the Zarqa demo fixtures in `src/lib/data.ts`.

---

## Documentation

All design and specification documents live in [`docs/`](docs/) (Markdown + rendered PDF).

| Document | What it is |
|---|---|
| [`GENERAL_CRISIS_BRAIN_BLUEPRINT`](docs/GENERAL_CRISIS_BRAIN_BLUEPRINT.md) | The domain-agnostic, deer-flow-style brain: Domain-Pack architecture, solver swarm, multi-domain proof, verified tech stack |
| [`Crisis_Intelligence_Core_Technical_Spec`](docs/Crisis_Intelligence_Core_Technical_Spec.md) | The engine spec: event correlation/stitching, root-cause analysis, National Risk Index cascade — with algorithms + the Zarqa worked example |
| [`SYSTEM_REQUIREMENTS`](docs/SYSTEM_REQUIREMENTS.pdf) | Software Requirements Specification (React + Python + PostgreSQL): 96 functional + 42 non-functional requirements, architecture, data design, API, security |
| [`MVP`](docs/MVP.md) | MVP scope, the dashboard-wizard walkthrough, full-stack architecture, API, PostgreSQL schema |
| [`FRONTEND_BUILD`](docs/FRONTEND_BUILD.md) | How the frontend is built — design system, screens, wizard, and a ready-to-paste Claude Design prompt |
| [`TECH_STACK`](docs/TECH_STACK.md) | The complete technology stack across every layer |
| [`GAP_ANALYSIS_REPORT`](docs/GAP_ANALYSIS_REPORT.pdf) / [`SUMMARY`](docs/GAP_ANALYSIS_SUMMARY.pdf) | Gap analysis of the original scope (28 confirmed gaps) — full + condensed |

---

## How it works

The brain runs one domain-agnostic loop; a **Domain Pack** (ontology, propagation rules, connectors, intervention library, simulator) plugs in per domain — water is one pack, public-health and power-grid are others.

```
Ingest → Resolve → Correlate → Root-Cause → Risk → Generate-Solution → Validate → Recommend → Learn
   │         │          │           │          │            │              │           │         │
 signals  entity     stitch     causal-     cascade     intervention    re-sim     human     outcome
          resolution  incident   graph apex  propagate   library        on graph   gate      feedback
```

A **deer-flow-style agent swarm** drives it: *coordinator → planner → [graph-builder · correlator · root-cause · solution-generator · simulator-validator] → adversarial critic → human gate → reporter*, on a LangGraph runtime.

**A solution is "valid"** iff it (a) targets the root cause not symptoms, (b) is simulated to reduce the risk index, (c) is feasible (resources/authority/time), (d) bounds second-order harm, and (e) carries confidence + evidence lineage.

---

## Tech stack

| Layer | Technology |
|---|---|
| **Frontend** | React 18 + TypeScript · Vite · Tailwind CSS · shadcn/ui · React Flow · Framer Motion · Recharts · MapLibre GL |
| **Backend / API** | Python 3.12 · FastAPI (REST + WebSocket) · Pydantic v2 · SQLAlchemy 2 + Alembic · Celery/Arq |
| **Agent swarm** | LangGraph (deer-flow pattern) |
| **Engines** | networkx/rustworkx · Splink/dedupe · DoWhy/causal-learn/PyRCA · PyOD/river · Mesa/PySD + WNTR/EPANET · OR-Tools |
| **Data** | PostgreSQL 16 + Apache AGE (graph) · pgvector · PostGIS · TimescaleDB · Redis · S3/MinIO |
| **Infra** | Docker + compose · GitHub Actions · OAuth2/OIDC + RBAC · OpenTelemetry |

See [`docs/TECH_STACK.md`](docs/TECH_STACK.md) for the full breakdown with verified open-source repos.

---

## Repository layout

```
crisis/
├── README.md
├── frontend/        # AEGIS React dashboard (the running MVP UI)
├── docs/            # blueprint, technical spec, SRS, MVP, frontend, tech stack, gap analysis
├── screenshots/     # dashboard captures (the images above)
└── Jordan Crisis Management Simulation Engine.pdf   # the original scope package
```
