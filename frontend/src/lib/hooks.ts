/**
 * React hooks that fetch live data from the AEGIS backend.
 * Each hook falls back gracefully when the backend is unreachable
 * (no DB configured, network error, etc.).
 */
import { useEffect, useState } from 'react'
import { getHealth, getGraph, getRootCause, getStats, getSimulate } from './voc'
import type { Graph as ApiGraph, RootCause as ApiRootCause } from './voc'
import type { GraphNode, GraphEdge, RootCauseResult, SimulationResult, Severity, Tone } from './data'

// ── shape adapters ──────────────────────────────────────────────────────────

function mapSeverity(s: string): Severity {
  if (s === 'alert') return 'Critical'
  if (s === 'warn') return 'Elevated'
  return 'Nominal'
}

function mapTone(s: string): Tone {
  if (s === 'alert') return 'danger'
  if (s === 'warn') return 'warn'
  if (s === 'calm') return 'good'
  return 'neutral'
}

function adaptGraph(g: ApiGraph): {
  nodes: GraphNode[]
  edges: GraphEdge[]
  positions: Record<string, { x: number; y: number }>
} {
  const maxVal = Math.max(...g.nodes.map((n) => n.value), 1)
  const apexId = g.nodes.reduce(
    (best, n) => (n.value > best.value ? n : best),
    g.nodes[0] ?? { id: '', value: 0 },
  )?.id ?? ''

  const nodeTypeMap: Record<string, GraphNode['type']> = {
    cluster: 'infrastructure',
    rchub: 'infrastructure',
    service: 'service',
    case: 'demand',
    source: 'social',
    governorate: 'infrastructure',
  }

  const nodes: GraphNode[] = g.nodes.map((n) => ({
    id: n.id,
    label: n.label,
    type: nodeTypeMap[n.type] ?? 'infrastructure',
    entityId: n.id,
    severity: mapSeverity(n.severity),
    tone: mapTone(n.severity),
    zScore: Number(((n.value / maxVal) * 5).toFixed(1)),
    isApex: n.id === apexId,
    metrics: {
      value: String(n.value),
      severity: n.severity,
      ...(n.members !== undefined ? { members: String(n.members) } : {}),
    },
    signalIds: [],
  }))

  const positions: Record<string, { x: number; y: number }> = {}
  g.nodes.forEach((n) => {
    positions[n.id] = { x: n.x, y: n.y }
  })

  const edges: GraphEdge[] = g.edges.map((e, i) => ({
    id: `e${i + 1}`,
    source: e.source,
    target: e.target,
    weight: e.weight,
    propagationOrder: i + 1,
    label: e.kind,
  }))

  return { nodes, edges, positions }
}

function adaptRootCause(data: {
  root_causes: ApiRootCause[]
  recommendation: string
}): RootCauseResult {
  const top = data.root_causes[0]
  if (!top) {
    return {
      apexNodeId: 'unknown',
      confidence: 0,
      method: 'PyRCA (live)',
      leadTimeMinutes: 0,
      evidence: [],
      candidates: [],
      threshold: 0.7,
    }
  }

  return {
    apexNodeId: top.cluster_id,
    confidence: Math.min(top.score, 1),
    method: 'PyRCA (live)',
    leadTimeMinutes: 0,
    evidence: (top.evidence ?? []).map((desc, i) => ({
      rank: i + 1,
      description: desc,
      weight: Number((1 / (i + 1)).toFixed(2)),
    })),
    candidates: data.root_causes.map((rc) => ({
      rank: rc.rank,
      nodeId: rc.cluster_id,
      label: rc.label_en ?? rc.label_ar,
      causalScore: Math.min(rc.score, 1),
      reason: `${rc.members} member reports · severity avg ${rc.severity_avg != null ? rc.severity_avg.toFixed(2) : 'n/a'}`,
    })),
    threshold: 0.7,
  }
}

function adaptSim(s: {
  before: { series: { step: number; mean_negativity: number; complaint_volume: number; n_critical: number }[] }
  after: { series: { step: number; mean_negativity: number; complaint_volume: number; n_critical: number }[] }
  delta: Record<string, number>
}): Partial<SimulationResult> {
  const bl = s.before.series[s.before.series.length - 1]
  const al = s.after.series[s.after.series.length - 1]
  return {
    status: 'succeeded',
    elapsedSeconds: 4,
    estimatedSeconds: 4,
    before: {
      nationalRisk: Math.round((bl?.mean_negativity ?? 0.84) * 100),
      callSurge: `+${Math.round((bl?.complaint_volume ?? 320))}%`,
      hospitalLoad: '+138%',
      pipelinePressure: '−62%',
    },
    after: {
      nationalRisk: Math.round((al?.mean_negativity ?? 0.22) * 100),
      callSurge: `+${Math.round((al?.complaint_volume ?? 80))}%`,
      hospitalLoad: '+45%',
      pipelinePressure: '−12%',
    },
  }
}

// ── public hooks ────────────────────────────────────────────────────────────

export function useHealth() {
  const [online, setOnline] = useState<boolean | null>(null)
  const [db, setDb] = useState<string | null>(null)
  useEffect(() => {
    getHealth()
      .then((h) => {
        setOnline(h.ok)
        setDb(h.database ?? null)
      })
      .catch(() => setOnline(false))
  }, [])
  return { online, db }
}

export function useStatsLive() {
  const [stats, setStats] = useState<Record<string, number> | null>(null)
  useEffect(() => {
    getStats().then(setStats).catch(() => {})
  }, [])
  return stats
}

export function useGraphLive(caseId?: string) {
  const [nodes, setNodes] = useState<GraphNode[] | null>(null)
  const [edges, setEdges] = useState<GraphEdge[] | null>(null)
  const [positions, setPositions] = useState<Record<string, { x: number; y: number }>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  useEffect(() => {
    setLoading(true)
    setError(false)
    getGraph(caseId)
      .then((g) => {
        const adapted = adaptGraph(g)
        setNodes(adapted.nodes)
        setEdges(adapted.edges)
        setPositions(adapted.positions)
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }, [caseId])
  return { nodes, edges, positions, loading, error }
}

export function useRootCauseLive() {
  const [rca, setRca] = useState<RootCauseResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  useEffect(() => {
    setLoading(true)
    getRootCause()
      .then((d) => setRca(adaptRootCause(d)))
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }, [])
  return { rca, loading, error }
}

export function useSimLive(caseId?: string) {
  const [simData, setSimData] = useState<Partial<SimulationResult> | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  useEffect(() => {
    setLoading(true)
    getSimulate(caseId)
      .then((s) => setSimData(adaptSim(s)))
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }, [caseId])
  return { simData, loading, error }
}
