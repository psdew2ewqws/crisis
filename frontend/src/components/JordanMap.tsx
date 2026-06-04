import { useState } from 'react'
import jordanData from '../lib/jordan-geojson'

/*
 * SVG Jordan governorate map — equirectangular projection with cos(lat)
 * correction so shapes look geographically natural.
 *
 * Bounding box has padding so borders never clip at the edge.
 * The outer wrapper is capped at max-width 640px so the card height
 * stays proportional on wide dashboard layouts.
 */

const MIN_LON = 34.75, MAX_LON = 39.55   // 4.8° lon span
const MIN_LAT = 28.95, MAX_LAT = 33.60   // 4.65° lat span

// Longitude is compressed by cos(centre lat) for geographic accuracy
const COS_LAT = Math.cos((31.3 * Math.PI) / 180) // ≈ 0.856

const W = 860
// Correct height: H/W = (lat_span) / (lon_span * cos_lat)
const H = Math.round(W * ((MAX_LAT - MIN_LAT) / ((MAX_LON - MIN_LON) * COS_LAT)))

function project(lon: number, lat: number): [number, number] {
  const x = ((lon - MIN_LON) / (MAX_LON - MIN_LON)) * W
  // Y is inverted in SVG; longitude is compressed by cos(lat) so shapes look right
  const y = ((MAX_LAT - lat) / (MAX_LAT - MIN_LAT)) * H
  return [x, y]
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
    return (geom.coordinates as number[][][][])
      .flatMap((p) => p.map(ringToD)).join(' ')
  return ''
}

function centroid(geom: { type: string; coordinates: unknown }): [number, number] {
  const ring: number[][] =
    geom.type === 'Polygon'
      ? (geom.coordinates as number[][][])[0]
      : (geom.coordinates as number[][][][])[0][0]
  const n = ring.length
  const lon = ring.reduce((s, c) => s + c[0], 0) / n
  const lat = ring.reduce((s, c) => s + c[1], 0) / n
  return project(lon, lat)
}

const GOV_AR: Record<string, string> = {
  Irbid: 'إربد', Madaba: 'مادبا', Karak: 'الكرك', Tafilah: 'الطفيلة',
  Aqaba: 'العقبة', Balqa: 'البلقاء', Mafraq: 'المفرق', 'Ma`an': 'معان',
  Amman: 'عمان', Zarqa: 'الزرقاء', Ajlun: 'عجلون', Jarash: 'جرش',
}
// Govs too small to label clearly at this scale
const SKIP_LABEL = new Set(['Ajlun', 'Jarash', 'Madaba', 'Tafilah'])

// Nudge labels off the auto-centroid for crowded govs
const LABEL_OFFSET: Record<string, [number, number]> = {
  Amman:  [0,  -12],
  Zarqa:  [0,  -10],
  Aqaba:  [0,   10],
}

export default function JordanMap() {
  const [hovered, setHovered] = useState<string | null>(null)

  return (
    // max-w-[640px] keeps the card at a natural height on wide screens
    <div className="mx-auto w-full max-w-[640px] group relative overflow-hidden rounded-xl border border-border bg-card transition-[border-color,box-shadow] duration-200 hover:border-border/80 hover:shadow-xl hover:shadow-black/20">
      {/* accent hairline */}
      <div className="pointer-events-none absolute inset-x-0 top-0 z-10 h-px bg-gradient-to-r from-blue/60 to-transparent" />

      {/* header */}
      <div className="flex items-center justify-between border-b border-border px-5 py-3">
        <div className="text-[13px] font-semibold text-txt">Jordan — Governorate Map</div>
        <div className="min-w-0 text-right text-[12px] text-faint">
          {hovered ? (
            <span className="font-medium text-txt">
              {hovered === "Ma\`an" ? "Ma'an" : hovered}
              {GOV_AR[hovered] && (
                <span className="ml-2 text-muted" dir="rtl">{GOV_AR[hovered]}</span>
              )}
            </span>
          ) : (
            '12 governorates · hover to explore'
          )}
        </div>
      </div>

      {/* SVG map — fills card width, height auto-follows viewBox ratio */}
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        style={{ display: 'block', background: '#0d0e11' }}
      >
        {/* subtle graticule */}
        {[30, 31, 32, 33].map((lat) => {
          const [, y] = project(MIN_LON, lat)
          return <line key={`lat${lat}`} x1={0} y1={y} x2={W} y2={y} stroke="#1c1d23" strokeWidth={0.8} />
        })}
        {[35, 36, 37, 38, 39].map((lon) => {
          const [x] = project(lon, MIN_LAT)
          return <line key={`lon${lon}`} x1={x} y1={0} x2={x} y2={H} stroke="#1c1d23" strokeWidth={0.8} />
        })}

        {/* governorate polygons */}
        {jordanData.features.map((feature) => {
          const name = feature.properties.NAME_1
          const d = geomToD(feature.geometry)
          const on = hovered === name
          const [cx, cy] = centroid(feature.geometry)
          const [ox, oy] = LABEL_OFFSET[name] ?? [0, 0]
          const displayName = name === "Ma\`an" ? "Ma'an" : name

          return (
            <g key={name}>
              <path
                d={d}
                fill={on ? '#1d4ed8' : '#1e3a5f'}
                stroke={on ? '#93c5fd' : '#3b82f6'}
                strokeWidth={on ? 1.6 : 0.8}
                strokeLinejoin="round"
                style={{ cursor: 'pointer', transition: 'fill 0.14s, stroke 0.14s, stroke-width 0.14s' }}
                onMouseEnter={() => setHovered(name)}
                onMouseLeave={() => setHovered(null)}
              />
              {!SKIP_LABEL.has(name) && (
                <text
                  x={cx + ox} y={cy + oy}
                  textAnchor="middle" dominantBaseline="middle"
                  fontSize={name === 'Mafraq' || name === "Ma\`an" ? 14 : 11.5}
                  fontFamily="system-ui, sans-serif"
                  fill={on ? '#dbeafe' : '#93c5fd'}
                  fontWeight={on ? 600 : 400}
                  style={{ pointerEvents: 'none', userSelect: 'none', transition: 'fill 0.14s' }}
                >
                  {displayName}
                </text>
              )}
            </g>
          )
        })}
      </svg>

      {/* footer */}
      <div className="border-t border-border px-4 py-2 text-right font-mono text-[10px] text-faint">
        boundaries · Apache Superset / GADM · WGS84
      </div>
    </div>
  )
}
