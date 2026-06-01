# Frontend Build Guide — Crisis-Solving Brain Dashboard

**How the React frontend is built · design system · the dashboard wizard · a ready-to-paste Claude Design prompt · 2026-05-31**

This document specifies **how the frontend is built** for the General Crisis-Solving Brain dashboard: the bold *national crisis command-center* aesthetic, the React + TypeScript stack, every screen, the guided **dashboard wizard**, the state/real-time/graph-rendering model, and — at the end (§6) — a **copy-paste-ready prompt for Claude (frontend-design)** to generate the actual UI. Examples use the Zarqa demo case.

---

## 1. Design System & Aesthetic Direction

The UI is a **national crisis command center**: mission-control × financial-terminal. Dark, layered, information-dense but legible; color carries severity meaning, never decoration. Built with React 18 + TS, Vite, Tailwind, shadcn/ui (Radix), React Flow (graph), MapLibre GL, and Motion. The dependency **graph is the hero surface**; signal feed and decision queue live on asymmetric side rails.

### 1.1 Typography

Distinctive, characterful — not Inter/Roboto/system, not Space Grotesk. Self-hosted via Fontsource.

| Role | Font | Use |
|------|------|-----|
| Display / headers | **Clash Display** (humanist grotesque, tall) | Cockpit titles, wizard step headings, risk index |
| UI / body | **Hanken Grotesk** (precise humanist grotesque) | Panels, labels, tables, buttons |
| Mono / data | **JetBrains Mono** | Signal IDs (`PIPE-ZN-44`), telemetry, coords, timestamps, ΔRisk |

```ts
fontFamily: {
  display: ['"Clash Display"', 'system-ui', 'sans-serif'],
  sans:    ['"Hanken Grotesk"', 'system-ui', 'sans-serif'],
  mono:    ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
}
```
Type scale (1.250 major-third): `11 / 13 / 14 / 16 / 20 / 25 / 31 / 39px`. Telemetry uses `tabular-nums` + `slashed-zero`; IDs render uppercase, `tracking-wide`.

### 1.2 Color System

Dark base (near-black blue), depth via layered panels, **signal-coded severity ramp** calm teal → amber → alert red. Semantic tokens map to severity, not raw hues — a 911 surge node and the `PIPE-ZN-44` apex both pull from the ramp by score.

```css
:root {
  /* base / surfaces (layered depth) */
  --bg-void:    #070A0F;  --bg-base:   #0B0F16;
  --panel-1:    #11161F;  --panel-2:   #161D28;  --panel-3: #1E2631;
  --border:     #232C39;  --border-bright: #33415A;
  --ink:        #E6ECF5;  --ink-muted: #93A1B5;  --ink-faint: #5C6B82;
  /* severity ramp (the signal scale) */
  --sev-0: #1FB8A6;  /* calm   teal  — nominal       */
  --sev-1: #4BD0B0;  /* watch        — informational */
  --sev-2: #F5C451;  /* amber  — elevated / strain   */
  --sev-3: #F08A3C;  /* high   — cascading           */
  --sev-4: #F2545B;  /* alert  red — critical / apex */
  /* semantic */
  --accent:  #4EA8FF; /* interactive / focus  */
  --rootcause: #F2545B; /* causal apex glow    */
  --ok: #1FB8A6;  --info: #4EA8FF;  --warn: #F5C451;  --crit: #F2545B;
}
```
Tailwind exposes these as `bg-panel-1`, `text-ink-muted`, `severity-4`, etc. Severity is the single source of node/edge/badge color across React Flow, MapLibre, and Recharts.

| Score | Token | Zarqa example |
|-------|-------|---------------|
| 0.0–0.2 | `sev-0` teal | hospital nominal |
| 0.4–0.6 | `sev-2` amber | traffic congestion |
| 0.6–0.8 | `sev-3` orange | hospital strain |
| 0.8–1.0 | `sev-4` red | `PIPE-ZN-44` rupture, 911 +320% |

### 1.3 Spacing, Radius, Elevation

```ts
spacing: 4px base → {1:4, 2:8, 3:12, 4:16, 6:24, 8:32, 12:48}
borderRadius: { sm:4, md:6, lg:10, xl:14, panel:12, pill:9999 }
```
Elevation = surface tint + hairline border + soft shadow (no heavy drop-shadows):

| Level | Surface | Border | Shadow |
|-------|---------|--------|--------|
| rail | `panel-1` | `border` | none |
| card | `panel-2` | `border` | `0 1px 0 #0006` |
| float / popover | `panel-3` | `border-bright` | `0 8px 30px #000A` |
| alert apex | `panel-2` | `--rootcause` | `0 0 0 1px #F2545B55, 0 0 24px #F2545B33` |

### 1.4 Texture & Atmosphere

- **Scanline + grain:** fixed `::after` overlay, repeating 3px horizontal lines at `opacity .03` + SVG fractal-noise grain at `.02`. Crisis-terminal feel without noise.
- **Grid wash:** hero graph backdrop = 32px dot grid (React Flow `<Background variant="dots">`), `--border` at 40%.
- **Glow ramp:** severity ≥ `sev-3` nodes/edges get a matching `drop-shadow`; apex pulses (§1.5).
- No pure black, no pure white, no flat even grey fields.

### 1.5 Motion Principles

Purposeful, staggered, meaning-bearing. Motion (Framer Motion); honor `prefers-reduced-motion`.

| Pattern | Spec |
|---------|------|
| Panel reveal (load) | stagger 60ms, `y:8→0`, fade, `spring(260,30)` |
| Cascade propagation | edges animate stroke-dashoffset apex→leaf, 400ms/hop, severity-colored |
| Signal pulse | new feed item: 1.2s ring pulse in its severity color |
| Root-cause apex | infinite 2s breathe: `box-shadow` 16px↔28px red glow |
| Wizard transition | step slide-x 24px + crossfade, 240ms `ease-out-expo` |
| Risk index tick | number roll + brief color flash on severity-band change |

### 1.6 Component Look & Feel

- **Panels:** `panel-2`, `rounded-panel`, hairline border, uppercase `mono` eyebrow label (`text-ink-faint tracking-wider`) + `display` title. Header rule line `border-bright`.
- **Cards (signals/solutions):** left 3px severity spine, `mono` ID row, `sans` body, status pill. Hover lifts to `panel-3`.
- **Graph canvas (hero):** dark dot-grid; nodes = rounded rects tinted + glowing by severity; root-cause apex outlined red + breathing; edges directional, animated during propagation, weight = propagation strength. Mini-map + severity legend pinned.
- **Alerts:** inline severity banners, no toasts for critical — a persistent **alert rail** badge with count; `sev-4` items sort to top, red spine + glow.
- **Wizard overlay:** left vertical 7-step stepper (Signals→Outcome) with done/active/locked states; right content stage with slide transitions; sticky footer **Back / Advance**, and a guarded red **Authorize** gate at Step 6.
- **Buttons:** primary = `accent` solid; destructive/authorize = `crit` solid with confirm; ghost = border-only. Focus ring `accent` 2px.

### 1.7 Tailwind Theme Token Snippet

```ts
// tailwind.config.ts — theme.extend
colors: {
  void:'#070A0F', base:'#0B0F16',
  panel:{1:'#11161F',2:'#161D28',3:'#1E2631'},
  border:{DEFAULT:'#232C39', bright:'#33415A'},
  ink:{DEFAULT:'#E6ECF5', muted:'#93A1B5', faint:'#5C6B82'},
  severity:{0:'#1FB8A6',1:'#4BD0B0',2:'#F5C451',3:'#F08A3C',4:'#F2545B'},
  accent:'#4EA8FF', rootcause:'#F2545B',
  ok:'#1FB8A6', info:'#4EA8FF', warn:'#F5C451', crit:'#F2545B',
},
borderRadius:{ sm:'4px', md:'6px', lg:'10px', xl:'14px', panel:'12px' },
boxShadow:{
  card:'0 1px 0 #0006',
  float:'0 8px 30px #000A',
  apex:'0 0 0 1px #F2545B55, 0 0 24px #F2545B33',
},
keyframes:{ breathe:{'0%,100%':{boxShadow:'0 0 16px #F2545B33'},'50%':{boxShadow:'0 0 28px #F2545B66'}} },
animation:{ breathe:'breathe 2s ease-in-out infinite' },
```

---

## 2. Frontend Tech Stack & Project Structure

The frontend is a **React 18 + TypeScript SPA** built with **Vite**, styled with **Tailwind + shadcn/ui**, with **React Flow** as the hero dependency-graph canvas. Server state lives in **TanStack Query**; ephemeral UI state (wizard step, selected node, panel layout) in **Zustand**. Realtime cascade updates arrive over a **native WebSocket** and hydrate the Query cache. The whole thing renders the Zarqa case — `PIPE-ZN-44` rupture → hospital/traffic/911 cascade → validated fix — as a guided 7-step wizard.

### 2.1 Dependency table

| Package | Version | Role in the system |
|---|---|---|
| `react` / `react-dom` | 18.3 | UI runtime, concurrent rendering for the live signal feed |
| `typescript` | 5.5 | Strict types end-to-end; shared API types generated from FastAPI OpenAPI |
| `vite` | 5.x | Dev server (HMR), build, env handling |
| `tailwindcss` | 3.4 | Utility styling, severity color ramp tokens (teal→amber→red) |
| `shadcn/ui` + `@radix-ui/*` | latest | Accessible primitives: Dialog (wizard overlay), Tabs, Command, Toast |
| `@tanstack/react-query` | 5.x | Server state: cases, signals, root-cause, sim runs; WS-driven cache updates |
| `zustand` | 4.x | UI state: active wizard step, selected graph node, map viewport |
| `reactflow` | 11.x | Incident dependency graph canvas — nodes (assets/incidents), animated cascade edges |
| `@visx/*` | 3.x | Risk-index sparklines, before/after simulation bars, 911-surge time-series |
| `recharts` | 2.x | Quick dashboard charts (cockpit KPI cards) |
| `maplibre-gl` | 4.x | Geospatial layer (OSM tiles): pipe network, hospital, tanker routes in Zarqa |
| `motion` (Framer Motion) | 11.x | Staggered panel reveals, edge-propagation animation, wizard transitions, signal pulse |
| `vitest` + `@testing-library/react` | latest | Unit/component tests |
| `@playwright/test` | latest | E2E: full Zarqa wizard walkthrough |
| `orval` / `openapi-typescript` | latest | Generates TS client + types from FastAPI schema |

Fonts (self-hosted via `@fontsource`): **Space Mono → no**; instead **Söhne**-style is avoided — headers use **Clash Display** (characterful technical display), UI uses **Hanken Grotesk** (precise humanist grotesk), data/IDs use **JetBrains Mono** (telemetry, `PIPE-ZN-44`, coordinates).

### 2.2 Folder structure

```
src/
├── app/                      # shell, providers, router, global layout grid
│   ├── App.tsx               # QueryClientProvider, WS provider, theme
│   └── routes.tsx            # cockpit / signals / graph / decisions
├── features/                 # vertical slices — each owns its UI + hooks + api
│   ├── cockpit/              # National Crisis Cockpit (risk index, KPI rail)
│   ├── signals/              # Signal Explorer + live feed side rail
│   ├── incident-graph/       # React Flow canvas, custom nodes/edges, layout
│   ├── root-cause/           # causal-apex panel + evidence chain
│   ├── solutions/            # candidate intervention review
│   ├── simulation/           # Simulation Console (before/after risk)
│   ├── decision-hub/         # authorize gate (human-in-the-loop)
│   └── wizard/               # 7-step overlay orchestrating the above
├── components/               # shared dumb UI (shadcn wrappers, SeverityBadge)
├── lib/                      # ws client, query keys, formatters, severity ramp
├── hooks/                    # cross-feature hooks (useCase, useWebSocket)
├── stores/                   # zustand slices (wizardStore, graphStore, mapStore)
├── api/                      # generated client + typed query/mutation fns
├── styles/                   # tailwind base, tokens, grain/scanline overlay
└── test/                     # vitest setup, MSW handlers, fixtures (zarqa.json)
```

**Feature-slice rule:** anything used by one screen stays in `features/<x>/`; promote to `components/`/`lib/` only on second use. Cross-cutting flow (wizard) composes feature components, never reimplements them.

### 2.3 State & data flow

```
FastAPI REST ──► api/ (generated) ──► TanStack Query ──┐
                                                        ├──► feature hooks ──► components
WS /ws/case/{id} ──► lib/ws ──► queryClient.setQueryData ┘
Zustand (wizardStore, graphStore) ──► UI-only selection/step state
```

REST seeds the case; the WebSocket streams `signal.ingested`, `edge.propagated`, `rootcause.found`, `sim.complete` events that patch the cache so the React Flow canvas animates the cascade live.

### 2.4 Build, env & testing

**Scripts:** `dev` (Vite HMR), `build` (`tsc -b && vite build`), `preview`, `test` (Vitest), `e2e` (Playwright), `gen:api` (regenerate client from `/openapi.json`), `lint`/`typecheck`.

**Env (`.env`, Vite `VITE_`-prefixed, validated at boot via Zod):**

```
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000/ws
VITE_MAP_STYLE_URL=https://tiles.local/osm.json   # MapLibre style
VITE_TILE_CACHE=true
```

**Testing approach (Goal-driven, per the wizard contract):**
- **Unit/component (Vitest + Testing Library):** severity ramp logic, root-cause apex selection rendering, graph node reducers. API mocked with **MSW** using `zarqa.json` fixtures.
- **E2E (Playwright):** one canonical spec drives the entire wizard — ingest signals → assert stitched incident graph has `PIPE-ZN-44` node → assert Root-Cause panel names the rupture (NOT the 911 surge) → run simulation → assert after-risk < before-risk → authorize. This spec is the executable definition of "MVP runs end-to-end."
- **CI (GitHub Actions):** typecheck → lint → vitest → build → Playwright against a docker-compose stack.

---

## 3. Screens, Information Architecture & Components

The frontend is a single-page React 18 + TypeScript app (Vite). All screens hang off one persistent **CommandShell** (top status bar with National Risk Index + clock, left nav rail, right Decision Queue rail). Server state comes from FastAPI via TanStack Query; live mutations stream over a single native WebSocket multiplexed by `channel`. UI state (active wizard step, selected node, panel collapse) lives in Zustand. Every screen consumes design-system tokens from §1: severity ramp (`--sev-calm` teal → `--sev-watch` amber → `--sev-alert` red), the layered panel depth scale, mono font for IDs/telemetry, the display face for headers.

### 3.1 Screen Map

| Screen | Route | Reads | Live channel |
|---|---|---|---|
| National Crisis Cockpit | `/` | `GET /api/cases`, `GET /api/risk/national` | `ws:risk`, `ws:cases` |
| Signal Explorer | `/signals` | `GET /api/signals?case=…` (Timescale) | `ws:signals` |
| Incident Graph | `/case/:id/graph` | `GET /api/cases/:id/graph` (AGE Cypher) | `ws:graph` |
| Root-Cause Panel | `/case/:id/root-cause` | `GET /api/cases/:id/rca` (PyRCA/DoWhy) | `ws:rca` |
| Solution Review | `/case/:id/solutions` | `GET /api/cases/:id/interventions` | `ws:solutions` |
| Simulation Console | `/case/:id/sim` | `POST /api/cases/:id/simulate` (WNTR job) | `ws:sim:{runId}` |
| Decision Hub | `/case/:id/decide` | `GET /api/cases/:id/decision` | `ws:decisions` |

The **Wizard** (`WizardShell`) is an overlay, not a route: it pins the seven steps (Signals→Stitched→Root Cause→Solutions→Validation→Decide→Learn) to the matching screen, syncing `wizardStep` in Zustand to the router.

### 3.2 National Crisis Cockpit

**Purpose:** at-a-glance posture across all live cases; entry point that escalates the Zarqa case into the wizard.

```
┌ STATUS BAR: NATIONAL RISK 0.71 ▲  | 14:32:07Z | 3 ACTIVE ───────────────┐
├──────────┬─────────────────────────────────────────┬──────────────────┤
│ NAV RAIL │  ┌─ RiskGauge ─┐  ┌─ MapLibre (PostGIS) ─┐ │ DECISION QUEUE   │
│ ▸Cockpit │  │   0.71 ▲    │  │  ● Zarqa  ▴ rupture  │ │ ┌ Intervention─┐ │
│  Signals │  │  alert-red  │  │  ◦ Irbid  ◦ Amman    │ │ │ ISOLATE+BYP. │ │
│  Graph   │  └─────────────┘  └──────────────────────┘ │ │ AWAIT AUTH   │ │
│  Sim     │  ┌─ Active Cases (sortable) ─────────────┐ │ └──────────────┘ │
│  Decide  │  │ ZARQA-WATER-CASCADE  sev�@alert  +320%│ │  SeverityBadge×3 │
│          │  │ AMMAN-GRID-DIP       sev@watch       │ │                  │
└──────────┴───────────────────────────────────────────┴──────────────────┘
```

**Components:** `RiskGauge`, `MapLibre` incident layer, case table (shadcn `DataTable`), `SeverityBadge`, right-rail `InterventionCard` stubs. **Interactions:** click a case row → routes to `/case/:id/graph` and opens the wizard at Step 2; map markers pulse (Motion) on new `ws:risk` ticks.

### 3.3 Signal Explorer

**Purpose:** raw signal triage — the Step 1 surface. Shows the 911 surge, hospital strain, SCADA pressure drop streaming in.

**Components:** `SignalFeed` (virtualized list, live pulse), faceted filter bar (source/type/severity), a `visx` time-series of signal rate (Timescale `time_bucket`), detail drawer with raw payload + pgvector "similar past signals". **Reads:** `GET /api/signals?case=ZARQA…&since=…`; subscribes `ws:signals`. **Interactions:** select signals → "Stitch into incident" dispatches the resolve/correlate agents and advances the wizard.

### 3.4 Incident Graph (hero surface)

**Purpose:** the stitched property graph — the cascade — rendered as the dominant canvas. This is where `PIPE-ZN-44` visually anchors the downstream fan-out.

```
┌─ Incident Graph ────────────────────────── [fit] [layout▾] [replay ▸] ┐
│   (PIPE-ZN-44)══RUPTURE══►(ZONE-NORTH lo-press)                        │
│        ╠═►(HOSP-ZARQA strain)══►(911 SURGE +320%)  ◄ loud symptom      │
│        ╚═►(TRAFFIC-HW35)                                               │
│  edges animate in cascade order; node color = SeverityBadge ramp      │
├───────────────────────────────────────────────────────────────────────┤
│ inspector: selected = PIPE-ZN-44 | type:trunk_main | flow:0 L/s        │
└───────────────────────────────────────────────────────────────────────┘
```

**Components:** `GraphCanvas` (React Flow), `replay` scrubber (Motion staggers edges in propagation order), node inspector. **Reads:** `GET /api/cases/:id/graph` returns AGE Cypher result `{nodes[], edges[]}`; `ws:graph` patches deltas. **Interactions:** click node → inspector + cross-highlights its signals; "Find root cause" triggers RCA.

### 3.5 Root-Cause Panel

**Purpose:** present the causal apex (`PIPE-ZN-44`) and *why* it beats the loud 911 symptom — Step 3.

**Components:** apex header card, `EvidenceTrail` (ranked causal path with confidence + counterfactual), candidate-cause ranking table (DoWhy effect size, PyRCA score). **Reads:** `GET /api/cases/:id/rca`. **Interactions:** expand each evidence link → jumps to source signal/graph node; "Accept root cause" → solutions.

### 3.6 Solution Review

**Purpose:** the OR-Tools intervention set — Step 4. For Zarqa: isolate `PIPE-ZN-44`, open bypass `PIPE-ZN-12`, dispatch tankers.

**Components:** `InterventionCard` grid (cost, ETA, predicted risk delta, side-effects), constraint summary. **Reads:** `GET /api/cases/:id/interventions`. **Interactions:** select a card → "Validate" launches a sim run.

### 3.7 Simulation Console

**Purpose:** prove the fix via WNTR/EPANET re-simulation — Step 5 — showing before/after risk.

**Components:** `SimDiff` (split before/after: pressure map, 911 projection, national risk), run-status stepper, artifact link (MinIO). **Reads:** `POST /api/cases/:id/simulate` → Arq job; progress + result on `ws:sim:{runId}`. **Interactions:** "Re-run with edits", "Promote to decision".

### 3.8 Decision Hub

**Purpose:** the human authorization gate — Step 6 — with full audit context.

**Components:** `DecisionGate` (Authorize / Reject / Request-changes with required justification), recommendation summary, validated-risk delta, RBAC actor badge. **Reads:** `GET /api/cases/:id/decision`; `POST /api/cases/:id/authorize`. **Interactions:** authorize writes an immutable audit record and advances to Step 7 (Outcome/Learn).

### 3.9 Component Inventory

| Component | Key props | Design-system ties (§1) |
|---|---|---|
| `WizardShell` | `steps: Step[]`, `current`, `onStep`, `caseId` | step rail uses display face; reveal = Motion stagger |
| `GraphCanvas` | `nodes`, `edges`, `severityOf(n)`, `onSelect`, `replay?: {order, speed}` | severity ramp on nodes, mono ID labels, panel depth |
| `RiskGauge` | `value: 0..1`, `delta`, `band: 'calm'\|'watch'\|'alert'` | ramp arc, mono readout |
| `SignalFeed` | `signals: Signal[]`, `onSelect`, `live` | pulse animation, mono timestamps, `SeverityBadge` |
| `EvidenceTrail` | `path: EvidenceLink[]`, `confidence`, `onJump` | layered cards, confidence as ramp tint |
| `InterventionCard` | `intervention`, `riskDelta`, `cost`, `eta`, `selected`, `onSelect` | accent border = predicted band |
| `SimDiff` | `before: RiskSnapshot`, `after: RiskSnapshot`, `metrics` | split-panel depth, ramp deltas |
| `DecisionGate` | `recommendation`, `actor`, `onDecision(verdict, note)` | high-contrast alert framing, mono audit IDs |
| `SeverityBadge` | `level: 'calm'\|'watch'\|'alert'`, `value?` | the canonical severity-ramp atom |

Shared types (`Signal`, `Intervention`, `RiskSnapshot`, `EvidenceLink`) are generated from the FastAPI OpenAPI schema, keeping props in lockstep with the backend contract.

---

## 4. The Dashboard Wizard — UX Flow

The Wizard is a **Motion-animated overlay** that walks a duty officer through one case along the engine loop. It is driven by a single `CaseRun` resource streamed over WebSocket (`/ws/case/{run_id}`) and hydrated via TanStack Query (`/api/runs/{run_id}`). UI step/visited/skip state lives in a Zustand `useWizardStore`; server truth (node statuses, artifacts) lives in TanStack Query cache. The same component tree serves both modes: **ONBOARDING** replays a canned Zarqa run with coach-mark callouts and forced linear progression; **LIVE CASE** binds to a real run, unlocks back/skip, and arms the human gate at Step 6.

```
 ┌──── progress rail (sticky top): ●─●─●─●─●─◍─○  Step 5/7 · ~120s elapsed ────┐
 │ 1 Signals → 2 Incident → 3 RootCause → 4 Solutions → 5 Validate → 6 DECIDE → 7 Outcome
 └────────────────────────────────────────────────────────────────────────────┘
   [ Back ]                 main step viewport (React Flow / Map / panels)        [ Skip ▷ ]
                                                                       [ Continue ▶ / AUTHORIZE 🔒 ]
   guard: each Continue calls canAdvance(step) → blocked steps disable the CTA + show reason
```

`<WizardShell>` renders `<ProgressRail>`, `<StepViewport>` (`AnimatePresence` slide+fade per step), and `<StepFooter>`. `Back` decrements (disabled at Step 1, and during onboarding). `Skip` jumps forward only to already-`reached` steps. `Continue` runs the step guard; **Step 6 swaps the CTA for a locked AUTHORIZE action** requiring an authenticated `commander`/`duty_officer` RBAC role + typed confirmation. Esc collapses the overlay to a docked mini-tracker without losing run state.

### Per-step specification (grounded in the Zarqa cascade)

| # | Step | User sees | Component(s) | Data source | CTA | Guard → advance |
|---|------|-----------|--------------|-------------|-----|------------------|
| 1 | **Signals** | Live feed of raw signals, severity-coded, with a "+320% 911" pulse and PostGIS mini-map of Zarqa North | `<SignalFeed>` (virtualized), `<PulseBadge>`, MapLibre `<SignalMap>` | Timescale hypertable via `/api/runs/{id}/signals`; realtime `signal.created` WS events | **Acknowledge feed** | ≥1 signal ingested (`run.signals_count>0`) → Resolve fires |
| 2 | **Stitched Incident** | One incident graph: 911 surge, hospital strain, traffic, `PIPE-ZN-44` as nodes; edges animate in as correlation lands | React Flow `<IncidentCanvas>`, `<EntityResolveBadge>` (Splink merges) | AGE Cypher `MATCH (i:Incident)-[:INVOLVES]->(e) ...` via `/api/runs/{id}/graph` | **Confirm stitch** | `incident.status='correlated'` and ≥2 entities resolved |
| 3 | **Root Cause** | Causal apex highlighted = `PIPE-ZN-44` rupture (NOT the loud 911 symptom), with ranked evidence + confidence | `<RootCausePanel>`, `<EvidenceList>`, `<ConfidenceMeter>` | PyRCA/DoWhy output `/api/runs/{id}/root-cause` (`{node_id, confidence, evidence[]}`) | **Accept root cause** / Challenge | `root_cause.confidence ≥ 0.7`; Challenge re-queues Root-Cause node |
| 4 | **Candidate Solutions** | 2–3 ranked interventions: *isolate PIPE-ZN-44 + bypass + tanker stopgap*, with cost/ETA/coverage | `<SolutionCards>`, `<TradeoffTable>` (visx) | OR-Tools intervention search `/api/runs/{id}/solutions` | **Select candidate** | exactly one candidate selected → Validate node primed |
| 5 | **Validation / Sim** | Before/after risk: 911 load and hospital strain projected to fall post-fix; WNTR/EPANET re-sim diff | `<SimConsole>`, `<BeforeAfterRisk>` (Recharts), `<MapDiff>` | Arq sim job → S3 artifact `/api/runs/{id}/sims/{sim_id}` | **Run / Re-run simulation** | sim `status='succeeded'` AND `risk_after < risk_before` |
| 6 | **Decide & Authorize** 🔒 | Decision summary, residual risk, audit preamble; **human gate** | `<DecisionHub>`, `<AuthorizeDialog>`, `<RbacGate>` | `POST /api/runs/{id}/decision` (writes immutable audit row) | **AUTHORIZE** (typed name + role check) | RBAC role ∈ {duty_officer,commander} AND confirmation typed → intervention dispatched |
| 7 | **Outcome / Learn** | Post-action telemetry: 911 returning to baseline; what the engine learned (rule weights updated) | `<OutcomePanel>`, `<LearnDiff>`, live Timescale chart | `/api/runs/{id}/outcome` + ongoing `signal.created` WS | **Close case / Start next** | none — terminal; emits `run.closed` |

### Guards, JSON contract & modes

Each step's guard is a pure predicate evaluated against the cached run snapshot; the footer CTA binds to it:

```ts
const GUARDS: Record<Step, (r: CaseRun) => GuardResult> = {
  signals:    r => ok(r.signals_count > 0),
  incident:   r => ok(r.incident?.status === 'correlated' && r.resolved_entities >= 2),
  root_cause: r => need(r.root_cause?.confidence >= 0.7, 'Confidence below 0.70 — challenge or wait'),
  solutions:  r => need(!!r.selected_candidate_id, 'Select one candidate'),
  validation: r => need(r.sim?.status === 'succeeded' && r.sim.risk_after < r.sim.risk_before, 'Sim must show risk reduction'),
  decide:     r => need(r.user.role !== 'viewer', 'Authorization requires duty_officer or commander'),
  outcome:    () => ok(true),
};
```

WS frames advance the rail automatically (`{type:'node.completed', node:'root_cause'}` marks Step 3 `reached`). The Step-6 authorization POST is the **only** mutating action in the wizard and is the human-in-the-loop gate: no intervention dispatches without it; the response carries the `audit_id` shown in Step 7.

**Onboarding mode** sets `useWizardStore.mode='tour'`: it loads the Zarqa fixture run, forces `Back`/`Skip` off, overlays `<CoachMark>` tooltips per step (e.g. "Notice the brain ignores the loud 911 spike and points at PIPE-ZN-44"), and replaces the live AUTHORIZE call with a sandbox no-op so new users reach Step 7 safely. **Live mode** (`mode='live'`) enables Back/Skip-to-reached, real RBAC, and persists every step transition to the audit log. Mode is the only behavioral switch; the component tree, guards, and data contracts are identical.

---

## 5. State, Data Flow, Real-Time & Graph Rendering

### 5.1 State Ownership

Two stores, strictly separated. **TanStack Query** owns all server-derived state (cache, refetch, mutation). **Zustand** owns ephemeral UI/wizard state that never touches the server.

| Concern | Owner | Example (Zarqa) |
|---|---|---|
| Signal pages, incident graph, root-cause report, sim runs, decisions | TanStack Query | `["incident", "INC-ZN-7"]` → stitched graph for the PIPE-ZN-44 cascade |
| Wizard step, selected node, graph viewport, panel layout, filters | Zustand | `wizardStep: 3 /* Root Cause */`, `selectedNodeId: "PIPE-ZN-44"` |
| Optimistic decision flag | TanStack mutation cache | `authorize(isolate+bypass+tanker)` pending |

Query key convention: `[domain, id, params]`. `staleTime` 30s for graph/report, `0` for live signal feed (WS-driven). All keys are typed via a `queryKeys` factory.

### 5.2 Data-Fetching Patterns

REST/FastAPI for snapshots + history; WebSocket for deltas. Initial load hydrates the cache; WS patches it.

```ts
// Snapshot load for Step 2 (Stitched Incident graph)
const { data: graph } = useQuery({
  queryKey: queryKeys.incidentGraph("INC-ZN-7"),
  queryFn: () => api.get(`/incidents/INC-ZN-7/graph`),  // nodes+edges from AGE Cypher
  staleTime: 30_000,
});
```

- Signals: cursor-paginated (`/signals?cursor=&limit=200`), backed by TimescaleDB hypertable; `useInfiniteQuery`.
- Root cause: `/incidents/{id}/root-cause` → causal apex + ranked evidence (PyRCA/DoWhy output).
- Geo (PostGIS) and embeddings (pgvector) ride the same incident payload; no separate round-trips for the wizard.

### 5.3 WebSocket Real-Time Channel

Single multiplexed socket `wss://api/ws?case=INC-ZN-7`, native `WebSocket`, JSON frames, server-assigned monotonic `seq` for gap detection. A thin client routes each frame into the Query cache via `queryClient.setQueryData` — **no refetch on the hot path**.

| Frame `type` | Reconciliation target |
|---|---|
| `signal.appended` | Prepend to `signals` infinite cache; trigger row "pulse" |
| `risk.updated` | Replace `riskIndex` cache (cockpit gauge) |
| `incident.patched` | Merge node/edge delta into `incidentGraph` cache |
| `rootcause.ready` | Set `rootCause` cache; advance wizard gate |
| `sim.progress` / `sim.done` | Stream into `simRun` cache (Simulation Console) |

```ts
ws.onmessage = (e) => {
  const f = JSON.parse(e.data);
  if (f.seq !== lastSeq + 1) refetchSnapshot();      // gap → resync
  lastSeq = f.seq;
  reconcilers[f.type](queryClient, f.payload);        // surgical setQueryData
};
```

Backpressure: signal frames coalesce in a 250ms buffer (rAF-flushed) so a +320% 911 surge can't thrash React. On disconnect: exponential backoff (1→30s), then one snapshot refetch to close the gap. Redis pub/sub fans the LangGraph node emissions out to socket subscribers.

### 5.4 Optimistic Decisions

The Decision Hub authorize action uses `useMutation` with optimistic apply + rollback, so the duty officer sees instant state.

```ts
useMutation({
  mutationFn: () => api.post(`/incidents/INC-ZN-7/decisions`,
    { action: "isolate+bypass+tanker", intervention: "PIPE-ZN-44" }),
  onMutate: async (v) => {
    await qc.cancelQueries({ queryKey: keys.decision("INC-ZN-7") });
    const prev = qc.getQueryData(keys.decision("INC-ZN-7"));
    qc.setQueryData(keys.decision("INC-ZN-7"),
      (d) => ({ ...d, status: "authorizing", action: v.action }));
    return { prev };
  },
  onError: (_e, _v, ctx) => qc.setQueryData(keys.decision("INC-ZN-7"), ctx.prev),
  onSettled: () => qc.invalidateQueries({ queryKey: keys.decision("INC-ZN-7") }),
});
```

The authoritative `decision.committed` WS frame (audit-logged, S3 export) later overwrites the optimistic value — server is the source of truth.

### 5.5 React Flow Graph Rendering

The incident graph is the hero surface. Zarqa's cascade is ~hundreds of nodes (pipe segments, hospital, traffic sensors, 911 cells); the strategy must scale to 5–10k.

- **Layout off the render thread:** elkjs (layered/`mrtree`) runs in a Web Worker; positions are computed once on `incident.patched`, memoized, and fed to React Flow. No layout in render.
- **Virtualization:** `onlyRenderVisibleElements`, viewport culling via `useStore`, and node `type` registry with `React.memo` custom nodes. Selector subscriptions (Zustand + RF store) prevent whole-canvas re-renders when one node updates.
- **Large-graph mode:** above ~1.5k visible nodes, switch to LOD — collapse low-severity subgraphs into cluster nodes, drop edge labels/animations, render via canvas-style minimal nodes.
- **Cascade animation (Motion):** edges animate in propagation order (PIPE-ZN-44 → trunk loss → hospital strain → traffic → 911) using `animated` edges gated by a Zustand `playhead`; severity ramp (teal→amber→red) maps to edge stroke. Animations disabled in large-graph mode.
- Edge/node deltas patch the RF state immutably; only changed nodes re-mount.

### 5.6 One-Case Data Flow (Zarqa)

```
 SCADA/911/hospital feeds
        │ ingest
        ▼
  FastAPI ──writes──► PostgreSQL16
   │  │              ├─ Timescale (signals)   ├─ AGE (incident graph)
   │  │              ├─ PostGIS (geo)         └─ pgvector (embeddings)
   │  └─ LangGraph swarm: Resolve→Correlate→RootCause(PyRCA)→Sim(WNTR)→Recommend
   │         │ node events
   │         ▼
   │      Redis pub/sub
   │         │
   ▼         ▼
 REST     WebSocket  (seq-ordered deltas)
   │         │
   └────┬────┘
        ▼
  TanStack Query cache  ◄── setQueryData reconcile (no refetch)
        │ selectors
        ▼
  React (Zustand UI/wizard)
   Step1 Signals ─► Step2 Graph(React Flow) ─► Step3 RootCause=PIPE-ZN-44
   ─► Step4 Solutions ─► Step5 Sim before/after ─► Step6 Authorize(optimistic)
   ─► Step7 Outcome/Learn
```

Result: raw +320% 911 surge enters as signals, the swarm patches the graph and names **PIPE-ZN-44** the causal apex (not the loud symptoms), simulation proves *isolate + bypass + tanker*, and the optimistic authorize commits through the same cache — all on one socket, one Query store.

---

## 6. Ready-to-Use Claude Design Prompt

**How to use:** Open Claude (or Claude Code with the `frontend-design` skill), paste the entire block below as your message, and let it scaffold the UI. It is self-contained — fonts, color tokens, stack, screens, sample Zarqa data, and motion are all inline. Generate the Cockpit + Incident Graph + Wizard first; iterate on the remaining screens after.

```text
You are building the frontend for AEGIS — a national crisis-solving command center. Build a
production-grade React UI, not a demo. Commit boldly to the aesthetic. Reject generic AI slop.

## STACK (use exactly — do not substitute)
React 18 + TypeScript + Vite. Tailwind CSS + shadcn/ui (Radix). TanStack Query (server state) +
Zustand (UI state). React Flow for the dependency graph. visx/Recharts for charts. MapLibre GL
(OSM tiles) for geo. Motion (Framer Motion) for animation. Native WebSocket for realtime.
Backend is FastAPI (REST + WS) over PostgreSQL 16 (Apache AGE graph, pgvector, PostGIS,
TimescaleDB). Assume REST under /api and a WS at /ws/case/{id} streaming the events below.

## AESTHETIC — mission-control × financial-terminal, calm under pressure
Dark, high-contrast, information-dense but legible. Layered panels with depth (inset borders,
soft shadow, a faint scanline/grain texture overlay at ~3% opacity). Precise 8px grid. Color
carries MEANING (severity), never decoration. No timid even greys. No glassmorphism, no neon
gradients, no purple/blue startup hero, no center-stacked marketing layout, no emoji icons,
no rounded-pill everything. Striking but never noisy.

### Fonts (load via Fontsource/Google; do NOT use Inter, Roboto, Arial, system-ui, Space Grotesk)
- Display / headers: "Neue Haas Grotesk Display" — fallback "Eurostile", "Michroma"
- UI / body: "Söhne" — fallback "IBM Plex Sans"
- Mono / IDs / telemetry: "Berkeley Mono" — fallback "JetBrains Mono", "IBM Plex Mono"
All IDs, coordinates, timestamps, metrics render in mono with tabular-nums.

### Color tokens (Tailwind theme.extend.colors + CSS vars, dark base)
| token            | hex      | use                                  |
|------------------|----------|--------------------------------------|
| bg.void          | #0A0E12  | app background                       |
| bg.panel         | #121821  | panels                               |
| bg.raised        | #1A2230  | cards / headers                      |
| line.hair        | #232C3A  | hairline borders                     |
| txt.primary      | #E6EDF3  | primary text                         |
| txt.muted        | #8A97A6  | labels                               |
| sev.calm         | #2DD4BF  | teal — nominal                       |
| sev.watch        | #FBBF24  | amber — elevated                     |
| sev.alert        | #F43F5E  | red — critical                       |
| accent.signal    | #38BDF8  | live signal pulse / focus ring       |
Severity ramp calm→watch→alert drives node fills, edge glow, badges, the risk gauge.

## SCREENS (build in this order)
1. National Crisis Cockpit — hero overview
2. Incident Graph — React Flow canvas (the hero surface)
3. Wizard overlay — 7 guided steps
Then: Signal Explorer, Root-Cause Panel, Solution Review, Simulation Console, Decision Hub.

### Layout — command-center grid (1440×900 baseline)
+--------------------------------------------------------------+
| TOPBAR  AEGIS · National Risk Index 72 ▲ · UTC clock · user  |
+----------+--------------------------------------+------------+
| LEFT RAIL| HERO: Incident Graph (React Flow)    | RIGHT RAIL |
| signal   |  nodes = entities, edges = cascade   | decision   |
| feed     |  animated propagation, severity fill | queue +    |
| (live,   |                                      | risk gauge |
| pulsing) +--------------------------------------+ + step nav |
|          | BOTTOM: timeline scrubber + charts   |            |
+----------+--------------------------------------+------------+
Asymmetric rails: left signal feed ~300px, hero flexes, right decision rail ~340px.

## DEMO DATA — Zarqa water-pipe cascade (wire components to this exact shape)
A trunk-main rupture (PIPE-ZN-44) cascades to hospital strain, traffic, and a 911 surge (+320%).
The brain must name the RUPTURE as root cause — NOT the loud 911/hospital symptoms — and output a
validated fix (isolate + bypass + tanker stopgap), proven by re-simulation.

// GET /api/case/zarqa-001/signals  → live feed (TimescaleDB)
[
  {"id":"SIG-9001","ts":"2026-05-31T08:14:03Z","source":"SCADA","type":"pressure_drop",
   "entity":"PIPE-ZN-44","value":-62,"unit":"%","severity":"alert","geo":[36.087,32.072]},
  {"id":"SIG-9002","ts":"2026-05-31T08:19:41Z","source":"911-CAD","type":"call_surge",
   "entity":"PSAP-ZN","value":320,"unit":"%","severity":"alert","geo":[36.094,32.066]},
  {"id":"SIG-9003","ts":"2026-05-31T08:22:10Z","source":"HIS","type":"ed_load",
   "entity":"HOSP-ZN-NEW","value":138,"unit":"%cap","severity":"watch","geo":[36.101,32.061]},
  {"id":"SIG-9004","ts":"2026-05-31T08:25:55Z","source":"TRAFFIC","type":"congestion",
   "entity":"JCT-31","value":0.82,"unit":"jam","severity":"watch","geo":[36.090,32.069]}
]

// GET /api/case/zarqa-001/incident  → stitched graph (AGE / React Flow)
{
  "caseId":"zarqa-001","title":"Zarqa Trunk-Main Cascade","riskIndex":72,
  "nodes":[
    {"id":"PIPE-ZN-44","label":"Trunk Main ZN-44","kind":"infrastructure","severity":"alert","isRoot":true,"geo":[36.087,32.072]},
    {"id":"ZONE-ZN-3","label":"Supply Zone 3","kind":"zone","severity":"alert"},
    {"id":"HOSP-ZN-NEW","label":"New Zarqa Hospital","kind":"facility","severity":"watch"},
    {"id":"PSAP-ZN","label":"911 PSAP","kind":"comms","severity":"alert"},
    {"id":"JCT-31","label":"Junction 31","kind":"transport","severity":"watch"}
  ],
  "edges":[
    {"id":"e1","source":"PIPE-ZN-44","target":"ZONE-ZN-3","relation":"supplies","weight":0.9,"lag_min":4},
    {"id":"e2","source":"ZONE-ZN-3","target":"HOSP-ZN-NEW","relation":"water_to","weight":0.7,"lag_min":8},
    {"id":"e3","source":"HOSP-ZN-NEW","target":"PSAP-ZN","relation":"drives_calls","weight":0.6,"lag_min":5},
    {"id":"e4","source":"ZONE-ZN-3","target":"JCT-31","relation":"crew_dispatch","weight":0.4,"lag_min":11}
  ]
}

// GET /api/case/zarqa-001/root-cause  → causal apex + evidence (PyRCA/DoWhy)
{
  "rootCause":"PIPE-ZN-44","confidence":0.91,"method":"PyRCA + Granger",
  "apexLabel":"Trunk-main rupture, Zone 3","leadTimeMin":5,
  "rejected":[{"id":"PSAP-ZN","why":"downstream symptom, +15min lag"},
              {"id":"HOSP-ZN-NEW","why":"effect of supply loss"}],
  "evidence":[{"k":"pressure -62% at 08:14","w":0.42},
              {"k":"first in time, upstream in graph","w":0.31},
              {"k":"all downstream paths trace here","w":0.18}]
}

// GET /api/case/zarqa-001/solutions  → candidate interventions (OR-Tools)
[
  {"id":"SOL-A","title":"Isolate ZN-44 + bypass via ZN-12 + 6 tankers to hospital",
   "actions":["close valve V-441","open bypass V-128","dispatch 6 tankers HOSP-ZN-NEW"],
   "projectedRisk":24,"etaMin":35,"cost":"$18k","feasible":true,"recommended":true},
  {"id":"SOL-B","title":"Full Zone-3 shutdown + citywide tanker relief",
   "actions":["shut Zone 3"],"projectedRisk":41,"etaMin":70,"cost":"$60k","feasible":true,"recommended":false}
]

// GET /api/case/zarqa-001/sim/SOL-A  → before/after re-simulation (WNTR/EPANET)
{
  "solutionId":"SOL-A","riskBefore":72,"riskAfter":24,
  "series":[
    {"t":0,"before":72,"after":72},{"t":15,"before":78,"after":51},
    {"t":30,"before":83,"after":33},{"t":45,"before":81,"after":24}
  ],
  "metrics":[{"k":"hospital water restored","v":"31 min"},
             {"k":"911 surge","before":"+320%","after":"+40%"},
             {"k":"pressure recovered","v":"Zone 3 nominal @ 38 min"}],
  "validated":true
}

// WS /ws/case/{id} frames (drive live motion)
{"kind":"signal","payload":{...}}        // append + pulse left rail
{"kind":"node_activate","id":"ZONE-ZN-3"} // light node, animate inbound edge
{"kind":"step","step":3,"status":"done"}  // advance wizard

## COMPONENTS
- TopBar: title, National Risk Index gauge (animated number + sev color), UTC mono clock, RBAC user.
- SignalFeed (left): virtualized list, newest on top, severity dot, mono ID/ts; each new item
  slides in + emits an accent.signal "pulse" ring that fades over 600ms.
- IncidentGraphCanvas (hero): React Flow. Custom node = rounded-rect, severity-tinted left bar,
  label (UI font) + id (mono), kind glyph; root node gets a pulsing alert ring + "ROOT" tag.
  Custom animated edges (SVG dash flow in cascade direction, glow = max(src,tgt) severity).
  On "node_activate" stagger-light the path. Minimap + zoom controls. Click node → opens panel.
- RootCausePanel: big apex card (label, confidence ring), evidence list with weight bars,
  a "REJECTED SYMPTOMS" group showing why 911/hospital are NOT the cause (this is the key insight).
- SolutionReview: stacked candidate cards; recommended card has accent border + projected-risk
  delta (72→24) as a teal down-arrow; actions checklist; non-recommended dimmed.
- SimulationConsole: visx/Recharts dual-line before(red)/after(teal) over t; metrics grid;
  big VALIDATED stamp when validated. Animate after-line drawing left→right on run.
- DecisionHub (right rail): authorize gate — solution summary, risk delta, required RBAC role,
  two-step "Authorize Intervention" confirm (typed initials), audit note field.
- RiskGauge: radial 0–100, needle eases to value, arc colored along the severity ramp.
- MiniMap (MapLibre, OSM dark): plot signals/entities by geo, severity-colored markers.

## WIZARD (overlay, primary case flow + onboarding) — 7 steps
1 Signals (live feed) → 2 Stitched Incident (graph) → 3 Root Cause (apex + evidence) →
4 Candidate Solutions → 5 Validation/Simulation (before/after) → 6 Decide & Authorize (human gate)
→ 7 Outcome/Learn. Persistent left step-rail with done/active/pending states. Each step pulls the
matching component into the focus area. Step transitions: outgoing slides/fades left, incoming
slides from right (Motion, ~280ms, ease [0.16,1,0.3,1]). Step 6 is a hard human gate — no
auto-advance; requires explicit authorize. Wizard doubles as onboarding for first-time users.

## MOTION (Motion / Framer Motion, purposeful only)
- Panel reveal on load: staggered (60ms) fade+rise, hero graph last.
- Graph: edges animate dash-flow continuously; on cascade, downstream nodes light in time order.
- Signals: pulse ring on arrival; risk index ticks up with the digits rolling.
- Wizard: smooth step slide. Respect prefers-reduced-motion (disable loops, keep fades).
Keep 60fps; no gratuitous parallax or bouncy springs.

## QUALITY BAR
TypeScript strict, typed API/WS payloads, loading skeletons (shimmer in panel tone, not white),
empty + error states, keyboard nav + focus rings (accent.signal), WCAG-AA contrast, responsive
down to 1024px (rails collapse to drawers). Seed with the Zarqa fixtures above so it runs with no
backend. Deliver real, composable components — no lorem, no placeholder boxes, no generic dashboard
template. Make it feel like a room people make life-and-death decisions in.
```

---
