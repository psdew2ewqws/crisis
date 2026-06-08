// SimulationPage — two tabs:
//   • Scenario Analysis — the detection/prediction console (retrieve precedents →
//     select agents → Mesa before/after → verdict), streamed over /api/scenario/detect.
//   • Agent-Based — a true agent-based model: a society of Jordan agents (citizens,
//     services, a lagged government operator, media) seeded from voc360, run as
//     problem (no intervention) vs solution (data-calibrated intervention), streamed
//     over /api/abm/simulate.

import { useState } from 'react'
import ScenarioSimulation from '../components/scenario/ScenarioSimulation'
import AgentBasedSimulation from '../components/scenario/AgentBasedSimulation'

type Tab = 'scenario' | 'agent'
const TABS: { key: Tab; ar: string; en: string }[] = [
  { key: 'scenario', ar: 'تحليل السيناريو', en: 'Scenario Analysis' },
  { key: 'agent', ar: 'محاكاة الوكلاء', en: 'Agent-Based' },
]

export default function SimulationPage(_props: { caseId?: string } = {}) {
  const [tab, setTab] = useState<Tab>('scenario')
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-6 border-b border-border px-8 pt-5">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`relative flex items-center gap-2 pb-3 text-[14px] transition-colors ${
              tab === t.key ? 'font-semibold text-txt' : 'text-muted hover:text-txt'
            }`}
          >
            <span dir="auto">{t.ar}</span>
            <span className="text-[11px] text-faint">{t.en}</span>
            {tab === t.key && <span className="absolute inset-x-0 -bottom-px h-0.5 rounded bg-blue" />}
          </button>
        ))}
      </div>

      {tab === 'scenario' ? (
        <ScenarioSimulation />
      ) : (
        <div className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-[1340px] px-8 py-7">
            <AgentBasedSimulation />
          </div>
        </div>
      )}
    </div>
  )
}
