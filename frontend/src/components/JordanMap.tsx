import { useRef, useState } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { X, AlertTriangle, Building2, Hospital, Loader2 } from 'lucide-react'
import jordanData from '../lib/jordan-geojson'
import { getGovSignals, severityTone, toneColor, type GovSummary } from '../lib/voc2'

// ── Projection ────────────────────────────────────────────────────────────────
const MIN_LON = 34.75, MAX_LON = 39.55
const MIN_LAT = 28.95, MAX_LAT = 33.60
const COS_LAT = Math.cos((31.3 * Math.PI) / 180)  // ≈ 0.856
const W = 860
const H = Math.round(W * ((MAX_LAT - MIN_LAT) / ((MAX_LON - MIN_LON) * COS_LAT)))

function project(lon: number, lat: number): [number, number] {
  return [
    ((lon - MIN_LON) / (MAX_LON - MIN_LON)) * W,
    ((MAX_LAT - lat) / (MAX_LAT - MIN_LAT)) * H,
  ]
}
function ringToD(ring: number[][]): string {
  return ring.map(([lon, lat], i) => {
    const [x, y] = project(lon, lat)
    return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ') + ' Z'
}
function geomToD(geom: { type: string; coordinates: unknown }): string {
  if (geom.type === 'Polygon')
    return (geom.coordinates as number[][][]).map(ringToD).join(' ')
  if (geom.type === 'MultiPolygon')
    return (geom.coordinates as number[][][][]).flatMap(p => p.map(ringToD)).join(' ')
  return ''
}
function centroid(geom: { type: string; coordinates: unknown }): [number, number] {
  const ring: number[][] =
    geom.type === 'Polygon'
      ? (geom.coordinates as number[][][])[0]
      : (geom.coordinates as number[][][][])[0][0]
  const n = ring.length
  return project(
    ring.reduce((s, c) => s + c[0], 0) / n,
    ring.reduce((s, c) => s + c[1], 0) / n,
  )
}

// ── Name maps ─────────────────────────────────────────────────────────────────
const GOV_AR: Record<string, string> = {
  Irbid: 'إربد', Madaba: 'مادبا', Karak: 'الكرك', Tafilah: 'الطفيلة',
  Aqaba: 'العقبة', Balqa: 'البلقاء', Mafraq: 'المفرق', 'Ma`an': 'معان',
  Amman: 'عمان', Zarqa: 'الزرقاء', Ajlun: 'عجلون', Jarash: 'جرش',
}
// GeoJSON NAME_1 → backend gov id
const GOV_ID: Record<string, string> = {
  Irbid: 'irbid', Madaba: 'madaba', Karak: 'karak', Tafilah: 'tafilah',
  Aqaba: 'aqaba', Balqa: 'balqa', Mafraq: 'mafraq', 'Ma`an': 'maan',
  Amman: 'amman', Zarqa: 'zarqa', Ajlun: 'ajlun', Jarash: 'jerash',
}
const SKIP_LABEL = new Set(['Ajlun', 'Jarash', 'Madaba', 'Tafilah'])
const LABEL_OFFSET: Record<string, [number, number]> = {
  Amman: [0, -12], Zarqa: [0, -10], Aqaba: [0, 10],
}

// ── Static facility data ──────────────────────────────────────────────────────
interface Facility { name: string; lat: number; lng: number }
const CIVIL_DEFENSE: Record<string, Facility[]> = {
  amman:   [{ name: 'Civil Defense Directorate HQ', lat: 31.955, lng: 35.933 },
             { name: 'Sweileh Civil Defense', lat: 31.990, lng: 35.878 }],
  zarqa:   [{ name: 'Zarqa Civil Defense HQ', lat: 32.073, lng: 36.088 },
             { name: 'Russeifa Civil Defense', lat: 32.020, lng: 36.030 }],
  irbid:   [{ name: 'Irbid Civil Defense Directorate', lat: 32.555, lng: 35.852 },
             { name: 'Ramtha Civil Defense', lat: 32.557, lng: 36.008 }],
  balqa:   [{ name: 'As-Salt Civil Defense', lat: 32.033, lng: 35.728 }],
  mafraq:  [{ name: 'Mafraq Civil Defense Directorate', lat: 32.342, lng: 36.200 }],
  madaba:  [{ name: 'Madaba Civil Defense', lat: 31.717, lng: 35.793 }],
  karak:   [{ name: 'Karak Civil Defense Directorate', lat: 31.185, lng: 35.704 },
             { name: "Mu'tah Civil Defense", lat: 31.039, lng: 35.716 }],
  tafilah: [{ name: 'Tafilah Civil Defense', lat: 30.842, lng: 35.604 }],
  maan:    [{ name: "Ma'an Civil Defense Directorate", lat: 30.192, lng: 35.735 }],
  aqaba:   [{ name: 'Aqaba Civil Defense Directorate', lat: 29.531, lng: 35.006 }],
  ajloun:  [{ name: 'Ajloun Civil Defense', lat: 32.333, lng: 35.752 }],
  jerash:  [{ name: 'Jerash Civil Defense', lat: 32.282, lng: 35.900 }],
}
const HOSPITALS: Record<string, Facility[]> = {
  amman:   [{ name: 'Al-Bashir Hospital', lat: 31.951, lng: 35.912 },
             { name: 'Jordan University Hospital', lat: 31.974, lng: 35.892 },
             { name: 'King Hussein Medical Center', lat: 31.980, lng: 35.930 }],
  zarqa:   [{ name: 'Prince Hashem Military Hospital', lat: 32.065, lng: 36.098 },
             { name: 'Zarqa Governmental Hospital', lat: 32.071, lng: 36.083 }],
  irbid:   [{ name: 'Princess Basma Hospital', lat: 32.548, lng: 35.848 },
             { name: 'King Abdullah University Hospital', lat: 32.504, lng: 35.826 }],
  balqa:   [{ name: 'Prince Ali Hospital (As-Salt)', lat: 32.036, lng: 35.735 }],
  mafraq:  [{ name: 'Mafraq Governmental Hospital', lat: 32.345, lng: 36.198 }],
  madaba:  [{ name: 'Madaba Governmental Hospital', lat: 31.718, lng: 35.796 }],
  karak:   [{ name: 'Karak Governmental Hospital', lat: 31.183, lng: 35.700 },
             { name: 'Prince Hussein Hospital', lat: 31.190, lng: 35.710 }],
  tafilah: [{ name: 'Tafilah Governmental Hospital', lat: 30.840, lng: 35.601 }],
  maan:    [{ name: "Ma'an Governmental Hospital", lat: 30.190, lng: 35.732 }],
  aqaba:   [{ name: 'Aqaba Governmental Hospital', lat: 29.528, lng: 35.003 },
             { name: 'Princess Haya Hospital', lat: 29.535, lng: 35.010 }],
  ajloun:  [{ name: 'Ajloun Governmental Hospital', lat: 32.330, lng: 35.748 }],
  jerash:  [{ name: 'Jerash Governmental Hospital', lat: 32.279, lng: 35.897 }],
}

// ── Details panel ─────────────────────────────────────────────────────────────
const isAr = (s: string | null | undefined) => !!s && /[؀-ۿ]/.test(s)
const clip  = (s: string | null | undefined, n = 90) =>
  !s ? '—' : s.length > n ? s.slice(0, n) + '…' : s
const SEVERITY_ORDER = ['critical', 'high', 'medium', 'low', 'unknown']
const SEV_COLOR: Record<string, string> = {
  critical: '#F04359', high: '#F97316', medium: '#FBBF24',
  low: '#34D399', unknown: '#62646D',
}

function DetailsPanel({
  name, govId, onClose,
}: { name: string; govId: string; onClose: () => void }) {
  const [summary, setSummary] = useState<GovSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const fetchedRef = useRef(false)

  // Fetch once per mount
  if (!fetchedRef.current) {
    fetchedRef.current = true
    getGovSignals(govId).then(s => { setSummary(s); setLoading(false) })
  }

  const cd   = CIVIL_DEFENSE[govId] ?? []
  const hosp = HOSPITALS[govId] ?? []
  const displayName = name === "Ma\`an" ? "Ma'an" : name

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 6 }}
      transition={{ duration: 0.18, ease: 'easeOut' }}
      className="border-t border-border"
    >
      {/* panel header */}
      <div className="relative flex items-center justify-between px-5 py-3">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-blue/40 to-transparent" />
        <div className="flex items-center gap-2">
          <span className="text-[14px] font-semibold text-txt">{displayName}</span>
          <span className="text-[13px] text-muted" dir="rtl">{GOV_AR[name]}</span>
          {summary && summary.total > 0 && (
            <span className="rounded-md border border-border bg-soft px-2 py-0.5 font-mono text-[11px] text-faint">
              {summary.total} signals
            </span>
          )}
        </div>
        <button
          onClick={onClose}
          className="rounded-lg p-1.5 text-muted transition-colors hover:bg-soft hover:text-txt"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* three columns */}
      <div className="grid grid-cols-1 gap-0 divide-y divide-border sm:grid-cols-3 sm:divide-x sm:divide-y-0">
        {/* Issues */}
        <div className="px-4 py-3">
          <div className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.1em] text-faint">
            <AlertTriangle className="h-3.5 w-3.5" />
            Issues &amp; Crises
          </div>
          {loading && (
            <div className="flex items-center gap-1.5 text-[12px] text-muted">
              <Loader2 className="h-3.5 w-3.5 animate-spin text-blue" /> Loading…
            </div>
          )}
          {!loading && (!summary || summary.total === 0) && (
            <p className="text-[12px] text-faint">No recorded issues.</p>
          )}
          {!loading && summary && summary.total > 0 && (
            <>
              <div className="mb-2 flex flex-wrap gap-1.5">
                {SEVERITY_ORDER.filter(s => summary.by_severity[s]).map(s => (
                  <span key={s} className="rounded px-1.5 py-0.5 text-[10px] font-semibold"
                    style={{ background: SEV_COLOR[s] + '22', color: SEV_COLOR[s] }}>
                    {s} · {summary.by_severity[s]}
                  </span>
                ))}
              </div>
              <ul className="space-y-1.5 max-h-[180px] overflow-y-auto">
                {summary.signals.slice(0, 8).map((sig, i) => {
                  const txt = sig.text_clean || sig.text
                  const tone = severityTone(sig.severity)
                  return (
                    <li key={sig.record_id ?? i}
                      className="rounded-lg border border-border/50 bg-soft/40 px-2.5 py-1.5">
                      <div className="flex items-center gap-1.5 mb-0.5">
                        <span className="h-1.5 w-1.5 rounded-full flex-shrink-0"
                          style={{ background: toneColor(tone) }} />
                        {sig.service_id && (
                          <span className="font-mono text-[10px] text-faint truncate">
                            {sig.service_id}
                          </span>
                        )}
                      </div>
                      <p className="text-[11.5px] leading-relaxed text-txt line-clamp-2"
                        dir={isAr(txt) ? 'rtl' : 'ltr'}>
                        {clip(txt, 80)}
                      </p>
                    </li>
                  )
                })}
              </ul>
            </>
          )}
        </div>

        {/* Civil Defense */}
        <div className="px-4 py-3">
          <div className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.1em] text-faint">
            <Building2 className="h-3.5 w-3.5" />
            Civil Defense
          </div>
          {cd.length === 0
            ? <p className="text-[12px] text-faint">No data.</p>
            : (
              <ul className="space-y-2">
                {cd.map(f => (
                  <li key={f.name} className="flex items-start gap-2">
                    <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-blue" />
                    <div>
                      <div className="text-[12px] text-txt leading-snug">{f.name}</div>
                      <div className="font-mono text-[10px] text-faint">
                        {f.lat.toFixed(3)}°N {f.lng.toFixed(3)}°E
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
        </div>

        {/* Hospitals */}
        <div className="px-4 py-3">
          <div className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.1em] text-faint">
            <Hospital className="h-3.5 w-3.5" />
            Hospitals
          </div>
          {hosp.length === 0
            ? <p className="text-[12px] text-faint">No data.</p>
            : (
              <ul className="space-y-2">
                {hosp.map(h => (
                  <li key={h.name} className="flex items-start gap-2">
                    <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-good" />
                    <div>
                      <div className="text-[12px] text-txt leading-snug">{h.name}</div>
                      <div className="font-mono text-[10px] text-faint">
                        {h.lat.toFixed(3)}°N {h.lng.toFixed(3)}°E
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
        </div>
      </div>
    </motion.div>
  )
}

// ── Map ───────────────────────────────────────────────────────────────────────
export default function JordanMap() {
  const [hovered,  setHovered]  = useState<string | null>(null)
  const [selected, setSelected] = useState<string | null>(null)

  const toggle = (name: string) =>
    setSelected(prev => (prev === name ? null : name))

  return (
    <div className="w-full group relative overflow-hidden rounded-xl border border-border bg-card transition-[border-color,box-shadow] duration-200 hover:border-border/80 hover:shadow-xl hover:shadow-black/20">
      <div className="pointer-events-none absolute inset-x-0 top-0 z-10 h-px bg-gradient-to-r from-blue/60 to-transparent" />

      {/* header */}
      <div className="flex items-center justify-between border-b border-border px-5 py-3">
        <div className="text-[13px] font-semibold text-txt">Jordan — Governorate Map</div>
        <div className="text-[12px] text-faint">
          {hovered && !selected ? (
            <span className="font-medium text-txt">
              {hovered === "Ma\`an" ? "Ma'an" : hovered}
              {GOV_AR[hovered] && (
                <span className="ml-2 text-muted" dir="rtl">{GOV_AR[hovered]}</span>
              )}
            </span>
          ) : selected ? (
            <span className="text-blue">Click again to close</span>
          ) : (
            '12 governorates · click to explore'
          )}
        </div>
      </div>

      {/* SVG */}
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        style={{ display: 'block', background: '#0d0e11' }}
      >
        {[30, 31, 32, 33].map(lat => {
          const [, y] = project(MIN_LON, lat)
          return <line key={`lat${lat}`} x1={0} y1={y} x2={W} y2={y} stroke="#1c1d23" strokeWidth={0.8} />
        })}
        {[35, 36, 37, 38, 39].map(lon => {
          const [x] = project(lon, MIN_LAT)
          return <line key={`lon${lon}`} x1={x} y1={0} x2={x} y2={H} stroke="#1c1d23" strokeWidth={0.8} />
        })}

        {jordanData.features.map(feature => {
          const name = feature.properties.NAME_1
          const d    = geomToD(feature.geometry)
          const isH  = hovered === name
          const isS  = selected === name
          const [cx, cy] = centroid(feature.geometry)
          const [ox, oy] = LABEL_OFFSET[name] ?? [0, 0]
          const displayName = name === "Ma\`an" ? "Ma'an" : name

          return (
            <g key={name}>
              <path
                d={d}
                fill={isS ? '#1d4ed8' : isH ? '#1e40af' : '#1e3a5f'}
                stroke={isS ? '#93c5fd' : isH ? '#60a5fa' : '#3b82f6'}
                strokeWidth={isS ? 2 : isH ? 1.6 : 0.8}
                strokeLinejoin="round"
                style={{ cursor: 'pointer', transition: 'fill 0.14s, stroke 0.14s' }}
                onMouseEnter={() => setHovered(name)}
                onMouseLeave={() => setHovered(null)}
                onClick={() => toggle(name)}
              />
              {/* selected ring */}
              {isS && (
                <path d={d} fill="none" stroke="#bfdbfe" strokeWidth={0.5}
                  strokeDasharray="4 3" style={{ pointerEvents: 'none' }} />
              )}
              {!SKIP_LABEL.has(name) && (
                <text
                  x={cx + ox} y={cy + oy}
                  textAnchor="middle" dominantBaseline="middle"
                  fontSize={name === 'Mafraq' || name === "Ma\`an" ? 14 : 11.5}
                  fontFamily="system-ui, sans-serif"
                  fill={isS ? '#dbeafe' : isH ? '#bfdbfe' : '#93c5fd'}
                  fontWeight={isS || isH ? 600 : 400}
                  style={{ pointerEvents: 'none', userSelect: 'none', transition: 'fill 0.14s' }}
                >
                  {displayName}
                </text>
              )}
            </g>
          )
        })}
      </svg>

      {/* details panel — slides in below the map */}
      <AnimatePresence>
        {selected && (
          <DetailsPanel
            key={selected}
            name={selected}
            govId={GOV_ID[selected] ?? selected.toLowerCase()}
            onClose={() => setSelected(null)}
          />
        )}
      </AnimatePresence>

      <div className="border-t border-border px-4 py-2 text-right font-mono text-[10px] text-faint">
        boundaries · Apache Superset / GADM · WGS84
      </div>
    </div>
  )
}
