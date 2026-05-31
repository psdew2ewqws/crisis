# Jordan Crisis Management Simulation Engine — Gap Analysis (Condensed)

**Specification gap analysis · 28 confirmed gaps · Readiness 3.5 / 10 · 2026-05-31**

---

## 1. Context

This is the condensed gap analysis of the 18-section scope package for the *Jordan Crisis Management Simulation Engine* (a simulation-first national crisis-intelligence platform). A 15-lens expert panel (business strategy + architecture + ML/data + crisis operations + security/governance + delivery/QA) ran a **detect → consolidate → adversarially-verify → prioritize** review: **119 raw gaps surfaced, 28 confirmed, 0 refuted**. This document keeps every confirmed gap in a tight *Gap / Impact / Fix* form, plus the readiness verdict, the workflow deep-dive, and the remediation roadmap.

---

## 2. Executive Summary — Readiness 3.5 / 10

*Scale: 0 = unbuildable/unsafe ambition · 5 = buildable but with major correctness/safety/evaluation gaps · 10 = fully buildable, safely operable, objectively evaluable.*

The spec is a thorough **functional inventory** — 4 layers, 9 engines, 6 domains, multiple simulations — that never specifies **how anyone proves it works, who decides anything, or how it fails safely**. It is strong on *what to build* and nearly silent on *how good*, *for whom*, and *how validated*. Three structural voids dominate:

1. **No measurable acceptance instrument, and circular validation.** No rubric/threshold/oracle, and the *same teams author both the synthetic puzzles and the engine graded on solving them* — every correctness claim is gameable (**G01 / G02**).
2. **An open intelligence loop.** No human authority gate between Recommendation and Action, and no feedback from Outcome back into the models — the system captures no accountable decision and cannot learn (**G03 / G04**).
3. **An asserted, not designed, central thesis.** The synthetic→production transition "without redesigning the core" is a deliverable, not an architectural property with a seam and a validation gate (**G15**).

Cross-cutting: an entire **security / privacy / governance** dimension is absent from a national-security-grade system *and* from the pass/fail bar (**G09–G13**), and **no non-functional targets** anchor any "national-grade" claim (**G20**).

**Headline risk — circular validation:** because ground truth is authored by, and visible to, the builders with no held-out oracle, *a hardcoded if-statement and a real inference engine score identically*. The project can declare total success while proving nothing about the only case that matters — a genuinely novel crisis.

---

## 3. Readiness Scorecard

| Theme | Status | Worst | Note |
|---|---|---|---|
| Spec Clarity & Strategic Focus | At Risk | High | Breadth-first catalogue; no MVP cut-line, no chosen strategic position. |
| Workflow, Decisioning & Feedback Loops | Critical | High | Loop is a line, not a cycle: no human authority gate, no learning feedback. |
| Intelligence & ML Method | At Risk | High | Root cause, prediction, confidence, Risk Index demanded as outputs; methods unspecified. |
| Data Realism & Synthetic-to-Production | Critical | High | Team-authored data with no ground-truth wall; transition thesis untested. |
| Simulation & Systems Modeling | At Risk | High | No stock-and-flow dynamics, delays, isolation, or fidelity validation. |
| Governance, Security & Safety | Critical | High | No security, RBAC, audit, privacy, sovereignty, adversarial-input, or safety floor. |
| Adoption, Stakeholders & Communication | At Risk | High | No named customer/job, no incumbent map, no public-communication layer. |
| Delivery & Evaluation | Critical | High | Acceptance tests presence, not correctness; no rubric, harness, or held-out set. |
| Architecture & NFRs | At Risk | High | No NFRs, no inter-layer contracts, no eventing/idempotency, no failure-mode model. |

---

## 4. Gap Register (28 confirmed)

*Severity is the verified post-review severity. Each gap: what is missing → why it matters → the fix.*

### Spec Clarity & Strategic Focus

**G05** — Unbounded breadth-first scope: 18+ flatly mandatory items plus high-bar extras, no MVP cut-line, timeline, tiering, or chosen strategic focus.  *(High · Delivery & Evaluation)*
- **Impact:** Forces mediocrity everywhere: teams spread thin, finish nothing, sacrifice the one end-to-end loop, converge on interchangeable demos.
- **Fix:** Define one domain/customer/correct Signal→Outcome loop as P0 walking skeleton; re-tier Section 16 into P0/P1/P2; state duration, team size, critical path, and an ERRC/value-curve choice.

**G28** — Ambiguous language: quality bars are unmeasurable adjectives and inconsistent modal verbs blur must vs may across sections 14/16.  *(Low · Spec Quality & Clarity)*
- **Impact:** When 'should' sometimes means 'must' and adjectives lack tests, builders mis-scope and acceptance disputes erupt at judging.
- **Fix:** Adopt consistent MUST/SHOULD/MAY (reconcile Sec 14 with 16), operationalize each adjective via Section 4 defect types, restructure sections as message-then-support, and segregate mandatory from aspirational.

### Workflow, Decisioning & Feedback Loops

**G03** — Loop jumps Recommendation→Action with no human authorization gate, decision state machine, accountable approver, override path, or immutable audit log.  *(High · Decision Workflow)*
- **Impact:** Diffuses responsibility; recommendations stall and leaders revert to the phone; no legally defensible record of who decided.
- **Fix:** Specify a recommendation/decision state machine with a human authorization gate, first-class Decision record (decider, verdict, rationale, timestamp, override) to an immutable audit log, and auto-escalating acknowledgment SLA.

**G04** — Loop ends at Outcome; expected-vs-actual delta is a display field that recalibrates nothing; cleanup/expiration erases calibration memory.  *(High · Decision Workflow)*
- **Impact:** System can't detect when it's systematically wrong; confidence scores are decoration; platform is a reporting pipeline, not a closed loop.
- **Fix:** Make the return arrow first-class: define actual outcome (simulation re-run vs no-action baseline), feed error back to recalibrate models and weights; require a demonstrable second turn.

**G24** — No alert thresholds, hysteresis/debounce, dedup, confidence gating, or alert-fatigue controls on a deliberately noisy detection and index layer.  *(High · Risk Index & Metrics)*
- **Impact:** Alert fatigue makes operators ignore the system that cries wolf and miss the one true alarm.
- **Fix:** Add per-level thresholds with hysteresis, minimum-confidence gating, dedup/correlation, escalation-on-persistence, per-role opt-in profiles with snooze/handoff, and a measurable precision/false-alarm acceptance target.

### Intelligence & ML Method

**G06** — National Risk Index has no formula, weights, normalization, cross-level aggregation, scale, thresholds, hysteresis, or anti-gaming; inputs are endogenous and self-referential.  *(High · Risk Index & Metrics)*
- **Impact:** Primary number leaders act on is arbitrary and oscillating: non-comparable across teams, un-trendable, indefensible to a minister, 'explain why' impossible.
- **Fix:** Require a versioned index contract: fixed inputs, per-factor normalization, declared weights, defined aggregation, deterministic factor-attribution, hysteresis, endogeneity statement; add directional-validity shock tests.

**G07** — Confidence scores mandated everywhere but undefined in meaning, computation, and calibration; demands single-cause attribution in plural-causation wicked regimes.  *(Medium · Intelligence & ML)*
- **Impact:** Leaders anchor on uncalibrated false precision, commit resources to confidently-wrong causes; miscalibration is invisible without validation.
- **Fix:** Define confidence semantics and computation; require calibration testing (reliability diagram/ECE) on held-out scenarios; surface competing hypotheses, an 'unknown/out-of-scope' state, and a per-source accuracy ledger; grade honesty over confidence.

**G08** — Root-cause and prediction methods unspecified (rules/ML/causal/LLM); forecasts lack horizon, uncertainty band, and backtesting against synthetic ground truth.  *(High · Intelligence & ML)*
- **Impact:** Central wicked-problem capability is unbuildable to a common bar, unreviewable; forecasts are guesses presented as fact driving interventions.
- **Fix:** Require each team to declare/justify root-cause method (recommend typed directional causal graph; LLM only narrates). Each forecast declares method, horizon, uncertainty, one backtest error.

**G26** — Conversational interface and AI advisors introduce unaddressed hallucination/grounding risk; no requirement that answers trace to canonical model/evidence.  *(High · Governance & Security)*
- **Impact:** Fluently-stated fabricated outages, casualty figures, or root causes directly mislead decision-makers in the highest-consequence surface.
- **Fix:** Require strict grounding: every assertion cites a canonical-model object, numbers read from data not generated, insufficient-evidence returns explicit 'unknown,' plus a hallucination/grounding acceptance check.

### Data Realism & Synthetic-to-Production

**G02** — No wall between generator's ground-truth layer and engine's observable layer; same team authors both, no held-out scenarios or randomized hidden cause.  *(High · Data & Synthetic)*
- **Impact:** Train-on-test leak: engine can just read the hidden_cause field; appears excellent on authors' puzzles, fails on novel crises.
- **Fix:** Mandate a sealed truth manifest the engine never reads at runtime, scored offline; add a separately-authored red-team holdout; report seen vs held-out separately.

**G15** — Synthetic-to-production transition (the headline claim) has no defined anti-corruption seam, cutover invariants, or validation/acceptance test.  *(Medium · Delivery & Evaluation)*
- **Impact:** Teams hardwire synthetic assumptions into engines; models drift silently at cutover; the production claim becomes aspirational.
- **Fix:** Make swappability architectural: source-adapter as sole synthetic-aware code; enumerate cutover invariants; gate transition with shadow run, drift monitoring, re-baselining, trust gate, rollback-to-synthetic, and a zero-core-change swap test.

**G25** — No data-quality framework defining metrics, per-source activation thresholds, or quality propagation, despite mandated dirty data and a required assessment step.  *(Medium · Data & Synthetic)*
- **Impact:** Intelligence treats duplicate-laden, half-stale feeds like clean ones, producing confidently-wrong insights; onboarding step stays undefined and unverifiable.
- **Fix:** Specify quality dimensions/metrics (completeness, dedup rate, timeliness, schema-conformance, conflict rate), per-source thresholds gating activation, and propagation rules down-weighting evidence and the Risk Index.

### Simulation & Systems Modeling

**G14** — Simulation isolation, rollback/cleanup semantics, and synthetic-vs-live boundary asserted but unmechanized; no provenance tagging, namespace isolation, or live-state guard.  *(High · Simulation & Modeling)*
- **Impact:** A simulated cascade leaking into the live index or executed simulated recommendation produces false national alarms or real false public alerts.
- **Fix:** Specify provenance/isolation: origin-tagged records, scoped scenario context, read-only baseline, verifiable rollback/cleanup post-conditions, hard sim-vs-live mode separation, acceptance tests proving no residual influence.

**G16** — Simulation models discrete events only — no stocks, inflow/outflow rates, time-to-depletion, delay constants, second-order effects, or fidelity validation.  *(Medium · Simulation & Modeling)*
- **Impact:** Cannot compute time-to-depletion, encourages over-intervention and oscillation, and produces fabricated, unvalidated numbers inviting misplaced national confidence.
- **Fix:** Model per-domain stocks with inflow/outflow rates integrated over time; add delay parameters and feedback loops; require second-order effect estimates plus determinism, sanity-invariant, and back-test fidelity checks.

### Governance, Security & Safety

**G09** — No authentication, authorization, RBAC, data classification, actor/role model, or governance anywhere; zero security items in the 18-item acceptance list.  *(High · Governance & Security)*
- **Impact:** Platform is unsafe to operate, un-accreditable under any government regime, and cannot make the promised no-redesign production transition.
- **Fix:** Add mandatory governance layer: actor/role model, RBAC at API and Experience-Layer, data-classification tagging every canonical object, security acceptance gate; demonstrate role-scoped access in sandbox.

**G10** — No audit trail or immutable record for state-changing actions; no decision-lineage linking recommendation back through simulation, root cause, and signals.  *(Medium · Governance & Security)*
- **Impact:** Insider event-injection or rollback manipulation is undetectable and unattributable; wrong recommendations cannot be diagnosed to the failing stage.
- **Fix:** Require append-only, tamper-evident audit log (actor, action, target, timestamp, before/after) per state change, plus per-recommendation lineage. Make audit trail an acceptance item.

**G11** — Adversarial/spoofed/poisoned feeds and untrusted onboarding treated as data-quality noise; no input-trust model, provenance, consistency checks, or injection plausibility limits.  *(High · Governance & Security)*
- **Impact:** One forged feed or malicious onboarded source can misallocate national resources or declare calm during a real crisis.
- **Fix:** Require input-trust model: per-source authentication, signed provenance, cross-source consistency checks, trust-tier weighting/quarantine, injection rate limits, vetting-gated onboarding; acceptance: resists a manipulated input.

**G12** — Distress, mobility, sentiment, and population-segment data carry no PII classification, minimization, consent, retention, residency/sovereignty, or agency tenancy isolation.  *(High · Governance & Security)*
- **Impact:** Ungoverned mass-surveillance capability with civil-liberties exposure; sovereignty-sensitive data leaks cross-border and across agency trust boundaries.
- **Fix:** Tag personal fields; default anonymization/aggregation; define retention/deletion and purpose limits; require national residency with gated external exchange; add RBAC-enforced tenancy isolation.

**G13** — No via-negativa safety floor: no prohibited-actions list, abstention rule, harm bounds, escalation rate limits, kill switch, or error budget; only additive sophistication.  *(High · Decision Workflow)*
- **Impact:** A confident wrong autonomous action can kill; optimizing for cleverness selects the most confidently-wrong system on unmodeled events.
- **Fix:** Add via-negativa layer (prohibited actions, mandatory human authorization for life-safety, default-abstain under uncertainty, escalation bounds, kill switch). Restructure incentives as barbell; make fail-safe and error rates acceptance criteria.

### Adoption, Stakeholders & Communication

**G17** — No named decision-maker, no job-to-be-done, and no map of the as-is manual EOC/spreadsheet/phone incumbent process to beat.  *(High · Adoption & Stakeholders)*
- **Impact:** Build cannot prove added value over today; tradeoffs unresolvable; under stress leaders revert to trusted people and platform is orphaned.
- **Fix:** Name one persona and their single decision; write 2-3 job stories; map current-state failure points; make a defend-one-real-decision-better-than-baseline acceptance criterion.

**G18** — Multi-agency coordination reduced to one 'responsible agency' field — no concurrent tasking, deconfliction, KPI arbitration, or data-access politics.  *(Medium · Adoption & Stakeholders)*
- **Impact:** Cannot represent unified-command/deconfliction realities, so platform fails the cross-agency scenarios it mandates; agencies won't adopt it.
- **Fix:** Model accountable-owner-plus-supporting agencies, shared common-operating-picture, resource-contention deconfliction, and KPI arbitration; add an agency-adoption/trust plan with convener and staged shadow-to-relied-upon rollout.

**G19** — Social Stability domain has no outbound public-communication layer (alerts, messaging, approval, channels, counter-misinformation) and no failure/degradation narrative.  *(Medium · Decision Workflow)*
- **Impact:** Diagnoses panic without a hose; addresses half the domain; one confident miss invites scapegoating and shutdown.
- **Fix:** Add public communications as a first-class intervention with approval workflow, trusted-messenger/channel model, alert-fatigue constraint, and closed misinformation loop; design an honest advisor-with-track-record failure narrative.

### Delivery & Evaluation

**G01** — Section 16 acceptance criteria is a checklist of nouns: no pass/fail thresholds, expected outputs, measurement method, or weighted scoring rubric.  *(High · Delivery & Evaluation)*
- **Impact:** A hardcoded if-statement scores identically to a real inference engine; judging is arbitrary, gameable, demo theater.
- **Fix:** Rewrite as Given/When/Then tests with per-capability thresholds; publish a weighted rubric (0–4 anchors) before the build and a shared evaluation harness.

**G27** — No regression strategy, deliverables list, demo plan, or team/dependency sequencing for a stochastic, dynamically-extended build.  *(Medium · Delivery & Evaluation)*
- **Impact:** New sources silently regress the safety-relevant index; builds aren't comparable, judges can't verify hidden logic, integration time hits zero.
- **Fix:** Require golden-scenario regression suite with fixed seeds run before/after changes; specify deliverables (repo, README, architecture one-pager, 5-min demo, seeded dataset), shared scripted scenario, role allocation, and critical-path.

### Architecture & NFRs

**G20** — No non-functional requirements anywhere — no latency, throughput, uptime/availability, recompute interval, simulation bound, or per-source freshness SLA.  *(High · Architecture & Integration)*
- **Impact:** NFRs drive architecture (streaming vs batch); without them 'national-grade' is untestable and teams build incomparable systems judges can't evaluate.
- **Fix:** Add an NFR table with target numbers: ingest rate, signal-to-insight p95, risk-index recompute time, simulation p95, freshness SLA, availability; make latency and freshness acceptance-checkable.

**G21** — Inter-layer data contracts, transport, idempotency/dedup, event-time vs ingest-time, cascade algorithm, and API versioning are all undefined.  *(High · Architecture & Integration)*
- **Impact:** Guarantees incompatible pipelines and demo-time integration failure; duplicates double-count the Risk Index; schema changes silently break downstream engines.
- **Fix:** Define canonical event envelope and one end-to-end trace; promote Insight to canonical; specify transport and engine contracts; mandate idempotent ingestion, event-time handling, an explicit cascade model, and a versioned API.

**G22** — No platform failure-mode, degraded-operation, or cyber-resilience model; single centralized core with no availability, integrity, DoS, or offline-fallback treatment.  *(Medium · Architecture & Integration)*
- **Impact:** Centralized brain fails precisely during crises that overload or attack it; dead sources silently freeze risk scores.
- **Fix:** Define per-source staleness states with downstream low-confidence flags, degraded-mode policy, engine-failure isolation, availability targets, ingest auth/rate-limiting, offline fallback, and chaos testing.

**G23** — No deployment/runtime topology or persistence architecture, despite requirements implying historical, snapshot, and queryable stores.  *(Low · Architecture & Integration)*
- **Impact:** Teams discover mid-build they kept no history to answer 'what changed,' or conflate sandbox generator with the platform.
- **Fix:** Name required persistent stores (canonical event log, time-series risk history, scenario state) and isolation, define service-vs-monolith boundaries, and make the sandbox generator a deployably separate component.

---

## 5. Workflow Gaps — Deep Dive (core question)

The defining artifact is the intelligence loop **Signal → Insight → Root Cause → Simulation → Recommendation → Action → Outcome**. As written it is a **line, not a cycle**, broken at three structural points: it never closes (no feedback), it has no human authority gate, and its lifecycle flows are asserted not mechanized. Hop by hop, what is missing:

1. **Signal → Insight** — no input-trust model, so a spoofed or unvetted feed flows straight in (**G11**); no event-time/idempotency, so duplicates double-count and late reports mislead (**G21**); no data-quality propagation, so a dirty feed is treated like a clean one (**G25**).
2. **Insight → Root Cause** — "Insight" is not even a first-class object (**G21**); the root-cause *method* is unspecified (**G08**); confidence is undefined and uncalibrated (**G07**); no grounding guardrail on conversational/LLM output (**G26**).
3. **Root Cause → Simulation** — no stock-and-flow substrate or delays, so it cannot show *why late intervention is catastrophic* (**G16**); no fidelity validation; no isolation mechanism, so a simulated cascade can leak into the live picture (**G14**).
4. **Simulation → Recommendation** — only first-order "expected impact," no second-order/feedback effects (**G16**); no via-negativa floor — never graded on producing a confident-but-wrong recommendation (**G13**).
5. **Recommendation → Action — the broken hinge** — no human authority gate; "responsible agency / due date" are *data fields*, not a model of who may approve, reject, defer, or override; no Decision state machine or record; no advisory-vs-autonomous line; no alert governance before a notification reaches a minister (**G03 / G13 / G24**).
6. **Action → Outcome** — "actual outcome" is never defined; no audit/lineage linking a recommendation back to its signals, leaving the loop an undebuggable black box (**G04 / G10**).
7. **Outcome → models — the missing arrow** — "expected vs actual" is a display field; nothing recalibrates prediction, confidence, or risk weights, and aggressive cleanup destroys any calibration memory (**G04**).

**Verdict:** the analytical *front half* (Signal→Root Cause→Simulation) is specified in reasonable detail; the decision/execution *back half* — which determines whether the platform is trusted or ignored — is structurally incomplete. Fix order: insert the human authority gate (**G03**), close the feedback arrow (**G04**), mechanize isolation (**G14**), define inter-stage contracts (**G21**).

---

## 6. Panel Consensus & Key Disagreements

**Consensus across the 15 lenses**

- Lists *what* to build but never *what good looks like* — no objective, success metric, or rubric.
- The pipeline is a linear chain, not a closed loop, with no human authority gate between Recommendation and Action.
- Correctness is unprovable: the same teams author the data and the graded engine; no oracle wall or held-out set.
- No named customer and no map of the incumbent manual process — so it can't prove it beats the status quo.
- Scope is unbounded and uniformly mandatory with no MVP cut-line — mathematically forcing thin, undifferentiated builds.
- Load-bearing properties (simulation isolation, synthetic→production) are one-line claims, not specified architecture.

**Key disagreements**

- **Expand or contract?** Depth-first (one domain, one correct loop) vs the spec's own breadth ambition and Creativity Zone.
- **Confidence on the tail:** define & calibrate it vs refuse single-cause attribution where causation is plural (Taleb).
- **Autonomy:** reward maximal cleverness vs quarantine it behind a dumb-simple, abstaining safe core.
- **Where it dies:** technical seams (architecture/data/QA) vs the politics of permission (adoption/trust/inter-agency).

---

## 7. Priority Roadmap

**Critical path (each unblocks the next):** G02 oracle wall → G01 measurable rubric → G05 MVP cut-line → G03 human authority gate → G04 close the loop → G15 transition as architecture → G21 inter-layer contracts → G09 governance baseline.

**Quick wins (high leverage, low effort):** G28 MUST/SHOULD/MAY + measurable adjectives · G01 Given/When/Then acceptance tests · G05 P0/P1/P2 tiering + timeline · G06 one-page Risk Index contract · G20 small NFR table · G17 named persona + baseline · G07 confidence calibration check · G10 audit-trail acceptance item.

| # | Gap | Title | Sev | Effort | Pri |
|---|---|---|---|---|---|
| 1 | G02 | No held-out eval / oracle wall (circular validation) | High | Med | **P0** |
| 2 | G01 | No measurable acceptance criteria / rubric | High | Med | **P0** |
| 3 | G03 | No human authority gate or audit on actions | High | Med | **P0** |
| 4 | G05 | Unbounded scope, no MVP cut-line | High | Low | **P0** |
| 5 | G04 | Signal→Outcome loop never closes (no feedback) | High | Med | **P0** |
| 6 | G15 | Synthetic→production asserted, not designed | Medium | High | **P0** |
| 7 | G14 | Simulation isolation unspecified (contamination) | High | Med | **P0** |
| 8 | G09 | No security/RBAC/classification anywhere | High | High | **P0** |
| 9 | G13 | No via-negativa safety floor / kill switch | High | Med | **P0** |
| 10 | G06 | Risk Index has no formula/weights/validation | High | Med | **P1** |
| 11 | G08 | Root-cause/prediction methods unspecified | High | High | **P1** |
| 12 | G21 | Inter-layer contracts/idempotency undefined | High | High | **P1** |
| 13 | G17 | No named customer/job or incumbent baseline | High | Low | **P1** |
| 14 | G11 | Adversarial inputs treated as noise, not attacks | High | High | **P1** |
| 15 | G12 | Citizen data: no privacy/residency/tenancy | High | High | **P1** |
| 16 | G20 | No non-functional requirements | High | Low | **P1** |
| 17 | G07 | Confidence scores undefined & uncalibrated | Medium | Low | **P1** |
| 18 | G24 | No alert thresholds / fatigue control | High | Med | **P1** |
| 19 | G10 | No audit trail / decision lineage | Medium | Med | **P1** |
| 20 | G16 | No stock-and-flow dynamics / fidelity check | Medium | High | **P2** |
| 21 | G26 | Conversational AI hallucination risk | High | Med | **P2** |
| 22 | G18 | Multi-agency = one 'responsible agency' field | Medium | Med | **P2** |
| 23 | G19 | No public-communication layer | Medium | Med | **P2** |
| 24 | G25 | No data-quality framework | Medium | Med | **P2** |
| 25 | G22 | No failure-mode / resilience model | Medium | High | **P2** |
| 26 | G27 | No regression/deliverables/demo plan | Medium | Low | **P2** |
| 27 | G28 | Ambiguous language; adjectives not measurable | Low | Low | **P2** |
| 28 | G23 | No deployment topology / persistence | Low | Med | **P3** |

---

## 8. Recommendations — Four Waves

**Wave 1 — Make success definable & honest (before any build):** ground-truth contract (G02); evaluation instrument — Given/When/Then + weighted rubric + shared harness (G01); MVP cut-line with P0/P1/P2 tiers + timeline (G05); language fixes (G28) and a named customer + current-state baseline (G17).

**Wave 2 — Repair the operational loop:** human authority gate + Decision record (G03); close the feedback arrow (G04); via-negativa safety floor — prohibited actions, default-to-abstain, kill switch (G13); alert governance (G24).

**Wave 3 — Specify the load-bearing architecture:** mechanize simulation isolation (G14); make synthetic→production an architectural property (G15); define inter-layer contracts (G21); add NFRs (G20) and the Risk Index / root-cause / confidence methods (G06 / G08 / G07).

**Wave 4 — Make it safe & accreditable:** governance baseline — RBAC, classification (G09); audit trail + lineage (G10); input-trust model (G11); privacy/residency/tenancy (G12). Then P2/P3 items as capacity allows (G16, G26, G18, G19, G25, G22, G27, G23).

**Single most important next step:** establish the **oracle wall (G02)** and the **measurable rubric (G01)** before another line of code — without them the project can declare success while proving nothing.

---

*Methodology: 15 expert lenses — Porter, Christensen, Drucker, Godin, Kim & Mauborgne, Collins, Taleb, Meadows, Doumont, plus Systems Architect, Data/ML Engineer, Crisis-Operations, Security & Governance, Product/Delivery, and QA/V&V. Detect → consolidate → adversarially verify → prioritize. 119 raw gaps → 28 confirmed, 0 refuted.*
