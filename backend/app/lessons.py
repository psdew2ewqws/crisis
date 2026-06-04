"""Lessons Memory System — in-context learning from validated successful cases.

After validation + authorization, extract a reusable lesson (LLM JSON) and persist
to PostgreSQL ``successful_lessons`` with semantic embeddings. Retrieval injects
top lessons into recommend / narrate / debate / ask prompts.

See ``backend/LESSONS_MEMORY_SYSTEM.md`` for the full spec.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Body, Query
from pydantic import BaseModel, Field

# Primary store is Pinecone (vector DB). The lesson's embedding IS the vector;
# the full lesson lives in the vector metadata. Cosine ranking + metadata filters
# happen server-side. Falls back to the local JSON store when Pinecone is absent.
try:
    from . import lessons_pinecone as _vs
except Exception:  # pragma: no cover
    _vs = None  # type: ignore

try:
    from . import db
except Exception:  # pragma: no cover
    db = None  # type: ignore

try:
    from . import llm
except Exception:  # pragma: no cover
    llm = None  # type: ignore

try:
    from . import validate as _validate_mod
except Exception:  # pragma: no cover
    _validate_mod = None  # type: ignore

try:
    from . import mesa_sim
except Exception:  # pragma: no cover
    mesa_sim = None  # type: ignore

router = APIRouter()

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_JSON_FALLBACK = os.path.join(_DATA_DIR, "successful_lessons.json")

EMBED_DIM = int(getattr(llm, "EMBED_DIM", 768) if llm else 768)

# Recency prior for retrieval: an exponential half-life on lesson age. Crisis
# playbooks age slowly, so the default is long; env-tunable. The recency term is a
# small additive prior (weight <=0.15) with a floor, so an old-but-perfect precedent
# is down-weighted — never erased. recency = 0.5 ** (age_days / HALF_LIFE_DAYS).
try:
    HALF_LIFE_DAYS = float(os.environ.get("TEMPORAL_HALFLIFE_DAYS", "240") or "240")
except (TypeError, ValueError):
    HALF_LIFE_DAYS = 240.0

Domain = Literal["water", "public_service", "healthcare", "supply_chain", "other"]
# Outcomes split into two families. The system stores BOTH so future cases can
# learn from what worked AND from what was confirmed not to work (anti-patterns).
Outcome = Literal[
    # success family — the intervention demonstrably reduced risk
    "validated_success", "partial_success", "contained",
    # failure family — the intervention was confirmed wrong / ineffective
    "failed", "rejected", "no_improvement", "made_worse",
]
SUCCESS_OUTCOMES = frozenset({"validated_success", "partial_success", "contained"})
FAILURE_OUTCOMES = frozenset({"failed", "rejected", "no_improvement", "made_worse"})


def _classify_kind(outcome: str, worked: Optional[bool]) -> str:
    """'success' or 'failure'. An explicit ``worked`` flag wins; else infer from outcome."""
    if worked is True:
        return "success"
    if worked is False:
        return "failure"
    return "failure" if outcome in FAILURE_OUTCOMES else "success"

LESSON_SYSTEM = """You are "Crisis Lessons Extractor" — an expert analyst specialized in distilling actionable lessons from successful crisis interventions.

Your sole job is to extract ONE high-quality, reusable lesson from a validated successful case so it can serve as a reference for future similar crises.

Why we do this:
We are building a growing memory of successful interventions. In future cases the system will retrieve the most relevant past lessons and include them in the prompt. This allows the model to improve recommendation quality through in-context learning without any fine-tuning or weight updates.

Strict rules for the lesson:
- Maximum 2 sentences.
- Must be specific and actionable (not generic advice like "communicate better").
- Focus on the key reason this intervention succeeded (timing, sequence, targeting the apex, coverage of cascade effects, resource allocation, etc.).
- The lesson should help the model in future cases decide "what kind of intervention works for this type of root cause".
- Do not invent information. Base the lesson strictly on the provided case data.
- Output must be valid JSON only. No extra text before or after the JSON."""


FAILURE_SYSTEM = """You are "Crisis Lessons Extractor" — an expert analyst specialized in distilling actionable WARNINGS from interventions that were confirmed NOT to work.

Your sole job is to extract ONE high-quality, reusable anti-pattern from a case where an intervention was rejected by validation or failed to reduce risk, so it can warn the system away from the same mistake in future similar crises.

Why we do this:
We are building a growing memory of BOTH successes and failures. In future cases the system retrieves the most relevant past cases and includes them in the prompt. Failures are as valuable as successes: they tell the model what to avoid for a given type of root cause.

Strict rules for the lesson:
- Maximum 2 sentences.
- Must be specific and actionable as a warning (not generic advice).
- Focus on the key reason this intervention failed (wrong target, mis-timing, ignored cascade, insufficient coverage, treating symptoms not the apex cause, etc.).
- The lesson should help the model in future cases decide "what kind of intervention to AVOID for this type of root cause, and what to do instead".
- Do not invent information. Base the lesson strictly on the provided case data.
- Output must be valid JSON only. No extra text before or after the JSON."""


class LessonExtract(BaseModel):
    lesson_text: str = Field(..., description="1-2 sentences, specific and actionable")
    why_it_worked: str
    applicable_when: str


class FailureLessonExtract(BaseModel):
    lesson_text: str = Field(..., description="1-2 sentences, an actionable warning / anti-pattern")
    why_it_failed: str
    avoid_when: str


class ReflectIn(BaseModel):
    domain: Optional[Domain] = None
    root_cause_category: str = ""
    root_cause_details: str = ""
    intervention: str = ""
    risk_before: float = 0.0
    risk_after: float = 0.0
    outcome: Outcome = "validated_success"
    # Did the intervention actually work? Overrides outcome-based inference when set.
    # Leave None to infer from `outcome` (success vs. failure family).
    worked: Optional[bool] = None
    source_case_id: str = ""
    cluster_id: Optional[str] = None
    service: Optional[str] = None
    validation_reasons: Optional[str] = None
    outcome_notes: Optional[str] = None
    confidence: float = 0.8
    # Ingestion / backfill overrides (optional):
    ts: Optional[str] = None            # source timestamp (ISO); defaults to now()
    risk_source: Optional[str] = None   # 'simulated' | 'heuristic' | 'measured'


class SearchIn(BaseModel):
    query: str = ""
    domain: Optional[Domain] = None
    root_cause_category: Optional[str] = None
    kind: Optional[Literal["success", "failure"]] = None  # None = both
    limit: int = 5


# --------------------------------------------------------------------------- #
# IDs, slugs, domain inference                                                 #
# --------------------------------------------------------------------------- #
def _new_id() -> str:
    ts = int(time.time() * 1000)
    rnd = hashlib.sha256(f"{ts}-{os.getpid()}".encode()).hexdigest()[:10]
    return f"01{ts:x}{rnd}"[:26]


def _slug(text: str, max_len: int = 48) -> str:
    t = re.sub(r"[^\w\s-]", "", (text or "").lower())
    t = re.sub(r"[-\s]+", "_", t).strip("_")
    return (t[:max_len] or "general")


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def infer_domain(service: Optional[str] = None, label: str = "") -> Domain:
    blob = f"{service or ''} {label}".lower()
    if any(k in blob for k in ("water", "pipe", "scada", "tanker", "مياه", "شبكة")):
        return "water"
    if any(k in blob for k in ("hospital", "ed ", "health", "مستشفى", "صحة")):
        return "healthcare"
    if any(k in blob for k in ("supply", "logistics", "chain")):
        return "supply_chain"
    if service or label:
        return "public_service"
    return "other"


# --------------------------------------------------------------------------- #
# Embeddings + semantic rank                                                   #
# --------------------------------------------------------------------------- #
def _embed_text(text: str) -> List[float]:
    if llm is not None:
        try:
            vec = llm.embed(text)
            if vec:
                return vec
        except Exception:
            pass
    return _hash_embed(text)


def _embed_real(text: str) -> tuple[List[float], bool]:
    """Embed and report whether the vector is a REAL model embedding (True) or the
    deterministic hash fallback (False).

    Callers use the flag to refuse poisoning the vector store / cosine ranking with
    semantically-null hash vectors when Ollama is down — a hash query vector makes
    Pinecone return confident-looking RANDOM neighbours, which is worse than blocking.
    """
    if llm is not None:
        try:
            vec = llm.embed(text)
            if vec:
                return vec, True
        except Exception:
            pass
    return _hash_embed(text), False


def _recency_weight(ts: Any) -> float:
    """Exponential half-life recency prior in [0.3, 1.0].

    Missing or unparseable ts -> 1.0 (no-op, never raises): Pinecone returns ts as an
    ISO string, so we parse defensively. The 0.3 floor means an old-but-perfect
    precedent is down-weighted, never erased.
    """
    if not ts:
        return 1.0
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        age_days = max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 86400.0)
        return max(0.3, min(1.0, 0.5 ** (age_days / HALF_LIFE_DAYS)))
    except Exception:
        return 1.0


def _hash_embed(text: str, dim: int = EMBED_DIM) -> List[float]:
    """Deterministic fallback when Ollama embeddings are unavailable."""
    raw = (text or "").encode("utf-8")
    out = [0.0] * dim
    for i in range(dim):
        h = hashlib.sha256(raw + str(i).encode()).digest()
        out[i] = (int.from_bytes(h[:4], "big") / 2**32) * 2 - 1
    norm = math.sqrt(sum(x * x for x in out)) or 1.0
    return [x / norm for x in out]


def _cosine(a: List[float], b: List[float]) -> float:
    if not a or not b:
        return 0.0
    n = min(len(a), len(b))
    dot = sum(a[i] * b[i] for i in range(n))
    na = math.sqrt(sum(a[i] * a[i] for i in range(n))) or 1.0
    nb = math.sqrt(sum(b[i] * b[i] for i in range(n))) or 1.0
    return dot / (na * nb)


def _parse_embedding(raw: Any) -> Optional[List[float]]:
    if raw is None:
        return None
    if isinstance(raw, list):
        return [float(x) for x in raw]
    if isinstance(raw, str):
        try:
            return [float(x) for x in json.loads(raw)]
        except Exception:
            return None
    return None


def _row_to_public(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    emb = out.pop("embedding", None)
    if emb is not None:
        out["has_embedding"] = bool(_parse_embedding(emb))
    if isinstance(out.get("ts"), datetime):
        out["ts"] = out["ts"].isoformat()
    if isinstance(out.get("metadata"), str):
        try:
            out["metadata"] = json.loads(out["metadata"])
        except Exception:
            pass
    return out


# --------------------------------------------------------------------------- #
# JSON fallback store (MVP parity)                                             #
# --------------------------------------------------------------------------- #
def _json_load() -> List[dict[str, Any]]:
    try:
        with open(_JSON_FALLBACK, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _json_save(rows: List[dict[str, Any]]) -> None:
    os.makedirs(_DATA_DIR, exist_ok=True)
    with open(_JSON_FALLBACK, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=1)


def _persist(row: dict[str, Any], *, allow_vector: bool = True) -> dict[str, Any]:
    """Persist a lesson. ``allow_vector=False`` (Ollama down → hash embedding) routes
    to the JSON store ONLY, so a semantically-null vector never poisons Pinecone."""
    stored = False
    if allow_vector and _vs is not None and _vs.available():
        try:
            _vs.insert_lesson(row)
            stored = True
        except Exception:
            pass
    if not stored:
        rows = _json_load()
        # Idempotent re-ingest: drop any existing row with the same id OR the same
        # real source_case_id, so re-running the backfill overwrites instead of piling up.
        sid = row.get("source_case_id")
        rows = [
            r for r in rows
            if r.get("id") != row["id"]
            and not (sid and sid != "manual" and r.get("source_case_id") == sid)
        ]
        clean = {k: v for k, v in row.items() if k != "embedding"}
        clean["embedding"] = row.get("embedding")
        rows.insert(0, clean)
        _json_save(rows)
    return row


def _load_all(limit: int = 200) -> List[dict[str, Any]]:
    if _vs is not None and _vs.available():
        try:
            return _vs.list_lessons(limit)
        except Exception:
            pass
    return _json_load()[:limit]


# --------------------------------------------------------------------------- #
# Extraction + store                                                           #
# --------------------------------------------------------------------------- #
def _build_user_prompt(payload: ReflectIn, risk_delta: float) -> str:
    return f"""### Successful Validated Case

Domain: {payload.domain or infer_domain(payload.service, payload.root_cause_details)}
Root Cause Category: {payload.root_cause_category}
Root Cause Details: {payload.root_cause_details}
Intervention Applied: {payload.intervention}
Risk Score Before: {payload.risk_before}
Risk Score After: {payload.risk_after}
Measured Outcome / Impact: {payload.outcome_notes or f"risk delta {risk_delta:+.1f}"}
Validation Reasons: {payload.validation_reasons or "validated by AEGIS checks"}

### Task
Extract exactly ONE concise, reusable lesson from this successful intervention.

The lesson must answer: "What made this intervention effective for this type of root cause, and under what conditions would a similar approach be useful again?"

Return ONLY a valid JSON object matching this exact schema:

{{
  "lesson_text": "string (1-2 sentences maximum, specific and actionable)",
  "why_it_worked": "string (the single most important reason this worked)",
  "applicable_when": "string (brief description of the situation/type of crisis where this lesson applies)"
}}"""


def _deterministic_extract(payload: ReflectIn, risk_delta: float) -> LessonExtract:
    cat = payload.root_cause_category or "crisis"
    return LessonExtract(
        lesson_text=(
            f"For {cat}, applying «{payload.intervention[:120]}» reduced risk by "
            f"{abs(risk_delta):.0f} points when executed after validation."
        ),
        why_it_worked="The intervention targeted the dominant root-cause cluster with measurable risk reduction.",
        applicable_when=f"Similar {payload.domain or 'public_service'} crises where {cat} is the ranked apex cause.",
    )


def _build_failure_prompt(payload: ReflectIn, risk_delta: float) -> str:
    return f"""### Confirmed UNSUCCESSFUL Case

Domain: {payload.domain or infer_domain(payload.service, payload.root_cause_details)}
Root Cause Category: {payload.root_cause_category}
Root Cause Details: {payload.root_cause_details}
Intervention Attempted: {payload.intervention}
Risk Score Before: {payload.risk_before}
Risk Score After: {payload.risk_after}
Why it did NOT work / how it was confirmed wrong: {payload.outcome_notes or f"risk delta {risk_delta:+.1f} (no meaningful reduction)"}
Validation / Rejection Reasons: {payload.validation_reasons or "rejected by AEGIS checks (insufficient evidence)"}

### Task
Extract exactly ONE concise, reusable WARNING (anti-pattern) from this unsuccessful case.

The lesson must answer: "What should the model AVOID for this type of root cause, why did this approach fail, and what would have been better?"

Return ONLY a valid JSON object matching this exact schema:

{{
  "lesson_text": "string (1-2 sentences maximum, an actionable warning)",
  "why_it_failed": "string (the single most important reason this failed)",
  "avoid_when": "string (brief description of the situation/type of crisis where this approach should be avoided)"
}}"""


def _deterministic_failure_extract(payload: ReflectIn, risk_delta: float) -> FailureLessonExtract:
    cat = payload.root_cause_category or "crisis"
    return FailureLessonExtract(
        lesson_text=(
            f"For {cat}, «{payload.intervention[:120]}» did NOT reduce risk "
            f"(moved {risk_delta:+.0f} points); avoid it as the primary response."
        ),
        why_it_failed="The intervention did not address the dominant root-cause cluster, so risk failed to drop.",
        avoid_when=(
            f"Similar {payload.domain or 'public_service'} crises where {cat} is the apex cause — "
            f"prefer interventions that target the source of the cascade instead."
        ),
    )


def reflect_and_store_lesson(payload: ReflectIn) -> dict[str, Any]:
    """Extract a lesson (LLM JSON or fallback), embed, persist to DB + JSON backup.

    Stores BOTH outcomes: a ``success`` becomes a positive reference ("what worked")
    and a ``failure`` becomes an anti-pattern ("what to avoid"). The kind is taken
    from ``payload.worked`` if set, otherwise inferred from ``payload.outcome``.
    The three text columns (lesson_text / why_it_worked / applicable_when) are reused
    for both kinds; for failures they hold the warning / why-it-failed / avoid-when.
    """
    domain = payload.domain or infer_domain(payload.service, payload.root_cause_details)
    risk_delta = float(payload.risk_after) - float(payload.risk_before)
    category = payload.root_cause_category or _slug(payload.root_cause_details)
    kind = _classify_kind(payload.outcome, payload.worked)

    if kind == "failure":
        fx: Optional[FailureLessonExtract] = None
        if llm is not None:
            try:
                fx = llm.ask_json(FAILURE_SYSTEM, _build_failure_prompt(payload, risk_delta), FailureLessonExtract)
            except Exception:
                fx = None
        if fx is None:
            fx = _deterministic_failure_extract(payload, risk_delta)
        lesson_text, reason, when = fx.lesson_text, fx.why_it_failed, fx.avoid_when
    else:
        extracted: Optional[LessonExtract] = None
        if llm is not None:
            try:
                extracted = llm.ask_json(LESSON_SYSTEM, _build_user_prompt(payload, risk_delta), LessonExtract)
            except Exception:
                extracted = None
        if extracted is None:
            extracted = _deterministic_extract(payload, risk_delta)
        lesson_text, reason, when = extracted.lesson_text, extracted.why_it_worked, extracted.applicable_when

    embed_src = " ".join([
        lesson_text, reason, when,
        payload.root_cause_details, payload.intervention, category,
    ])
    embedding, embed_is_real = _embed_real(embed_src)
    risk_source = payload.risk_source or "simulated"

    row = {
        "id": _new_id(),
        "ts": payload.ts or _now_iso(),
        "kind": kind,
        "domain": domain,
        "root_cause_category": category,
        "root_cause_details": payload.root_cause_details,
        "intervention": payload.intervention,
        "risk_before": float(payload.risk_before),
        "risk_after": float(payload.risk_after),
        "risk_delta": risk_delta,
        "outcome": payload.outcome,
        "lesson_text": lesson_text,
        "why_it_worked": reason,
        "applicable_when": when,
        "source_case_id": payload.source_case_id or payload.cluster_id or "manual",
        "confidence": float(payload.confidence),
        "risk_source": risk_source,
        "embedding": embedding,
        "metadata": json.dumps({
            "cluster_id": payload.cluster_id,
            "service": payload.service,
            "risk_source": risk_source,
            "engine": "llm" if embed_is_real else "deterministic",
        }),
    }
    # Never poison Pinecone with a semantically-null hash vector (Ollama down):
    # gate the vector write on whether we got a REAL model embedding.
    _persist(row, allow_vector=embed_is_real)
    pub = _row_to_public(row)
    pub["stored"] = True
    return pub


def retrieve_relevant_lessons(
    *,
    domain: Optional[str] = None,
    root_cause_category: Optional[str] = None,
    query: Optional[str] = None,
    kind: Optional[str] = None,
    limit: int = 5,
) -> List[dict[str, Any]]:
    """Filter by domain/category (and optionally kind), then rank by cosine similarity.

    ``kind=None`` returns BOTH successes and failures so the model sees what worked
    and what to avoid; pass ``"success"`` or ``"failure"`` to restrict.
    """
    limit = max(1, min(limit, 20))

    # Build ONE query vector and track whether it is a REAL model embedding. A hash
    # query vector is NEVER sent to Pinecone — it returns confident-looking RANDOM
    # neighbours. When Ollama is down we browse by metadata filter (qvec=None) and let
    # keyword + recency carry the ranking ("grounded-keyword" mode).
    qtext = (query or "").strip() or f"{domain or ''} {root_cause_category or ''}".strip()
    qvec: Optional[List[float]] = None
    qvec_real = False
    if qtext:
        qvec, qvec_real = _embed_real(qtext)

    candidates: List[dict[str, Any]] = []
    if _vs is not None and _vs.available():
        try:
            candidates = _vs.query(
                qvec=qvec if qvec_real else None,
                domain=domain, category=root_cause_category, kind=kind, top_k=50,
            )
        except Exception:
            candidates = []
    if not candidates:
        candidates = _json_load()
        if domain:
            candidates = [c for c in candidates if c.get("domain") == domain]
        if kind:
            candidates = [c for c in candidates if (c.get("kind") or "success") == kind]
        if root_cause_category:
            cat = root_cause_category.lower()
            candidates = [
                c for c in candidates
                if cat in (c.get("root_cause_category") or "").lower()
                or cat in (c.get("root_cause_details") or "").lower()
            ]

    qtokens = {t for t in re.split(r"\W+", (query or "").lower()) if len(t) > 2}
    scored: List[tuple] = []
    for c in candidates:
        # Semantic term — REAL cosine only. JSON rows carry the raw embedding; Pinecone
        # rows carry a server-side cosine ``score``. With no real query vector, semantics
        # contribute 0 and keyword + recency carry the ranking.
        if qvec_real:
            emb = _parse_embedding(c.get("embedding"))
            sem = _cosine(qvec, emb) if emb else float(c.get("score") or 0.0)
        else:
            sem = 0.0
        kw = 0.0
        if root_cause_category:
            blob = f"{c.get('root_cause_category','')} {c.get('lesson_text','')} {c.get('root_cause_details','')}".lower()
            if root_cause_category.lower() in blob:
                kw += 0.25
        if not qvec_real and qtokens:
            blob = (
                f"{c.get('lesson_text','')} {c.get('root_cause_details','')} "
                f"{c.get('intervention','')} {c.get('root_cause_category','')}"
            ).lower()
            hits = sum(1 for t in qtokens if t in blob)
            kw += 0.35 * (hits / len(qtokens))
        recency = _recency_weight(c.get("ts"))
        score = (
            sem * 0.60
            + recency * 0.15
            + float(c.get("confidence") or 0.5) * 0.10
            + kw
            + (0.05 if c.get("domain") == domain else 0.0)
        )
        scored.append((score, c))
    scored.sort(key=lambda x: -x[0])
    out = []
    for sc, c in scored[:limit]:
        pub = _row_to_public(c)
        pub["relevance"] = round(float(sc), 4)   # blended score, for downstream confidence
        out.append(pub)
    if not out and candidates:
        out = [_row_to_public(c) for c in candidates[:limit]]
    return out


def format_lessons_for_prompt(lessons: List[dict[str, Any]]) -> str:
    if not lessons:
        return ""
    lines = [
        "Relevant past cases — learn from what WORKED (✓) and what to AVOID (✗) "
        "when formulating your recommendation:"
    ]
    for i, L in enumerate(lessons[:5], 1):
        is_fail = (L.get("kind") or "success") == "failure"
        tag = "✗ FAILED — AVOID" if is_fail else "✓ WORKED"
        reason_label = "Why it failed" if is_fail else "Why it worked"
        when_label = "Avoid when" if is_fail else "Applicable when"
        lines.append(f"\n{i}. [{tag}] {L.get('lesson_text','')}")
        lines.append(f"   {reason_label}: {L.get('why_it_worked','')}")
        lines.append(f"   {when_label}: {L.get('applicable_when','')}")
    return "\n".join(lines)


def lessons_context_block(
    *,
    domain: Optional[str] = None,
    root_cause_category: Optional[str] = None,
    query: Optional[str] = None,
    kind: Optional[str] = None,
    limit: int = 4,
) -> str:
    hits = retrieve_relevant_lessons(
        domain=domain,
        root_cause_category=root_cause_category,
        query=query,
        kind=kind,
        limit=limit,
    )
    return format_lessons_for_prompt(hits)


# --------------------------------------------------------------------------- #
# Pipeline hook: decision → reflect                                            #
# --------------------------------------------------------------------------- #
_AUTHORIZED = frozenset({"approved", "authorized", "done"})


def _cluster_meta(cluster_id: str) -> dict[str, Any]:
    if db is None or not cluster_id:
        return {}
    try:
        row = db.fetchone("""
            SELECT cluster_id, canonical_label_ar, canonical_label_en,
                   severity_avg, member_count
            FROM ril_problem_clusters WHERE cluster_id = %(cid)s
        """, {"cid": cluster_id})
        return row or {}
    except Exception:
        return {}


def _risk_from_simulation(cluster_id: str, service: Optional[str]) -> tuple[float, float, str]:
    if mesa_sim is None:
        return 70.0, 35.0, "estimated from default propagation curve"
    try:
        case = service or None
        sim = mesa_sim.simulate(case, intervene=True, intervention_node=f"cluster:{cluster_id}")
        b_series = (sim.get("before") or {}).get("series") or []
        a_series = (sim.get("after") or {}).get("series") or []
        b_last = b_series[-1] if b_series else {}
        a_last = a_series[-1] if a_series else {}
        rb = float(b_last.get("mean_negativity", 0.75)) * 100
        ra = float(a_last.get("mean_negativity", 0.30)) * 100
        note = sim.get("note") or "Mesa agent-based propagation with intervention"
        return rb, ra, note
    except Exception:
        return 70.0, 35.0, "fallback risk estimate"


def maybe_reflect_from_decision(decision: dict[str, Any]) -> Optional[dict[str, Any]]:
    """After authorized decision + valid validation, extract and store a lesson."""
    status = str(decision.get("status") or "").lower()
    if status not in _AUTHORIZED:
        return None
    cluster_id = decision.get("cluster_id") or ""
    if not cluster_id:
        return None

    validation_reasons = ""
    confidence = 0.75
    verdict = "valid"
    if _validate_mod is not None:
        try:
            v = _validate_mod.validate_case(cluster_id, decision.get("service"))
            verdict = str(v.get("verdict") or "").lower()
            validation_reasons = "; ".join(
                f"{c.get('name')}: {c.get('detail')}" for c in (v.get("checks") or [])[:4]
                if isinstance(c, dict)
            )
            confidence = float(v.get("confidence") or confidence)
        except Exception:
            return None

    meta = _cluster_meta(cluster_id)
    label_ar = meta.get("canonical_label_ar") or decision.get("label") or ""
    label_en = meta.get("canonical_label_en") or ""
    details = f"{label_en or label_ar} · {meta.get('member_count', 0)} clustered reports"
    category = _slug(label_en or label_ar or cluster_id[:12])
    rb, ra, note = _risk_from_simulation(cluster_id, decision.get("service"))
    risk_delta = ra - rb

    # Decide success vs. failure from the GROUNDED signals (verdict + simulation),
    # then store EITHER way. A confirmed-wrong case is as valuable as a win: it
    # becomes a retrievable anti-pattern instead of being silently discarded.
    if verdict == "insufficient":
        worked, outcome = False, "rejected"
        note = f"Validation rejected this root cause (insufficient evidence). {note}"
    elif risk_delta >= -1.0:  # simulation showed no meaningful risk reduction
        worked, outcome = False, "no_improvement"
        note = f"Simulation showed no meaningful risk reduction (delta {risk_delta:+.1f}). {note}"
    else:
        worked = True
        outcome = "validated_success" if confidence >= 0.65 else "partial_success"

    payload = ReflectIn(
        domain=infer_domain(decision.get("service"), details),
        root_cause_category=category,
        root_cause_details=details,
        intervention=decision.get("action") or decision.get("title") or "",
        risk_before=rb,
        risk_after=ra,
        outcome=outcome,  # type: ignore[arg-type]
        worked=worked,
        source_case_id=decision.get("id") or cluster_id,
        cluster_id=cluster_id,
        service=decision.get("service"),
        validation_reasons=validation_reasons,
        outcome_notes=note,
        confidence=confidence,
    )
    try:
        return reflect_and_store_lesson(payload)
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# Seed records (spec example + bootstrap)                                      #
# --------------------------------------------------------------------------- #
_SEED_EXAMPLE = {
    "domain": "water",
    "root_cause_category": "trunk_main_rupture",
    "root_cause_details": (
        "PIPE-ZN-44 pressure drop causing cascade to hospital ED overload "
        "and +320% 911 surge"
    ),
    "intervention": (
        "Immediate isolation of valve V-12 + activation of bypass B-3 + "
        "dispatch of 4 tankers to affected zones"
    ),
    "risk_before": 84.0,
    "risk_after": 22.0,
    "outcome": "validated_success",
    "lesson_text": (
        "Directly targeting the upstream infrastructure failure with isolation + "
        "immediate alternative supply (bypass + tankers) was far more effective than "
        "attempting to mitigate downstream symptoms (911 surge and hospital load)."
    ),
    "why_it_worked": (
        "The intervention stopped the cascade at its source before secondary effects "
        "fully propagated, while simultaneously providing rapid coverage to the affected population."
    ),
    "applicable_when": (
        "Critical infrastructure failures that create multi-domain cascades "
        "(water + health + mobility) where quick containment at the apex plus "
        "temporary redundant capacity is feasible."
    ),
    "source_case_id": "INC-ZARQA-2026-05",
    "confidence": 0.87,
}

# A confirmed anti-pattern: the symptom-chasing approach that did NOT work, so the
# system ships knowing both what to do and what to avoid for the same crisis type.
_FAILURE_SEED_EXAMPLE = {
    "domain": "water",
    "root_cause_category": "trunk_main_rupture",
    "root_cause_details": (
        "PIPE-ZN-44 pressure drop causing cascade to hospital ED overload "
        "and +320% 911 surge"
    ),
    "intervention": (
        "Surged extra 911 dispatchers and added hospital ED beds while leaving "
        "the ruptured trunk main unaddressed"
    ),
    "risk_before": 84.0,
    "risk_after": 80.0,
    "outcome": "no_improvement",
    "lesson_text": (
        "Do NOT respond to an upstream infrastructure rupture by scaling downstream "
        "symptom capacity (more dispatchers / ED beds); risk barely moved while the "
        "source kept feeding the cascade."
    ),
    "why_it_worked": (  # stored as 'why it failed' for failure rows
        "It treated symptoms instead of the apex cause, so the rupture kept "
        "propagating and the added capacity was overwhelmed."
    ),
    "applicable_when": (  # stored as 'avoid when' for failure rows
        "Any multi-domain cascade driven by a single upstream infrastructure failure — "
        "contain the source first; downstream capacity alone will not reduce risk."
    ),
    "source_case_id": "INC-ZARQA-2026-05-FAILED-ATTEMPT",
    "confidence": 0.82,
}


def _seed_row(example: dict[str, Any], kind: str) -> dict[str, Any]:
    risk_delta = float(example["risk_after"]) - float(example["risk_before"])
    embed_src = " ".join([
        example["lesson_text"], example["why_it_worked"],
        example["applicable_when"], example["root_cause_details"],
    ])
    return {
        "id": _new_id(),
        "ts": _now_iso(),
        "kind": kind,
        "domain": example["domain"],
        "root_cause_category": example["root_cause_category"],
        "root_cause_details": example["root_cause_details"],
        "intervention": example["intervention"],
        "risk_before": float(example["risk_before"]),
        "risk_after": float(example["risk_after"]),
        "risk_delta": risk_delta,
        "outcome": example["outcome"],
        "lesson_text": example["lesson_text"],
        "why_it_worked": example["why_it_worked"],
        "applicable_when": example["applicable_when"],
        "source_case_id": example["source_case_id"],
        "confidence": example["confidence"],
        "embedding": _embed_text(embed_src),
        "metadata": json.dumps({"seed": True, "kind": kind}),
    }


def seed_bootstrap(force: bool = False) -> dict[str, Any]:
    """Ensure schema and insert one success + one failure example if the store is empty."""
    if _vs is not None and _vs.available():
        info = _vs.ensure_schema()
        if not info.get("ok"):
            return info
        if not force and (info.get("count") or 0) > 0:
            return {"ok": True, "seeded": 0, "count": info["count"], "message": "already populated"}
    elif _json_load() and not force:
        return {"ok": True, "seeded": 0, "message": "json store already populated"}

    # Pre-written lesson text (skip LLM) for deterministic seeds — one of each kind.
    rows = [
        _seed_row(_SEED_EXAMPLE, "success"),
        _seed_row(_FAILURE_SEED_EXAMPLE, "failure"),
    ]
    for row in rows:
        _persist(row)
    return {"ok": True, "seeded": len(rows), "lesson_ids": [r["id"] for r in rows]}


def stats() -> dict[str, Any]:
    count = 0
    success_count = 0
    failure_count = 0
    backend = "none"
    if _vs is not None and _vs.available():
        try:
            c = _vs.counts()
            count = c.get("total", 0)
            success_count = c.get("success", 0)
            failure_count = c.get("failure", 0)
            backend = "pinecone"
        except Exception:
            pass
    if count == 0 and backend != "pinecone":
        rows = _json_load()
        count = len(rows)
        if count:
            backend = "json_fallback"
            success_count = sum(1 for r in rows if (r.get("kind") or "success") == "success")
            failure_count = sum(1 for r in rows if (r.get("kind") or "success") == "failure")
    return {
        "ok": True,
        "count": count,
        "success_count": success_count,
        "failure_count": failure_count,
        "backend": backend,
        "embed_model": getattr(llm, "EMBED_MODEL", "nomic-embed-text") if llm else "nomic-embed-text",
        "embed_dim": EMBED_DIM,
    }


# --------------------------------------------------------------------------- #
# Routes                                                                       #
# --------------------------------------------------------------------------- #
@router.get("/api/lessons")
def get_lessons(limit: int = Query(20, ge=1, le=100)) -> dict[str, Any]:
    try:
        if stats().get("count", 0) == 0:
            seed_bootstrap(force=False)
    except Exception:
        pass
    rows = [_row_to_public(r) for r in _load_all(limit)]
    return {"ok": True, "lessons": rows, **stats()}


@router.get("/api/lessons/search")
def search_lessons(
    q: Optional[str] = Query(default=None),
    domain: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    kind: Optional[str] = Query(default=None, description="success | failure | (omit for both)"),
    limit: int = Query(5, ge=1, le=20),
) -> dict[str, Any]:
    hits = retrieve_relevant_lessons(
        domain=domain,  # type: ignore[arg-type]
        root_cause_category=category,
        query=q,
        kind=kind,
        limit=limit,
    )
    return {"ok": True, "query": q, "lessons": hits}


@router.post("/api/lessons/search")
def post_search(body: SearchIn) -> dict[str, Any]:
    hits = retrieve_relevant_lessons(
        domain=body.domain,
        root_cause_category=body.root_cause_category,
        query=body.query,
        kind=body.kind,
        limit=body.limit,
    )
    return {"ok": True, "lessons": hits}


@router.post("/api/lessons/reflect")
def post_reflect(body: ReflectIn) -> dict[str, Any]:
    return {"ok": True, "lesson": reflect_and_store_lesson(body)}


@router.post("/api/lessons/seed")
def post_seed(force: bool = Query(False)) -> dict[str, Any]:
    return seed_bootstrap(force=force)


@router.post("/api/lessons/schema")
def post_schema() -> dict[str, Any]:
    if _vs is None or not _vs.available():
        return {"ok": False, "error": "PINECONE_API_KEY not configured"}
    return _vs.ensure_schema()


__all__ = [
    "router",
    "reflect_and_store_lesson",
    "retrieve_relevant_lessons",
    "format_lessons_for_prompt",
    "lessons_context_block",
    "maybe_reflect_from_decision",
    "seed_bootstrap",
    "stats",
]