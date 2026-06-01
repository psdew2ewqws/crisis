// Demo fixtures for the AEGIS Crisis Console — Zarqa Trunk-Main Cascade.

export type Tone = 'danger' | 'good' | 'warn' | 'neutral'

export interface Kpi {
  title: string
  value: string
  unit?: string
  badge: { text: string; tone: Tone }
  trend: { text: string; dir: 'up' | 'down'; tone: Tone }
  sub: string
}

export const kpis: Kpi[] = [
  {
    title: 'National Risk',
    value: '84',
    badge: { text: '▲ +12', tone: 'danger' },
    trend: { text: 'Spiking in Zarqa North', dir: 'up', tone: 'danger' },
    sub: 'Critical threshold exceeded',
  },
  {
    title: 'Apex Confidence',
    value: '0.91',
    badge: { text: 'PyRCA', tone: 'neutral' },
    trend: { text: 'PIPE-ZN-44 isolated', dir: 'up', tone: 'good' },
    sub: 'Loud symptoms demoted',
  },
  {
    title: 'Projected Risk',
    value: '22',
    badge: { text: '▼ −62', tone: 'good' },
    trend: { text: 'Validated fix holds', dir: 'down', tone: 'good' },
    sub: '74% reduction post-sim',
  },
  {
    title: 'Time to Mitigate',
    value: '35',
    unit: 'min',
    badge: { text: 'ETA', tone: 'neutral' },
    trend: { text: 'Isolate + bypass + tanker', dir: 'down', tone: 'good' },
    sub: '6 tankers to hospital',
  },
]

export interface Point {
  t: string
  v: number
}

// Flat/noisy baseline that ramps sharply on the right (the cascade onset).
export const signalVolume: Point[] = [
  { t: '08:00', v: 12 },
  { t: '08:15', v: 13 },
  { t: '08:30', v: 11 },
  { t: '08:45', v: 16 },
  { t: '09:00', v: 14 },
  { t: '09:15', v: 12 },
  { t: '09:30', v: 13 },
  { t: '09:45', v: 15 },
  { t: '10:00', v: 18 },
  { t: '10:15', v: 16 },
  { t: '10:30', v: 14 },
  { t: '10:45', v: 13 },
  { t: '11:00', v: 12 },
  { t: '11:15', v: 14 },
  { t: '11:30', v: 17 },
  { t: '11:45', v: 22 },
  { t: '12:00', v: 28 },
  { t: '12:15', v: 33 },
  { t: '12:30', v: 41 },
  { t: '12:45', v: 52 },
  { t: '13:00', v: 64 },
  { t: '13:15', v: 78 },
  { t: '13:30', v: 88 },
]

export type Severity = 'Critical' | 'Elevated' | 'Nominal'

export interface SignalRow {
  entity: string
  observation: string
  source: string
  severity: Severity
  delta: string
  z: string
  time: string
}

export const signals: SignalRow[] = [
  { entity: 'PIPE-ZN-44', observation: 'Pressure drop', source: 'SCADA', severity: 'Critical', delta: '−62%', z: '4.8', time: '08:14' },
  { entity: 'PSAP-ZN', observation: '911 call surge', source: '911-CAD', severity: 'Critical', delta: '+320%', z: '5.1', time: '08:19' },
  { entity: 'ZONE-ZN-3', observation: 'Reservoir level', source: 'SCADA', severity: 'Critical', delta: '−28%', z: '3.9', time: '08:27' },
  { entity: 'HOSP-ZN-NEW', observation: 'ED load', source: 'HIS', severity: 'Elevated', delta: '+138%', z: '2.7', time: '08:22' },
  { entity: 'JCT-31', observation: 'Congestion', source: 'TRAFFIC', severity: 'Elevated', delta: '+0.82', z: '2.1', time: '08:25' },
  { entity: 'CITY', observation: 'Public sentiment', source: 'SOCIAL', severity: 'Nominal', delta: '+12%', z: '0.9', time: '08:29' },
]

export interface CaseItem {
  name: string
  score: number
  tone: Tone
}
export const cases: CaseItem[] = [
  { name: 'Zarqa Cascade', score: 84, tone: 'danger' },
  { name: 'Amman Grid Dip', score: 38, tone: 'warn' },
  { name: 'Irbid Watch', score: 16, tone: 'good' },
]
