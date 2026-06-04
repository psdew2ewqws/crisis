"""Dedupe + Reciprocal Rank Fusion. RANK-based (k=60) — never average raw BM25/cosine/
citation scales. Pure stdlib (difflib-free; normalized-token + DOI/title keys)."""
from __future__ import annotations

import re
from typing import Any, Dict, List


def _norm_title(t: Any) -> str:
    return re.sub(r"\W+", " ", (t or "").lower()).strip() if isinstance(t, str) else ""


def _key(it: Dict[str, Any]) -> str:
    return (it.get("doi") or "").lower().strip() or _norm_title(it.get("title")) or str(it.get("id") or id(it))


def dedupe(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen, out = set(), []
    for it in items:
        k = _key(it)
        if k in seen:
            continue
        seen.add(k)
        out.append(it)
    return out


def rrf(ranked_lists: List[List[Dict[str, Any]]], k: int = 60) -> List[Dict[str, Any]]:
    """Reciprocal Rank Fusion across several ranked result lists."""
    score: Dict[str, float] = {}
    ref: Dict[str, Dict[str, Any]] = {}
    for lst in ranked_lists:
        for rank, it in enumerate(lst or []):
            key = _key(it)
            score[key] = score.get(key, 0.0) + 1.0 / (k + rank + 1)
            ref.setdefault(key, it)
    return sorted(ref.values(), key=lambda it: -score[_key(it)])
