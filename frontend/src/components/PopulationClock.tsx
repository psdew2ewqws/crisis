import { useEffect, useState } from 'react'
import { Users } from 'lucide-react'

/* ──────────────────────────────────────────────────────────────────────────
 * Jordan live population clock — running total = baseline + net growth so far,
 * where net growth explicitly accounts for deaths:
 *
 *   net rate = crude birth rate − crude death rate   (natural increase)
 *   total(t) = POP_BASELINE × (1 + netRate)^(years since baseline)
 *
 * The value is recomputed from real elapsed time every second, so it
 * self-corrects and the displayed total ticks upward continuously.
 *
 * Sources (update these constants when newer official figures publish):
 *   • Baseline   — Jordan Department of Statistics (DoS), start-of-2024 ≈ 11.5M.
 *   • Birth rate — DoS / World Bank crude birth rate ≈ 22.0 per 1,000 / year.
 *   • Death rate — DoS / World Bank crude death rate ≈  4.0 per 1,000 / year.
 *   ⇒ net natural increase ≈ 18.0 per 1,000 / year = 1.80 % / year.
 * ──────────────────────────────────────────────────────────────────────── */
const POP_BASELINE = 11_500_000
const BASELINE_TS = Date.UTC(2024, 0, 1) // 1 Jan 2024, 00:00 UTC
const BIRTH_RATE = 0.022 // 22.0 births per 1,000 / year
const DEATH_RATE = 0.004 //  4.0 deaths per 1,000 / year
const NET_GROWTH_RATE = BIRTH_RATE - DEATH_RATE // 1.80 % / year, net of deaths
const SECONDS_PER_YEAR = 365.25 * 24 * 60 * 60

function populationAt(ms: number): number {
  const years = (ms - BASELINE_TS) / (SECONDS_PER_YEAR * 1000)
  return POP_BASELINE * Math.pow(1 + NET_GROWTH_RATE, years)
}

const intFmt = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 })
const fmtInt = (n: number) => intFmt.format(Math.floor(n))

export default function PopulationClock() {
  const [now, setNow] = useState(() => Date.now())

  // Tick once per second — the requirement is a per-second live update.
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(id)
  }, [])

  const population = populationAt(now)
  const intPart = Math.floor(population)
  const decimals = (population - intPart).toFixed(3).slice(1) // ".453"

  // Births and deaths are modelled separately, then netted — so deaths are
  // explicitly subtracted from the headline total rather than assumed away.
  const birthsPerDay = (population * BIRTH_RATE) / 365.25
  const deathsPerDay = (population * DEATH_RATE) / 365.25
  const netPerDay = birthsPerDay - deathsPerDay
  const netPerSecond = netPerDay / 86_400
  const growthSinceBaseline = population - POP_BASELINE

  return (
    <div className="group relative overflow-hidden rounded-xl border border-border bg-card p-6 transition-[border-color,background-color,box-shadow] duration-200 hover:border-border/80 hover:bg-cardhi hover:shadow-xl hover:shadow-black/20">
      {/* tone-tinted hairline + soft corner glow, matching KpiCard */}
      <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-good/70 to-transparent" />
      <div className="pointer-events-none absolute -right-12 -top-12 h-32 w-32 rounded-full bg-gradient-to-br from-good/40 to-transparent opacity-0 blur-3xl transition-opacity duration-300 group-hover:opacity-50" />

      <div className="flex flex-wrap items-end justify-between gap-x-8 gap-y-5">
        {/* left — label + running total */}
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-[13px] text-muted">
            <Users className="h-4 w-4 text-good" />
            Jordan Population
            <span className="inline-flex items-center gap-1.5 font-medium text-good">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-good opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-good" />
              </span>
              Live
            </span>
          </div>

          <div className="mt-3.5 flex items-end gap-1.5">
            <span className="text-[clamp(40px,5.5vw,56px)] font-semibold leading-none tracking-[-0.02em] text-txt tnum">
              {fmtInt(intPart)}
              <span className="text-muted/60">{decimals}</span>
            </span>
            <span className="pb-1.5 text-[15px] text-muted">people</span>
          </div>

          <div className="mt-2.5 text-[12px] text-faint">
            <span className="text-good">+{netPerSecond.toFixed(4)}</span> net / sec (births − deaths)
            {' · '}
            <span className="font-mono">{fmtInt(POP_BASELINE)}</span> baseline (DoS · Jan 2024){' '}
            <span className="text-good">+ {fmtInt(growthSinceBaseline)}</span> since
          </div>
        </div>

        {/* right — births − deaths = net, divider style matches the Case Summary card */}
        <div className="flex shrink-0 items-center gap-6">
          <div className="text-right">
            <div className="font-mono text-[11px] text-faint">Births / day</div>
            <div className="font-mono text-[15px] text-good tnum">+{fmtInt(birthsPerDay)}</div>
          </div>
          <div className="h-9 w-px bg-border" />
          <div className="text-right">
            <div className="font-mono text-[11px] text-faint">Deaths / day</div>
            <div className="font-mono text-[15px] text-danger tnum">−{fmtInt(deathsPerDay)}</div>
          </div>
          <div className="h-9 w-px bg-border" />
          <div className="text-right">
            <div className="font-mono text-[11px] text-faint">Net / day</div>
            <div className="font-mono text-[15px] text-txt tnum">+{fmtInt(netPerDay)}</div>
          </div>
        </div>
      </div>
    </div>
  )
}
