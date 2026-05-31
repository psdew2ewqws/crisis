import type { Signal, Incident, RootCause, Solution, Sim } from '../types'

// Zarqa water-pipe cascade — the demo case the brain must solve.
// A trunk-main rupture (PIPE-ZN-44) cascades to hospital strain, traffic, and a
// 911 surge (+320%). The root cause is the RUPTURE — not the loud symptoms.

export const signals: Signal[] = [
  { id: 'SIG-9001', ts: '2026-05-31T08:14:03Z', source: 'SCADA', type: 'pressure_drop', entity: 'PIPE-ZN-44', value: -62, unit: '%', severity: 'alert', geo: [36.087, 32.072] },
  { id: 'SIG-9002', ts: '2026-05-31T08:19:41Z', source: '911-CAD', type: 'call_surge', entity: 'PSAP-ZN', value: 320, unit: '%', severity: 'alert', geo: [36.094, 32.066] },
  { id: 'SIG-9003', ts: '2026-05-31T08:22:10Z', source: 'HIS', type: 'ed_load', entity: 'HOSP-ZN-NEW', value: 138, unit: '%cap', severity: 'watch', geo: [36.101, 32.061] },
  { id: 'SIG-9004', ts: '2026-05-31T08:25:55Z', source: 'TRAFFIC', type: 'congestion', entity: 'JCT-31', value: 0.82, unit: 'jam', severity: 'watch', geo: [36.09, 32.069] },
  { id: 'SIG-9005', ts: '2026-05-31T08:27:12Z', source: 'SCADA', type: 'reservoir_level', entity: 'ZONE-ZN-3', value: -28, unit: '%', severity: 'alert', geo: [36.088, 32.07] },
  { id: 'SIG-9006', ts: '2026-05-31T08:29:48Z', source: 'SOCIAL', type: 'sentiment', entity: 'CITY', value: 12, unit: '%neg', severity: 'calm', geo: [36.1, 32.06] },
]

export const incident: Incident = {
  caseId: 'zarqa-001',
  title: 'Zarqa Trunk-Main Cascade',
  riskIndex: 72,
  nodes: [
    { id: 'PIPE-ZN-44', label: 'Trunk Main ZN-44', kind: 'infrastructure', severity: 'alert', isRoot: true, geo: [36.087, 32.072] },
    { id: 'ZONE-ZN-3', label: 'Supply Zone 3', kind: 'zone', severity: 'alert' },
    { id: 'HOSP-ZN-NEW', label: 'New Zarqa Hospital', kind: 'facility', severity: 'watch' },
    { id: 'PSAP-ZN', label: '911 PSAP', kind: 'comms', severity: 'alert' },
    { id: 'JCT-31', label: 'Junction 31', kind: 'transport', severity: 'watch' },
  ],
  edges: [
    { id: 'e1', source: 'PIPE-ZN-44', target: 'ZONE-ZN-3', relation: 'supplies', weight: 0.9, lag_min: 4 },
    { id: 'e2', source: 'ZONE-ZN-3', target: 'HOSP-ZN-NEW', relation: 'water_to', weight: 0.7, lag_min: 8 },
    { id: 'e3', source: 'HOSP-ZN-NEW', target: 'PSAP-ZN', relation: 'drives_calls', weight: 0.6, lag_min: 5 },
    { id: 'e4', source: 'ZONE-ZN-3', target: 'JCT-31', relation: 'crew_dispatch', weight: 0.4, lag_min: 11 },
  ],
}

export const rootCause: RootCause = {
  rootCause: 'PIPE-ZN-44',
  confidence: 0.91,
  method: 'PyRCA + Granger',
  apexLabel: 'Trunk-main rupture, Zone 3',
  leadTimeMin: 5,
  rejected: [
    { id: 'PSAP-ZN', why: 'downstream symptom, +15 min lag' },
    { id: 'HOSP-ZN-NEW', why: 'effect of supply loss, not a driver' },
  ],
  evidence: [
    { k: 'Pressure −62% at 08:14 (SCADA, first event)', w: 0.42 },
    { k: 'First in time, upstream in dependency graph', w: 0.31 },
    { k: 'All downstream symptom paths trace here', w: 0.18 },
  ],
}

export const solutions: Solution[] = [
  {
    id: 'SOL-A',
    title: 'Isolate ZN-44 + bypass via ZN-12 + 6 tankers to hospital',
    actions: ['Close valve V-441', 'Open bypass V-128', 'Dispatch 6 tankers → HOSP-ZN-NEW'],
    projectedRisk: 24,
    etaMin: 35,
    cost: '$18k',
    feasible: true,
    recommended: true,
  },
  {
    id: 'SOL-B',
    title: 'Full Zone-3 shutdown + citywide tanker relief',
    actions: ['Shut Zone 3', 'Citywide tanker relief'],
    projectedRisk: 41,
    etaMin: 70,
    cost: '$60k',
    feasible: true,
    recommended: false,
  },
  {
    id: 'SOL-C',
    title: 'Surge ER staff + add 911 call-takers (symptom-only)',
    actions: ['+12 ER staff', '+8 call-takers'],
    projectedRisk: 66,
    etaMin: 20,
    cost: '$9k',
    feasible: true,
    recommended: false,
  },
]

export const sim: Sim = {
  solutionId: 'SOL-A',
  riskBefore: 72,
  riskAfter: 24,
  series: [
    { t: 0, before: 72, after: 72 },
    { t: 15, before: 78, after: 51 },
    { t: 30, before: 83, after: 33 },
    { t: 45, before: 81, after: 24 },
    { t: 60, before: 80, after: 21 },
  ],
  metrics: [
    { k: 'Hospital water restored', v: '31 min' },
    { k: '911 surge', before: '+320%', after: '+40%' },
    { k: 'Zone-3 pressure', v: 'nominal @ 38 min' },
  ],
  validated: true,
}
