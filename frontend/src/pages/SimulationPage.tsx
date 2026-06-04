// SimulationPage — reworked into the scenario crisis DETECTION + PREDICTION console.
// Describe a novel crisis in free text → retrieve historical precedents → select the
// right agents by skill → simulate (Mesa before/after) → detect + predict, all streamed
// over POST /api/scenario/detect. The full experience lives in ScenarioSimulation; this
// page is a thin mount so routing/imports stay stable.
//
// The previous standalone Mesa A/B view is preserved in git history; its before/after
// charts now live inside the scenario flow (components/scenario/ScenarioCharts.tsx).

import ScenarioSimulation from '../components/scenario/ScenarioSimulation'

export default function SimulationPage(_props: { caseId?: string } = {}) {
  return <ScenarioSimulation />
}
