export type Severity = 'calm' | 'watch' | 'alert'

export interface Signal {
  id: string
  ts: string
  source: string
  type: string
  entity: string
  value: number
  unit: string
  severity: Severity
  geo: [number, number]
}

export interface GNode {
  id: string
  label: string
  kind: string
  severity: Severity
  isRoot?: boolean
  geo?: [number, number]
}

export interface GEdge {
  id: string
  source: string
  target: string
  relation: string
  weight: number
  lag_min: number
}

export interface Incident {
  caseId: string
  title: string
  riskIndex: number
  nodes: GNode[]
  edges: GEdge[]
}

export interface RootCause {
  rootCause: string
  confidence: number
  method: string
  apexLabel: string
  leadTimeMin: number
  rejected: { id: string; why: string }[]
  evidence: { k: string; w: number }[]
}

export interface Solution {
  id: string
  title: string
  actions: string[]
  projectedRisk: number
  etaMin: number
  cost: string
  feasible: boolean
  recommended: boolean
}

export interface Sim {
  solutionId: string
  riskBefore: number
  riskAfter: number
  series: { t: number; before: number; after: number }[]
  metrics: { k: string; v?: string; before?: string; after?: string }[]
  validated: boolean
}

export const SEV_HEX: Record<Severity, string> = {
  calm: '#2DD4BF',
  watch: '#FBBF24',
  alert: '#F43F5E',
}
export const SEV_LABEL: Record<Severity, string> = {
  calm: 'NOMINAL',
  watch: 'ELEVATED',
  alert: 'CRITICAL',
}
