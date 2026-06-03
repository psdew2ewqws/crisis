import { motion } from 'motion/react'
import { Users } from 'lucide-react'
import type { ScenarioAgent } from '../../lib/voc'

interface AgentRosterProps {
  agents: ScenarioAgent[]
  engine?: string
}

const ROLE_COLOR: Record<string, string> = {
  analyst: '#93C5FD',
  advocate: '#34D399',
  skeptic: '#FBBF24',
  synthesizer: '#C4B5FD',
  data: '#22D3EE',
  service: '#60A5FA',
  citizen: '#4ADE80',
  ops: '#38BDF8',
  risk: '#F472B6',
  priority: '#A78BFA',
  comms: '#2DD4BF',
  budget: '#FCD34D',
  legal: '#FB7185',
}
const FALLBACK_COLOR = '#8B8D96'

const colorFor = (key: string): string => ROLE_COLOR[key] ?? FALLBACK_COLOR

export default function AgentRoster({ agents, engine }: AgentRosterProps) {
  const grounded = engine === 'grounded'

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="rounded-xl border border-border bg-card p-5"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <Users className="h-4 w-4 text-faint" />
          <h3 className="text-[15px] font-semibold text-txt" dir="auto">
            الوكلاء المختارون
            <span className="ml-2 text-[12px] font-normal uppercase tracking-wide text-faint">
              · SELECTED AGENTS
            </span>
          </h3>
        </div>
        {engine && (
          <span
            className={
              'inline-flex shrink-0 items-center rounded-md border px-2.5 py-1 text-[12px] ' +
              (grounded
                ? 'border-warn/30 bg-warn/10 text-warn'
                : 'border-good/30 bg-good/10 text-good')
            }
            dir="auto"
          >
            {grounded ? 'استرجاع مبني على الكلمات' : 'نموذج محلي'}
          </span>
        )}
      </div>

      <div className="mt-4 flex flex-wrap gap-2.5">
        {agents.map((agent) => {
          const color = colorFor(agent.key)
          return (
            <div
              key={agent.key}
              className="relative flex min-w-[180px] max-w-[260px] flex-1 items-start gap-2.5 overflow-hidden rounded-lg border border-border bg-card px-3 py-2.5 transition-colors hover:bg-cardhi"
            >
              <span
                aria-hidden
                className="absolute inset-y-0 left-0 w-[3px] rounded-l-lg"
                style={{ backgroundColor: color }}
              />
              <span
                aria-hidden
                className="mt-1 h-2 w-2 shrink-0 rounded-full"
                style={{ backgroundColor: color }}
              />
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate text-[13.5px] font-medium text-txt" dir="auto">
                    {agent.name}
                  </span>
                  {agent.floor ? (
                    <span
                      className="shrink-0 rounded border border-border bg-cardhi px-1.5 py-0.5 text-[11px] text-faint"
                      dir="auto"
                    >
                      أساسي
                    </span>
                  ) : (
                    <span className="tnum shrink-0 text-[11px] text-faint">
                      {agent.score.toFixed(2)}
                    </span>
                  )}
                </div>
                {!agent.floor && agent.reason && (
                  <p className="mt-0.5 line-clamp-2 text-[12px] text-faint" dir="auto">
                    {agent.reason}
                  </p>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </motion.div>
  )
}
