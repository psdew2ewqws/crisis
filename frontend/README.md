# AEGIS Crisis Console — Frontend

The **AEGIS Crisis Console**: the operator dashboard for the General Crisis-Solving Brain. A clean, dark command console — left command rail, KPI cards, a live signal-volume chart, and a tabbed signals/incidents/solutions table — driven by the **Zarqa** demo case. No backend required.

## Stack

React 18 · TypeScript · Vite · Tailwind CSS · Recharts (signal-volume chart) · lucide-react · Geist font.

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
├── App.tsx                    # console shell (sidebar + topbar + dashboard)
├── lib/data.ts                # demo fixtures (KPIs, signal volume, signals, cases)
└── components/
    ├── Sidebar.tsx            # brand, Run Analysis, operations nav, active cases, user
    ├── Topbar.tsx             # breadcrumb, search, notifications, UTC clock
    ├── KpiCard.tsx            # KPI metric card (value, badge, trend, sub)
    ├── SignalVolume.tsx       # area chart with time-range toggle (Recharts)
    └── DataTable.tsx          # tabbed signals / incidents / solutions table
```

Theme tokens (dark palette, blue accent, severity colors, typography) live in `tailwind.config.js`.
