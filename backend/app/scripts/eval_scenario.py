"""Phase 5 — leave-one-out backtest for the scenario engine.

This is what separates "it RUNS" (the per-stage smoke checks) from "it PREDICTS". For K
held-out cases it HIDES each case (removes it from the retrieval corpus), runs retrieval
on that case's own problem text, and scores how well the engine reconstructs it:

  • hit@1 / hit@3 — does a retrieved precedent share the case's root_cause_category or
    domain? (the core CBR question: do we surface analogous cases)
  • outcome-family agreement — does the modal kind (success/failure) of the retrieved
    precedents match the held-out case's actual kind?
  • relevance separation — mean blended relevance of hits vs misses (a calibration proxy:
    a useful retriever scores true analogs higher than spurious ones).

HONEST LIMITS (printed in the report, never silently hidden):
  • The seeded corpus carries HEURISTIC risk and has NO ground-truth "did it escalate"
    label, so escalation precision/recall is reported as n/a until RETAIN accumulates
    real, acted-on outcomes. hit@k + outcome-agreement are the defensible v1 metrics.
  • With Ollama DOWN retrieval is keyword-only; semantic hit@k will be materially higher
    once Ollama is up. The engine mode is printed so a low score is read in context.

Run:  python -m app.scripts.eval_scenario [--k 12]
Gate: only claim "predicts" when hit@3 clears the floor you choose AND the relevance
      separation is positive (hits score higher than misses).
"""
from __future__ import annotations

import argparse
import json
import statistics
from typing import Any, Dict, List

from app import lessons


def _same_type(a: dict, b: dict) -> bool:
    """A genuine analog shares the root_cause_category (e.g. one 'flood' retrieving other
    'flood' cases). Domain alone is too coarse — most seeded cases share a domain, which
    would make hit@k trivially 1.0 and meaningless."""
    ca, cb = a.get("root_cause_category"), b.get("root_cause_category")
    return bool(ca and cb and ca == cb)


def evaluate(k: int = 12, top_k: int = 5) -> Dict[str, Any]:
    all_rows = lessons._json_load()
    usable = [r for r in all_rows if (r.get("root_cause_details") or r.get("lesson_text"))
              and r.get("source_case_id")]
    sample = usable[: max(1, min(k, len(usable)))]
    engine = "llm" if (lessons.llm and lessons.llm.available()) else "grounded-keyword"

    orig_loader = lessons._json_load
    hit1 = hit3 = outcome_ok = 0
    hit_rels: List[float] = []
    miss_rels: List[float] = []
    per_case: List[dict] = []
    try:
        for c in sample:
            cid = c.get("source_case_id")
            loo = [r for r in all_rows if r.get("source_case_id") != cid]
            lessons._json_load = (lambda rows: (lambda: rows))(loo)  # leave-one-out

            query = c.get("root_cause_details") or c.get("lesson_text") or ""
            retr = lessons.retrieve_relevant_lessons(query=query, domain=None, limit=top_k)
            retr = [r for r in retr if r.get("source_case_id") != cid]

            matches = [i for i, r in enumerate(retr) if _same_type(r, c)]
            h1 = bool(matches and matches[0] == 0)
            h3 = bool(any(i < 3 for i in matches))
            hit1 += int(h1)
            hit3 += int(h3)
            for i, r in enumerate(retr):
                (hit_rels if i in matches else miss_rels).append(float(r.get("relevance") or 0.0))

            kinds = [(r.get("kind") or "success") for r in retr]
            pred_kind = max(set(kinds), key=kinds.count) if kinds else None
            ok = (pred_kind == (c.get("kind") or "success"))
            outcome_ok += int(ok)

            per_case.append({
                "source_case_id": cid, "kind": c.get("kind"),
                "hit@1": h1, "hit@3": h3, "pred_kind": pred_kind, "outcome_ok": ok,
            })
    finally:
        lessons._json_load = orig_loader

    n = len(sample)
    mean_hit = round(sum(hit_rels) / len(hit_rels), 4) if hit_rels else None
    mean_miss = round(sum(miss_rels) / len(miss_rels), 4) if miss_rels else None
    sep = round((mean_hit - mean_miss), 4) if (mean_hit is not None and mean_miss is not None) else None
    return {
        "engine": engine,
        "n": n,
        "hit@1": round(hit1 / n, 3) if n else 0,
        "hit@3": round(hit3 / n, 3) if n else 0,
        "outcome_family_agreement": round(outcome_ok / n, 3) if n else 0,
        "relevance_hits_mean": mean_hit,
        "relevance_misses_mean": mean_miss,
        "relevance_separation": sep,
        "escalation_precision_recall": "n/a — seeded corpus has no ground-truth escalation labels; "
                                       "accrues via RETAIN of real acted-on outcomes",
        "per_case": per_case,
    }


if __name__ == "__main__":  # pragma: no cover
    ap = argparse.ArgumentParser(description="Leave-one-out backtest for the scenario engine.")
    ap.add_argument("--k", type=int, default=12)
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    rep = evaluate(k=args.k, top_k=args.top_k)
    pc = rep.pop("per_case")
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    if args.verbose:
        for r in pc:
            print("  ", json.dumps(r, ensure_ascii=False))
