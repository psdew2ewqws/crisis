import { Brain } from 'lucide-react'

export default function LearnDiff({ items }: { items: string[] }) {
  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="text-[10px] font-semibold tracking-[0.14em] text-faint mb-4">WHAT THE ENGINE LEARNED</div>
      <div className="space-y-3">
        {items.map((item, i) => (
          <div key={i} className="flex items-start gap-3">
            <Brain className="mt-0.5 h-4 w-4 shrink-0 text-blue" />
            <span className="text-[13px] text-muted">{item}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
