// Themed button for the auth pages. `primary` matches the console's "Run Analysis"
// CTA; `outline` is the secondary action. Full-width by default.
import type { ButtonHTMLAttributes } from 'react'

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'outline'
}

export default function AuthButton({ variant = 'primary', className = '', children, ...rest }: Props) {
  const base =
    'flex w-full items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-[14px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue/60 disabled:cursor-not-allowed disabled:opacity-60'
  const styles =
    variant === 'primary'
      ? 'bg-blue text-white shadow-lg shadow-blue/20 hover:bg-[#2f76e8]'
      : 'border border-border text-txt hover:bg-soft'
  return (
    <button className={`${base} ${styles} ${className}`} {...rest}>
      {children}
    </button>
  )
}
