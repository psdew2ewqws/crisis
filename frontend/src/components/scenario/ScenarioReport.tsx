// ScenarioReport — a full WRITTEN crisis report (rich Arabic prose), captured to a
// downloadable PDF. Two sibling elements so the PDF places references on their OWN page:
//   #aegis-report           — masthead, key-figures box, and the written narrative sections
//   #aegis-references-page  — the references appendix (separate PDF page)
// Light theme, RTL, explicit hex colors (html2canvas-safe). Narrative comes from the
// deterministic backend report_writer (works with Ollama down); falls back to a compact
// summary if the doc has not loaded.

import type { ScenarioDetection, ScenarioPrediction, ScenarioConfidence, ScenarioEvent, ScenarioReportDoc } from '../../lib/voc'

export interface ReportData {
  text: string
  domain?: string
  location?: string
  service?: string
  engine?: string | null
  generatedAt: string
  detection?: ScenarioDetection
  prediction?: ScenarioPrediction
  confidence?: ScenarioConfidence
  flagsAr: string[]
  sim: ScenarioEvent | null
}

const C = {
  ink: '#111418', sub: '#5b6470', faint: '#8a929c', line: '#e3e6ea', bg: '#ffffff',
  panel: '#f6f7f9', blue: '#1f6feb', good: '#16794a', warn: '#9a6700', danger: '#b42318',
}
const PAGE: React.CSSProperties = {
  width: 820, background: C.bg, color: C.ink, padding: '34px 40px', boxSizing: 'border-box',
  fontFamily: '"Segoe UI", system-ui, "Helvetica Neue", Arial, sans-serif', lineHeight: 1.7,
}

function Masthead({ data, doc }: { data: ReportData; doc: ScenarioReportDoc | null }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end',
      borderBottom: `3px solid ${C.blue}`, paddingBottom: 12 }}>
      <div>
        <div style={{ fontSize: 21, fontWeight: 800 }}>AEGIS · {doc?.meta?.title_ar || 'تقرير المحاكاة'}</div>
        <div style={{ fontSize: 12.5, color: C.sub }}>خلية إدارة أزمات الشرق الأوسط — تقرير دعم قرار</div>
        {doc?.meta?.report_no && <div style={{ fontSize: 11.5, color: C.faint, marginTop: 2 }}>{doc.meta.report_no}</div>}
      </div>
      <div style={{ fontSize: 11, color: C.faint, textAlign: 'left' }}>صدر في<br />{doc?.meta?.generated_at || data.generatedAt}</div>
    </div>
  )
}

export default function ScenarioReport({ data, doc }: { data: ReportData; doc: ScenarioReportDoc | null }) {
  const kf = doc?.key_figures || []
  const sections = doc?.sections || []
  const refs = doc?.references

  return (
    <>
      {/* ---- page 1+: masthead + key figures + written narrative ---- */}
      <div id="aegis-report" dir="rtl" style={PAGE}>
        <Masthead data={data} doc={doc} />

        <div style={{ marginTop: 16, fontSize: 13.5 }}>
          <span style={{ color: C.sub }}>الموقف المُحاكى: </span>
          <span style={{ fontWeight: 600 }}>{doc?.meta?.scenario || data.text}</span>
        </div>

        {/* key figures box */}
        {kf.length > 0 && (
          <div style={{ marginTop: 16 }}>
            <h2 style={{ fontSize: 14, fontWeight: 700, margin: '0 0 8px' }}>صندوق الأرقام الرئيسية</h2>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12.5 }}>
              <tbody>
                {kf.map((r, i) => (
                  <tr key={i} style={{ borderBottom: `1px solid ${C.line}` }}>
                    <td style={{ padding: '6px 4px', color: C.sub, width: '42%' }}>{r.label}</td>
                    <td style={{ padding: '6px 4px', fontWeight: 700 }}>{r.value}</td>
                    <td style={{ padding: '6px 4px', color: C.faint, fontSize: 11, textAlign: 'left' }}>{r.source}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* written narrative */}
        {sections.length > 0 ? (
          sections.map((s, i) => (
            <div key={i} style={{ marginTop: 20 }}>
              <h2 style={{ fontSize: 15, fontWeight: 700, margin: '0 0 6px', borderBottom: `1px solid ${C.line}`, paddingBottom: 5 }}>
                {s.title_ar} <span style={{ fontSize: 10, color: C.faint, letterSpacing: 0.5 }}>· {s.title_en}</span>
              </h2>
              {s.paragraphs.map((p, j) => (
                <p key={j} style={{ margin: '0 0 10px', fontSize: 13, textAlign: 'justify' }}>{p}</p>
              ))}
            </div>
          ))
        ) : (
          // fallback: compact summary if the narrative hasn't loaded
          <div style={{ marginTop: 18, fontSize: 13, color: C.sub }}>
            {data.detection && (
              <p>الوضع: {data.detection.is_crisis ? 'أزمة قائمة' : 'تحت المراقبة'} · الشدّة {data.detection.severity_ar} ·{' '}
                {data.detection.escalating ? 'تصاعد متوقّع' : 'استقرار'}.</p>
            )}
            {data.confidence && <p>مستوى الثقة: {data.confidence.band_ar}.</p>}
            <p style={{ color: C.faint }}>جارٍ تجهيز التقرير المكتوب…</p>
          </div>
        )}

        <div style={{ marginTop: 18, borderTop: `1px solid ${C.line}`, paddingTop: 8, fontSize: 10.5, color: C.faint, textAlign: 'center' }}>
          AEGIS Crisis Console · {doc?.meta?.generated_at || data.generatedAt} · للتخطيط ودعم القرار فقط — لا توقّع للواقع
        </div>
      </div>

      {/* ---- separate page: references appendix ---- */}
      {refs && (refs.peer_reviewed.length > 0 || refs.institutional.length > 0) && (
        <div id="aegis-references-page" dir="rtl" style={{ ...PAGE, marginTop: 18 }}>
          <div style={{ borderBottom: `3px solid ${C.blue}`, paddingBottom: 10, marginBottom: 14 }}>
            <div style={{ fontSize: 18, fontWeight: 800 }}>ملحق المراجع</div>
            <div style={{ fontSize: 12, color: C.faint }}>References — {refs.count} مصدرًا موثّقًا · كلّ رقم في التقرير يتتبّع إلى مصدره</div>
          </div>

          {refs.peer_reviewed.length > 0 && (
            <div>
              <h3 style={{ fontSize: 13.5, fontWeight: 700, margin: '0 0 6px' }}>أ. الدوريّات المحكّمة</h3>
              <ol style={{ margin: 0, paddingInlineStart: 20, fontSize: 12.5 }}>
                {refs.peer_reviewed.map((r, i) => (
                  <li key={i} style={{ marginBottom: 6 }}>
                    {r.title} {r.year ? `(${r.year})` : ''} {r.oa ? `· OA: ${r.oa}` : ''}
                    {r.doi ? <span style={{ color: C.blue }}> · doi:{r.doi}</span> : null}
                  </li>
                ))}
              </ol>
            </div>
          )}

          {refs.institutional.length > 0 && (
            <div style={{ marginTop: 14 }}>
              <h3 style={{ fontSize: 13.5, fontWeight: 700, margin: '0 0 6px' }}>ب. المصادر المؤسسية الأوّلية</h3>
              <ol style={{ margin: 0, paddingInlineStart: 20, fontSize: 12.5 }}>
                {refs.institutional.map((r, i) => (
                  <li key={i} style={{ marginBottom: 6 }}>
                    {r.name} — <span style={{ color: C.blue, wordBreak: 'break-all' }}>{r.url}</span>
                  </li>
                ))}
              </ol>
            </div>
          )}
        </div>
      )}
    </>
  )
}
