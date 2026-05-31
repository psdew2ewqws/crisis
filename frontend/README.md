# AEGIS Dashboard — Frontend

The **AEGIS National Crisis Command** dashboard: the MVP UI for the General Crisis-Solving Brain. A dark, mission-control command center that walks a duty officer through a crisis case via a 7-step wizard (signals → incident graph → root cause → solutions → simulation → authorize → outcome).

Runs entirely on the embedded **Zarqa** demo fixtures — no backend required.

## Stack

React 18 · TypeScript · Vite · Tailwind CSS · React Flow (dependency graph) · Framer Motion · Recharts · lucide-react.

## Develop

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # type-check + production build
npm run preview  # preview the production build
```

## Structure

```
src/
├── App.tsx                 # layout + wizard state machine
├── data/zarqa.ts           # the Zarqa demo fixtures (signals, incident, root cause, solutions, sim)
├── types.ts                # shared domain types + severity tokens
└── components/
    ├── TopBar.tsx          # title, National Risk Index, UTC clock
    ├── SignalFeed.tsx      # live signal stream (left rail)
    ├── IncidentGraph.tsx   # React Flow dependency-graph canvas (hero)
    ├── RiskGauge.tsx       # animated radial risk index
    ├── WizardRail.tsx      # 7-step case wizard (right rail)
    ├── RootCausePanel.tsx  # causal apex + evidence + rejected symptoms
    ├── SolutionReview.tsx  # candidate interventions
    ├── SimulationConsole.tsx # before/after counterfactual (Recharts)
    ├── DecisionHub.tsx     # human authorization gate
    └── SeverityBadge.tsx
```

Theme tokens (severity ramp, command-center palette, typography) live in `tailwind.config.js`.
