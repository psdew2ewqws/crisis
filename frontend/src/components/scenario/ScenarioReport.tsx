// ScenarioReport — a full, print/PDF-clean report of a scenario run. Light theme, RTL,
// explicit hex colors (so html2canvas captures it reliably). Rendered inside the report
// modal and captured to a downloadable PDF. Pure layout from the accumulated run state.

import type {
  ScenarioDetection, ScenarioPrediction, ScenarioConfidence, ScenarioEvent,
  ScenarioSolutionEval, ScenarioEvidence, ScenarioReference,
} from '../../lib/voc'

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
  solutionEval: ScenarioSolutionEval | null
  evidence: ScenarioEvidence[]
}

const C = {
  ink: '#111418', sub: '#5b6470', faint: '#8a929c', line: '#e3e6ea', bg: '#ffffff',
  panel: '#f6f7f9', blue: '#1f6feb', good: '#16794a', warn: '#9a6700', danger: '#b42318',
}
const sevColor = (s?: string) => (s === 'critical' ? C.danger : s === 'elevated' ? C.warn : C.good)

function Section({ title, en, children }: { title: string; en?: string; children: React.ReactNode }) {
  return (
    <div style={{ marginTop: 22 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, borderBottom: `1px solid ${C.line}`, paddingBottom: 6, marginBottom: 10 }}>
        <h2 style={{ margin: 0, fontSize: 15, fontWeight: 700, color: C.ink }}>{title}</h2>
        {en && <span style={{ fontSize: 10, letterSpacing: 1, color: C.faint, textTransform: 'uppercase' }}>{en}</span>}
      </div>
      {children}
    </div>
  )
}

function Row({ k, v, color }: { k: string; v: React.ReactNode; color?: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', fontSize: 13 }}>
      <span style={{ color: C.sub }}>{k}</span>
      <span style={{ color: color || C.ink, fontWeight: 600, textAlign: 'left' }}>{v}</span>
    </div>
  )
}

function Bar({ label, pct }: { label: string; pct: number }) {
  const col = pct >= 70 ? C.danger : pct >= 42 ? C.warn : C.good
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 3 }}>
        <span style={{ color: C.sub }}>{label}</span>
        <span style={{ color: col, fontWeight: 700 }}>{pct}%</span>
      </div>
      <div style={{ height: 7, background: C.panel, borderRadius: 4, overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${pct}%`, background: col, borderRadius: 4 }} />
      </div>
    </div>
  )
}

export default function ScenarioReport({ data }: { data: ReportData }) {
  const d = data.detection
  const p = data.prediction
  const c = data.confidence
  const sim = data.sim
  const sectors = (sim?.sectors_after || {}) as Record<string, number>
  const mc = sim?.montecarlo
  const sectorAr: Record<string, string> = {
    water_supply: 'إمداد المياه', agriculture: 'الزراعة', groundwater: 'المياه الجوفية', social: 'التوتر الاجتماعي',
  }
  const w = p?.which_intervention_worked
  const refs: ScenarioReference[] = (sim?.references || []) as ScenarioReference[]

  return (
    <div
      id="aegis-report"
      dir="rtl"
      style={{ width: 820, background: C.bg, color: C.ink, padding: '34px 40px', boxSizing: 'border-box',
        fontFamily: '"Segoe UI", system-ui, "Helvetica Neue", Arial, sans-serif', lineHeight: 1.55 }}
    >
      {/* header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end',
        borderBottom: `3px solid ${C.blue}`, paddingBottom: 12 }}>
        <div>
          <div style={{ fontSize: 22, fontWeight: 800, letterSpacing: 0.5 }}>AEGIS · تقرير المحاكاة</div>
          <div style={{ fontSize: 12.5, color: C.sub }}>منصّة إدارة الأزمات — تقرير دعم قرار</div>
        </div>
        <div style={{ fontSize: 11, color: C.faint, textAlign: 'left' }}>
          صدر في<br />{data.generatedAt}
        </div>
      </div>

      {/* scenario */}
      <Section title="الموقف" en="Scenario">
        <p style={{ margin: '0 0 6px', fontSize: 13.5 }}>{data.text}</p>
        <div style={{ fontSize: 12, color: C.faint }}>
          المجال: {data.domain || '—'}
          {data.location ? ` · الموقع: ${data.location}` : ''}
          {data.service ? ` · الخدمة: ${data.service}` : ''}
          {data.engine ? ` · المحرّك: ${data.engine}` : ''}
        </div>
      </Section>

      {/* executive summary */}
      {d && p && c && (
        <Section title="الخلاصة التنفيذية" en="Executive summary">
          <div style={{ padding: 12, background: C.panel, borderRight: `4px solid ${sevColor(d.severity)}`, borderRadius: 6 }}>
            <div style={{ fontSize: 16, fontWeight: 700, color: sevColor(d.severity) }}>
              {d.is_crisis ? 'أزمة قائمة' : 'وضع تحت المراقبة'} · الشدّة {d.severity_ar}
            </div>
            <ul style={{ margin: '8px 0 0', paddingInlineStart: 18, fontSize: 13 }}>
              <li>{d.escalating ? 'الاتجاه: تصاعد متوقّع — يتطلّب تحرّكًا عاجلًا.' : 'الاتجاه: مستقر، دون تصاعد متوقّع.'}</li>
              {p.likely_outcome_ar && <li>النتيجة الأرجح: {p.likely_outcome_ar}.</li>}
              {w && <li>أفضل تدخّل تاريخيًّا: «{w.intervention}»{typeof w.risk_reduction === 'number' ? ` (خفض الخطر بنحو ${Math.abs(w.risk_reduction).toFixed(0)} نقطة).` : '.'}</li>}
              <li>مستوى الثقة: {c.band_ar}.</li>
            </ul>
          </div>
        </Section>
      )}

      {/* detection + prediction */}
      {d && p && (
        <Section title="التشخيص والتنبؤ" en="Detection & prediction">
          <Row k="أزمة قائمة؟" v={d.is_crisis ? 'نعم' : 'لا'} color={d.is_crisis ? C.danger : C.good} />
          <Row k="الشدّة" v={d.severity_ar} color={sevColor(d.severity)} />
          <Row k="الاتجاه" v={d.escalating ? 'تصاعد' : 'استقرار'} color={d.escalating ? C.danger : C.good} />
          {p.likely_outcome_ar && <Row k="النتيجة المرجّحة" v={p.likely_outcome_ar} />}
          {p.risk_trajectory && (
            <Row k="مسار الخطر" v={`${p.risk_trajectory.risk_before ?? '—'} ← ${p.risk_trajectory.risk_after ?? '—'} (انخفاض ${p.risk_trajectory.risk_reduction ?? '—'})`} />
          )}
          {p.avoid && p.avoid.length > 0 && (
            <div style={{ marginTop: 8, fontSize: 12.5, color: C.warn }}>
              تجنّب: {p.avoid.map((a) => a.warning).join(' · ')}
            </div>
          )}
        </Section>
      )}

      {/* cascade study (drought) */}
      {sim?.engine === 'cascade' && (
        <Section title="دراسة متعددة القطاعات" en="Multi-sector cascade study">
          <div style={{ fontSize: 12, color: C.faint, marginBottom: 8 }}>{sim.label || 'استكشاف سيناريو منظَّم — وليس تنبؤًا مُعايرًا'}</div>
          {Object.keys(sectors).map((k) => (
            <Bar key={k} label={sectorAr[k] ?? k} pct={Math.round((sectors[k] || 0) * 100)} />
          ))}
          {mc?.available && (
            <Row k="نطاق عدم اليقين (مونت كارلو)" v={`P10 ${mc.p10} · P50 ${mc.p50} · P90 ${mc.p90}`} />
          )}
          {sim.non_mitigating && sim.non_mitigating.length > 0 && (
            <div style={{ marginTop: 8, fontSize: 12.5, color: C.warn }}>لا يخفّف الأزمة خلال السنة: {sim.non_mitigating.join('، ')}.</div>
          )}
        </Section>
      )}

      {/* confidence + notes */}
      {c && (
        <Section title="الثقة والملاحظات" en="Confidence & caveats">
          <Row k="مستوى الثقة" v={`${c.band_ar} (${c.score})`} />
          <Row k="متوسط الصِلة" v={`${(c.breakdown.mean_relevance * 100).toFixed(0)}%`} />
          <Row k="توافق النتائج" v={`${(c.breakdown.outcome_agreement * 100).toFixed(0)}%`} />
          <Row k="عدد السوابق" v={c.breakdown.distinct_precedents} />
          {data.flagsAr.length > 0 && (
            <div style={{ marginTop: 8, fontSize: 12, color: C.faint }}>ملاحظات: {data.flagsAr.join(' · ')}</div>
          )}
        </Section>
      )}

      {/* solution evaluation */}
      {data.solutionEval && (
        <Section title="تقييم الحل المقترح" en="Solution evaluation">
          <Row k="التوافق" v={data.solutionEval.alignment_ar} />
          <Row k="درجة التطابق مع ما نجح" v={`${(data.solutionEval.alignment_score * 100).toFixed(0)}%`} />
          <p style={{ margin: '6px 0 0', fontSize: 13, padding: 10, background: C.panel, borderRadius: 6 }}>
            الحل المُحسَّن: {data.solutionEval.optimized_solution}
          </p>
        </Section>
      )}

      {/* evidence + references */}
      {(data.evidence.length > 0 || refs.length > 0) && (
        <Section title="الأدلة والمراجع" en="Evidence & references">
          <ol style={{ margin: 0, paddingInlineStart: 20, fontSize: 12.5 }}>
            {data.evidence.map((e, i) => (
              <li key={`e${i}`} style={{ marginBottom: 5 }}>
                {e.title} {e.year ? `(${e.year})` : ''} {e.oa_status ? `· OA: ${e.oa_status}` : ''}
                {e.doi ? <span style={{ color: C.blue }}> · doi:{e.doi}</span> : null}
              </li>
            ))}
            {refs.map((r, i) => (
              <li key={`r${i}`} style={{ marginBottom: 5 }}>
                {r.name} — <span style={{ color: C.blue, wordBreak: 'break-all' }}>{r.url}</span>
              </li>
            ))}
          </ol>
        </Section>
      )}

      {/* methodology + disclaimer */}
      <Section title="المنهجية وإخلاء المسؤولية" en="Methodology & disclaimer">
        <p style={{ margin: 0, fontSize: 11.5, color: C.sub }}>
          أُنتج هذا التقرير آليًّا من محرّك AEGIS: استرجاع سوابق موثّقة، محاكاة حتمية متعددة القطاعات،
          واسترجاع أدلة من مصادر علمية مفتوحة قابلة للتحقّق. الأرقام المسبوقة بـ«تقديري» تقديرات وليست قياسات.
          هذا التقرير لدعم القرار فقط، وليس بديلًا عن البيانات الرسمية للجهات المختصّة، ولا يُقدَّم بأي ضمان.
        </p>
      </Section>

      <div style={{ marginTop: 18, borderTop: `1px solid ${C.line}`, paddingTop: 8, fontSize: 10.5, color: C.faint, textAlign: 'center' }}>
        AEGIS Crisis Console · {data.generatedAt} · decision-support only
      </div>
    </div>
  )
}
