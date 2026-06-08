import 'leaflet/dist/leaflet.css'
import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { MapContainer, GeoJSON, CircleMarker, Popup } from 'react-leaflet'
import * as L from 'leaflet'
import type { Map as LeafletMap, CircleMarker as LeafletCircleMarker, PathOptions } from 'leaflet'
import type { Feature } from 'geojson'
import { Radio, ExternalLink, Loader2 } from 'lucide-react'
import {
  getRssSignals, getCaseStudiesMap, relTime,
  SEVERITY_COLOR, SEVERITY_RADIUS, CATEGORIES, SEVERITIES,
  type RssSignal, type RssCategory, type RssSeverity, type CaseStudySignal,
} from '../lib/rss'
import meGeoJSON from '../lib/middle-east-geojson'

// ── Map constants ────────────────────────────────────────────────────────────
const CENTER: [number, number] = [29.0, 42.0]
const ZOOM = 4
const MAX_BOUNDS: [[number, number], [number, number]] = [[12, 24], [42, 62]]
const POLL_MS = 20000

// ── Country signal count (used for intensity scaling) ────────────────────────
// Colors per signal-count tier: no data → dim | 1-5 → teal | 6-20 → blue | 21+ → amber
function tierColor(n: number): { fill: string; stroke: string } {
  if (n === 0) return { fill: '#131820', stroke: '#1e2a3a' }
  if (n <= 5)  return { fill: '#0e3040', stroke: '#0ea5e9' }   // teal-low
  if (n <= 20) return { fill: '#1a3a6e', stroke: '#3b82f6' }   // blue-mid
  return       { fill: '#3d2206', stroke: '#f97316' }           // amber-high (many signals)
}

function makeCountryStyle(signalsByCountry: Map<string, number>) {
  return (feature?: Feature): PathOptions => {
    const name: string = (feature?.properties as { name?: string } | null)?.name ?? ''
    const n = signalsByCountry.get(name) ?? 0
    const { fill, stroke } = tierColor(n)
    return {
      fillColor:   fill,
      fillOpacity: n > 0 ? 0.90 : 0.60,
      color:       stroke,
      weight:      n > 0 ? 1.5 : 0.6,
    }
  }
}

const CAT_COLOR: Record<RssCategory, string> = {
  conflict: '#ef4444', disaster: '#f97316', health: '#34d399',
  political: '#3b82f6', economic: '#fbbf24', other: '#8B8D96',
}
const isAr = (s: string | null | undefined) => !!s && /[؀-ۿ]/.test(s)
const clip = (s: string | null | undefined, n = 200) =>
  !s ? '' : s.length > n ? s.slice(0, n).trimEnd() + '…' : s

// ── Arabic governorate names for simulation prefill ─────────────────────────
const GOV_AR: Record<string, string> = {
  amman:'عمان', zarqa:'الزرقاء', irbid:'إربد', balqa:'البلقاء',
  mafraq:'المفرق', madaba:'مادبا', karak:'الكرك', tafilah:'الطفيلة',
  maan:'معان', aqaba:'العقبة', ajloun:'عجلون', jerash:'جرش',
}

function simulateSignal(sig: RssSignal | CaseStudySignal, type: 'rss' | 'case') {
  const text = type === 'case'
    ? `${(sig as CaseStudySignal).disaster_type} في الأردن: ${(sig as CaseStudySignal).title} — ${clip((sig as CaseStudySignal).crisis, 200)}`
    : `أزمة في الأردن: ${sig.title}${(sig as RssSignal).summary ? ' — ' + clip((sig as RssSignal).summary, 200) : ''}`
  const location = type === 'case'
    ? (GOV_AR[(sig as CaseStudySignal).gov] ?? (sig as CaseStudySignal).gov)
    : undefined
  sessionStorage.setItem('aegis_scenario_prefill', JSON.stringify({ text, location, run: true }))
  window.dispatchEvent(new CustomEvent('aegis:navigate', { detail: 'Simulation' }))
}

// ── Case study marker (purple, ai_case_studies data) ────────────────────────
const CaseStudyMarker = memo(function CaseStudyMarker({ c }: { c: CaseStudySignal }) {
  return (
    <CircleMarker
      center={[c.lat, c.lng]}
      radius={10}
      pathOptions={{ color: '#a855f7', fillColor: '#a855f7', fillOpacity: 0.7, weight: 2 }}
    >
      <Popup>
        <div className="aegis-popup">
          <div className="aegis-popup-title" dir="rtl">{c.title}</div>
          <div className="aegis-popup-meta">
            <span>{c.country}</span>
            {c.gov_match === 'text' && <span>· {GOV_AR[c.gov] ?? c.gov}</span>}
          </div>
          <div className="aegis-popup-badges">
            <span className="aegis-badge" style={{ background: '#a855f722', color: '#a855f7' }}>
              {c.disaster_type}
            </span>
            <span className="aegis-badge aegis-badge-muted">{c.source_site}</span>
          </div>
          {c.crisis && (
            <p className="aegis-popup-summary" dir="auto">{clip(c.crisis, 200)}</p>
          )}
          {c.solution && (
            <p style={{ color: '#34d399', fontSize: 11, marginTop: 4 }} dir="auto">
              ✓ {clip(c.solution, 150)}
            </p>
          )}
          <button
            className="aegis-sim-btn"
            dir="rtl"
            onClick={() => simulateSignal(c, 'case')}
          >
            ⚡ محاكاة هذا الحدث في الأردن
          </button>
        </div>
      </Popup>
    </CircleMarker>
  )
})

// ── Single marker (memoised so unchanged points don't re-render on poll) ─────
interface MarkerProps {
  sig: RssSignal
  selected: boolean
  onSelect: (id: string, lat: number, lng: number) => void
}

const SignalMarker = memo(
  function SignalMarker({ sig, selected, onSelect }: MarkerProps) {
    const ref = useRef<LeafletCircleMarker>(null)
    useEffect(() => {
      if (selected && ref.current) ref.current.openPopup()
    }, [selected])

    const color = SEVERITY_COLOR[sig.severity]
    const pulse = sig.severity === 'critical' || sig.severity === 'high'
    return (
      <CircleMarker
        ref={ref}
        center={[sig.lat as number, sig.lng as number]}
        radius={SEVERITY_RADIUS[sig.severity]}
        pathOptions={{
          color, fillColor: color, fillOpacity: 0.55, weight: 1.5,
          className: pulse ? 'aegis-pulse' : undefined,
        }}
        eventHandlers={{ click: () => onSelect(sig.id, sig.lat as number, sig.lng as number) }}
      >
        <Popup>
          <div className="aegis-popup">
            <a href={sig.link} target="_blank" rel="noopener noreferrer"
              className="aegis-popup-title" dir={isAr(sig.title) ? 'rtl' : 'ltr'}>
              {sig.title}
              <ExternalLink size={11} style={{ display: 'inline', marginLeft: 4, verticalAlign: 'middle' }} />
            </a>
            <div className="aegis-popup-meta">
              <span>{sig.source}</span>
              {sig.published && <span>· {relTime(sig.published)}</span>}
            </div>
            <div className="aegis-popup-badges">
              <span className="aegis-badge" style={{ background: CAT_COLOR[sig.category] + '22', color: CAT_COLOR[sig.category] }}>
                {sig.category}
              </span>
              <span className="aegis-badge" style={{ background: color + '22', color }}>
                {sig.severity}
              </span>
              {sig.country && <span className="aegis-badge aegis-badge-muted">{sig.country}</span>}
            </div>
            {sig.summary && (
              <p className="aegis-popup-summary" dir={isAr(sig.summary) ? 'rtl' : 'ltr'}>
                {clip(sig.summary, 200)}
              </p>
            )}
            <button
              className="aegis-sim-btn"
              dir="rtl"
              onClick={(e) => { e.stopPropagation(); simulateSignal(sig, 'rss') }}
            >
              ⚡ محاكاة هذا الحدث
            </button>
          </div>
        </Popup>
      </CircleMarker>
    )
  },
  (a, b) => a.sig.id === b.sig.id && a.selected === b.selected && a.sig.severity === b.sig.severity,
)

// ── Filter chip ──────────────────────────────────────────────────────────────
function Chip({ label, on, color, onClick }: { label: string; on: boolean; color: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="rounded-full border px-2 py-0.5 text-[10px] font-medium capitalize transition-colors"
      style={{
        borderColor: on ? color : 'var(--tw-border, #212228)',
        background: on ? color + '22' : 'transparent',
        color: on ? color : '#62646D',
      }}
    >
      {label}
    </button>
  )
}

// ── Map ───────────────────────────────────────────────────────────────────────
export default function MiddleEastMap() {
  const [signals, setSignals] = useState<RssSignal[]>([])
  const [lastFetch, setLastFetch] = useState<string | null>(null)
  const [sourceCount, setSourceCount] = useState(0)
  const [polledAt, setPolledAt] = useState<number>(Date.now())
  const [now, setNow] = useState<number>(Date.now())
  const [loaded, setLoaded] = useState(false)

  const [catOn, setCatOn] = useState<Set<RssCategory>>(() => new Set(CATEGORIES))
  const [sevOn, setSevOn] = useState<Set<RssSeverity>>(() => new Set(SEVERITIES))
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [caseStudies, setCaseStudies] = useState<CaseStudySignal[]>([])

  const mapRef = useRef<LeafletMap | null>(null)
  const prevIdsRef = useRef<string>('')

  // Poll the live feed every 20s; only update state when the id set changed so
  // memoised markers don't churn on every tick.
  useEffect(() => {
    let alive = true
    const load = () => getRssSignals({ limit: 500 }).then(res => {
      if (!alive) return
      setLastFetch(res.last_fetch)
      setSourceCount(res.source_count)
      setPolledAt(Date.now())
      setLoaded(true)
      const ids = res.signals.map(s => s.id).join(',')
      if (ids !== prevIdsRef.current) {
        prevIdsRef.current = ids
        setSignals(res.signals)
      }
    })
    load()
    const t = setInterval(load, POLL_MS)
    return () => { alive = false; clearInterval(t) }
  }, [])

  // 1s ticker for the "Updated Ns ago" label.
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [])

  // Fetch ai_case_studies cases once on mount.
  useEffect(() => {
    getCaseStudiesMap().then(d => setCaseStudies(d.cases || []))
  }, [])

  const filtered = useMemo(
    () => signals.filter(s => catOn.has(s.category) && sevOn.has(s.severity)),
    [signals, catOn, sevOn],
  )
  const located = useMemo(
    () => filtered.filter(s => s.lat != null && s.lng != null),
    [filtered],
  )
  const feed = useMemo(() => filtered.slice(0, 20), [filtered])

  // Signal count per country — drives polygon color intensity.
  const signalsByCountry = useMemo<Map<string, number>>(() => {
    const m = new Map<string, number>()
    for (const s of signals) {
      if (s.country) m.set(s.country, (m.get(s.country) ?? 0) + 1)
    }
    return m
  }, [signals])

  const countryStyle = useCallback(
    (feature?: Feature) => makeCountryStyle(signalsByCountry)(feature),
    [signalsByCountry],
  )

  // Add country name tooltip on hover.
  const onEachFeature = useCallback((feature: Feature, layer: L.Layer) => {
    const name: string = (feature?.properties as { name?: string } | null)?.name ?? ''
    const n = signalsByCountry.get(name) ?? 0
    const label = n > 0 ? `${name} · ${n} signals` : name
    layer.bindTooltip(label, {
      permanent: false, direction: 'center', className: 'aegis-country-tip',
    })
  }, [signalsByCountry])

  const toggleCat = (c: RssCategory) =>
    setCatOn(prev => { const n = new Set(prev); n.has(c) ? n.delete(c) : n.add(c); return n })
  const toggleSev = (s: RssSeverity) =>
    setSevOn(prev => { const n = new Set(prev); n.has(s) ? n.delete(s) : n.add(s); return n })

  const onSelect = (id: string, lat: number, lng: number) => {
    setSelectedId(id)
    const m = mapRef.current
    if (m) m.flyTo([lat, lng], Math.max(m.getZoom(), 6), { duration: 0.6 })
  }

  const secsAgo = Math.max(0, Math.round((now - polledAt) / 1000))

  return (
    <div className="group relative w-full overflow-hidden rounded-xl border border-border bg-card transition-[border-color,box-shadow] duration-200 hover:border-border/80 hover:shadow-xl hover:shadow-black/20">
      <div className="pointer-events-none absolute inset-x-0 top-0 z-[1100] h-px bg-gradient-to-r from-blue/60 to-transparent" />

      {/* pulse animation for critical/high markers */}
      <style>{`
        @keyframes aegisPulse { 0%,100% { stroke-opacity:1; fill-opacity:.55 } 50% { stroke-opacity:.25; fill-opacity:.2 } }
        .aegis-pulse { animation: aegisPulse 1.8s ease-in-out infinite; }
        .leaflet-container { background:#0d0e11; font-family:inherit; }
        .leaflet-popup-content-wrapper { background:#131417; color:#ECEDEE; border:1px solid #212228; border-radius:10px; box-shadow:0 10px 30px rgba(0,0,0,.5); }
        .leaflet-popup-tip { background:#131417; border:1px solid #212228; }
        .leaflet-popup-content { margin:10px 12px; width:260px !important; }
        .leaflet-container a.leaflet-popup-close-button { color:#8B8D96; }
        .aegis-popup-title { display:block; font-size:12.5px; font-weight:600; line-height:1.35; color:#ECEDEE; text-decoration:none; }
        .aegis-popup-title:hover { color:#3B82F6; }
        .aegis-popup-meta { margin-top:4px; display:flex; gap:5px; font-size:10px; color:#62646D; }
        .aegis-popup-badges { margin-top:6px; display:flex; flex-wrap:wrap; gap:4px; }
        .aegis-badge { border-radius:4px; padding:1px 6px; font-size:9.5px; font-weight:600; text-transform:capitalize; }
        .aegis-badge-muted { background:#1A1B20; color:#8B8D96; }
        .aegis-popup-summary { margin-top:6px; font-size:11px; line-height:1.5; color:#8B8D96; }
        .aegis-sim-btn { display:block; width:100%; margin-top:8px; padding:5px 10px; background:#3b82f620; border:1px solid #3b82f660; border-radius:6px; color:#60a5fa; font-size:11.5px; cursor:pointer; text-align:center; font-weight:600; }
        .aegis-sim-btn:hover { background:#3b82f640; }
        .aegis-country-tip { background:#0d1117dd !important; border:1px solid #3b82f660 !important; color:#93c5fd !important; font-size:11px !important; font-weight:600 !important; padding:3px 8px !important; border-radius:4px !important; white-space:nowrap; }
        .aegis-country-tip::before { display:none !important; }
        .leaflet-container { font-family: system-ui, sans-serif; }
      `}</style>

      <div className="flex items-center justify-between border-b border-border px-5 py-3">
        <div className="flex items-center gap-2 text-[13px] font-semibold text-txt">
          الشرق الأوسط — إشارات الأزمات المباشرة
          <span className="flex items-center gap-1 rounded-full border border-blue/40 bg-blue/10 px-2 py-0.5 text-[10px] font-medium text-blue">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-blue" />
            {signals.length} إشارة · {signalsByCountry.size} دولة
          </span>
        </div>
        <div className="flex items-center gap-3 text-[11px] text-faint">
          <span className="flex items-center gap-1">
            <Radio className="h-3 w-3" /> {sourceCount} مصدر
          </span>
          <span className="font-mono">{secsAgo}s ago</span>
        </div>
      </div>

      <div className="flex flex-col lg:flex-row">
        {/* map + overlay controls */}
        <div className="relative flex-1">
          <MapContainer
            center={CENTER}
            zoom={ZOOM}
            minZoom={3}
            maxZoom={9}
            maxBounds={MAX_BOUNDS}
            maxBoundsViscosity={0.8}
            scrollWheelZoom
            style={{ height: 480, width: '100%', background: '#0d1117' }}
            ref={(m) => { if (m) mapRef.current = m }}
            attributionControl={false}
          >
            {/* Data-only country polygons — signal-intensity coloring */}
            <GeoJSON
              data={meGeoJSON}
              style={countryStyle}
              onEachFeature={onEachFeature}
              key={signalsByCountry.size}
            />
            {located.map(sig => (
              <SignalMarker key={sig.id} sig={sig} selected={selectedId === sig.id} onSelect={onSelect} />
            ))}
            {caseStudies.map(c => (
              <CaseStudyMarker key={`cs-${c.id}`} c={c} />
            ))}
          </MapContainer>

          {/* control overlay — top-right */}
          <div className="pointer-events-auto absolute right-3 top-3 z-[1000] w-[200px] rounded-xl border border-border bg-card/90 p-3 backdrop-blur-sm">
            <div className="mb-1.5 text-[9.5px] font-semibold uppercase tracking-[0.1em] text-faint">Category</div>
            <div className="mb-2.5 flex flex-wrap gap-1">
              {CATEGORIES.map(c => (
                <Chip key={c} label={c} on={catOn.has(c)} color={CAT_COLOR[c]} onClick={() => toggleCat(c)} />
              ))}
            </div>
            <div className="mb-1.5 text-[9.5px] font-semibold uppercase tracking-[0.1em] text-faint">Severity</div>
            <div className="flex flex-wrap gap-1">
              {SEVERITIES.map(s => (
                <Chip key={s} label={s} on={sevOn.has(s)} color={SEVERITY_COLOR[s]} onClick={() => toggleSev(s)} />
              ))}
            </div>
          </div>

          {/* empty / loading state */}
          {located.length === 0 && (
            <div className="pointer-events-none absolute inset-0 z-[900] flex items-center justify-center">
              <div className="flex items-center gap-2 rounded-lg border border-border bg-card/90 px-4 py-2 text-[12px] text-muted backdrop-blur-sm">
                <Loader2 className="h-3.5 w-3.5 animate-spin text-blue" />
                {loaded ? 'Waiting for signals…' : 'Loading live signals…'}
              </div>
            </div>
          )}
        </div>

        {/* signal feed sidebar */}
        <div className="flex w-full shrink-0 flex-col border-t border-border lg:w-72 lg:border-l lg:border-t-0">
          <div className="border-b border-border px-3.5 py-2 text-[10px] font-semibold uppercase tracking-[0.1em] text-faint">
            Latest Signals
          </div>
          <ul className="max-h-[440px] divide-y divide-border/60 overflow-y-auto">
            {feed.length === 0 && (
              <li className="px-3.5 py-4 text-[11px] text-faint">No signals match the current filters.</li>
            )}
            {feed.map(sig => {
              const color = SEVERITY_COLOR[sig.severity]
              const hasGeo = sig.lat != null && sig.lng != null
              const active = selectedId === sig.id
              return (
                <li
                  key={sig.id}
                  onClick={() => hasGeo && onSelect(sig.id, sig.lat as number, sig.lng as number)}
                  className={`px-3.5 py-2.5 transition-colors ${hasGeo ? 'cursor-pointer hover:bg-soft/50' : ''} ${active ? 'bg-soft/60' : ''}`}
                >
                  <div className="flex items-start gap-2">
                    <span className="mt-1 h-2 w-2 shrink-0 rounded-full" style={{ background: color }} />
                    <div className="min-w-0 flex-1">
                      <a
                        href={sig.link} target="_blank" rel="noopener noreferrer"
                        onClick={e => e.stopPropagation()}
                        className="line-clamp-2 text-[12px] font-medium leading-snug text-txt hover:text-blue"
                        dir={isAr(sig.title) ? 'rtl' : 'ltr'}
                      >
                        {sig.title}
                      </a>
                      <div className="mt-1 flex items-center gap-1.5 text-[10px] text-faint">
                        <span className="truncate">{sig.source}</span>
                        {sig.country && <span>· {sig.country}</span>}
                        {sig.published && <span className="font-mono">· {relTime(sig.published)}</span>}
                      </div>
                    </div>
                  </div>
                </li>
              )
            })}
          </ul>
        </div>
      </div>

      <div className="border-t border-border px-4 py-2.5 flex flex-wrap items-center justify-between gap-2 text-[10px] text-faint">
        <div className="flex flex-wrap items-center gap-3">
          {/* signal-intensity legend */}
          <span className="flex items-center gap-1">
            <span className="inline-block h-2.5 w-2.5 rounded-sm border" style={{ background: '#0e3040', borderColor: '#0ea5e9' }} />
            1–5 إشارات
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block h-2.5 w-2.5 rounded-sm border" style={{ background: '#1a3a6e', borderColor: '#3b82f6' }} />
            6–20 إشارة
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block h-2.5 w-2.5 rounded-sm border" style={{ background: '#3d2206', borderColor: '#f97316' }} />
            +21 إشارة
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: '#a855f7' }} />
            حالات تاريخية ({caseStudies.length})
          </span>
        </div>
        <span className="font-mono">live RSS · {lastFetch ? relTime(lastFetch) : 'جارٍ التحميل…'} · Natural Earth</span>
      </div>
    </div>
  )
}
