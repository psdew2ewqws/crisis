# AEGIS Crisis Console — Project Deep Dive & June 3 2026 Update

> **Status:** branch `dev` @ `4581b22` · Frontend + Backend running locally · voc360 DB connected (live)
> **Scope of this doc:** a full, deep reference for the whole system — architecture, frontend, backend, data, setup/run, environment, and the June 3 2026 cleanup + first-run UX work.

---

## 1. What this project is

**AEGIS Crisis Console** is a crisis-intelligence platform for the **Jordan Crisis Management Simulation Engine**. It turns real citizen Voice-of-Customer signals (the **voc360** database) into a live operating picture and walks an operator through a decision workflow:

```
Citizen signals  →  Dependency graph  →  Root-cause clusters  →  Solutions  →  Simulation  →  Decisions
   (voc360)            (graph)              (RIL clusters)        (countermeasures)  (Mesa A/B)    (human gate)
```

It also includes a **scenario engine** (describe a novel crisis in free text → retrieve historical precedents → select agents → simulate → detect/predict), a **deep-reasoning console** (why-chains, forecasting, validation, grounded Q&A), an **expert chat** with a guardrail system, and a **scholarly research agent**.

The product surface is a single-page web **console**; the brain is a **FastAPI** service reading the live voc360 Postgres database plus several optional reasoning/simulation engines that degrade gracefully when absent.

---

## 2. High-level architecture

```
┌──────────────────────────────┐         HTTP / NDJSON          ┌───────────────────────────────────────────┐
│   Frontend (Vite SPA)        │  ───────────────────────────▶  │   Backend (FastAPI, app.main:app)           │
│   React 19 + TS + Tailwind   │   fetch(VITE_API or            │   uvicorn :8000                              │
│   :5173/5174                 │   http://127.0.0.1:8000)       │                                             │
│                              │  ◀───────────────────────────  │   ┌─────────────────────────────────────┐   │
│   - view-switcher console    │       JSON / streamed NDJSON   │   │ Core: graph / rootcause / flow / sim  │   │
│   - scenario engine UI       │                                │   │ v2:   signals / kpis / solutions /…   │   │
│   - deep-analysis UI         │                                │   │ v3:   forecast / whys / validate /ask │   │
└──────────────────────────────┘                                │   │ scenario · debate · expert · lessons  │   │
                                                                 │   │ proof · research · guardrails gateway │   │
                                                                 │   └─────────────────────────────────────┘   │
                                                                 │              │            │                 │
                                                                 │   read-only  │            │ optional        │
                                                                 │   pooled     ▼            ▼                 │
                                                                 │   ┌────────────────┐  ┌──────────────────┐  │
                                                                 │   │ voc360 (PG 16) │  │ LangGraph · Mesa │  │
                                                                 │   │  the_data,     │  │ Pinecone · Ollama│  │
                                                                 │   │  ril_* tables  │  │  (degrade if off)│  │
                                                                 │   └────────────────┘  └──────────────────┘  │
                                                                 └───────────────────────────────────────────┘
```

- **Frontend ↔ Backend:** plain `fetch`. Most endpoints return JSON; the analysis flow (`/api/flow/run`) and scenario detection (`/api/scenario/detect`) **stream NDJSON** stages.
- **Backend ↔ Database:** a **read-only, pooled** `psycopg` connection to voc360. The session is forced `default_transaction_read_only=on`. No writes to voc360.
- **Optional engines:** LangGraph (the "Deer Graph" flow), Mesa (agent-based simulation), Pinecone (crisis-lessons vector store), and a local Ollama LLM (narration, embeddings, expert chat). Each is wrapped in `try/except` import guards — the app boots and serves without them.

---

## 3. Repository layout

```
Crisis New/
├── README.md                         # top-level project readme
├── guardrails.json                   # expert-chat guardrails (corrections store)
├── Jordan Crisis Management Simulation Engine.pdf
├── frontend/                         # Vite + React + TS SPA   (see §4)
├── backend/                          # FastAPI service          (see §5)
├── docs/                             # specs, blueprints, schema, this file
├── screenshots/
└── .vite/                            # local vite cache (ignored)
```

---

## 4. Frontend — deep dive

### 4.1 Stack

| Concern | Choice |
|---|---|
| Build tool | **Vite 8** (`@vitejs/plugin-react`) |
| UI | **React 19**, **TypeScript ~6** |
| Styling | **Tailwind CSS 3.4** + PostCSS/autoprefixer, CSS variables for theming |
| State | **zustand 5** (theme store); local component state + `localStorage` for the rest |
| Charts | **recharts 3** |
| Graph canvas | **reactflow 11** (live dependency graph + why-chain graph) |
| Animation | **motion 12** (`motion/react`) |
| Icons | **lucide-react** |

> Dev tooling: ESLint 10 + typescript-eslint. Scripts in `frontend/package.json`: `dev`, `build` (`tsc -b && vite build`), `lint`, `preview`.

### 4.2 Application architecture

The app **does not use a router**. `main.tsx` mounts `App`, and [App.tsx](../frontend/src/App.tsx) is a **state-based view switcher**: a `view` string selects which page component renders inside the shell. Pages are **lazy-loaded** (`React.lazy` + `Suspense`).

```
main.tsx → App.tsx
              ├── Onboarding gate (first run; localStorage "aegis-onboarded")
              └── Console shell
                   ├── Sidebar (grouped nav + CASE·SERVICE list + footer)
                   ├── Topbar  (sidebar toggle · breadcrumb · search · help · theme · clock)
                   └── <view>  (one of the pages below, in an ErrorBoundary + Suspense)
```

**Why no router:** an earlier "wizard" generation used `react-router-dom`; it was fully removed on June 3 (see §9). Navigation is now a single in-memory `view` switch, which keeps deep-state (active service, run progress) trivially shared.

### 4.3 Navigation (grouped)

The sidebar groups the nine destinations by workflow:

| Group | Items (`view` keys) |
|---|---|
| **MONITOR** | Dashboard · Signals · Incident Graph |
| **ANALYZE** | Root Cause · Deep Analysis |
| **RESPOND** | Solutions · Simulation · Decisions |
| **ASSIST** | Expert Chat |

Below the nav is the live **CASE · SERVICE** list (top voc360 services by critical/signal count); selecting one scopes every view to that service. The sidebar is **collapsible** to a 68px icon rail (toggled from the Topbar; persisted in `localStorage` `aegis-sidebar-collapsed`).

### 4.4 Pages (what each renders and which API it calls)

| View | File | Purpose | Primary backend calls |
|---|---|---|---|
| Dashboard | `App.tsx` (`DashboardView`) | KPIs, signal-volume chart, signals/clusters/solutions table, Run Analysis | `/api/kpis`, `/api/cases`, `/api/signal-volume`, `/api/signals`, `/api/flow/run` |
| Signals | `pages/SignalsPage.tsx` | Filterable, paginated feed over `the_data` (22,882 rows) | `/api/signals` |
| Incident Graph | `components/LiveGraph.tsx` | Live reactflow dependency graph (source→service→governorate) | `/api/graph`, `/api/flow/run` |
| Root Cause | `pages/RootCausePage.tsx` | Ranked RIL problem clusters (EN/AR labels, evidence, matched solution) | `/api/rootcause`, `/api/solutions` |
| Solutions | `pages/SolutionsPage.tsx` | "Valid solution" card per top cluster → Authorize → Decision | `/api/solutions`, `/api/decisions` |
| Simulation | `pages/SimulationPage.tsx` → `components/scenario/ScenarioSimulation.tsx` | Scenario **detection + prediction** console (free-text crisis → precedents → agents → Mesa A/B → verdict) | `/api/scenario/detect` (NDJSON), `/api/scenario/options`, `/api/scenario/retain` |
| Decisions | `pages/DecisionsPage.tsx` | Operator decision log + human authorization gate | `/api/decisions` (GET/POST) |
| Deep Analysis | `pages/DeepAnalysisPage.tsx` | v3 reasoning: why-chain graph, forecast, validation, grounded ASK | `/api/suggest`, `/api/whys`, `/api/forecast`, `/api/validate`, `/api/ask`, `/api/rootcause-graph` |
| Expert Chat | `pages/ExpertChatPage.tsx` | Domain chat (Gemma/Ollama) with correction→guardrail capture | `/api/expert/chat`, `/api/expert/guardrail(s)`, `/api/expert/health` |

### 4.5 Component map

- **Shell / chrome:** `Sidebar`, `Topbar`, `SettingsDrawer`, `HelpDrawer`, `ErrorBoundary`.
- **Dashboard widgets:** `KpiCard`, `SignalVolume`, `DataTable`.
- **Graph / proof:** `LiveGraph`, `ProofPanel`.
- **Scenario engine (`components/scenario/`):** `ScenarioSimulation` (orchestrator) + `ScenarioInput`, `ScenarioStepper`, `PrecedentCards`, `AgentRoster`, `ScenarioCharts`, `VerdictPanel`, `DebateStream`, `PastRuns`, `SolutionEval`, `ResultSummary`, `ScenarioSuggestions`, `EvidencePanel`, `JordanDroughtStudy`.
- **First-run UX (new, June 3):** `WelcomeCard`, `Tour`.
- **Shared states (new, June 3):** `States.tsx` → `LoadingState`, `EmptyState`, `ErrorState`.
- **Onboarding hero:** `Onboarding` + `BackgroundPaths` (animated "crisis cascade" SVG).

### 4.6 Libs & stores

| File | Role |
|---|---|
| `lib/voc.ts` | Primary API client (graph, rootcause, flow stream, signals, kpis, solutions, decisions, debate, scenario…). API base = `import.meta.env.VITE_API ?? 'http://127.0.0.1:8000'`. |
| `lib/voc2.ts` | Secondary client (used by Decisions). Same base-URL resolution. |
| `lib/labels.ts` / `lib/labels.gen.ts` | English labels for RIL clusters (build-time map + canonical fallback). |
| `lib/data.ts` | Fallback KPI/tone types and default cards (used until live KPIs load). |
| `stores/themeStore.ts` | zustand dark/light theme (writes `data-theme` on `<html>`). |

### 4.7 First-run journey & accessibility (June 3 additions)

- **Welcome card** (`WelcomeCard.tsx`): a dismissible, first-visit-only panel on the Dashboard — "Get your first answer in 3 steps" with **Run my first analysis**, **Take a quick tour**, **Skip for now**. Persisted via `localStorage` `aegis-welcome-dismissed`.
- **Guided tour** (`Tour.tsx`): a 5-step spotlight coachmark walkthrough (nav → Run → KPIs → cases → help). It reads `data-tour="…"` anchors on the chrome, dims everything else, and floats a tooltip. Skippable, arrow-key/Esc navigable, **replayable** from the Help drawer.
- **Keyboard shortcuts** (wired in `App.tsx`, ignored while typing): `?` toggles Help · `[` toggles sidebar · `Esc` closes the top-most panel/overlay.
- **Accessibility:** aria-labels on icon-only buttons, `aria-current`/`aria-pressed` on nav/case items, a global keyboard focus ring (`index.css`), and `prefers-reduced-motion` support (the animated hero renders static; long transitions are neutralised).
- **KPI explainers:** hover (ⓘ) tooltips on each KPI card.

### 4.8 Build & run (frontend)

```bash
cd frontend
npm install
npm run dev        # Vite dev server on :5173 (falls back to :5174 if taken)
# production:
npm run build      # tsc -b && vite build → dist/
npm run preview
```

Configure a non-default API base with `VITE_API` (e.g. in `frontend/.env`): `VITE_API=http://127.0.0.1:8000`.

---

## 5. Backend — deep dive

### 5.1 Stack

| Concern | Choice |
|---|---|
| Framework | **FastAPI 0.115** on **uvicorn 0.34** (`app.main:app`) |
| Runtime | **Python 3.13**, virtualenv |
| DB driver | **psycopg 3** (binary) + **psycopg_pool** — read-only pooled |
| Validation | **pydantic 2** |
| Graph | **networkx 3** |
| Reports | **openpyxl** (Excel root-cause reports) |
| Scraping | **requests** + **beautifulsoup4** |
| Optional engines | **langgraph** (Deer Graph flow) · **mesa 3** (agent sim) · **pinecone** (lessons vector store) |

CORS allows any `localhost`/`127.0.0.1`/`0.0.0.0` origin (any port), so the Vite dev server on 5173/5174 connects without config.

### 5.2 App structure & router composition

`app/main.py` defines the FastAPI app and the **core** endpoints, then conditionally includes additional routers (each guarded so a missing dependency never breaks boot):

```
main.py
 ├── core endpoints: /api/health, /api/stats, /api/cases, /api/graph,
 │                   /api/rootcause, /api/flow/run (NDJSON), /api/simulate
 ├── include main_v2.router  → /api/signals, /api/kpis, /api/signal-volume,
 │                              /api/solutions, /api/decisions, /api/narrate, /api/graph2
 ├── include api_v3.router   → /api/forecast(+/escalations,/status), /api/whys,
 │                              /api/validate(+/rank), /api/ask, /api/suggest,
 │                              /api/rootcause-graph, /api/v3/health
 ├── include proof router    → /api/proof, /api/report/{cluster_id}.xlsx
 ├── include scenario router → /api/scenario/detect, /api/scenario/retain, /api/scenario/options
 ├── include debate router   → /api/debate
 ├── include expert router   → /api/expert/chat, /api/expert/health, /api/expert/guardrail(s)…
 ├── include lessons router  → /api/lessons(+/search,/reflect,/schema,/seed), /api/memory(+/rebuild)
 └── include research router → /api/research/run
```

### 5.3 Module responsibilities

| Module | Responsibility |
|---|---|
| `db.py` | Read-only **pooled** psycopg connection to voc360; `fetchall/fetchone/health`. Reads `VOC_DSN` (via `python-dotenv`). |
| `graph_builder.py`, `graph_real.py` | Build the Source→Service→Governorate dependency graph + RIL root-cause clusters. |
| `rootcause.py`, `rootcause_graph.py` | Rank `ril_problem_clusters` by member_count × severity; build the root-cause graph. |
| `deer_flow.py` | LangGraph "Deer Graph" streamed flow (connect→ingest→graph→rootcause→recommend). Optional. |
| `mesa_sim.py`, `cascade_sim.py` | Mesa agent-based sentiment-propagation / cascade simulation (before/after). Optional. |
| `forecaster.py`, `series.py` | Time-series forecasting (mean+band) and escalation flags. |
| `whys.py` | 5-Whys causal chain → graph. |
| `validate.py`, `causal_validate.py` | Validation verdict + grounded axes + confidence; ranking. |
| `suggest.py` | Suggested-question chips grounded in ranked root causes. |
| `scenario.py`, `scenario_runs.py` | Free-text scenario **detect/predict** (NDJSON), agent selection, persistence/retain. |
| `debate.py` | Multi-agent debate stream. |
| `expert_chat.py` | Gemma/Ollama domain chat + correction→guardrail capture. |
| `guardrails_gateway.py`, `guardrails_store.py` | **Deterministic input/output gateway on the LLM routers** (added on `dev`) + storage. |
| `solutions.py` | Valid-solution (cause→countermeasure) engine. |
| `decisions.py`, `db_write.py` | Decision log + the only writes (to an app-side store, not voc360). |
| `lessons*.py` (`lessons`, `lessons_db`, `lessons_pinecone`, `lessons_backfill`) | Crisis-lessons store (success + failure cases) in Pinecone + DB. |
| `llm.py` | Local LLM (Ollama) client — narration, lesson extraction, embeddings. |
| `memory_light.py` | Lightweight memory layer. |
| `proof.py`, `provenance.py` | Proof panel + provenance trail; Excel report export. |
| `research_agent.py` + `scholar/` | Scholarly research agent (`crossref`, `openalex`, `unpaywall`, `worldbank`, `fusion`) — a sci-hub-free legal research path. |
| `jordan_water_baseline.py` | Jordan WEF-nexus / water-crisis baseline (flagship drought study). |
| `agent_router.py`, `subthemes.py`, `cluster_link.py`, `qa.py`, `api_kpis.py`, `api_signals.py` | Supporting routers/helpers. |

### 5.4 Full endpoint reference

**Core (`main.py`)**
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | voc360 connectivity |
| GET | `/api/stats` | row counts (signals, services, sources, governorates, clusters, segments) |
| GET | `/api/cases` | selectable services (signal/critical counts) |
| GET | `/api/graph?case=` | live dependency graph (nodes + edges) |
| GET | `/api/rootcause?limit=` | ranked RIL clusters + recommendation |
| POST | `/api/flow/run?case=` | **NDJSON** streamed data→graph→rootcause→recommend flow |
| POST | `/api/simulate?case=` | sentiment-propagation simulation (before/after) |

**Console v2 (`main_v2.py`)** — `/api/signals`, `/api/kpis`, `/api/signal-volume`, `/api/solutions`, `/api/decisions` (GET/POST), `/api/narrate` (POST), `/api/graph2`.

**Deep-reasoning v3 (`api_v3.py`)** — `/api/forecast` (+ `/forecast/escalations`, `/forecast/status`), `/api/whys` (POST), `/api/validate` (+ `/validate/rank`), `/api/ask` (POST), `/api/suggest`, `/api/rootcause-graph`, `/api/v3/health`.

**Scenario** — `/api/scenario/detect` (POST, NDJSON), `/api/scenario/retain` (POST), `/api/scenario/options`.

**Proof / reports** — `/api/proof`, `/api/report/{cluster_id}.xlsx`.

**Expert chat** — `/api/expert/chat` (POST), `/api/expert/health`, `/api/expert/guardrail` (POST), `/api/expert/guardrails` (GET), `/api/expert/guardrails/{id}` (DELETE), `/api/expert/guardrails/migrate` (POST).

**Lessons / memory** — `/api/lessons`, `/api/lessons/search` (GET/POST), `/api/lessons/reflect` (POST), `/api/lessons/schema` (POST), `/api/lessons/seed` (POST), `/api/memory`, `/api/memory/rebuild` (POST).

**Other** — `/api/debate` (POST), `/api/research/run` (POST).

### 5.5 Scraper (`backend/scraper/`)

Standalone ingestion scripts that build a curated crisis-case corpus from public sources: **FEMA, GDACS, IFRC, OCHA, PreventionWeb, ReliefWeb, UNICEF, WHO, Wikipedia, World Bank**, plus `insert_curated_cases.py`. Run independently of the API service.

### 5.6 Build & run (backend)

```bash
cd backend
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
cp .env.example .env            # then fill VOC_DSN (see §7) — NEVER commit the real .env
./.venv/bin/uvicorn app.main:app --reload --port 8000
# API docs: http://127.0.0.1:8000/docs
```

The app **boots without `VOC_DSN`** but every data endpoint returns HTTP 500 (`VOC_DSN is not set`) until configured. Optional engines (LangGraph/Mesa/Pinecone/Ollama) are skipped silently if their packages/services are absent.

---

## 6. End-to-end setup (clean machine)

1. **Clone & branch** — `git clone -b dev <repo> .`
2. **Backend** — create venv, `pip install -r requirements.txt`, create `backend/.env` with `VOC_DSN`, run uvicorn on :8000.
3. **Verify DB** — `curl http://127.0.0.1:8000/api/health` → `{"connected": true, "database": "voc360", …}`. `GET /api/stats` returns live counts (e.g. **22,882 signals · 154 services · 20 clusters**).
4. **Frontend** — `cd frontend`, `npm install`, `npm run dev` → open the printed URL (5173/5174).
5. **Connectivity** — the SPA defaults to `http://127.0.0.1:8000`; CORS already allows localhost. The Dashboard KPIs/table populate from live voc360.

---

## 7. Environment variables (`backend/.env`)

| Key | Required | Purpose |
|---|---|---|
| `VOC_DSN` | **Yes** | voc360 Postgres DSN. Format: `host=… port=5432 dbname=voc360 user=… password=… sslmode=require connect_timeout=15` |
| `LLM_BASE_URL` | No | Local Ollama base (default `http://localhost:11434`) — narration, lessons, embeddings, expert chat |
| `LLM_MODEL` | No | e.g. `llama3.1` (expert chat uses a Gemma model) |
| `EMBED_MODEL` / `EMBED_DIM` | No | Embedding model + dim (e.g. `nomic-embed-text` / `768`) |
| `PINECONE_API_KEY` / `PINECONE_INDEX` / `PINECONE_NAMESPACE` | No | Crisis-lessons vector store |

> **Connection coordinates (June 3 2026):** host `87.239.129.246`, port `5432`, db `voc360`, user `voc_admin`, `sslmode=require`. **The password lives only in `backend/.env` (git-ignored) and is intentionally not written into this doc.** See §10.

---

## 8. Data model (voc360, read-only)

The graph and root causes are built entirely from real tables:

- **`the_data`** — the signal layer (22,882 citizen reports). Columns used: `record_id`, `source_type`, `source_platform`, `service_id`, `governorate`, `text`/`text_clean` (Arabic, RTL), `observed_at`, `rating`, `sentiment_label`, `severity`.
- **`ril_problem_clusters`** — root-cause clusters (`canonical_label_en`/`canonical_label_ar`, member_count, severity).
- **`ril_cluster_members`**, **`ril_text_segments`** — cluster membership + evidence segments.

Full schema: [docs/VOC360_SCHEMA.md](VOC360_SCHEMA.md).

---

## 9. June 3 2026 update log

Two work streams landed on top of `dev` @ `4581b22`.

### 9.1 Branch sync & local bring-up
- Pulled `dev` (fast-forward through `4581b22 feat(guardrails): deterministic input/output gateway on the LLM routers`).
- Stood up backend (venv + deps + `.env` with `VOC_DSN`) and frontend; verified live data end-to-end (`/api/health` connected, `/api/stats` = 22,882 signals).

### 9.2 UI cleanup (structural)
- **Removed an entire orphaned "wizard" generation** — 39 dead files: `router.tsx`, 8 gen-1 pages (`Dashboard, SignalExplorer, IncidentGraph, RootCause, Solutions, Simulation, DecisionHub, Outcome`), 8 dead component folders (`wizard, decision, graph, outcome, rca, simulation, signals, solutions`), `PageShell.tsx`, and dead libs/stores (`lib/hooks`, `lib/useDashboard`, `stores/appStore`, `stores/wizardStore`). Frontend went ~80 → **44 source files**.
- **Dropped now-unused deps:** `react-router-dom`, `@xyflow/react`. (Live graph uses `reactflow` v11.)
- **Grouped navigation** into MONITOR / ANALYZE / RESPOND / ASSIST; added a **collapsible icon-rail** sidebar (Topbar toggle, persisted).
- Removed the redundant Dashboard "Run Analysis" button; made the Dashboard header consistent with the other pages.

### 9.3 First-run journey + UX polish
- **Welcome card** + **guided spotlight tour** (replayable from Help). `localStorage` keys: `aegis-onboarded`, `aegis-welcome-dismissed`, `aegis-sidebar-collapsed`.
- **Real keyboard shortcuts** (`?`, `[`, `Esc`); Help drawer rewritten with accurate shortcuts + a **glossary**; stale "wizard mini-tracker" shortcut and stale build date removed; Contact is a real `mailto:`.
- **Drawer alignment** fixed to follow the collapsed/expanded sidebar width.
- **KPI explainer tooltips**; **unified empty/loading/error states** (`States.tsx`).
- **Accessibility:** aria-labels, focus rings, `prefers-reduced-motion`; **Settings** placeholders clearly marked `SOON`.
- **No backend functionality changed** in this stream — presentation + client-state only.

Verification each step: `tsc -b` (exit 0) + `vite build` (success) + headless screenshots of dashboard, collapsed rail, welcome card, and tour.

---

## 10. Security notes

- **Database is read-only** at the session level (`default_transaction_read_only=on`); the service never writes to voc360.
- **Secrets:** `VOC_DSN` and all keys live in `backend/.env`, which is **git-ignored**. Do not commit real credentials, and do not paste them into tracked docs.
- The voc360 password was shared in plaintext during setup on June 3 — **rotating it is recommended** as routine hygiene.
- CORS is permissive for localhost only; tighten `allow_origin_regex` before any non-local deployment.

---

## 11. Known follow-ups (optional, not yet done)

- **Bundle size:** the main JS chunk is ~270 kB gzip; could be code-split further (`vite` warns >500 kB pre-gzip).
- **Search scope:** the Topbar search currently filters the Dashboard table only; could be made global.
- **Inner-page density:** the six live pages were left intact under the "light polish" scope; a focused density pass per page is available on request.
- **Optional engines off by default locally:** wire `LLM_BASE_URL` (Ollama) and `PINECONE_*` to enable narration, expert chat, and the lessons store.

---

*Generated June 3 2026. Source of truth is the code on branch `dev` @ `4581b22`; update this doc as the system evolves.*
