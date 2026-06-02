// First-run onboarding hero. Reuses the existing BackgroundPaths component
// (flowing "crisis cascade" paths) and hands it the AEGIS framing, an Arabic-first
// tagline, three capability chips, and a grounded footer line — so the first thing
// an operator sees states, in their language, what the console actually does.
// onDone is fired from the CTA — App persists the flag.
import { Target, ShieldCheck, TrendingUp } from 'lucide-react'
import { BackgroundPaths } from './BackgroundPaths'
import { useT } from '../lib/i18n'

const CHIPS = [
  { icon: Target, ar: 'اكتشف السبب الجذري' },
  { icon: ShieldCheck, ar: 'أثبته بالأدلة' },
  { icon: TrendingUp, ar: 'تنبّأ بما هو قادم' },
]

export default function Onboarding({ onDone }: { onDone: () => void }) {
  const { t } = useT()
  return (
    <BackgroundPaths
      title={t('AEGIS Crisis Console')}
      subtitle="منصّة ذكاء الأزمات · اكتشف السبب الجذري، أثبته بالأدلة، وتنبّأ بما هو قادم"
      cta="ابدأ · Enter Console"
      onCta={onDone}
      footer={
        <div className="flex flex-col items-center gap-4">
          <div className="flex flex-wrap items-center justify-center gap-2.5">
            {CHIPS.map(({ icon: Icon, ar }) => (
              <span
                key={ar}
                dir="rtl"
                className="inline-flex items-center gap-2 rounded-full border border-border bg-card/60 px-3.5 py-1.5 text-[12.5px] text-muted backdrop-blur"
              >
                <Icon className="h-3.5 w-3.5 text-blue" />
                {ar}
              </span>
            ))}
          </div>
          <small className="font-mono text-[12px] tracking-wide text-faint" dir="rtl">
            ٢٢٬٨٨٢ إشارة مواطن · ٢٠ محور سبب جذري · voc360 مباشر
          </small>
        </div>
      }
    />
  )
}
