import { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import {
  X, AlertTriangle, Building2, Hospital, Loader2, ZoomOut, Newspaper, ExternalLink, FlaskConical,
} from 'lucide-react'
import jordanData from '../lib/jordan-geojson'
import {
  getGovSignals, getNews, severityTone, toneColor,
  type GovSummary, type NewsItem, type NewsByGov,
} from '../lib/voc2'

// ── Projection ────────────────────────────────────────────────────────────────
const MIN_LON = 34.75, MAX_LON = 39.55
const MIN_LAT = 28.95, MAX_LAT = 33.60
const COS_LAT = Math.cos((31.3 * Math.PI) / 180)
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

// ── Drill-down: fit a governorate's projected bbox into the W×H viewport ────────
type ViewBox = { x: number; y: number; w: number; h: number }
const FULL_VIEW: ViewBox = { x: 0, y: 0, w: W, h: H }
const ASPECT = W / H
const PAD = 0.18       // breathing room around the focused governorate
const MIN_W = W * 0.22 // tightest zoom (~4.5×) so even tiny governorates stay legible

function geomBBox(geom: { type: string; coordinates: unknown }) {
  const rings: number[][][] =
    geom.type === 'Polygon'
      ? (geom.coordinates as number[][][])
      : (geom.coordinates as number[][][][]).flat()
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
  for (const ring of rings)
    for (const [lon, lat] of ring) {
      const [x, y] = project(lon, lat)
      if (x < minX) minX = x
      if (x > maxX) maxX = x
      if (y < minY) minY = y
      if (y > maxY) maxY = y
    }
  return { minX, minY, maxX, maxY }
}

// Centre on the bbox, pad it, force the W:H aspect (so the <svg> never reshapes),
// clamp the zoom, then keep the box fully inside the map so we never reveal empty
// background — the live viewBox is tweened toward this on select.
function fitViewBox(geom: { type: string; coordinates: unknown }): ViewBox {
  const { minX, minY, maxX, maxY } = geomBBox(geom)
  const cx = (minX + maxX) / 2, cy = (minY + maxY) / 2
  const bw = (maxX - minX) * (1 + PAD * 2), bh = (maxY - minY) * (1 + PAD * 2)
  let w = bw / bh > ASPECT ? bw : bh * ASPECT
  w = Math.max(MIN_W, Math.min(W, w))
  const h = w / ASPECT
  return {
    x: Math.max(0, Math.min(W - w, cx - w / 2)),
    y: Math.max(0, Math.min(H - h, cy - h / 2)),
    w,
    h,
  }
}

const easeOutCubic = (t: number) => 1 - Math.pow(1 - t, 3)

// ── Name maps ─────────────────────────────────────────────────────────────────
const GOV_AR: Record<string, string> = {
  Irbid: 'إربد', Madaba: 'مادبا', Karak: 'الكرك', Tafilah: 'الطفيلة',
  Aqaba: 'العقبة', Balqa: 'البلقاء', Mafraq: 'المفرق', 'Ma`an': 'معان',
  Amman: 'عمان', Zarqa: 'الزرقاء', Ajlun: 'عجلون', Jarash: 'جرش',
}
const GOV_ID: Record<string, string> = {
  Irbid: 'irbid', Madaba: 'madaba', Karak: 'karak', Tafilah: 'tafilah',
  Aqaba: 'aqaba', Balqa: 'balqa', Mafraq: 'mafraq', 'Ma`an': 'maan',
  Amman: 'amman', Zarqa: 'zarqa', Ajlun: 'ajlun', Jarash: 'jerash',
}
const LABEL_OFFSET: Record<string, [number, number]> = {
  Amman: [0, -12], Zarqa: [0, -10], Aqaba: [0, 10],
  // Northern trio (Irbid · Ajlun · Jarash) is tightly packed — nudge the small
  // Ajlun/Jarash labels apart so all 12 names render without overlapping.
  Ajlun: [-5, -7], Jarash: [11, 9],
}

// Per-governorate centroid in viewBox space, keyed by backend gov id.
const GOV_CENTROID: Record<string, [number, number]> = Object.fromEntries(
  jordanData.features.map(f => [GOV_ID[f.properties.NAME_1], centroid(f.geometry)]),
)
// gov id → English display name (reverse of GOV_ID)
const GOV_NAME: Record<string, string> = Object.fromEntries(
  Object.entries(GOV_ID).map(([en, id]) => [id, en === 'Ma`an' ? "Ma'an" : en]),
)

function relTime(iso: string | null): string {
  if (!iso) return ''
  const ms = new Date(iso).getTime()
  if (Number.isNaN(ms)) return ''
  const s = (Date.now() - ms) / 1000
  if (s < 90) return 'just now'
  if (s < 3600) return `${Math.round(s / 60)}m ago`
  if (s < 86400) return `${Math.round(s / 3600)}h ago`
  return `${Math.round(s / 86400)}d ago`
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

  if (!fetchedRef.current) {
    fetchedRef.current = true
    getGovSignals(govId).then(s => { setSummary(s); setLoading(false) })
  }

  const cd   = CIVIL_DEFENSE[govId] ?? []
  const hosp = HOSPITALS[govId] ?? []
  const displayName = name === "Ma`an" ? "Ma'an" : name

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 6 }}
      transition={{ duration: 0.18, ease: 'easeOut' }}
      className="border-t border-border"
    >
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

      <div className="grid grid-cols-1 gap-0 divide-y divide-border sm:grid-cols-3 sm:divide-x sm:divide-y-0">
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

// ── Live-news popup ─────────────────────────────────────────────────────────
function simulateArticle(gov: string, article: NewsItem, allItems: NewsItem[]) {
  // Build scenario text from the chosen article: title + summary.
  const text = article.summary && article.summary.trim() && article.summary.trim() !== article.title.trim()
    ? `${article.title} — ${clip(article.summary, 200)}`
    : article.title
  sessionStorage.setItem(
    'aegis_scenario_prefill',
    JSON.stringify({ text, location: gov, articles: allItems.slice(0, 20) }),
  )
  window.dispatchEvent(new CustomEvent('aegis:navigate', { detail: 'Simulation' }))
}

function NewsPopup({
  items, govName, gov, side, onClose,
}: { items: NewsItem[]; govName: string; gov: string; side: 'left' | 'right'; onClose: () => void }) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.96, y: 6 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.97, y: 4 }}
      transition={{ duration: 0.16, ease: 'easeOut' }}
      className={`pointer-events-auto absolute top-3 z-30 w-[min(340px,calc(100%-1.5rem))] overflow-hidden rounded-xl border border-border bg-card shadow-2xl shadow-black/50 ${
        side === 'left' ? 'left-3' : 'right-3'
      }`}
    >
      <div className="flex items-center justify-between border-b border-border px-3.5 py-2.5">
        <div className="flex items-center gap-1.5 text-[12px] font-semibold text-txt">
          <Newspaper className="h-3.5 w-3.5 text-blue" />
          {govName}
          <span className="rounded bg-soft px-1.5 py-0.5 font-mono text-[10px] text-faint">
            {items.length}
          </span>
        </div>
        <button
          onClick={onClose}
          className="rounded-lg p-1 text-muted transition-colors hover:bg-soft hover:text-txt"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      {gov && gov !== '__national__' && (
        <div className="border-b border-border/50 bg-soft/30 px-3.5 py-2 text-[10.5px] text-faint">
          Click <FlaskConical className="inline h-3 w-3 text-blue" /> on any article to simulate that scenario
        </div>
      )}

      <ul className="max-h-[340px] divide-y divide-border/60 overflow-y-auto">
        {items.map(n => (
          <li key={n.id} className="group/row relative px-3.5 py-2.5 transition-colors hover:bg-soft/40">
            {/* per-article Simulate button — shown on row hover */}
            {gov && gov !== '__national__' && (
              <button
                onClick={() => simulateArticle(gov, n, items)}
                title="Simulate this scenario"
                className="absolute right-2 top-2.5 flex items-center gap-1 rounded-md border border-blue/40 bg-blue/10 px-1.5 py-0.5 text-[10px] font-medium text-blue opacity-0 transition-opacity group-hover/row:opacity-100 hover:bg-blue/20"
              >
                <FlaskConical className="h-3 w-3" />
                Simulate
              </button>
            )}

            <a
              href={n.link}
              target="_blank"
              rel="noopener noreferrer"
              className="group/link flex items-start gap-1.5 pr-16 text-[12.5px] font-medium leading-snug text-txt transition-colors hover:text-blue"
              dir={isAr(n.title) ? 'rtl' : 'ltr'}
            >
              <span className="flex-1">{n.title}</span>
              <ExternalLink className="mt-0.5 h-3 w-3 shrink-0 text-faint opacity-0 transition-opacity group-hover/link:opacity-100" />
            </a>
            {n.summary && n.summary.trim() !== n.title.trim() && (
              <p
                className="mt-1 text-[11px] leading-relaxed text-muted line-clamp-2"
                dir={isAr(n.summary) ? 'rtl' : 'ltr'}
              >
                {clip(n.summary, 140)}
              </p>
            )}
            <div className="mt-1 flex items-center gap-1.5 text-[10px] text-faint">
              <span className="truncate" dir={isAr(n.source) ? 'rtl' : 'ltr'}>{n.source}</span>
              {n.published && <span>·</span>}
              {n.published && <span className="font-mono">{relTime(n.published)}</span>}
            </div>
          </li>
        ))}
      </ul>
    </motion.div>
  )
}

// ── Map ───────────────────────────────────────────────────────────────────────
export default function JordanMap() {
  const [hovered,  setHovered]  = useState<string | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  // Live viewBox — tweened toward the selected governorate's bbox (drill-down).
  const [vb, setVb] = useState<ViewBox>(FULL_VIEW)
  const vbRef = useRef<ViewBox>(FULL_VIEW)
  const rafRef = useRef<number | undefined>(undefined)
  const [news, setNews] = useState<NewsByGov>({
    generated_at: '', total: 0, by_gov: {}, national: [], source: 'fallback',
  })
  const [openMarker, setOpenMarker] = useState<string | null>(null) // gov id, or '__national__'

  // Poll live news every 60s (backend serves from a 5-min TTL cache).
  useEffect(() => {
    let alive = true
    const load = () => getNews().then(n => { if (alive) setNews(n) })
    load()
    const t = setInterval(load, 60000)
    return () => { alive = false; clearInterval(t) }
  }, [])

  const toggle = (name: string) =>
    setSelected(prev => (prev === name ? null : name))

  // Animate the viewBox from wherever it is now to the new target (the selected
  // governorate, or the full map when nothing is selected) with a rAF tween.
  useEffect(() => {
    const feat = selected
      ? jordanData.features.find(f => f.properties.NAME_1 === selected)
      : undefined
    const target = feat ? fitViewBox(feat.geometry) : FULL_VIEW
    const from = vbRef.current
    const t0 = performance.now()
    const DUR = 480
    if (rafRef.current !== undefined) cancelAnimationFrame(rafRef.current)
    const step = (now: number) => {
      const e = easeOutCubic(Math.min(1, (now - t0) / DUR))
      const next: ViewBox = {
        x: from.x + (target.x - from.x) * e,
        y: from.y + (target.y - from.y) * e,
        w: from.w + (target.w - from.w) * e,
        h: from.h + (target.h - from.h) * e,
      }
      vbRef.current = next
      setVb(next)
      if (e < 1) rafRef.current = requestAnimationFrame(step)
    }
    rafRef.current = requestAnimationFrame(step)
    return () => { if (rafRef.current !== undefined) cancelAnimationFrame(rafRef.current) }
  }, [selected])

  // Zoom factor in user-space (≤1 when drilled in).
  const k = vb.w / W

  const NATIONAL = '__national__'
  const openItems: NewsItem[] =
    openMarker === NATIONAL ? news.national
    : openMarker ? (news.by_gov[openMarker] ?? [])
    : []
  const openName =
    openMarker === NATIONAL ? 'National · Jordan'
    : openMarker ? (GOV_NAME[openMarker] ?? openMarker)
    : ''
  const popupSide: 'left' | 'right' =
    openMarker && openMarker !== NATIONAL && (GOV_CENTROID[openMarker]?.[0] ?? 0) < W / 2
      ? 'right' : 'left'

  return (
    <div className="w-full group relative overflow-hidden rounded-xl border border-border bg-card transition-[border-color,box-shadow] duration-200 hover:border-border/80 hover:shadow-xl hover:shadow-black/20">
      <div className="pointer-events-none absolute inset-x-0 top-0 z-10 h-px bg-gradient-to-r from-blue/60 to-transparent" />

      <div className="flex items-center justify-between border-b border-border px-5 py-3">
        <div className="flex items-center gap-2 text-[13px] font-semibold text-txt">
          Jordan — Governorate Map
          {news.total > 0 && (
            <span className="flex items-center gap-1 rounded-full border border-blue/40 bg-blue/10 px-2 py-0.5 text-[10px] font-medium text-blue">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-blue" />
              {news.total} live
            </span>
          )}
        </div>
        <div className="text-[12px] text-faint">
          {hovered && !selected ? (
            <span className="font-medium text-txt">
              {hovered === "Ma`an" ? "Ma'an" : hovered}
              {GOV_AR[hovered] && (
                <span className="ml-2 text-muted" dir="rtl">{GOV_AR[hovered]}</span>
              )}
            </span>
          ) : selected ? (
            <span className="text-blue">Click again to zoom out</span>
          ) : (
            '12 governorates · click to drill down'
          )}
        </div>
      </div>

      {/* SVG + live-news overlay (own relative box so markers track the SVG,
          not the full card height once the details panel expands below) */}
      <div className="relative">
        <AnimatePresence>
          {selected && (
            <motion.button
              key="zoomout"
              initial={{ opacity: 0, x: -6 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -6 }}
              transition={{ duration: 0.16, ease: 'easeOut' }}
              onClick={() => setSelected(null)}
              className="absolute left-3 top-3 z-20 flex items-center gap-1.5 rounded-lg border border-border bg-card/85 px-2.5 py-1.5 text-[11px] font-medium text-muted backdrop-blur-sm transition-colors hover:border-blue/50 hover:text-txt"
            >
              <ZoomOut className="h-3.5 w-3.5" /> Zoom out
            </motion.button>
          )}
        </AnimatePresence>

        <svg
          viewBox={`${vb.x.toFixed(2)} ${vb.y.toFixed(2)} ${vb.w.toFixed(2)} ${vb.h.toFixed(2)}`}
          className="w-full"
          style={{ display: 'block', background: '#0d0e11' }}
        >
          {[30, 31, 32, 33].map(lat => {
            const [, y] = project(MIN_LON, lat)
            return <line key={`lat${lat}`} x1={0} y1={y} x2={W} y2={y} stroke="#1c1d23" strokeWidth={0.8} vectorEffect="non-scaling-stroke" />
          })}
          {[35, 36, 37, 38, 39].map(lon => {
            const [x] = project(lon, MIN_LAT)
            return <line key={`lon${lon}`} x1={x} y1={0} x2={x} y2={H} stroke="#1c1d23" strokeWidth={0.8} vectorEffect="non-scaling-stroke" />
          })}

          {jordanData.features.map(feature => {
            const name = feature.properties.NAME_1
            const d    = geomToD(feature.geometry)
            const isH  = hovered === name
            const isS  = selected === name
            const dim  = selected !== null && !isS
            const [cx, cy] = centroid(feature.geometry)
            const [ox, oy] = LABEL_OFFSET[name] ?? [0, 0]
            const displayName = name === "Ma`an" ? "Ma'an" : name

            return (
              <g key={name} style={{ opacity: dim ? 0.4 : 1, transition: 'opacity 0.3s ease' }}>
                <path
                  d={d}
                  fill={isS ? '#1d4ed8' : isH ? '#1e40af' : '#1e3a5f'}
                  stroke={isS ? '#93c5fd' : isH ? '#60a5fa' : '#3b82f6'}
                  strokeWidth={isS ? 2 : isH ? 1.6 : 0.8}
                  strokeLinejoin="round"
                  vectorEffect="non-scaling-stroke"
                  style={{ cursor: 'pointer', transition: 'fill 0.14s, stroke 0.14s' }}
                  onMouseEnter={() => setHovered(name)}
                  onMouseLeave={() => setHovered(null)}
                  onClick={() => toggle(name)}
                />
                {isS && (
                  <path d={d} fill="none" stroke="#bfdbfe" strokeWidth={0.5}
                    strokeDasharray="4 3" vectorEffect="non-scaling-stroke"
                    style={{ pointerEvents: 'none' }} />
                )}
                <text
                  x={cx + ox} y={cy + oy}
                  textAnchor="middle" dominantBaseline="middle"
                  fontSize={(name === 'Mafraq' || name === "Ma`an" ? 14 : 11.5) * k}
                  fontFamily="system-ui, sans-serif"
                  fill={isS ? '#dbeafe' : isH ? '#bfdbfe' : '#93c5fd'}
                  fontWeight={isS || isH ? 600 : 400}
                  style={{ pointerEvents: 'none', userSelect: 'none', transition: 'fill 0.14s' }}
                >
                  {displayName}
                </text>
              </g>
            )
          })}
        </svg>

        {/* live-news marker overlay — inside the relative wrapper so absolute
            positioning is relative to the SVG area, not the full card */}
        <div className="pointer-events-none absolute inset-0 z-20">
          {Object.entries(news.by_gov).map(([gov, items]) => {
            if (!items || items.length === 0) return null
            const c = GOV_CENTROID[gov]
            if (!c) return null
            const [cx, cy] = c
            // Adjust for current zoom: map viewBox coords → container %.
            const screenX = ((cx - vb.x) / vb.w) * 100
            const screenY = ((cy - vb.y) / vb.h) * 100
            // Hide markers scrolled outside the current viewBox.
            if (screenX < -5 || screenX > 105 || screenY < -5 || screenY > 105) return null
            const isOpen = openMarker === gov
            return (
              <button
                key={gov}
                onClick={e => { e.stopPropagation(); setOpenMarker(p => (p === gov ? null : gov)) }}
                onMouseEnter={() => setHovered(null)}
                title={`${GOV_NAME[gov] ?? gov} — ${items.length} news`}
                className="pointer-events-auto absolute flex -translate-x-1/2 -translate-y-1/2 items-center gap-1 rounded-full border px-1.5 py-1 font-mono text-[10px] font-semibold shadow-lg transition-transform hover:scale-110"
                style={{
                  left: `${screenX}%`,
                  top: `${screenY}%`,
                  background: isOpen ? '#3b82f6' : 'rgba(59,130,246,0.92)',
                  borderColor: isOpen ? '#dbeafe' : '#93c5fd',
                  color: '#fff',
                }}
              >
                <Newspaper className="h-3 w-3" />
                {items.length}
              </button>
            )
          })}

          {/* national pill — always bottom-left */}
          {news.national.length > 0 && (
            <button
              onClick={e => { e.stopPropagation(); setOpenMarker(p => (p === NATIONAL ? null : NATIONAL)) }}
              className="pointer-events-auto absolute bottom-8 left-3 flex items-center gap-1.5 rounded-full border border-blue/50 bg-card/90 px-2.5 py-1 text-[11px] font-medium text-blue shadow-lg backdrop-blur transition-colors hover:bg-soft"
            >
              <Newspaper className="h-3.5 w-3.5" />
              National · {news.national.length}
            </button>
          )}

          {/* popup */}
          <AnimatePresence>
            {openMarker && openItems.length > 0 && (
              <NewsPopup
                key={openMarker}
                items={openItems}
                govName={openName}
                gov={openMarker}
                side={popupSide}
                onClose={() => setOpenMarker(null)}
              />
            )}
          </AnimatePresence>
        </div>
      </div>

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