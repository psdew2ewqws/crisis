import { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import type { GraphNode } from '../../lib/data'

const sevBorder: Record<string, string> = {
  danger: 'border-l-danger',
  warn: 'border-l-warn',
  good: 'border-l-good',
  neutral: 'border-l-muted',
}

const sevDot: Record<string, string> = {
  Critical: 'bg-danger',
  Elevated: 'bg-warn',
  Nominal: 'bg-good',
}

function CrisisNode({ data }: NodeProps) {
  const d = data as unknown as GraphNode
  return (
    <div
      className={`w-[200px] rounded-xl border border-border bg-card ${sevBorder[d.tone]} border-l-4 ${d.isApex ? 'apex-glow border-danger' : ''}`}
    >
      <Handle type="target" position={Position.Left} className="!bg-border !border-none !w-2 !h-2" />
      <div className="p-3">
        <div className="flex items-center justify-between">
          <span className="text-[13px] font-medium text-txt truncate">{d.label}</span>
          <span className={`h-2 w-2 rounded-full shrink-0 ${sevDot[d.severity]}`} />
        </div>
        <div className="mt-1 font-mono text-[11px] text-faint">{d.id}</div>
        <div className="mt-2 flex items-center justify-between">
          <span className="text-[11px] text-muted">{d.type}</span>
          <span className="font-mono text-[11px] text-muted">Z {d.zScore}</span>
        </div>
      </div>
      <Handle type="source" position={Position.Right} className="!bg-border !border-none !w-2 !h-2" />
    </div>
  )
}

export default memo(CrisisNode)
