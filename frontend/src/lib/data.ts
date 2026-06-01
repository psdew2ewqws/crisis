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

// ---------------------------------------------------------------------------
// Extended signal feed (Phase 2)
// ---------------------------------------------------------------------------

export type SignalSource = 'SCADA' | '911-CAD' | 'HIS' | 'TRAFFIC' | 'SOCIAL'

export interface Signal {
  id: string
  source: SignalSource
  entity: string
  entityId: string
  observation: string
  severity: Severity
  tone: Tone
  delta: string
  zScore: number
  timestamp: string
  lat: number
  lng: number
  rawPayload: Record<string, unknown>
}

export const signalFeed: Signal[] = [
  { id: 'SIG-9001', source: 'SCADA', entity: 'Trunk-Main ZN-44', entityId: 'PIPE-ZN-44', observation: 'pressure_drop', severity: 'Critical', tone: 'danger', delta: '−62%', zScore: 4.8, timestamp: '2026-05-31T08:14:03Z', lat: 32.072, lng: 36.087, rawPayload: { sensor_id: 'PS-ZN44-01', reading_bar: 0.4, baseline_bar: 1.05, unit: 'bar', alarm_code: 'LO-PRESS-CRIT' } },
  { id: 'SIG-9009', source: 'SCADA', entity: 'Valve 441', entityId: 'VALVE-441', observation: 'flow_rate_zero', severity: 'Critical', tone: 'danger', delta: '−100%', zScore: 5.0, timestamp: '2026-05-31T08:15:00Z', lat: 32.073, lng: 36.088, rawPayload: { valve_id: 'V-441', flow_lps: 0, baseline_lps: 48.2, status: 'closed', trigger: 'auto_shutoff' } },
  { id: 'SIG-9006', source: 'SCADA', entity: 'Zone North', entityId: 'ZONE-NORTH', observation: 'low_pressure_alarm', severity: 'Critical', tone: 'danger', delta: '−45%', zScore: 4.2, timestamp: '2026-05-31T08:16:30Z', lat: 32.075, lng: 36.090, rawPayload: { zone_id: 'ZN-3', avg_pressure_bar: 0.58, threshold_bar: 0.80, affected_connections: 12400 } },
  { id: 'SIG-9002', source: '911-CAD', entity: '911 PSAP Zarqa', entityId: 'PSAP-ZN', observation: 'call_surge', severity: 'Critical', tone: 'danger', delta: '+320%', zScore: 5.1, timestamp: '2026-05-31T08:22:17Z', lat: 32.066, lng: 36.094, rawPayload: { psap_id: 'PSAP-ZN-MAIN', calls_15min: 84, baseline_15min: 20, queue_depth: 31, avg_wait_sec: 142 } },
  { id: 'SIG-9004', source: 'TRAFFIC', entity: 'Junction HW35-31', entityId: 'JCT-HW35', observation: 'congestion_index', severity: 'Elevated', tone: 'warn', delta: '+89%', zScore: 2.7, timestamp: '2026-05-31T08:28:10Z', lat: 32.069, lng: 36.090, rawPayload: { junction_id: 'JCT-31', congestion_idx: 0.82, baseline_idx: 0.43, avg_speed_kmh: 12, lanes_blocked: 1 } },
  { id: 'SIG-9003', source: 'HIS', entity: 'New Zarqa Hospital', entityId: 'HOSP-ZN-NEW', observation: 'ed_load', severity: 'Elevated', tone: 'warn', delta: '+138%', zScore: 3.9, timestamp: '2026-05-31T08:31:45Z', lat: 32.061, lng: 36.101, rawPayload: { facility_id: 'HOSP-ZN-NEW', ed_occupancy_pct: 94, baseline_pct: 62, beds_available: 3, diversion_status: false } },
  { id: 'SIG-9010', source: 'TRAFFIC', entity: 'HW35 North', entityId: 'HW35-NORTH', observation: 'avg_speed_drop', severity: 'Nominal', tone: 'good', delta: '−35%', zScore: 1.9, timestamp: '2026-05-31T08:33:18Z', lat: 32.078, lng: 36.085, rawPayload: { segment_id: 'HW35-N-KM12', avg_speed_kmh: 38, baseline_kmh: 58, incident_flag: false } },
  { id: 'SIG-9005', source: 'SOCIAL', entity: 'Twitter Zarqa', entityId: 'TWITTER-ZN', observation: 'sentiment_shift', severity: 'Nominal', tone: 'good', delta: '+210%', zScore: 1.8, timestamp: '2026-05-31T08:35:22Z', lat: 32.063, lng: 36.092, rawPayload: { platform: 'twitter', keyword_hits: 847, baseline_hits: 273, top_hashtag: '#ZarqaWater', sentiment_score: -0.42 } },
  { id: 'SIG-9007', source: '911-CAD', entity: '911 PSAP Zarqa', entityId: 'PSAP-ZN', observation: 'avg_wait_time', severity: 'Elevated', tone: 'warn', delta: '+180%', zScore: 3.1, timestamp: '2026-05-31T08:40:05Z', lat: 32.066, lng: 36.094, rawPayload: { psap_id: 'PSAP-ZN-MAIN', avg_wait_sec: 196, baseline_wait_sec: 70, abandoned_calls: 12 } },
  { id: 'SIG-9008', source: 'HIS', entity: 'New Zarqa Hospital', entityId: 'HOSP-ZN-NEW', observation: 'ambulance_diversion', severity: 'Critical', tone: 'danger', delta: 'active', zScore: 4.5, timestamp: '2026-05-31T08:45:12Z', lat: 32.061, lng: 36.101, rawPayload: { facility_id: 'HOSP-ZN-NEW', diversion_active: true, reason: 'capacity_exceeded', redirect_to: 'HOSP-AMMAN-CENTRAL', ambulances_redirected: 4 } },
  { id: 'SIG-9011', source: 'SCADA', entity: 'Bypass Pipe ZN-12', entityId: 'PIPE-ZN-12', observation: 'bypass_capacity', severity: 'Nominal', tone: 'good', delta: '70%', zScore: 0.8, timestamp: '2026-05-31T08:50:00Z', lat: 32.074, lng: 36.089, rawPayload: { pipe_id: 'PIPE-ZN-12', capacity_pct: 70, flow_lps: 33.7, max_lps: 48.2, status: 'standby' } },
  { id: 'SIG-9012', source: 'HIS', entity: 'Blood Bank Zarqa', entityId: 'BLOOD-BANK-ZN', observation: 'supply_draw', severity: 'Elevated', tone: 'warn', delta: '+45%', zScore: 2.3, timestamp: '2026-05-31T09:01:30Z', lat: 32.064, lng: 36.098, rawPayload: { facility_id: 'BB-ZN-01', units_drawn_24h: 58, baseline_24h: 40, o_neg_remaining: 12, alert_threshold: 10 } },
]

// ---------------------------------------------------------------------------
// Incident graph data (Phase 2)
// ---------------------------------------------------------------------------

export interface GraphNode {
  id: string
  label: string
  type: 'infrastructure' | 'service' | 'demand' | 'social'
  entityId: string
  severity: Severity
  tone: Tone
  zScore: number
  isApex: boolean
  metrics: Record<string, string>
  signalIds: string[]
}

export interface GraphEdge {
  id: string
  source: string
  target: string
  weight: number
  propagationOrder: number
  label: string
}

export const graphNodes: GraphNode[] = [
  { id: 'PIPE-ZN-44', label: 'Trunk-Main Rupture', type: 'infrastructure', entityId: 'PIPE-ZN-44', severity: 'Critical', tone: 'danger', zScore: 4.8, isApex: true, metrics: { flow: '0 L/s', pressure: '0.4 bar', status: 'ruptured' }, signalIds: ['SIG-9001', 'SIG-9009'] },
  { id: 'ZONE-NORTH', label: 'Zone 3 Low Pressure', type: 'infrastructure', entityId: 'ZONE-NORTH', severity: 'Critical', tone: 'danger', zScore: 4.2, isApex: false, metrics: { pressure: '−45%', connections: '12,400' }, signalIds: ['SIG-9006'] },
  { id: 'VALVE-441', label: 'Valve 441 Closed', type: 'infrastructure', entityId: 'VALVE-441', severity: 'Critical', tone: 'danger', zScore: 5.0, isApex: false, metrics: { status: 'closed', flow: '0 L/s' }, signalIds: ['SIG-9009'] },
  { id: 'HOSP-ZN-NEW', label: 'New Zarqa Hospital', type: 'service', entityId: 'HOSP-ZN-NEW', severity: 'Elevated', tone: 'warn', zScore: 3.9, isApex: false, metrics: { 'ED load': '+138%', occupancy: '94%' }, signalIds: ['SIG-9003', 'SIG-9008'] },
  { id: 'JCT-HW35', label: 'Junction 31 Gridlock', type: 'service', entityId: 'JCT-HW35', severity: 'Elevated', tone: 'warn', zScore: 2.7, isApex: false, metrics: { congestion: '+89%', 'avg speed': '12 km/h' }, signalIds: ['SIG-9004'] },
  { id: 'PSAP-ZN', label: '911 Call Surge', type: 'demand', entityId: 'PSAP-ZN', severity: 'Critical', tone: 'danger', zScore: 5.1, isApex: false, metrics: { calls: '+320%', 'queue depth': '31' }, signalIds: ['SIG-9002', 'SIG-9007'] },
  { id: 'SOCIAL-ZN', label: 'Public Sentiment', type: 'social', entityId: 'TWITTER-ZN', severity: 'Nominal', tone: 'good', zScore: 1.8, isApex: false, metrics: { sentiment: '−40%', tweets: '847' }, signalIds: ['SIG-9005'] },
]

export const graphEdges: GraphEdge[] = [
  { id: 'e1', source: 'PIPE-ZN-44', target: 'ZONE-NORTH', weight: 0.95, propagationOrder: 1, label: 'pressure_cascade' },
  { id: 'e2', source: 'PIPE-ZN-44', target: 'VALVE-441', weight: 0.90, propagationOrder: 1, label: 'flow_disruption' },
  { id: 'e3', source: 'ZONE-NORTH', target: 'HOSP-ZN-NEW', weight: 0.78, propagationOrder: 2, label: 'supply_loss' },
  { id: 'e4', source: 'ZONE-NORTH', target: 'JCT-HW35', weight: 0.45, propagationOrder: 2, label: 'emergency_routing' },
  { id: 'e5', source: 'HOSP-ZN-NEW', target: 'PSAP-ZN', weight: 0.82, propagationOrder: 3, label: 'medical_calls' },
  { id: 'e6', source: 'JCT-HW35', target: 'PSAP-ZN', weight: 0.38, propagationOrder: 3, label: 'traffic_reports' },
  { id: 'e7', source: 'PSAP-ZN', target: 'SOCIAL-ZN', weight: 0.55, propagationOrder: 4, label: 'public_awareness' },
  { id: 'e8', source: 'HOSP-ZN-NEW', target: 'SOCIAL-ZN', weight: 0.42, propagationOrder: 4, label: 'health_concern' },
]

// ---------------------------------------------------------------------------
// Root-cause analysis data (Phase 2)
// ---------------------------------------------------------------------------

export interface RootCauseResult {
  apexNodeId: string
  confidence: number
  method: string
  leadTimeMinutes: number
  evidence: { rank: number; description: string; weight: number }[]
  candidates: { rank: number; nodeId: string; label: string; causalScore: number; reason: string }[]
  threshold: number
}

export const rootCauseResult: RootCauseResult = {
  apexNodeId: 'PIPE-ZN-44',
  confidence: 0.91,
  method: 'PyRCA + Granger',
  leadTimeMinutes: 5,
  evidence: [
    { rank: 1, description: 'Pressure −62% at 08:14', weight: 0.42 },
    { rank: 2, description: 'First in time, upstream in graph', weight: 0.31 },
    { rank: 3, description: 'All downstream paths trace here', weight: 0.18 },
    { rank: 4, description: 'Granger p-value < 0.001', weight: 0.09 },
  ],
  candidates: [
    { rank: 1, nodeId: 'PIPE-ZN-44', label: 'Trunk-Main Rupture', causalScore: 0.91, reason: 'Upstream apex; pressure drop precedes all downstream spikes' },
    { rank: 2, nodeId: 'HOSP-ZN-NEW', label: 'New Zarqa Hospital', causalScore: 0.22, reason: 'Symptom — strain follows supply loss' },
    { rank: 3, nodeId: 'PSAP-ZN', label: '911 Call Surge', causalScore: 0.08, reason: 'Loudest signal, lowest causal score' },
  ],
  threshold: 0.70,
}

// ---------------------------------------------------------------------------
// Phase 3 — Solutions, Simulation, Decision, Outcome
// ---------------------------------------------------------------------------

export interface Intervention {
  id: string
  title: string
  description: string
  actions: string[]
  projectedRisk: number
  etaMinutes: number
  costUsd: number
  feasible: boolean
  recommended: boolean
  severityBand: Tone
}

export interface ConstraintSummary {
  availableTankers: { used: number; total: number }
  bypassCapacity: string
  authRequired: boolean
}

export const interventions: Intervention[] = [
  {
    id: 'SOL-A',
    title: 'Isolate ZN-44 + bypass via ZN-12 + 6 tankers',
    description: 'Primary recommended intervention — isolate the ruptured trunk main, reroute supply through ZN-12 bypass, and deploy tankers to critical facilities.',
    actions: ['Close valve V-441', 'Open bypass valve V-128 (ZN-12 line)', 'Dispatch 6 water tankers to New Zarqa Hospital', 'Notify Zone 3 residents via SMS alert'],
    projectedRisk: 22,
    etaMinutes: 35,
    costUsd: 18000,
    feasible: true,
    recommended: true,
    severityBand: 'good',
  },
  {
    id: 'SOL-B',
    title: 'Full Zone-3 shutdown + citywide tanker relief',
    description: 'Maximum containment — shut down all Zone 3 distribution and activate citywide emergency tanker fleet.',
    actions: ['Emergency shutdown of Zone 3 main distribution', 'Activate citywide tanker fleet (12 units)', 'Open emergency supply from Zone 2 reservoir', 'Establish 3 public water distribution points'],
    projectedRisk: 41,
    etaMinutes: 70,
    costUsd: 60000,
    feasible: true,
    recommended: false,
    severityBand: 'warn',
  },
  {
    id: 'SOL-C',
    title: 'Temporary pressure redistribution (no isolate)',
    description: 'Minimal intervention — redistribute pressure across adjacent zones without isolating the rupture.',
    actions: ['Reduce pressure in adjacent Zone 2 by 15%', 'Increase Zone 4 output to compensate', 'Monitor PIPE-ZN-44 leak rate', 'Prepare isolation as fallback'],
    projectedRisk: 58,
    etaMinutes: 20,
    costUsd: 5000,
    feasible: true,
    recommended: false,
    severityBand: 'neutral',
  },
]

export const constraintSummary: ConstraintSummary = {
  availableTankers: { used: 6, total: 12 },
  bypassCapacity: '70%',
  authRequired: true,
}

export interface RiskSnapshot {
  nationalRisk: number
  callSurge: string
  hospitalLoad: string
  pipelinePressure: string
}

export interface SimulationResult {
  runId: string
  interventionId: string
  status: 'queued' | 'running' | 'succeeded' | 'failed'
  elapsedSeconds: number
  estimatedSeconds: number
  before: RiskSnapshot
  after: RiskSnapshot
  artifactUrl: string
}

export const simulationResult: SimulationResult = {
  runId: 'sim_run_2026-05-31_zarqa',
  interventionId: 'SOL-A',
  status: 'succeeded',
  elapsedSeconds: 38,
  estimatedSeconds: 45,
  before: { nationalRisk: 84, callSurge: '+320%', hospitalLoad: '94% capacity', pipelinePressure: '0.12 bar (critical)' },
  after: { nationalRisk: 22, callSurge: '+41%', hospitalLoad: '62% capacity', pipelinePressure: '2.1 bar (nominal)' },
  artifactUrl: 'sim_run_2026-05-31_zarqa.json',
}

export interface DecisionRecord {
  caseId: string
  rootCause: string
  intervention: string
  confidence: number
  simValidated: boolean
  riskBefore: number
  riskAfter: number
  riskReduction: string
  actor: { name: string; role: string; authLevel: string }
  auditId: string
  auditActions: string[]
}

export const decisionRecord: DecisionRecord = {
  caseId: 'zarqa-2025-08',
  rootCause: 'PIPE-ZN-44 (trunk-main rupture)',
  intervention: 'Isolate ZN-44 + bypass via ZN-12 + 6 tankers',
  confidence: 0.91,
  simValidated: true,
  riskBefore: 84,
  riskAfter: 22,
  riskReduction: '−62 (−74%)',
  actor: { name: 'Cmdr. Haddad', role: 'commander', authLevel: 'AUTHORIZE' },
  auditId: 'AUD-2026-05-31-0042',
  auditActions: ['Dispatch intervention to field teams', 'Write immutable audit record to S3/MinIO', 'Record decision with full evidence lineage'],
}

export interface OutcomeRecord {
  caseId: string
  caseName: string
  duration: string
  status: 'RESOLVED' | 'MITIGATED' | 'ONGOING'
  rootCause: string
  fix: string
  riskBefore: number
  riskActual: number
  auditId: string
  telemetry: { metric: string; values: { time: string; value: number }[]; trend: 'down' | 'stable' | 'up' }[]
  learned: string[]
}

export const outcomeRecord: OutcomeRecord = {
  caseId: 'ZARQA-2025-08',
  caseName: 'Zarqa Trunk-Main Cascade',
  duration: '47 min',
  status: 'RESOLVED',
  rootCause: 'PIPE-ZN-44',
  fix: 'isolate+bypass',
  riskBefore: 84,
  riskActual: 22,
  auditId: 'AUD-2026-05-31-0042',
  telemetry: [
    {
      metric: '911 Call Volume',
      values: [
        { time: 'T+0', value: 320 },
        { time: 'T+5', value: 280 },
        { time: 'T+10', value: 190 },
        { time: 'T+15', value: 110 },
        { time: 'T+20', value: 60 },
        { time: 'T+25', value: 35 },
      ],
      trend: 'down',
    },
    {
      metric: 'Hospital ED Load (%)',
      values: [
        { time: 'T+0', value: 94 },
        { time: 'T+5', value: 82 },
        { time: 'T+10', value: 68 },
        { time: 'T+15', value: 58 },
        { time: 'T+20', value: 52 },
        { time: 'T+25', value: 48 },
      ],
      trend: 'down',
    },
    {
      metric: 'Pipeline Pressure (bar)',
      values: [
        { time: 'T+0', value: 0.12 },
        { time: 'T+5', value: 0.8 },
        { time: 'T+10', value: 1.4 },
        { time: 'T+15', value: 1.8 },
        { time: 'T+20', value: 2.0 },
        { time: 'T+25', value: 2.1 },
      ],
      trend: 'stable',
    },
  ],
  learned: [
    'Rule weight updated: pressure_drop → cascade (0.72 → 0.88)',
    'New signal pattern stored in pgvector for future recall',
    'Similar-case embedding indexed for trunk-main failures',
  ],
}
