// First-run onboarding hero. Reuses the existing BackgroundPaths component
// (flowing "crisis cascade" paths) and hands it the AEGIS framing + a grounded
// footer line so the very first thing an operator sees states what the console
// actually holds. onDone is fired from the CTA — App persists the flag.
import { BackgroundPaths } from './BackgroundPaths'

export default function Onboarding({ onDone }: { onDone: () => void }) {
  return (
    <BackgroundPaths
      title="AEGIS Crisis Console"
      subtitle="Find the root cause. Prove it. Predict what's next."
      cta="Enter Console"
      onCta={onDone}
      footer={
        <small className="font-mono text-[12px] tracking-wide text-faint">
          22,882 citizen signals · 20 root-cause clusters · live voc360
        </small>
      }
    />
  )
}
