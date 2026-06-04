import { MessagesSquare } from 'lucide-react'
import { motion } from 'motion/react'

/**
 * DebateStream — the agents arguing.
 * Renders the stream of `debate` turns emitted by the scenario pipeline as a
 * vertical list of chat bubbles, each tinted / accented by the agent's role.
 */
export interface DebateTurn {
  role: string
  agent: string
  text: string
  engine?: string
}

interface DebateStreamProps {
  turns: DebateTurn[]
}

// Same role palette as AgentRoster — inlined so this component is self-contained.
const ROLE_COLOR: Record<string, string> = {
  delegate: '#22D3EE',
  analyst: '#3B82F6',
  advocate: '#34D399',
  skeptic: '#FBBF24',
  synthesizer: '#A78BFA',
}
const FALLBACK_COLOR = '#8B8D96'

export default function DebateStream({ turns }: DebateStreamProps) {
  if (turns.length === 0) return null

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="mb-4 flex items-baseline gap-2">
        <MessagesSquare className="h-4 w-4 text-blue" />
        <h3 className="text-[15px] font-semibold text-txt" dir="auto">نقاش الوكلاء</h3>
        <span className="text-[12px] uppercase tracking-wide text-faint">· AGENT DEBATE</span>
      </div>

      <div className="flex flex-col gap-2.5">
        {turns.map((turn, i) => {
          const color = ROLE_COLOR[turn.role] ?? FALLBACK_COLOR
          const engineLabel = turn.engine !== 'llm' ? 'تقديري' : 'نموذج محلي'
          return (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, delay: i * 0.04 }}
              className="rounded-lg border border-border border-l-2 p-3"
              style={{ borderLeftColor: color, background: `${color}0D` }}
            >
              <div className="flex items-baseline justify-between gap-2">
                <span className="text-[13.5px] font-semibold" dir="auto" style={{ color }}>
                  {turn.agent}
                </span>
                <span className="shrink-0 text-[12px] text-faint">{engineLabel}</span>
              </div>
              <p dir="auto" className="mt-1 text-[13px] leading-relaxed text-muted">
                {turn.text}
              </p>
            </motion.div>
          )
        })}
      </div>
    </div>
  )
}
