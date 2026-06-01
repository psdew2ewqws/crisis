import { memo } from 'react'
import {
  BaseEdge,
  EdgeLabelRenderer,
  getSmoothStepPath,
  type EdgeProps,
} from '@xyflow/react'

function CrisisEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  style,
}: EdgeProps) {
  const weight = (data?.weight as number) ?? 0.5
  const label = (data?.label as string) ?? ''

  const color = weight > 0.7 ? '#F04359' : weight >= 0.4 ? '#FBBF24' : '#8B8D96'

  const [edgePath, labelX, labelY] = getSmoothStepPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
    borderRadius: 16,
  })

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        style={{
          stroke: color,
          strokeWidth: 2,
          ...style,
        }}
        className="edge-animated"
        markerEnd={`url(#arrow-${id})`}
      />
      <defs>
        <marker
          id={`arrow-${id}`}
          markerWidth="8"
          markerHeight="8"
          refX="8"
          refY="4"
          orient="auto"
        >
          <path d="M0,0 L8,4 L0,8" fill="none" stroke={color} strokeWidth="1.5" />
        </marker>
      </defs>
      {label && (
        <EdgeLabelRenderer>
          <div
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
              pointerEvents: 'all',
            }}
            className="rounded bg-bg/90 px-1.5 py-0.5 font-mono text-[9px] text-faint"
          >
            {label}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  )
}

export default memo(CrisisEdge)
