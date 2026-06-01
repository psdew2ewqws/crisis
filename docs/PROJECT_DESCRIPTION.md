# AEGIS — Project Description

**General Crisis-Solving Brain · Graph-based multi-agent system · 2026-06-01**

---

## What is AEGIS?

AEGIS is a **graph-based, deer-flow-style multi-agent system** that takes any crisis case, connects every signal in a dependency graph, finds the **root cause** (not the loudest symptom), and produces a **validated solution** — proven by re-simulation before a human authorizes action.

The system is demonstrated end-to-end on the **Jordan Crisis Management Simulation Engine** scope, with a working React command-center dashboard (the **AEGIS Crisis Console**).

---

## The Problem

During a crisis, operators are overwhelmed by loud, high-volume signals (e.g. a +320% spike in 911 calls) that are actually **downstream symptoms**, not the root cause. Traditional dashboards show alerts by volume — so the loudest signal gets attention first, even when the quiet upstream failure (e.g. a pipe rupture) is the actual thing to fix.

AEGIS flips this: it builds a causal dependency graph, runs root-cause analysis (PyRCA/DoWhy), and surfaces the true apex — the one node that, if fixed, resolves the entire cascade.

---

## The Zarqa Demo Case

The system is demonstrated on a real-world-modeled scenario: a **trunk-main water pipe rupture** (`PIPE-ZN-44`) in Zarqa, Jordan, that cascades into:

- **Hospital strain** — New Zarqa Hospital ED load +138%
- **Traffic congestion** — Junction 31 gridlocked by emergency crews
- **911 call surge** — +320% call volume (the loudest signal, but a symptom)
- **Public sentiment shift** — social media activity rising

The brain identifies `PIPE-ZN-44` (quiet pressure drop, Z-score 4.8) as the true root cause — not the loud 911 surge (Z-score 5.1, but downstream) — and outputs a validated fix: **isolate the pipe + open bypass + dispatch 6 tankers to the hospital**, proven by WNTR/EPANET hydraulic re-simulation to reduce risk from 84 → 22.

---

## How It Works

The brain runs one **domain-agnostic loop**. A **Domain Pack** (ontology, propagation rules, connectors, intervention library, simulator) plugs in per domain — water is one pack, public-health and power-grid are others.

```
Ingest → Resolve → Correlate → Root-Cause → Risk → Generate-Solution → Validate → Recommend → Learn
   │         │          │           │          │            │              │           │         │
 signals  entity     stitch     causal-     cascade     intervention    re-sim     human     outcome
          resolution  incident   graph apex  propagate   library        on graph   gate      feedback
```

A **deer-flow-style agent swarm** drives it: coordinator → planner → [graph-builder · correlator · root-cause · solution-generator · simulator-validator] → adversarial critic → human gate → reporter, on a LangGraph runtime.

**A solution is "valid" if it:**
1. Targets the root cause, not symptoms
2. Is simulated to reduce the risk index
3. Is feasible (resources, authority, time)
4. Bounds second-order harm
5. Carries confidence + evidence lineage

---

## System Architecture

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

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | React 19 + TypeScript · Vite · Tailwind CSS · Recharts · lucide-react |
| **Frontend (full MVP)** | + shadcn/ui · React Flow · MapLibre GL · Framer Motion · TanStack Query · Zustand |
| **Backend / API** | Python 3.12 · FastAPI (REST + WebSocket) · Pydantic v2 · SQLAlchemy 2 + Alembic · Arq |
| **Agent swarm** | LangGraph (deer-flow pattern) · LangChain core |
| **Engines** | NetworkX/rustworkx · Splink/dedupe · DoWhy/causal-learn/PyRCA · PyOD/river · Mesa/PySD + WNTR/EPANET · OR-Tools |
| **Data** | PostgreSQL 16 + Apache AGE (graph) · pgvector · PostGIS · TimescaleDB · Redis · S3/MinIO |
| **Infra** | Docker + compose · GitHub Actions · OAuth2/OIDC + RBAC · OpenTelemetry |

---

## Repository Layout

```
crisis/
├── README.md                                          # Project overview + run instructions
├── frontend/                                          # AEGIS React dashboard (running MVP UI)
│   ├── src/
│   │   ├── App.tsx                                    # Root layout — sidebar + topbar + dashboard
│   │   ├── components/                                # Sidebar, Topbar, KpiCard, SignalVolume, DataTable
│   │   └── lib/data.ts                                # Demo fixtures (Zarqa case)
│   ├── package.json                                   # React 19, Vite 8, Tailwind, Recharts, lucide
│   └── tailwind.config.js                             # Dark command-center theme tokens
├── docs/                                              # All design & specification documents
│   ├── FRONTEND_SETUP.md                              # Frontend setup guide + full page specs
│   ├── FRONTEND_BUILD.md                              # Design system, screens, wizard, Claude prompt
│   ├── MVP.md                                         # MVP scope, wizard walkthrough, API, schema
│   ├── TECH_STACK.md                                  # Complete stack with repos
│   ├── SYSTEM_REQUIREMENTS.md                         # 96 functional + 42 non-functional requirements
│   ├── GENERAL_CRISIS_BRAIN_BLUEPRINT.md              # Domain-agnostic brain architecture
│   ├── WATER_CRISIS_BRAIN_BLUEPRINT.md                # Water domain pack spec
│   ├── Crisis_Intelligence_Core_Technical_Spec.md     # Engine algorithms + Zarqa worked example
│   ├── GAP_ANALYSIS_REPORT.md                         # 28 confirmed gaps in original scope
│   └── GAP_ANALYSIS_SUMMARY.md                        # Condensed gap analysis
├── screenshots/                                       # Dashboard captures
│   ├── dashboard.png
│   └── dashboard-table.png
└── Jordan Crisis Management Simulation Engine.pdf     # Original scope package
```

---

## Current State

The **frontend dashboard shell** is built and running — a dark command-center UI with:
- 4 KPI cards (National Risk, Apex Confidence, Projected Risk, Time to Mitigate)
- Signal Volume area chart (911 call rate & pressure anomalies)
- Tabbed data table (Signals / Incidents / Solutions)
- Left navigation sidebar with case list
- Top bar with search, notifications, and live UTC clock

All data is static demo fixtures (no backend required). The full MVP requires 8 additional pages, backend integration, and the wizard overlay — all specified in `docs/FRONTEND_SETUP.md`.

---

## Key Differentiators

1. **Root cause over loudest signal** — the brain demotes high-volume symptoms and finds the upstream causal apex
2. **Simulation-validated** — no intervention is recommended without a re-simulation proving it reduces risk
3. **Human-in-the-loop** — the system recommends but never acts without explicit human authorization (Step 6 gate)
4. **Domain-agnostic** — the engine loop is the same for water, power, health; only the Domain Pack changes
5. **Evidence lineage** — every recommendation carries its full causal chain, confidence score, and audit trail
