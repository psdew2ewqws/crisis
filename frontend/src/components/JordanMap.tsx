import 'leaflet/dist/leaflet.css'
import { useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import { MapContainer, TileLayer, GeoJSON as LeafletGeoJSON, CircleMarker, Tooltip } from 'react-leaflet'
import { X, Building2, Hospital, AlertTriangle, Loader2 } from 'lucide-react'
import { motion, AnimatePresence } from 'motion/react'
import { GOVERNORATES, CIVIL_DEFENSE, HOSPITALS, type Governorate } from '../lib/jordan-geo'
import { getGovSignals, type GovSummary } from '../lib/voc2'

// Fix Leaflet's bundler icon path issue by not using image markers.
delete (L.Icon.Default.prototype as unknown as Record<string, unknown>)._getIconUrl

const SEVERITY_ORDER = ['critical', 'high', 'medium', 'low', 'unknown']

const sevColor: Record<string, string> = {
  critical: '#F04359',
  high:     '#F97316',
  medium:   '#FBBF24',
  low:      '#34D399',
  unknown:  '#62646D',
}

function fillForTotal(total: number): string {
  if (total >= 50) return '#F04359'
  if (total >= 20) return '#F97316'
  if (total >= 5)  return '#FBBF24'
  if (total >= 1)  return '#3B82F6'
  return '#212228'
}

function toGeoJSON(gov: Governorate) {
  return {
    type: 'Feature' as const,
    properties: { id: gov.id },
    geometry: {
      type: 'MultiPolygon' as const,
      coordinates: gov.polygon.map((ring) => [ring]),
    },
  }
}

const isAr = (s: string | null | undefined) => !!s && /[؀-ۿ]/.test(s)
const clip = (s: string | null | undefined, n = 80) =>
  !s ? '—' : s.length > n ? s.slice(0, n) + '…' : s

function SeverityBadge({ sev }: { sev: string | null }) {
  const color = sevColor[sev ?? 'unknown'] ?? sevColor.unknown
  return (
    <span className="inline-flex items-center gap-1 text-[11px]" style={{ color }}>
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: color }} />
      {sev ?? 'unknown'}
    </span>
  )
}

interface PanelProps {
  gov: Governorate
  summary: GovSummary | null
  loading: boolean
  onClose: () => void
}

function GovernoratePanel({ gov, summary, loading, onClose }: PanelProps) {
  const cd = CIVIL_DEFENSE[gov.id] ?? []
  const hospitals = HOSPITALS[gov.id] ?? []

  return (
    <motion.div
      initial={{ x: 320, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: 320, opacity: 0 }}
      transition={{ duration: 0.22, ease: 'easeOut' }}
      className="absolute right-0 top-0 z-[1000] flex h-full w-[320px] flex-col overflow-hidden rounded-r-xl border-l border-border bg-card shadow-2xl shadow-black/40"
    >
      {/* header */}
      <div className="relative flex items-center justify-between border-b border-border px-4 py-3.5">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-blue/70 to-transparent" />
        <div>
          <div className="text-[15px] font-semibold text-txt">{gov.name}</div>
          <div className="text-[12px] text-muted" dir="rtl">{gov.name_ar}</div>
        </div>
        <button
          onClick={onClose}
          className="rounded-lg p-1.5 text-muted transition-colors hover:bg-soft hover:text-txt"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto">
        {/* issues from DB */}
        <div className="border-b border-border px-4 py-3">
          <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-faint">
            <AlertTriangle className="h-3.5 w-3.5" />
            Issues &amp; Crises
          </div>

          {loading && (
            <div className="mt-3 flex items-center gap-2 text-[12px] text-muted">
              <Loader2 className="h-3.5 w-3.5 animate-spin text-blue" />
              Loading…
            </div>
          )}

          {!loading && summary && summary.total === 0 && (
            <p className="mt-2 text-[12px] text-faint">No recorded issues for this governorate.</p>
          )}

          {!loading && summary && summary.total > 0 && (
            <>
              {/* severity breakdown */}
              <div className="mt-3 flex flex-wrap gap-2">
                {SEVERITY_ORDER.filter((s) => summary.by_severity[s]).map((s) => (
                  <span
                    key={s}
                    className="rounded-md px-2 py-0.5 text-[11px] font-medium"
                    style={{ background: sevColor[s] + '20', color: sevColor[s] }}
                  >
                    {s}: {summary.by_severity[s]}
                  </span>
                ))}
                <span className="ml-auto text-[11px] text-faint">{summary.total} total</span>
              </div>

              {/* recent signals */}
              <div className="mt-3 space-y-2">
                {summary.signals.map((sig, i) => {
                  const txt = sig.text_clean || sig.text
                  return (
                    <div key={sig.record_id ?? i} className="rounded-lg border border-border/60 bg-soft/50 px-3 py-2">
                      <div className="flex items-center justify-between gap-2">
                        {sig.service_id && (
                          <span className="font-mono text-[10px] text-faint">{sig.service_id}</span>
                        )}
                        <SeverityBadge sev={sig.severity} />
                      </div>
                      <p
                        className="mt-1 text-[12px] leading-relaxed text-txt"
                        dir={isAr(txt) ? 'rtl' : 'ltr'}
                      >
                        {clip(txt)}
                      </p>
                    </div>
                  )
                })}
              </div>
            </>
          )}
        </div>

        {/* civil defense */}
        <div className="border-b border-border px-4 py-3">
          <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-faint">
            <Building2 className="h-3.5 w-3.5" />
            Civil Defense Centers
          </div>
          {cd.length === 0 ? (
            <p className="mt-2 text-[12px] text-faint">No data.</p>
          ) : (
            <ul className="mt-2 space-y-1.5">
              {cd.map((f) => (
                <li key={f.name} className="flex items-start gap-2">
                  <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-blue" />
                  <div>
                    <div className="text-[12.5px] text-txt">{f.name}</div>
                    <div className="font-mono text-[10px] text-faint">
                      {f.lat.toFixed(3)}°N {f.lng.toFixed(3)}°E
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* hospitals */}
        <div className="px-4 py-3">
          <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-faint">
            <Hospital className="h-3.5 w-3.5" />
            Hospitals
          </div>
          {hospitals.length === 0 ? (
            <p className="mt-2 text-[12px] text-faint">No data.</p>
          ) : (
            <ul className="mt-2 space-y-1.5">
              {hospitals.map((h) => (
                <li key={h.name} className="flex items-start gap-2">
                  <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-good" />
                  <div>
                    <div className="text-[12.5px] text-txt">{h.name}</div>
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

export default function JordanMap() {
  const [selected, setSelected] = useState<Governorate | null>(null)
  const [summary, setSummary] = useState<GovSummary | null>(null)
  const [loading, setLoading] = useState(false)
  const [totals, setTotals] = useState<Record<string, number>>({})
  const abortRef = useRef<AbortController | null>(null)

  // Preload totals for all governorates to colour the choropleth.
  useEffect(() => {
    let alive = true
    Promise.all(
      GOVERNORATES.map((g) =>
        getGovSignals(g.id).then((s) => [g.id, s.total] as [string, number]),
      ),
    ).then((pairs) => {
      if (!alive) return
      setTotals(Object.fromEntries(pairs))
    })
    return () => { alive = false }
  }, [])

  const selectGov = (gov: Governorate) => {
    if (selected?.id === gov.id) { setSelected(null); return }
    abortRef.current?.abort()
    setSelected(gov)
    setSummary(null)
    setLoading(true)
    const ac = new AbortController()
    abortRef.current = ac
    getGovSignals(gov.id).then((s) => {
      if (ac.signal.aborted) return
      setSummary(s)
      setLoading(false)
    })
  }

  return (
    <div className="group relative overflow-hidden rounded-xl border border-border bg-card transition-[border-color,box-shadow] duration-200 hover:border-border/80 hover:shadow-xl hover:shadow-black/20">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-blue/60 to-transparent" />

      {/* card header */}
      <div className="flex items-center justify-between border-b border-border px-5 py-3">
        <div className="text-[13px] font-semibold text-txt">Jordan — Governorate Map</div>
        <div className="flex items-center gap-4 text-[11px] text-faint">
          {[
            { label: '50+ signals', color: '#F04359' },
            { label: '20-49', color: '#F97316' },
            { label: '5-19', color: '#FBBF24' },
            { label: '1-4', color: '#3B82F6' },
            { label: 'No data', color: '#212228' },
          ].map((l) => (
            <span key={l.label} className="flex items-center gap-1">
              <span className="h-2.5 w-2.5 rounded-sm border border-border/60" style={{ background: l.color }} />
              {l.label}
            </span>
          ))}
        </div>
      </div>

      {/* map + panel wrapper */}
      <div className="relative h-[480px]">
        <MapContainer
          center={[31.24, 36.51]}
          zoom={7}
          minZoom={6}
          maxZoom={10}
          style={{ height: '100%', width: '100%', background: '#0A0A0B' }}
          zoomControl={true}
          attributionControl={false}
        >
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
            attribution='&copy; <a href="https://carto.com/">CARTO</a>'
          />

          {GOVERNORATES.map((gov) => {
            const total = totals[gov.id] ?? 0
            const fill = fillForTotal(total)
            const isActive = selected?.id === gov.id

            return (
              <LeafletGeoJSON
                key={gov.id}
                data={toGeoJSON(gov)}
                style={() => ({
                  fillColor: fill,
                  fillOpacity: isActive ? 0.65 : 0.35,
                  color: isActive ? '#60A5FA' : '#3B82F6',
                  weight: isActive ? 2 : 0.8,
                  opacity: 0.9,
                })}
                eventHandlers={{
                  click: () => selectGov(gov),
                  mouseover: (e) => { e.target.setStyle({ fillOpacity: 0.6, weight: 1.5 }) },
                  mouseout: (e) => { e.target.setStyle({ fillOpacity: isActive ? 0.65 : 0.35, weight: isActive ? 2 : 0.8 }) },
                }}
              >
                <Tooltip sticky direction="top" offset={[0, -4]}>
                  <div className="font-sans text-[13px] font-semibold">{gov.name}</div>
                  <div className="text-[11px] text-gray-400">
                    {total > 0 ? `${total} signal${total !== 1 ? 's' : ''}` : 'No data'}
                  </div>
                </Tooltip>
              </LeafletGeoJSON>
            )
          })}

          {/* Civil defense markers (blue) — shown when a governorate is selected */}
          {selected && (CIVIL_DEFENSE[selected.id] ?? []).map((f) => (
            <CircleMarker
              key={f.name}
              center={[f.lat, f.lng]}
              radius={6}
              pathOptions={{ color: '#3B82F6', fillColor: '#3B82F6', fillOpacity: 0.9, weight: 2 }}
            >
              <Tooltip direction="top" offset={[0, -8]}>
                <div className="text-[12px] font-semibold">🚒 {f.name}</div>
                <div className="text-[10px] text-gray-400">Civil Defense</div>
              </Tooltip>
            </CircleMarker>
          ))}

          {/* Hospital markers (green) — shown when a governorate is selected */}
          {selected && (HOSPITALS[selected.id] ?? []).map((h) => (
            <CircleMarker
              key={h.name}
              center={[h.lat, h.lng]}
              radius={6}
              pathOptions={{ color: '#34D399', fillColor: '#34D399', fillOpacity: 0.9, weight: 2 }}
            >
              <Tooltip direction="top" offset={[0, -8]}>
                <div className="text-[12px] font-semibold">🏥 {h.name}</div>
                <div className="text-[10px] text-gray-400">Hospital</div>
              </Tooltip>
            </CircleMarker>
          ))}
        </MapContainer>

        {/* side panel */}
        <AnimatePresence>
          {selected && (
            <GovernoratePanel
              gov={selected}
              summary={summary}
              loading={loading}
              onClose={() => setSelected(null)}
            />
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}
