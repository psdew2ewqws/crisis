import type { RootCauseResult } from '../../lib/data'

function scoreColor(score: number): string {
  if (score > 0.7) return 'text-good'
  if (score >= 0.2) return 'text-warn'
  return 'text-muted'
}

export default function CandidateTable({ candidates }: { candidates: RootCauseResult['candidates'] }) {
  return (
    <div className="rounded-xl border border-border bg-card">
      <div className="px-5 pt-5 pb-3">
        <div className="text-[10px] font-semibold tracking-[0.14em] text-faint">CANDIDATE RANKING</div>
      </div>
      <table className="w-full text-left">
        <thead>
          <tr className="text-[11px] font-medium tracking-[0.08em] text-faint">
            <th className="px-5 py-2 font-medium">RANK</th>
            <th className="py-2 font-medium">NODE</th>
            <th className="py-2 font-medium text-right">CAUSAL SCORE</th>
            <th className="py-2 px-5 font-medium">REASON</th>
          </tr>
        </thead>
        <tbody>
          {candidates.map((c) => (
            <tr
              key={c.nodeId}
              className={`border-t border-border/70 transition-colors hover:bg-soft/50 ${
                c.rank === 1 ? 'border-l-2 border-l-blue' : ''
              }`}
            >
              <td className="px-5 py-3 font-mono text-[13px] text-muted">{c.rank}</td>
              <td className="py-3">
                <div className="text-[13.5px] font-medium text-txt">{c.label}</div>
                <div className="font-mono text-[11px] text-faint">{c.nodeId}</div>
              </td>
              <td className={`py-3 text-right font-mono text-[14px] font-semibold ${scoreColor(c.causalScore)}`}>
                {c.causalScore.toFixed(2)}
              </td>
              <td className="py-3 px-5 text-[12.5px] text-muted max-w-[300px]">{c.reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
