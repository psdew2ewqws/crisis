# Lessons Memory System (In-Context Learning)

**Goal**: Allow Gemma 4 26B (via Ollama) to improve over time by referencing past interventions — both the ones that **worked** and the ones that were **confirmed wrong** — **without any fine-tuning**.

The model does **not** learn weights. Instead, we build a growing, queryable memory of cases. When the system faces a new crisis, it retrieves the most relevant past lessons and injects them into the prompt as high-quality references. This is classic **in-context learning + case-based reasoning**.

> **Implemented behavior (extends the original success-only spec):** the store keeps **two kinds** of lesson — `success` ("what worked") and `failure` ("what to avoid", an anti-pattern). Nothing is stored until the outcome is *confirmed* by the grounded engines (validation verdict + simulation risk delta). On retrieval, the top 3–5 most relevant cases are returned **mixed**, each tagged `✓ WORKED` or `✗ FAILED — AVOID`, so the model learns equally from wins and mistakes. See §8.

This document contains:
- The exact English prompt used for lesson extraction
- The structured data schema
- Storage strategy (MVP → production)
- How to integrate retrieval into the pipeline

---

## 1. Why This Exists

During the pipeline, after a solution is **validated** and produces a clear positive outcome (risk reduction, successful containment, validated simulation), we want to extract a concise, reusable **lesson**.

This lesson becomes a reference for future similar cases. Over time the system becomes smarter at recommending interventions because it has seen "what worked before in comparable situations".

**Core Principle (aligned with AEGIS grounded AI philosophy)**:
- Facts, numbers, root cause ranking, and validation scores → come from deterministic engines (graph traversal, PyRCA, simulation, risk index).
- The LLM only **phrases** and **reasons over references** — it never invents facts.

---

## 2. The English Prompt (for Gemma via Ollama)

Use this prompt with `ask_json()` (strict JSON mode + Pydantic validation).

### System Prompt

```text
You are "Crisis Lessons Extractor" — an expert analyst specialized in distilling actionable lessons from successful crisis interventions.

Your sole job is to extract ONE high-quality, reusable lesson from a validated successful case so it can serve as a reference for future similar crises.

Why we do this:
We are building a growing memory of successful interventions. In future cases the system will retrieve the most relevant past lessons and include them in the prompt. This allows the model to improve recommendation quality through in-context learning without any fine-tuning or weight updates.

Strict rules for the lesson:
- Maximum 2 sentences.
- Must be specific and actionable (not generic advice like "communicate better").
- Focus on the key reason this intervention succeeded (timing, sequence, targeting the apex, coverage of cascade effects, resource allocation, etc.).
- The lesson should help the model in future cases decide "what kind of intervention works for this type of root cause".
- Do not invent information. Base the lesson strictly on the provided case data.
- Output must be valid JSON only. No extra text before or after the JSON.
```

### User Prompt Template

```text
### Successful Validated Case

Domain: {domain}
Root Cause Category: {root_cause_category}
Root Cause Details: {root_cause_details}
Intervention Applied: {intervention}
Risk Score Before: {risk_before}
Risk Score After: {risk_after}
Measured Outcome / Impact: {outcome_notes}
Validation Reasons: {validation_reasons}

### Task
Extract exactly ONE concise, reusable lesson from this successful intervention.

The lesson must answer: "What made this intervention effective for this type of root cause, and under what conditions would a similar approach be useful again?"

Return ONLY a valid JSON object matching this exact schema:

{
  "lesson_text": "string (1-2 sentences maximum, specific and actionable)",
  "why_it_worked": "string (the single most important reason this worked)",
  "applicable_when": "string (brief description of the situation/type of crisis where this lesson applies)"
}
```

---

## 3. Output Schema (Pydantic)

```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Literal

class SuccessfulLesson(BaseModel):
    id: str = Field(..., description="ULID")
    timestamp: datetime
    domain: Literal["water", "public_service", "healthcare", "supply_chain", "other"]
    root_cause_category: str          # e.g. "trunk_main_rupture", "service_fee_delay", "hospital_overload"
    root_cause_details: str
    intervention: str
    risk_before: float
    risk_after: float
    risk_delta: float
    outcome: Literal["validated_success", "partial_success", "contained"]
    lesson_text: str
    why_it_worked: str
    applicable_when: str
    source_case_id: str
    confidence: float = 0.8
    embedding: Optional[list[float]] = None   # 768-dim from nomic-embed-text (future use)
```

---

## 4. Example Stored Record (JSON)

```json
{
  "id": "01JXYZABC1234567890",
  "timestamp": "2026-06-02T09:45:12Z",
  "domain": "water",
  "root_cause_category": "trunk_main_rupture",
  "root_cause_details": "PIPE-ZN-44 pressure drop causing cascade to hospital ED overload and +320% 911 surge",
  "intervention": "Immediate isolation of valve V-12 + activation of bypass B-3 + dispatch of 4 tankers to affected zones",
  "risk_before": 84.0,
  "risk_after": 22.0,
  "risk_delta": -62.0,
  "outcome": "validated_success",
  "lesson_text": "Directly targeting the upstream infrastructure failure with isolation + immediate alternative supply (bypass + tankers) was far more effective than attempting to mitigate downstream symptoms (911 surge and hospital load).",
  "why_it_worked": "The intervention stopped the cascade at its source before secondary effects fully propagated, while simultaneously providing rapid coverage to the affected population.",
  "applicable_when": "Critical infrastructure failures that create multi-domain cascades (water + health + mobility) where quick containment at the apex plus temporary redundant capacity is feasible.",
  "source_case_id": "INC-ZARQA-2026-05",
  "confidence": 0.87
}
```

---

## 5. Storage Strategy

### Phase 1 – MVP (Recommended to start here)

- File: `backend/data/successful_lessons.json`
- Simple append-only list of the records above.
- Extremely fast to implement, easy to inspect, no database migration needed initially.
- Sufficient for the first 100–300 successful cases.

### Phase 2 – Production

- Create a new PostgreSQL table: `successful_lessons`
- Columns:
  - `id` (ULID, PK)
  - `timestamp`
  - `kind` (`success` | `failure`) ← see §8
  - `domain`
  - `root_cause_category`
  - `root_cause_details` (text)
  - `intervention` (text)
  - `risk_before`, `risk_after`, `risk_delta`
  - `outcome`
  - `lesson_text` (text)
  - `why_it_worked` (text)
  - `applicable_when` (text)
  - `source_case_id`
  - `confidence`
  - `embedding` (vector(768)) ← for semantic search later
- Use `JSONB` for flexible metadata if needed.

---

## 6. Integration into the Pipeline

### When to extract and store the lesson

Call the reflection function **after**:
- The `validate` stage succeeds, **and**
- A decision is recorded (either human authorization or auto-approved in 100% AI mode)

Best place: at the end of the `learn` node in the LangGraph swarm, or immediately after `POST /api/decisions`.

### When to retrieve and use lessons

In these nodes (before calling the LLM):
- `recommend_node`
- `narrate_node`
- `debate_node`
- `ask_node` (Deep Analysis)

**Retrieval logic (MVP)**:
1. Filter by `domain`
2. Filter by similar `root_cause_category` (exact or fuzzy match)
3. (Later) Add embedding cosine similarity using `nomic-embed-text`
4. Return top 3–5 most relevant lessons

**Prompt injection example**:

```text
Relevant past successful cases (use these as reference when formulating your recommendation):

1. [lesson_text]
   Why it worked: [why_it_worked]
   Applicable when: [applicable_when]

2. ...
```

---

## 7. Benefits

- No fine-tuning required
- Fully grounded (lessons are always tied to real validated outcomes)
- Improves over time as more successful cases are added
- Transparent and auditable (you can inspect every stored lesson)
- Works with the existing `ask_json` + Pydantic pattern already used in the project
- Compatible with the current "LLM only narrates" philosophy

---

## 8. Storing Failures (Anti-Patterns) — *implemented*

Successes alone are half the signal. A confirmed-wrong intervention is just as
valuable: it tells the model what **not** to do for a given root cause. The store
therefore keeps both, distinguished by a `kind` column (`success` | `failure`).

**Confirm before storing** (the user's hard requirement — only store once the
outcome is verified, never a guess). The auto-hook `maybe_reflect_from_decision`
classifies from grounded signals, not the LLM:

| Grounded signal | Stored as | `outcome` |
|---|---|---|
| Validation verdict `insufficient` | `failure` | `rejected` |
| Validated, but simulation risk Δ ≥ −1 (no real drop) | `failure` | `no_improvement` |
| Validated **and** simulation shows a real risk reduction | `success` | `validated_success` / `partial_success` |

You can also record either kind explicitly via `POST /api/lessons/reflect` by
setting `outcome` to a failure value (`failed`, `rejected`, `no_improvement`,
`made_worse`) or by passing `"worked": false` (which overrides outcome inference).

**Failure extraction** uses a dedicated `FAILURE_SYSTEM` prompt that produces an
anti-pattern: `{ lesson_text (the warning), why_it_failed, avoid_when }`. These map
onto the same three text columns as successes, relabeled on output.

**Retrieval & prompt injection.** `retrieve_relevant_lessons(..., kind=None)`
returns **both** kinds ranked together (top 3–5); pass `kind="success"` or
`kind="failure"` to restrict. `GET|POST /api/lessons/search` accept the same
`kind` filter. The injected block tags each case so the model sees the contrast:

```text
Relevant past cases — learn from what WORKED (✓) and what to AVOID (✗):

1. [✓ WORKED] Isolate the upstream rupture + bypass + tankers …
   Why it worked: stopped the cascade at its source …
   Applicable when: multi-domain cascades from one infrastructure failure …

2. [✗ FAILED — AVOID] Scaling downstream 911/ED capacity while the trunk main
   stayed ruptured did NOT reduce risk …
   Why it failed: treated symptoms, not the apex cause …
   Avoid when: any cascade driven by a single upstream failure …
```

`GET /api/lessons` and `stats()` report `success_count` and `failure_count`.

---

## Next Steps for Implementation

1. Create `backend/app/lessons.py` with:
   - `reflect_and_store_lesson(...)`
   - `retrieve_relevant_lessons(...)`
2. Add the reflection call after successful validation/decision.
3. Modify the relevant swarm nodes to retrieve and inject lessons into prompts.
4. Start with JSON file storage, migrate to PostgreSQL table when volume grows.

This system turns every validated successful intervention into a permanent improvement to the quality of future recommendations.
