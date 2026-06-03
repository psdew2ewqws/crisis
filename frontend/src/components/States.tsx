// Shared, consistent placeholder states (loading / empty / error) so every widget
// reads the same way instead of ad-hoc one-liners. Presentational only.
import { Loader2, Inbox, AlertTriangle, RotateCw, type LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

export function LoadingState({ label }: { label?: string }) {
  const { t } = useTranslation()
  return (
    <div className="flex items-center justify-center gap-2 py-10 text-[13px] text-muted">
      <Loader2 className="h-4 w-4 animate-spin text-blue" />
      {label ?? t('general.loading')}
    </div>
  )
}

export function EmptyState({
  icon: Icon = Inbox,
  title,
  hint,
  action,
}: {
  icon?: LucideIcon
  title: string
  hint?: string
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-12 text-center">
      <span className="grid h-10 w-10 place-items-center rounded-full bg-soft text-muted">
        <Icon className="h-5 w-5" />
      </span>
      <div className="text-[13.5px] font-medium text-txt">{title}</div>
      {hint && <div className="max-w-[320px] text-[12.5px] text-muted">{hint}</div>}
      {action && <div className="mt-1">{action}</div>}
    </div>
  )
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  const { t } = useTranslation()
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-12 text-center">
      <span className="grid h-10 w-10 place-items-center rounded-full bg-danger/10 text-danger">
        <AlertTriangle className="h-5 w-5" />
      </span>
      <div className="text-[13.5px] font-medium text-txt">{t('general.error')}</div>
      <div className="max-w-[320px] text-[12.5px] text-muted">{message}</div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-1 flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-[12.5px] text-txt transition-colors hover:bg-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue/60"
        >
          <RotateCw className="h-3.5 w-3.5" />
          {t('general.retry')}
        </button>
      )}
    </div>
  )
}
