interface Props {
  name: string
  role: string
  authLevel: string
}

export default function RbacBadge({ name, role, authLevel }: Props) {
  const initials = name
    .split(' ')
    .map((w) => w[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()

  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="flex items-center gap-4">
        <div className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-blue/10 text-[13px] font-semibold text-blue">
          {initials}
        </div>
        <div className="text-[14px] font-medium text-txt">{name}</div>
        <div className="h-5 w-px bg-border" />
        <div className="text-[12px] text-muted">
          Role: <span className="rounded-md bg-blue/10 px-2 py-0.5 text-[11px] font-medium text-blue">{role}</span>
        </div>
        <div className="h-5 w-px bg-border" />
        <div className="text-[12px] text-muted">
          Auth Level: <span className="font-mono text-[12px] text-txt">{authLevel}</span>
        </div>
      </div>
    </div>
  )
}
