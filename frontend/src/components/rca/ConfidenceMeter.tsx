export default function ConfidenceMeter({ value, threshold }: { value: number; threshold: number }) {
  const pct = Math.round(value * 100)
  const threshPct = Math.round(threshold * 100)

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="text-[10px] font-semibold tracking-[0.14em] text-faint mb-4">CONFIDENCE METER</div>
      <div className="relative h-6 rounded-full bg-bg overflow-hidden">
        {/* fill */}
        <div
          className="absolute inset-y-0 left-0 rounded-full"
          style={{
            width: `${pct}%`,
            background: 'linear-gradient(90deg, #34D399 0%, #3B82F6 60%, #34D399 100%)',
          }}
        />
        {/* threshold marker */}
        <div
          className="absolute top-0 bottom-0 w-px bg-txt"
          style={{ left: `${threshPct}%` }}
        />
        <div
          className="absolute -top-5 text-[10px] font-mono text-faint -translate-x-1/2"
          style={{ left: `${threshPct}%` }}
        >
          {threshold}
        </div>
      </div>
      <div className="mt-3 flex items-center justify-between">
        <span className="font-mono text-[14px] font-semibold text-txt">
          {value.toFixed(2)} / 1.00
        </span>
        <span className="rounded-md border border-good/30 bg-good/10 px-2 py-0.5 text-[11px] font-medium text-good">
          HIGH
        </span>
      </div>
    </div>
  )
}
