import { useEffect, useState } from 'react'

export default function RiskGauge({ value, size = 168 }: { value: number; size?: number }) {
  const [shown, setShown] = useState(0)
  useEffect(() => {
    let raf = 0
    const start = performance.now()
    const dur = 1100
    const tick = (now: number) => {
      const p = Math.min(1, (now - start) / dur)
      const eased = 1 - Math.pow(1 - p, 3)
      setShown(Math.round(value * eased))
      if (p < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [value])

  const color = value >= 75 ? '#F43F5E' : value >= 50 ? '#FBBF24' : '#2DD4BF'
  const ring = size
  const inner = size - 26
  return (
    <div className="relative grid place-items-center" style={{ width: ring, height: ring }}>
      <div
        className="rounded-full transition-all"
        style={{
          width: ring,
          height: ring,
          background: `conic-gradient(${color} ${shown * 3.6}deg, #1A2230 ${shown * 3.6}deg 360deg)`,
          boxShadow: `0 0 30px -8px ${color}66`,
        }}
      />
      <div
        className="absolute grid place-items-center rounded-full bg-panel"
        style={{ width: inner, height: inner, boxShadow: 'inset 0 0 0 1px #232C3A' }}
      >
        <div className="text-center leading-none">
          <div className="font-display text-4xl tnum" style={{ color }}>
            {shown}
          </div>
          <div className="mt-2 font-mono text-[9px] tracking-[0.2em] text-muted">RISK INDEX</div>
        </div>
      </div>
    </div>
  )
}
