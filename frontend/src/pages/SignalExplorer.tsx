import { useState, useMemo, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'motion/react'
import { signalFeed, type Signal, type SignalSource, type Severity } from '../lib/data'
import FilterBar from '../components/signals/FilterBar'
import SignalCard from '../components/signals/SignalCard'
import SignalDetail from '../components/signals/SignalDetail'
import { useWizardStore } from '../stores/wizardStore'
import { useAppStore } from '../stores/appStore'

const ALL_SOURCES = new Set<SignalSource>(['SCADA', '911-CAD', 'HIS', 'TRAFFIC', 'SOCIAL'])

export default function SignalExplorer() {
  const [activeSources, setActiveSources] = useState<Set<SignalSource>>(new Set(ALL_SOURCES))
  const [severity, setSeverity] = useState<Severity | 'All'>('All')
  const [selected, setSelected] = useState<Signal | null>(null)
  const navigate = useNavigate()
  const wizardOpen = useWizardStore((s) => s.open)
  const setGuard = useWizardStore((s) => s.setGuard)
  const highlightedSignalId = useAppStore((s) => s.highlightedSignalId)
  const setHighlightedSignalId = useAppStore((s) => s.setHighlightedSignalId)

  // Wizard guard: signals always exist
  useEffect(() => {
    if (wizardOpen) setGuard(1, true)
  }, [wizardOpen])

  // Cross-page: auto-select highlighted signal
  useEffect(() => {
    if (highlightedSignalId) {
      const sig = signalFeed.find((s) => s.id === highlightedSignalId)
      if (sig) setSelected(sig)
      setHighlightedSignalId(null)
    }
  }, [highlightedSignalId])

  const toggleSource = (s: SignalSource) => {
    setActiveSources((prev) => {
      const next = new Set(prev)
      if (next.has(s)) next.delete(s)
      else next.add(s)
      return next
    })
  }

  const filtered = useMemo(() => {
    return signalFeed
      .filter((s) => activeSources.has(s.source))
      .filter((s) => severity === 'All' || s.severity === severity)
      .sort((a, b) => b.timestamp.localeCompare(a.timestamp))
  }, [activeSources, severity])

  const handleViewInGraph = (signal: Signal) => {
    // Find a graph node linked to this signal
    const nodeId = signal.entityId
    if (nodeId) {
      useAppStore.getState().setHighlightedNodeId(nodeId)
      navigate('/case/zarqa-2025-08/graph')
    }
  }

  return (
    <div className="mx-auto max-w-[1340px] px-8 py-7">
      <h1 className="text-[28px] font-semibold tracking-tight text-txt">Signal Explorer</h1>
      <p className="mt-1.5 text-[14px] text-muted mb-5">
        Raw signal feed · {filtered.length} signals shown · Zarqa Trunk-Main Cascade
      </p>

      <FilterBar
        activeSources={activeSources}
        toggleSource={toggleSource}
        severity={severity}
        setSeverity={setSeverity}
      />

      <div className="mt-5 flex gap-5" style={{ height: 'calc(100vh - 280px)' }}>
        {/* signal list */}
        <div className="w-[55%] shrink-0 space-y-2 overflow-y-auto pr-2">
          {filtered.map((s, i) => (
            <motion.div
              key={s.id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i < 6 ? i * 0.05 : 0, duration: 0.3 }}
            >
              <SignalCard
                signal={s}
                selected={selected?.id === s.id}
                onSelect={setSelected}
              />
            </motion.div>
          ))}
          {filtered.length === 0 && (
            <div className="flex h-40 items-center justify-center text-[13px] text-faint">
              No signals match the current filters
            </div>
          )}
        </div>

        {/* detail panel */}
        <div className="flex-1 rounded-xl border border-border bg-card overflow-hidden">
          <SignalDetail signal={selected} onViewInGraph={selected ? () => handleViewInGraph(selected) : undefined} />
        </div>
      </div>
    </div>
  )
}
