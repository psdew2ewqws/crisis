// Centralized, i18n-aware humanizers for the raw voc360 values shown across pages.
// Each takes the i18next `t` so labels translate; colors/icons are presentation tokens.
import {
  Smartphone,
  FileText,
  Phone,
  ClipboardList,
  Globe,
  Mail,
  MessageSquare,
  type LucideIcon,
} from 'lucide-react'

type T = (key: string, opts?: Record<string, unknown>) => string

function titleCase(s: string): string {
  return s.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

export function humanizeSentiment(
  raw: string | null | undefined,
  t: T,
): { label: string; color: string; dot: string } {
  const s = (raw ?? '').toLowerCase()
  if (s.includes('positive') || s.endsWith('pos'))
    return { label: t('sentiment.positive'), color: 'text-good', dot: 'bg-good' }
  if (s.includes('negative') || s.endsWith('neg'))
    return { label: t('sentiment.negative'), color: 'text-danger', dot: 'bg-danger' }
  if (s.includes('neutral'))
    return { label: t('sentiment.neutral'), color: 'text-muted', dot: 'bg-muted' }
  return { label: raw ? titleCase(raw) : '—', color: 'text-muted', dot: 'bg-muted' }
}

const SOURCE_ICON: Record<string, LucideIcon> = {
  social_media: Smartphone,
  social_media_sentiment: Smartphone,
  social: Smartphone,
  twitter: Smartphone,
  facebook: Smartphone,
  complaint: FileText,
  complaints: FileText,
  call: Phone,
  phone: Phone,
  hotline: Phone,
  survey: ClipboardList,
  email: Mail,
  web: Globe,
  portal: Globe,
}
const SOURCE_KEY: Record<string, string> = {
  social_media: 'source.socialMedia',
  social_media_sentiment: 'source.socialMedia',
  social: 'source.socialMedia',
  complaint: 'source.complaint',
  complaints: 'source.complaint',
  call: 'source.call',
  phone: 'source.call',
  survey: 'source.survey',
  email: 'source.email',
  web: 'source.web',
  portal: 'source.web',
}
export function humanizeSource(
  raw: string | null | undefined,
  t: T,
): { label: string; Icon: LucideIcon } {
  const s = (raw ?? '').toLowerCase().trim()
  const Icon = SOURCE_ICON[s] ?? MessageSquare
  const key = SOURCE_KEY[s]
  return { label: key ? t(key) : raw ? titleCase(raw) : '—', Icon }
}

export function humanizeTimestamp(value: string | Date | null | undefined, t: T): string {
  if (!value) return '—'
  const ms = typeof value === 'string' ? new Date(value).getTime() : value.getTime()
  if (Number.isNaN(ms)) return String(value)
  const m = Math.round((Date.now() - ms) / 60000)
  if (m < 1) return t('time.justNow')
  if (m < 60) return t('time.minutesAgo', { n: m })
  const h = Math.round(m / 60)
  if (h < 24) return t('time.hoursAgo', { n: h })
  return t('time.daysAgo', { n: Math.round(h / 24) })
}

const SEV_MAP: Record<string, { key: string; color: string; dot: string }> = {
  critical: { key: 'severity.critical', color: 'text-danger', dot: 'bg-danger' },
  high: { key: 'severity.high', color: 'text-danger', dot: 'bg-danger' },
  elevated: { key: 'severity.elevated', color: 'text-warn', dot: 'bg-warn' },
  medium: { key: 'severity.medium', color: 'text-warn', dot: 'bg-warn' },
  moderate: { key: 'severity.medium', color: 'text-warn', dot: 'bg-warn' },
  low: { key: 'severity.low', color: 'text-blue', dot: 'bg-blue' },
  nominal: { key: 'severity.low', color: 'text-good', dot: 'bg-good' },
}
export function humanizeSeverity(
  level: string | null | undefined,
  t: T,
): { label: string; color: string; dot: string } {
  const m = SEV_MAP[(level ?? '').toLowerCase().trim()]
  if (!m) return { label: level ? titleCase(level) : '—', color: 'text-muted', dot: 'bg-faint' }
  return { label: t(m.key), color: m.color, dot: m.dot }
}

const TYPE_KEY_MAP: Record<string, string> = {
  why_chain: 'typeKey.whyChain',
  cluster_subthemes: 'typeKey.subthemes',
  cluster_services: 'typeKey.services',
  case_validation: 'typeKey.validation',
  sim_impact: 'typeKey.simImpact',
}
export function humanizeTypeKey(key: string | null | undefined, t: T): string {
  const mapped = TYPE_KEY_MAP[(key ?? '').toLowerCase().trim()]
  return mapped ? t(mapped) : key ? titleCase(key) : ''
}
