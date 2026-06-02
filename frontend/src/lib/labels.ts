// labels.ts — T3 build-time Arabic→English label map for REAL voc360 data.
//
// No LLM key is available in the environment, so the Arabic cluster / service /
// governorate / source-type / sentiment labels surfaced by voc360 are translated
// here at BUILD time (these strings are taken verbatim from the verified voc360
// schema: ril_problem_clusters.canonical_label_ar, the_data.service_id /
// governorate / source_type / sentiment_label). At runtime `t(s)` returns the
// English gloss when known and the original string otherwise — so the UI degrades
// gracefully for any label we have not translated yet.
//
// Consumed by pages/RootCausePage.tsx via `import('../lib/labels')`, which reads
// `LABELS ?? labels ?? default`. The map is keyed by the raw label text (Arabic
// or canonical id) and values are either an English string or `{ en, ar }` — both
// shapes are accepted by the consumer. Import-safe: pure data + pure functions,
// no side effects, no network, no env access.

/* ----------------------------------------------------------------- types */

export type LabelEntry = { en?: string; ar?: string }
export type LabelsMap = Record<string, LabelEntry | string>

/* --------------------------------------------------- ar→en (build-time) */
// Keyed by the EXACT voc360 string. Keep keys verbatim (incl. underscores in
// service_id / source_type values) so lookups are 1:1 with the database.

export const AR_EN: Record<string, string> = {
  // --- ril_problem_clusters.canonical_label_ar (root-cause layer) ---
  'تأخير دعم صندوق المعونة': 'National Aid Fund support delays',
  'تأخير صرف المعونة لأكثر من شهرين دون إشعار':
    'Aid disbursement delayed over two months without notice',
  'الباص السريع': 'Bus Rapid Transit (BRT)',
  'رسوم الخدمة المستعجلة': 'Urgent-service fees',
  'منصة تكافل': 'Takaful platform',

  // --- the_data.service_id ---
  Sanad: 'Sanad',
  'Amman Bus': 'Amman Bus',
  Bekhedmetkom: 'Bekhedmetkom',
  'نقل_عام': 'Public transit',
  'طرق_وبنية_تحتية': 'Roads & infrastructure',
  'مراكز_الخدمة': 'Service centers',
  'جوازات_السفر': 'Passports',
  'الخدمات_الإلكترونية': 'E-services',

  // --- the_data.source_type (signal layer) ---
  app_review: 'App review',
  social_media_sentiment: 'Social-media sentiment',
  employee_complaint: 'Employee complaint',
  complaint: 'Complaint',
  qr_survey: 'QR survey',
  ces_survey: 'CES survey',
  csat_survey: 'CSAT survey',
  'فساد_إداري': 'Administrative corruption',
  'سوء_الخدمة': 'Poor service',
  'عدم_الرد': 'No response',

  // --- the_data.governorate ---
  'الزرقاء': 'Zarqa',
  'إربد': 'Irbid',
  'العقبة': 'Aqaba',
  'السلط': 'Salt',
  'المفرق': 'Mafraq',
  'جرش': 'Jerash',

  // --- the_data.sentiment_label ---
  negative: 'Negative',
  positive: 'Positive',
  neutral_citizen_sentiment: 'Neutral',
  high_severity_complaint: 'High-severity complaint',

  // --- the_data.severity ---
  low: 'Low',
  medium: 'Medium',
  high: 'High',
  critical: 'Critical',
}

/* --------------------------------------------- consumer-facing LABELS map */
// Same data, exposed in the `{ en, ar }` shape the RootCausePage consumer also
// accepts. Both `LABELS` and the alias `labels` are exported so either lookup
// (`mod.LABELS ?? mod.labels ?? mod.default`) resolves.

export const LABELS: LabelsMap = Object.fromEntries(
  Object.entries(AR_EN).map(([ar, en]) => [ar, { ar, en }]),
)

export const labels = LABELS

/* ---------------------------------------------------------------- helper */
// t(s): English gloss if known, else the original string. Trims and tolerates
// null/undefined so call sites can pass raw db values directly.

export function t(s: string | null | undefined): string {
  if (s == null) return ''
  const key = String(s).trim()
  if (!key) return ''
  return AR_EN[key] ?? key
}

export default LABELS
