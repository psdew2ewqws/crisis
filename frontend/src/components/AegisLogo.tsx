// AEGIS mark: a shield (AEGIS = the shield of Zeus → protection/defense) enclosing a
// 3-node triangle graph (the dependency / crisis-network analysis the console runs).
// Themed to the console's blue accent — dim shield outline, bright nodes.
import { useTranslation } from 'react-i18next'

export default function AegisLogo({ size = 32, className = '' }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      className={className}
      aria-hidden="true"
    >
      {/* shield outline */}
      <path
        d="M16 2.5 L27.5 6.5 V15 C27.5 22.3 22.3 27 16 29.5 C9.7 27 4.5 22.3 4.5 15 V6.5 Z"
        stroke="#3B82F6"
        strokeOpacity="0.55"
        strokeWidth="1.5"
        strokeLinejoin="round"
        fill="#3B82F6"
        fillOpacity="0.06"
      />
      {/* node connections (the dependency graph) */}
      <path
        d="M16 11.5 L11 19 M16 11.5 L21 19 M11 19 L21 19"
        stroke="#3B82F6"
        strokeOpacity="0.7"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
      {/* nodes */}
      <circle cx="16" cy="11.5" r="2.4" fill="#60A5FA" />
      <circle cx="11" cy="19" r="2.4" fill="#60A5FA" />
      <circle cx="21" cy="19" r="2.4" fill="#60A5FA" />
    </svg>
  )
}

// Icon + wordmark. The "AEGIS" wordmark stays Latin (brand identity); the subtitle is
// translated. Letter-spacing is applied only in LTR — it breaks Arabic letter-joining.
export function AegisLogoFull({ size = 36, className = '' }: { size?: number; className?: string }) {
  const { t } = useTranslation()
  return (
    <div className={`flex items-center gap-2.5 ${className}`}>
      <span className="grid place-items-center rounded-lg bg-blue/15 p-1.5">
        <AegisLogo size={size - 12} />
      </span>
      <div className="leading-tight">
        <div className="text-[16px] font-semibold tracking-tight text-txt">AEGIS</div>
        <div className="text-[10px] font-medium text-faint ltr:tracking-[0.16em]">{t('brand.subtitle')}</div>
      </div>
    </div>
  )
}
