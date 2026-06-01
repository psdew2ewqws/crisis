# Frontend Setup Guide — AEGIS Crisis Console

**Everything you need to run, understand, and extend the frontend · 2026-06-01**

---

## 1. Prerequisites

| Requirement | Minimum Version | Check |
|---|---|---|
| **Node.js** | 18.x (LTS) or later | `node -v` |
| **npm** | 9.x or later (ships with Node 18+) | `npm -v` |
| **Git** | any recent | `git --version` |
| **OS** | macOS, Linux, or Windows (WSL recommended) | — |

No backend is required — the dashboard ships with embedded Zarqa demo fixtures and runs entirely client-side.

---

## 2. Quick Start

```bash
# 1. Clone the repo (if you haven't already)
git clone <repo-url> && cd Crisis

# 2. Enter the frontend directory
cd frontend

# 3. Install dependencies
npm install

# 4. Start the dev server
npm run dev

# 5. Open in browser
#    → http://localhost:5173
```

You should see the **AEGIS Crisis Console** dashboard with the Zarqa Trunk-Main Cascade demo case loaded.

---

## 3. Available Scripts

| Script | Command | What it does |
|---|---|---|
| **Dev server** | `npm run dev` | Starts Vite HMR dev server on `localhost:5173` |
| **Build** | `npm run build` | Runs `tsc -b` (type-check) then `vite build` → outputs to `dist/` |
| **Preview** | `npm run preview` | Serves the production build locally for verification |
| **Lint** | `npm run lint` | Runs ESLint across all `.ts` / `.tsx` files |

---

## 4. Tech Stack (Current Build)

| Technology | Version | Purpose |
|---|---|---|
| **React** | 19.2 | UI framework (concurrent rendering) |
| **TypeScript** | 6.0 | Type-safe development |
| **Vite** | 8.x | Dev server with HMR + production bundler |
| **Tailwind CSS** | 3.4 | Utility-first styling with custom design tokens |
| **Recharts** | 3.8 | Signal Volume area chart |
| **lucide-react** | 1.17 | Icon library (Zap, Activity, Settings, etc.) |

### Dev Dependencies

| Package | Role |
|---|---|
| `@vitejs/plugin-react` | Vite React plugin (Fast Refresh) |
| `autoprefixer` | PostCSS vendor prefixing |
| `postcss` | CSS transform pipeline for Tailwind |
| `eslint` + plugins | Linting (React Hooks, React Refresh, TypeScript) |

---

## 5. Project Structure

```
frontend/
├── index.html                 # App shell — loads Google Fonts (Geist, Inter)
├── package.json               # Dependencies & scripts
├── vite.config.ts             # Vite config (React plugin)
├── tailwind.config.js         # Tailwind theme — custom colors, fonts, radius
├── postcss.config.js          # PostCSS plugins (Tailwind + Autoprefixer)
├── tsconfig.json              # TS project references root
├── tsconfig.app.json          # App TS config (ES2023, React JSX, bundler mode)
├── tsconfig.node.json         # Node TS config (for vite.config.ts)
├── eslint.config.js           # Flat ESLint config
├── public/
│   ├── favicon.svg
│   └── icons.svg
└── src/
    ├── main.tsx               # Entry point — mounts <App /> into #root
    ├── App.tsx                # Root layout — Sidebar + Topbar + Dashboard
    ├── index.css              # Tailwind directives + global styles + scrollbar
    ├── lib/
    │   └── data.ts            # Demo fixtures (KPIs, signals, signal volume, cases)
    ├── components/
    │   ├── Sidebar.tsx        # Left nav rail — brand, Run Analysis, nav items, cases
    │   ├── Topbar.tsx         # Top bar — breadcrumb, search, notifications, UTC clock
    │   ├── KpiCard.tsx        # KPI metric card (National Risk, Apex Confidence, etc.)
    │   ├── SignalVolume.tsx   # Area chart — 911 call rate & pressure anomalies
    │   └── DataTable.tsx      # Tabbed table — Signals / Incidents / Solutions
    └── assets/                # Static assets (currently empty)
```

---

## 6. Design System

### 6.1 Color Palette

The UI uses a dark command-center aesthetic. All colors are defined as Tailwind tokens in `tailwind.config.js`:

| Token | Hex | Use |
|---|---|---|
| `bg` | `#0A0A0B` | App background |
| `sidebar` | `#0B0B0D` | Sidebar background |
| `card` | `#131417` | Card / panel background |
| `cardhi` | `#181A1E` | Card hover / active state |
| `border` | `#212228` | Borders and dividers |
| `soft` | `#1A1B20` | Hover backgrounds |
| `txt` | `#ECEDEE` | Primary text |
| `muted` | `#8B8D96` | Secondary text / labels |
| `faint` | `#62646D` | Tertiary text / hints |
| `blue` | `#3B82F6` | Primary accent / interactive |
| `bluehi` | `#60A5FA` | Accent highlight |
| `danger` | `#F04359` | Critical severity (red) |
| `good` | `#34D399` | Nominal / positive (green) |
| `warn` | `#FBBF24` | Elevated / caution (amber) |

### 6.2 Typography

Loaded via Google Fonts in `index.html`:

| Role | Font Stack | Use |
|---|---|---|
| **UI / body** | Geist → Inter → system-ui | All interface text |
| **Monospace** | Geist Mono → JetBrains Mono | Entity IDs, deltas, Z-scores, timestamps |

Telemetry values use the `.tnum` utility class (`font-variant-numeric: tabular-nums`) for aligned columns.

### 6.3 Spacing & Radius

- Border radius: `xl: 14px` (cards and panels)
- Standard Tailwind spacing scale

---

## 7. Component Reference

### `<App />` — Root Layout
The top-level layout: a flex row with `<Sidebar>` (fixed 248px) on the left and a `<main>` column containing `<Topbar>` and the scrollable dashboard content. Manages the `running` state for the "Run Analysis" button animation.

### `<Sidebar />` — Left Navigation Rail
- **Brand block:** AEGIS logo + "CRISIS CONSOLE" label
- **Run Analysis button:** triggers the analysis animation (1.6s spinner)
- **Operations nav:** Dashboard, Signals, Incident Graph, Root Cause, Solutions, Simulation, Decisions — with active state highlighting and optional badge counts
- **Case list:** Active cases with severity dot and risk score (Zarqa Cascade 84, Amman Grid Dip 38, Irbid Watch 16)
- **Footer:** Settings, Help, user avatar (Cmdr. Haddad)

### `<Topbar />` — Top Bar
- Sidebar toggle button (placeholder)
- Breadcrumb: Crisis Console / Zarqa Cascade
- Search input: "Search signals, entities..."
- Notification bell + theme toggle
- Live UTC clock (updates every second)

### `<KpiCard />` — KPI Metric Card
Displays a single KPI with:
- Title + severity badge (e.g. "▲ +12" in red)
- Large numeric value (40px) + optional unit
- Trend line with directional arrow
- Subtitle description

Four KPIs are rendered in a responsive grid:

| KPI | Value | Meaning |
|---|---|---|
| National Risk | 84 | Critical threshold exceeded (spiking in Zarqa North) |
| Apex Confidence | 0.91 | PyRCA isolated PIPE-ZN-44, loud symptoms demoted |
| Projected Risk | 22 | 74% reduction post-simulation (validated fix holds) |
| Time to Mitigate | 35 min | Isolate + bypass + tanker dispatch, 6 tankers to hospital |

### `<SignalVolume />` — Area Chart
- Recharts `<AreaChart>` with blue gradient fill
- Time-series data: 911 call rate & pressure anomalies for Zarqa North
- Shows flat baseline ramping sharply into cascade onset (08:00–13:30)
- Range selector tabs: Last 6h / 24 hours / 7 days (UI only — same data)

### `<DataTable />` — Tabbed Data Table
- Three tabs: Signals (6), Incidents (5), Solutions (3)
- Customize button + Run Analysis button in header
- Table columns: Entity, Observation (+ source badge), Severity (with colored dot), Δ Value, Z-score, Time
- 6 signal rows from the Zarqa demo case, sorted by time

---

## 8. Data Layer

All data is currently **static fixtures** defined in `src/lib/data.ts`. No backend or API calls are required.

### Types

| Type | Fields | Used by |
|---|---|---|
| `Kpi` | title, value, unit?, badge{text, tone}, trend{text, dir, tone}, sub | `<KpiCard>` |
| `Point` | t (time string), v (numeric value) | `<SignalVolume>` |
| `SignalRow` | entity, observation, source, severity, delta, z, time | `<DataTable>` |
| `CaseItem` | name, score, tone | `<Sidebar>` |
| `Tone` | `'danger' \| 'good' \| 'warn' \| 'neutral'` | Severity coloring everywhere |
| `Severity` | `'Critical' \| 'Elevated' \| 'Nominal'` | Signal severity levels |

### Demo Case: Zarqa Trunk-Main Cascade

The dashboard is hardcoded to the **Zarqa** scenario — a trunk-main pipe rupture (`PIPE-ZN-44`) that cascades into hospital strain, traffic congestion, and a 911 call surge. The key insight the system demonstrates: `PIPE-ZN-44` (quiet pressure drop, Z=4.8) is the true root cause behind the loud 911/hospital spikes (Z=5.1, but downstream symptoms).

---

## 9. What's Needed to Reach Full MVP

The current frontend is a **static dashboard shell**. The full MVP (as specified in `docs/MVP.md` and `docs/FRONTEND_BUILD.md`) requires the following additions:

### 9.1 Dependencies to Add

| Package | Role | Why needed |
|---|---|---|
| `@tanstack/react-query` | Server state management | REST data fetching, cache, WS-driven updates |
| `zustand` | UI state management | Wizard step, selected node, graph viewport, panel layout |
| `reactflow` (`@xyflow/react`) | Dependency graph canvas | Hero incident graph surface (Steps 2–3) |
| `maplibre-gl` + `react-map-gl` | Geospatial map | Zarqa zone map with pipe network, hospitals, tanker routes |
| `motion` (Framer Motion) | Animation | Panel reveals, cascade propagation, signal pulse, wizard transitions |
| `@radix-ui/*` + `shadcn/ui` | Accessible UI primitives | Dialog (wizard overlay), Tabs, Command palette, Toast |
| `@visx/*` | Advanced charts | Risk-index sparklines, before/after simulation bars |
| `@fontsource/clash-display` | Display font | Headers and cockpit titles (per design spec) |
| `@fontsource/hanken-grotesk` | Body font | UI text (per design spec) |
| `vitest` + `@testing-library/react` | Unit/component testing | Test severity logic, graph reducers, component rendering |
| `@playwright/test` | E2E testing | Full wizard walkthrough test |
| `msw` | API mocking | Mock REST/WS in tests with Zarqa fixtures |
| `orval` or `openapi-typescript` | API client generation | Generate typed client from FastAPI OpenAPI schema |

### 9.2 Pages to Develop

Below is the full specification for every page that needs to be built. Each entry includes the route, purpose, layout, components, data sources, interactions, and the Zarqa demo context.

---

#### Page 1 — National Crisis Cockpit (upgrade existing Dashboard)

| | |
|---|---|
| **Route** | `/` |
| **Status** | Partial — KPIs + signal volume chart + data table exist |
| **Purpose** | At-a-glance national posture across all live cases; entry point that escalates a case into the wizard |

**Layout:**

```
┌ STATUS BAR: NATIONAL RISK 0.71 ▲  | 14:32:07Z | 3 ACTIVE ───────────────┐
├──────────┬─────────────────────────────────────────┬──────────────────────┤
│ NAV RAIL │  ┌─ RiskGauge ─┐  ┌─ MapLibre (PostGIS)─┐ │ DECISION QUEUE     │
│ ▸Cockpit │  │   0.71 ▲    │  │  ● Zarqa  ▴ rupture │ │ ┌ Intervention──┐  │
│  Signals │  │  alert-red  │  │  ◦ Irbid  ◦ Amman   │ │ │ ISOLATE+BYP.  │  │
│  Graph   │  └─────────────┘  └─────────────────────┘ │ │ AWAIT AUTH    │  │
│  Sim     │  ┌─ Active Cases (sortable) ────────────┐  │ └───────────────┘  │
│  Decide  │  │ ZARQA-WATER-CASCADE  sev@alert  +320%│  │  SeverityBadge×3   │
│          │  │ AMMAN-GRID-DIP       sev@watch       │  │                    │
└──────────┴──────────────────────────────────────────┴──────────────────────┘
```

**What needs to be added to the current dashboard:**

| Component | Description |
|---|---|
| `RiskGauge` | Arc gauge showing national risk index (0–1), severity-colored (teal→amber→red), mono readout, delta indicator |
| MapLibre layer | PostGIS-backed map of Jordan with incident markers (Zarqa, Irbid, Amman); markers pulse on new `ws:risk` ticks |
| Active Cases table | Sortable case list (shadcn `DataTable`) with severity badge, risk delta, and click → route to `/case/:id/graph` |
| Decision Queue rail | Right sidebar rail with pending `InterventionCard` stubs showing awaiting-authorization items |
| `SeverityBadge` | Canonical severity-ramp atom: `calm` (teal) / `watch` (amber) / `alert` (red) with optional value |

**Data:** `GET /api/cases`, `GET /api/risk/national` · WS channels: `ws:risk`, `ws:cases`

**Interactions:** Click a case row → routes to `/case/:id/graph` and opens wizard at Step 2. Map markers pulse (Motion) on new risk ticks.

---

#### Page 2 — Signal Explorer

| | |
|---|---|
| **Route** | `/signals` |
| **Status** | Not started |
| **Purpose** | Raw signal triage — Wizard Step 1. Shows 911 surge, hospital strain, SCADA pressure drop streaming in real-time |

**Layout:**

```
┌─ Signal Explorer ──────────────────────────────────────────────────────────┐
│  ┌─ Filter Bar ─────────────────────────────────────────────────────────┐  │
│  │ Source: [SCADA] [911-CAD] [HIS] [TRAFFIC]  Severity: [All ▾]       │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│  ┌─ Signal Feed (left) ──────────────┐  ┌─ Time-Series (right) ────────┐  │
│  │ ● SIG-9001 SCADA PIPE-ZN-44      │  │  visx line chart: signal     │  │
│  │   pressure_drop  -62%  ALERT      │  │  rate per time_bucket        │  │
│  │   08:14:03Z                       │  │  (from TimescaleDB)          │  │
│  │ ● SIG-9002 911-CAD PSAP-ZN       │  │                              │  │
│  │   call_surge  +320%  ALERT        │  └──────────────────────────────┘  │
│  │ ● SIG-9003 HIS HOSP-ZN-NEW       │  ┌─ PostGIS Mini-Map ───────────┐  │
│  │   ed_load  +138%  WATCH           │  │  signal geo points on        │  │
│  │ ...                               │  │  Zarqa North map             │  │
│  └───────────────────────────────────┘  └──────────────────────────────┘  │
│  ┌─ Detail Drawer (on signal click) ───────────────────────────────────┐  │
│  │  Raw payload JSON + pgvector "similar past signals" list            │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────┘
```

**Components:**

| Component | Description |
|---|---|
| `SignalFeed` | Virtualized list of incoming signals with live pulse animation on new items. Mono timestamps, severity-coded rows |
| `PulseBadge` | Animated ring pulse (1.2s) in severity color on new signal arrival |
| Faceted filter bar | Filter by source (SCADA, 911-CAD, HIS, TRAFFIC), type, severity level |
| `visx` time-series chart | Signal rate over time using Timescale `time_bucket` aggregation |
| `SignalMap` | MapLibre mini-map showing signal geo-locations in Zarqa North |
| Detail drawer | Slide-out panel showing raw signal payload + pgvector similar-signal search results |

**Data:** `GET /api/signals?case=ZARQA…&since=…` (cursor-paginated, `useInfiniteQuery`) · WS channel: `ws:signals`

**Interactions:** Select signals → "Stitch into incident" button dispatches resolve/correlate agents and advances wizard to Step 2.

---

#### Page 3 — Incident Graph (Hero Surface)

| | |
|---|---|
| **Route** | `/case/:id/graph` |
| **Status** | Not started |
| **Purpose** | The stitched property graph — the cascade — rendered as the dominant canvas. Wizard Steps 2–3. This is where `PIPE-ZN-44` visually anchors the downstream fan-out |

**Layout:**

```
┌─ Incident Graph ────────────────────────── [fit] [layout▾] [replay ▸] ──┐
│                                                                          │
│   (PIPE-ZN-44)══RUPTURE══►(ZONE-NORTH lo-press)                         │
│        ╠═►(HOSP-ZARQA strain)══►(911 SURGE +320%)  ◄ loud symptom       │
│        ╚═►(TRAFFIC-HW35)                                                │
│                                                                          │
│   edges animate in cascade order; node color = severity ramp             │
│   dot-grid backdrop (32px, --border at 40%)                              │
│                                                                          │
├──────────────────────────────────────────────────────────────────────────┤
│ Inspector: selected = PIPE-ZN-44 | type: trunk_main | flow: 0 L/s       │
│            severity: alert | geo: [36.087, 32.072] | signals: 1         │
└──────────────────────────────────────────────────────────────────────────┘
```

**Components:**

| Component | Props | Description |
|---|---|---|
| `GraphCanvas` | `nodes`, `edges`, `severityOf(n)`, `onSelect`, `replay?` | React Flow canvas with custom node/edge types. Severity ramp colors nodes, mono ID labels |
| Custom nodes | — | Rounded rects tinted + glowing by severity. Root-cause apex = red outline + breathing glow animation (`2s ease-in-out infinite`) |
| Custom edges | — | Directional, animated during propagation replay. Edge weight = propagation strength. Severity-colored stroke |
| Replay scrubber | `order`, `speed` | Motion-staggered edge animation in propagation order (PIPE-ZN-44 → trunk loss → hospital → traffic → 911), 400ms/hop |
| Node inspector | `selectedNode` | Bottom panel showing entity details, type, telemetry, linked signals |
| `EntityResolveBadge` | — | Shows Splink merge status when duplicate entities are resolved (e.g. 3 hospital spellings → 1 node) |
| Layout controls | — | Fit view, layout algorithm picker (elkjs layered/mrtree via Web Worker), zoom |
| Mini-map | — | React Flow mini-map with severity legend pinned |

**Data:** `GET /api/cases/:id/graph` returns AGE Cypher result `{nodes[], edges[]}` · WS channel: `ws:graph` patches deltas

**Interactions:** Click node → inspector + cross-highlights its signals in Signal Explorer. "Find root cause" button triggers RCA engine. Layout computed off-render-thread via elkjs in a Web Worker.

**Performance:** Virtualization via `onlyRenderVisibleElements`. Above ~1.5k visible nodes → LOD mode (collapse low-severity subgraphs into cluster nodes, drop edge labels/animations).

---

#### Page 4 — Root-Cause Panel

| | |
|---|---|
| **Route** | `/case/:id/root-cause` |
| **Status** | Not started |
| **Purpose** | Present the causal apex (`PIPE-ZN-44`) and why it beats the loud 911 symptom — Wizard Step 3 |

**Layout:**

```
┌─ Root Cause Analysis ───────────────────────────────────────────────────┐
│  ┌─ Apex Card ──────────────────────────────────────────────────────┐   │
│  │  🎯 PIPE-ZN-44 — Trunk-main rupture, Zone 3                     │   │
│  │  Confidence: 0.91 (PyRCA + Granger)     Lead time: 5 min        │   │
│  │  [breathing red glow border]                                     │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─ Evidence Trail ─────────────────────────────────────────────────┐   │
│  │  1. Pressure −62% at 08:14 .......................... weight 0.42│   │
│  │  2. First in time, upstream in graph ................. weight 0.31│   │
│  │  3. All downstream paths trace here .................. weight 0.18│   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─ Candidate Ranking ──────────────────────────────────────────────┐   │
│  │  Rank │ Node          │ Causal Score │ Reason                     │   │
│  │  1    │ PIPE-ZN-44    │ 0.91         │ upstream apex              │   │
│  │  2    │ HOSP-ZN-NEW   │ 0.22         │ symptom — strain follows   │   │
│  │  3    │ PSAP-ZN       │ 0.08         │ loudest signal, lowest     │   │
│  │       │               │              │ causal score               │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─ Confidence Meter ──────────────────────────────────────────────┐    │
│  │  ████████████████████░░░  0.91 / 1.00  — HIGH                   │    │
│  │  Threshold for advance: ≥ 0.70                                  │    │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  [ Accept Root Cause ▶ ]                        [ Challenge ↻ ]         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Components:**

| Component | Description |
|---|---|
| `RootCausePanel` | Full-page container with apex card, evidence, ranking |
| Apex header card | Root-cause entity with breathing red glow (`animation: breathe 2s ease-in-out infinite`), confidence score, method used, lead time |
| `EvidenceTrail` | Ranked causal path with confidence + counterfactual evidence. Each item is expandable → jumps to source signal or graph node |
| `ConfidenceMeter` | Horizontal bar showing confidence level (0–1) against the 0.70 threshold |
| Candidate ranking table | All candidate root causes ranked by causal score with rejection reasons (DoWhy effect size, PyRCA score) |

**Data:** `GET /api/cases/:id/rca` → `{node_id, confidence, method, evidence[], rejected[]}` · WS channel: `ws:rca`

**Interactions:** "Accept root cause" → advances to Solutions (Step 4). "Challenge" → re-queues the Root-Cause agent node for reanalysis.

**Guard:** `root_cause.confidence ≥ 0.7` required to advance. Below threshold → CTA disabled with reason text.

---

#### Page 5 — Solution Review

| | |
|---|---|
| **Route** | `/case/:id/solutions` |
| **Status** | Not started |
| **Purpose** | Present the OR-Tools intervention set — Wizard Step 4. For Zarqa: isolate PIPE-ZN-44, open bypass, dispatch tankers |

**Layout:**

```
┌─ Candidate Solutions ───────────────────────────────────────────────────┐
│                                                                         │
│  ┌─ SOL-A (recommended) ────────────────────────────────────────────┐   │
│  │  Isolate ZN-44 + bypass via ZN-12 + 6 tankers to hospital       │   │
│  │  Actions: close valve V-441, open bypass V-128, dispatch tankers │   │
│  │  Projected Risk: 24  │  ETA: 35 min  │  Cost: $18k              │   │
│  │  ✓ Feasible  ★ Recommended                                      │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─ SOL-B ──────────────────────────────────────────────────────────┐   │
│  │  Full Zone-3 shutdown + citywide tanker relief                   │   │
│  │  Projected Risk: 41  │  ETA: 70 min  │  Cost: $60k              │   │
│  │  ✓ Feasible                                                      │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─ Tradeoff Table (visx) ──────────────────────────────────────────┐   │
│  │  Bar chart: risk reduction vs cost vs ETA for each candidate     │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─ Constraint Summary ────────────────────────────────────────────┐    │
│  │  Available tankers: 8/12 │ Bypass capacity: 70% │ Auth: needed  │    │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  [ Select & Validate ▶ ]                                                │
└─────────────────────────────────────────────────────────────────────────┘
```

**Components:**

| Component | Description |
|---|---|
| `SolutionCards` | Grid of `InterventionCard` components, each showing title, actions list, projected risk, ETA, cost, feasibility, and recommended flag |
| `InterventionCard` | Single intervention card with left accent border colored by predicted severity band. Props: `intervention`, `riskDelta`, `cost`, `eta`, `selected`, `onSelect` |
| `TradeoffTable` | visx grouped bar chart comparing risk reduction vs cost vs ETA across candidates |
| Constraint summary | Resource/authority/time constraints panel (available tankers, bypass capacity, authorization requirement) |

**Data:** `GET /api/cases/:id/interventions` · WS channel: `ws:solutions`

**Interactions:** Select exactly one candidate → "Validate" button launches a simulation run (advances to Step 5).

**Guard:** Exactly one candidate must be selected to advance.

---

#### Page 6 — Simulation Console

| | |
|---|---|
| **Route** | `/case/:id/sim` |
| **Status** | Not started |
| **Purpose** | Prove the fix via WNTR/EPANET re-simulation — Wizard Step 5 — showing before/after risk |

**Layout:**

```
┌─ Simulation Console ───────────────────────────────────────────────────┐
│                                                                        │
│  ┌─ Run Status Stepper ────────────────────────────────────────────┐   │
│  │  ● Queued → ● Running (WNTR/EPANET) → ○ Complete               │   │
│  │  Elapsed: 12s / est. 45s                                        │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                        │
│  ┌─ Before ─────────────────┐  ┌─ After ──────────────────────────┐   │
│  │  National Risk: 84       │  │  National Risk: 22               │   │
│  │  911 load: +320%         │  │  911 load: +41%                  │   │
│  │  Hospital: 94% cap       │  │  Hospital: 62% cap               │   │
│  │  Pressure map (red)      │  │  Pressure map (green)            │   │
│  │  ████████████ 0.84       │  │  ███        0.22  ✓ validated    │   │
│  └──────────────────────────┘  └───────────────────────────────────┘   │
│                                                                        │
│  ┌─ Recharts: Before/After Risk Bars ──────────────────────────────┐   │
│  │  [risk index] [911 calls] [hospital load] [pressure]            │   │
│  │  red bars (before) vs green bars (after)                        │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                        │
│  ┌─ MapDiff ───────────────────────────────────────────────────────┐   │
│  │  Side-by-side MapLibre: pressure network before vs after        │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                        │
│  Artifact: sim_run_2026-05-31_zarqa.json (MinIO) [Download]            │
│                                                                        │
│  [ Re-run with edits ]                     [ Promote to Decision ▶ ]   │
└────────────────────────────────────────────────────────────────────────┘
```

**Components:**

| Component | Description |
|---|---|
| `SimConsole` | Full simulation page container |
| `SimDiff` | Split-panel before/after view: pressure map, 911 projection, national risk index. Props: `before: RiskSnapshot`, `after: RiskSnapshot`, `metrics` |
| `BeforeAfterRisk` | Recharts grouped bar chart comparing metrics pre/post simulation |
| `MapDiff` | Side-by-side MapLibre maps showing pipe network pressure before vs after |
| Run-status stepper | Progress indicator: Queued → Running → Complete with elapsed time |
| Artifact link | Download link to MinIO-stored simulation output (JSON, hydraulic plots) |

**Data:** `POST /api/cases/:id/simulate` → Arq job. Progress + result on `ws:sim:{runId}`. Artifact stored in S3/MinIO.

**Interactions:** "Re-run with edits" → re-launches sim with modified parameters. "Promote to decision" → advances to Step 6.

**Guard:** `sim.status === 'succeeded'` AND `risk_after < risk_before` required to advance.

---

#### Page 7 — Decision Hub

| | |
|---|---|
| **Route** | `/case/:id/decide` |
| **Status** | Not started |
| **Purpose** | The human authorization gate — Wizard Step 6 — with full audit context. The only mutating action in the wizard |

**Layout:**

```
┌─ Decision Hub ─────────────────────────────────────────────────────────┐
│                                                                        │
│  ┌─ Recommendation Summary ────────────────────────────────────────┐   │
│  │  Root Cause: PIPE-ZN-44 (trunk-main rupture)                    │   │
│  │  Intervention: Isolate ZN-44 + bypass via ZN-12 + 6 tankers     │   │
│  │  Confidence: 0.91 │ Sim validated: ✓ │ Risk: 84 → 22            │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                        │
│  ┌─ Validated Risk Delta ──────────────────────────────────────────┐   │
│  │  Before: ████████████ 84 (critical)                             │   │
│  │  After:  ███          22 (nominal)    Δ = −62  (−74%)           │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                        │
│  ┌─ RBAC Actor Badge ─────────────────────────────────────────────┐    │
│  │  Cmdr. Haddad │ Role: commander │ Auth level: AUTHORIZE         │    │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                        │
│  ┌─ Audit Preamble ───────────────────────────────────────────────┐    │
│  │  This action will:                                              │    │
│  │  • Dispatch intervention to field teams                         │    │
│  │  • Write immutable audit record to S3/MinIO                     │    │
│  │  • Record decision with full evidence lineage                   │    │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                        │
│  ┌─ Justification ────────────────────────────────────────────────┐    │
│  │  [textarea: required justification for audit trail]             │    │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                        │
│  [ Request Changes ]  [ Reject ]  [ 🔒 AUTHORIZE — type name to confirm ]│
└────────────────────────────────────────────────────────────────────────┘
```

**Components:**

| Component | Description |
|---|---|
| `DecisionHub` | Full decision page with summary, risk delta, actor badge, audit context |
| `DecisionGate` | Three-action control: Authorize / Reject / Request-changes, each requiring a typed justification |
| `AuthorizeDialog` | Confirmation dialog requiring the officer to type their name to confirm. High-contrast alert framing, mono audit IDs |
| `RbacGate` | Checks user role (`commander` or `duty_officer`). Viewers see the summary but the authorize button is disabled |
| Recommendation summary | Read-only recap: root cause, intervention, confidence, sim result |
| Risk delta bar | Visual before/after risk comparison with percentage reduction |

**Data:** `GET /api/cases/:id/decision` · `POST /api/cases/:id/authorize` (writes immutable audit row) · WS channel: `ws:decisions`

**Interactions:** Authorize writes an immutable audit record, dispatches the intervention, and advances to Step 7. Uses `useMutation` with optimistic apply + rollback so the officer sees instant state.

**Guard:** RBAC role must be `duty_officer` or `commander`. Confirmation text must be typed. Justification required.

---

#### Page 8 — Outcome / Learn

| | |
|---|---|
| **Route** | `/case/:id/outcome` |
| **Status** | Not started |
| **Purpose** | Post-action telemetry and learning — Wizard Step 7. Terminal step |

**Layout:**

```
┌─ Outcome & Learn ──────────────────────────────────────────────────────┐
│                                                                        │
│  ┌─ Closed-Loop Summary ──────────────────────────────────────────┐    │
│  │  Case: ZARQA-2025-08 │ Duration: 47 min │ Status: RESOLVED      │    │
│  │  Root cause: PIPE-ZN-44 │ Fix: isolate+bypass+tanker            │    │
│  │  Risk: 84 → 22 (actual) │ Audit: AUD-2026-05-31-0042           │    │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                        │
│  ┌─ Post-Action Telemetry (live Timescale chart) ──────────────────┐   │
│  │  911 calls: returning to baseline ↘                              │   │
│  │  Hospital load: 94% → 68% → 52% ↘                               │   │
│  │  Pipe pressure: stabilized at 2.1 bar ✓                          │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                        │
│  ┌─ Learn Diff ───────────────────────────────────────────────────┐    │
│  │  What the engine learned:                                       │    │
│  │  • Rule weight updated: pressure_drop → cascade (0.72 → 0.88)  │    │
│  │  • New signal pattern stored in pgvector for future recall      │    │
│  │  • Similar-case embedding indexed for trunk-main failures       │    │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                        │
│  [ Close Case ]                              [ Replay This Case ↻ ]    │
└────────────────────────────────────────────────────────────────────────┘
```

**Components:**

| Component | Description |
|---|---|
| `OutcomePanel` | Full outcome summary: case metadata, duration, risk trajectory, audit ID |
| Post-action telemetry | Live Timescale-backed Recharts line chart showing 911 calls, hospital load, and pipe pressure returning to baseline over time |
| `LearnDiff` | What the engine learned — updated rule weights, new pgvector embeddings stored, pattern indexed for future recall |

**Data:** `GET /api/runs/:id/outcome` + ongoing `signal.created` WS events for live telemetry

**Interactions:** "Close case" emits `run.closed` event. "Replay this case" reloads the wizard in onboarding mode with the Zarqa fixture.

**Guard:** None — this is the terminal step.

---

#### Page 9 — Wizard Overlay (orchestrator)

| | |
|---|---|
| **Route** | Overlay (not a route) — syncs `wizardStep` in Zustand to the router |
| **Status** | Not started |
| **Purpose** | 7-step guided walkthrough that orchestrates Pages 2–8 along the engine loop |

**Layout:**

```
┌──── Progress Rail (sticky top): ●─●─●─●─●─◍─○  Step 5/7 · ~120s ─────┐
│ 1 Signals → 2 Incident → 3 Root Cause → 4 Solutions → 5 Validate      │
│ → 6 DECIDE → 7 Outcome                                                 │
└─────────────────────────────────────────────────────────────────────────┘
  [ Back ]           Main Step Viewport (slide + fade transitions)  [ Skip ▷ ]
                                                     [ Continue ▶ / AUTHORIZE 🔒 ]
```

**Components:**

| Component | Description |
|---|---|
| `WizardShell` | Top-level overlay rendering `ProgressRail`, `StepViewport`, `StepFooter`. Props: `steps`, `current`, `onStep`, `caseId` |
| `ProgressRail` | Horizontal 7-step progress bar with done/active/locked states. Display font for step labels |
| `StepViewport` | `AnimatePresence` container — slides + fades between step content (24px slide-x, 240ms ease-out-expo) |
| `StepFooter` | Back / Skip / Continue buttons. Step 6 swaps Continue for locked AUTHORIZE action |
| `CoachMark` | Tooltip overlays for onboarding mode (e.g. "Notice the brain ignores the loud 911 spike and points at PIPE-ZN-44") |

**Wizard Step → Page mapping:**

| Step | Page | CTA | Guard |
|---|---|---|---|
| 1 — Signals | Signal Explorer | Acknowledge feed | ≥1 signal ingested |
| 2 — Incident | Incident Graph | Confirm stitch | `incident.status='correlated'` and ≥2 entities resolved |
| 3 — Root Cause | Root-Cause Panel | Accept / Challenge | `confidence ≥ 0.7` |
| 4 — Solutions | Solution Review | Select candidate | Exactly one candidate selected |
| 5 — Validate | Simulation Console | Run / Re-run sim | `sim.succeeded` AND `risk_after < risk_before` |
| 6 — Decide | Decision Hub | AUTHORIZE 🔒 | RBAC role + typed confirmation |
| 7 — Outcome | Outcome / Learn | Close / Replay | None (terminal) |

**Guard logic (TypeScript contract):**

```ts
const GUARDS: Record<Step, (r: CaseRun) => GuardResult> = {
  signals:    r => ok(r.signals_count > 0),
  incident:   r => ok(r.incident?.status === 'correlated' && r.resolved_entities >= 2),
  root_cause: r => need(r.root_cause?.confidence >= 0.7, 'Confidence below 0.70'),
  solutions:  r => need(!!r.selected_candidate_id, 'Select one candidate'),
  validation: r => need(r.sim?.status === 'succeeded' && r.sim.risk_after < r.sim.risk_before, 'Sim must show risk reduction'),
  decide:     r => need(r.user.role !== 'viewer', 'Authorization requires duty_officer or commander'),
  outcome:    () => ok(true),
};
```

**Two modes:**

| Mode | Behavior |
|---|---|
| **Onboarding** (`mode='tour'`) | Loads Zarqa fixture, forces Back/Skip off, overlays CoachMark tooltips, replaces AUTHORIZE with sandbox no-op |
| **Live** (`mode='live'`) | Real data, Back/Skip-to-reached enabled, real RBAC, step transitions persisted to audit log |

**Keyboard:** Esc collapses overlay to a docked mini-tracker without losing run state.

---

### 9.3 Infrastructure to Wire

| Concern | What's needed |
|---|---|
| **Routing** | Add `react-router-dom` for screen navigation (cockpit, signals, graph, sim, decide) |
| **WebSocket client** | Native WS client connecting to `ws://localhost:8000/ws/case/{id}` with seq-gap detection, reconnect, and Query cache reconciliation |
| **REST API client** | Generated typed client from FastAPI OpenAPI schema (`/api/cases`, `/api/signals`, `/api/cases/:id/graph`, etc.) |
| **Environment config** | `.env` with `VITE_API_URL`, `VITE_WS_URL`, `VITE_MAP_STYLE_URL` (Zod-validated at boot) |
| **State stores** | Zustand slices: `wizardStore` (step, mode), `graphStore` (viewport, selected node), `mapStore` |
| **Testing** | Vitest + Testing Library for components, Playwright for the full wizard E2E spec |
| **CI** | GitHub Actions: typecheck → lint → vitest → build → Playwright against docker-compose |

### 9.4 Design System Upgrades

The current Tailwind theme uses a simplified color palette. The full design spec (in `docs/FRONTEND_BUILD.md` §1) calls for:

- **Severity ramp tokens:** `sev-0` (teal) through `sev-4` (red) replacing the current `danger`/`good`/`warn`
- **Panel depth scale:** `panel-1` / `panel-2` / `panel-3` with layered borders and shadows
- **Atmosphere effects:** Scanline + grain overlay at ~3% opacity, dot-grid backdrop for graph canvas
- **Motion system:** Staggered panel reveals, cascade edge animation, root-cause apex breathing glow
- **Font upgrade:** Clash Display (headers) + Hanken Grotesk (body) replacing current Geist/Inter

### 9.5 Backend Integration Points

When the FastAPI backend is available, the frontend needs to connect to:

| Endpoint | Method | Data |
|---|---|---|
| `/api/cases` | GET | List active crisis cases |
| `/api/cases/{id}/signals` | GET | Paginated signals (TimescaleDB) |
| `/api/cases/{id}/graph` | GET | Incident graph nodes + edges (AGE Cypher) |
| `/api/cases/{id}/root-cause` | GET | Causal apex + evidence (PyRCA/DoWhy) |
| `/api/cases/{id}/solutions` | GET | Ranked interventions (OR-Tools) |
| `/api/cases/{id}/simulate` | POST | Launch WNTR/EPANET sim (Arq job) |
| `/api/cases/{id}/decision` | GET/POST | Read/authorize decision (human gate) |
| `/ws/case/{id}` | WebSocket | Real-time signal/sim/graph/rca deltas |

---

## 10. Configuration Files Reference

| File | Purpose |
|---|---|
| `vite.config.ts` | Vite build config — React plugin enabled |
| `tailwind.config.js` | Custom theme: colors (bg, card, severity), fonts (Geist, mono), border radius |
| `postcss.config.js` | PostCSS pipeline: Tailwind CSS + Autoprefixer |
| `tsconfig.json` | Project references root → `tsconfig.app.json` + `tsconfig.node.json` |
| `tsconfig.app.json` | App code: ES2023 target, bundler module resolution, React JSX, strict linting |
| `tsconfig.node.json` | Config files (vite.config.ts): ES2023 target, Node types |
| `eslint.config.js` | Flat config: recommended TS + React Hooks + React Refresh rules |
| `.gitignore` | Ignores `node_modules/`, `dist/`, logs, editor files |

---

## 11. Troubleshooting

| Issue | Fix |
|---|---|
| `npm install` fails | Ensure Node 18+ is installed. Delete `node_modules` and `package-lock.json`, then retry |
| Port 5173 in use | Vite will auto-increment to 5174. Or kill the process: `lsof -ti:5173 \| xargs kill` |
| Fonts not loading | Check internet connection — Geist and Inter are loaded from Google Fonts CDN |
| Tailwind classes not applying | Ensure `postcss.config.js` has both `tailwindcss` and `autoprefixer` plugins |
| TypeScript errors on build | Run `npx tsc --noEmit` to check. The project uses `erasableSyntaxOnly: true` |
