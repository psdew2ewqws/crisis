import {
  Zap,
  LayoutGrid,
  Activity,
  Share2,
  Target,
  FlaskConical,
  Gauge,
  PenLine,
  Settings,
  HelpCircle,
} from 'lucide-react'
import { cases, type Tone } from '../lib/data'

const OPS = [
  { label: 'Dashboard', icon: LayoutGrid, badge: null },
  { label: 'Signals', icon: Activity, badge: '6' },
  { label: 'Incident Graph', icon: Share2, badge: null },
  { label: 'Root Cause', icon: Target, badge: null },
  { label: 'Solutions', icon: FlaskConical, badge: null },
  { label: 'Simulation', icon: Gauge, badge: null },
  { label: 'Decisions', icon: PenLine, badge: null },
]

const dot: Record<Tone, string> = {
  danger: 'bg-danger',
  good: 'bg-good',
  warn: 'bg-warn',
  neutral: 'bg-muted',
}
const score: Record<Tone, string> = {
  danger: 'text-danger',
  good: 'text-good',
  warn: 'text-warn',
  neutral: 'text-muted',
}

export default function Sidebar({
  onRun,
  active,
  onNavigate,
}: {
  onRun: () => void
  active: string
  onNavigate: (s: string) => void
}) {
  return (
    <aside className="flex w-[248px] shrink-0 flex-col border-r border-border bg-sidebar">
      {/* brand */}
      <div className="flex items-center gap-2.5 px-5 pb-4 pt-5">
        <div className="grid h-9 w-9 place-items-center rounded-lg bg-blue shadow-[0_0_18px_-4px_#3b82f6]">
          <Zap className="h-5 w-5 fill-white text-white" />
        </div>
        <div className="leading-tight">
          <div className="text-[15px] font-semibold tracking-tight text-txt">AEGIS</div>
          <div className="text-[10px] font-medium tracking-[0.16em] text-faint">CRISIS CONSOLE</div>
        </div>
      </div>

      {/* run analysis */}
      <div className="px-4 pb-2">
        <button
          onClick={onRun}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-blue py-2.5 text-[13.5px] font-semibold text-white transition-colors hover:bg-[#2f76e8]"
        >
          <Zap className="h-4 w-4 fill-white" />
          Run Analysis
        </button>
      </div>

      <nav className="mt-3 flex-1 overflow-y-auto px-3">
        <div className="px-2 pb-1.5 pt-2 text-[10px] font-semibold tracking-[0.14em] text-faint">
          OPERATIONS
        </div>
        {OPS.map((item) => {
          const on = active === item.label
          const Icon = item.icon
          return (
            <button
              key={item.label}
              onClick={() => onNavigate(item.label)}
              className={`group mb-0.5 flex w-full items-center gap-3 rounded-lg px-3 py-2 text-[13.5px] transition-colors ${
                on ? 'bg-cardhi text-txt' : 'text-muted hover:bg-soft hover:text-txt'
              }`}
            >
              <Icon className={`h-[18px] w-[18px] ${on ? 'text-blue' : 'text-muted group-hover:text-txt'}`} />
              <span className={on ? 'font-medium' : ''}>{item.label}</span>
              {item.badge && (
                <span className="ml-auto font-mono text-[11px] text-faint">{item.badge}</span>
              )}
            </button>
          )
        })}

        <div className="px-2 pb-1.5 pt-4 text-[10px] font-semibold tracking-[0.14em] text-faint">CASE</div>
        {cases.map((c) => (
          <button
            key={c.name}
            onClick={() => onNavigate(c.name)}
            className="group mb-0.5 flex w-full items-center gap-3 rounded-lg px-3 py-2 text-[13.5px] text-muted transition-colors hover:bg-soft hover:text-txt"
          >
            <span className={`h-2 w-2 rounded-full ${dot[c.tone]}`} />
            <span className="group-hover:text-txt">{c.name}</span>
            <span className={`ml-auto font-mono text-[11px] ${score[c.tone]}`}>{c.score}</span>
          </button>
        ))}
      </nav>

      {/* footer */}
      <div className="border-t border-border px-3 py-3">
        <button className="mb-0.5 flex w-full items-center gap-3 rounded-lg px-3 py-2 text-[13.5px] text-muted transition-colors hover:bg-soft hover:text-txt">
          <Settings className="h-[18px] w-[18px]" />
          Settings
        </button>
        <button className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-[13.5px] text-muted transition-colors hover:bg-soft hover:text-txt">
          <HelpCircle className="h-[18px] w-[18px]" />
          Get Help
        </button>
        <div className="mt-2 flex items-center gap-3 px-3 py-2">
          <div className="grid h-8 w-8 place-items-center rounded-full bg-cardhi text-[11px] font-semibold text-muted">
            LH
          </div>
          <div className="leading-tight">
            <div className="text-[13px] font-medium text-txt">Cmdr. Haddad</div>
            <div className="text-[11px] text-faint">Commander</div>
          </div>
        </div>
      </div>
    </aside>
  )
}
