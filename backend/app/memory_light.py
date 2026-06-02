"""LightMem-AEGIS — a lightweight, Arabic-first adaptation of LightMem
(ICLR 2026, zjunlp · arXiv:2510.18866) to the voc360 crisis brain.

The paper's three-stage cognitive memory, re-implemented WITHOUT its heavy
dependencies (no LLMLingua-2 BERT, no qdrant, no torch) so it runs on this
lightweight, read-only-DB, local-Ollama, no-GPU stack:

  • Light1 — Sensory memory: lightweight COMPRESSION (drop off-topic / duplicate
    citizen segments by vocabulary relevance, the paper's noise filtering) +
    TOPIC SEGMENTATION (group segments by their dominant sub-theme, reusing the
    existing Arabic sub-theme extractor instead of attention boundaries).
  • Light2 — Short-term memory: CONSOLIDATE each topic group into one structured,
    Arabic-first memory entry (summary + representative quotes + keywords).
  • Light3 — Long-term memory with sleep-time update: an OFFLINE-built JSON store
    (decoupled from inference) with SOFT updates (append/merge, never overwrite,
    so global information is preserved) + HYBRID retrieval (BM25-lite keyword +
    char-ngram embedding) that injects COMPACT summaries — not raw text — into
    the debate / ask / proof prompts. This both fixes topic-mixing noise and
    cuts prompt tokens for the slow local model.

Public surface:
  rebuild(top_n)                      -> dict     build/refresh the LTM store (offline)
  memory_for_cluster(cluster_id, k)   -> list     consolidated entries for a cluster
  retrieve(query, cluster_id, limit)  -> list     hybrid retrieval of entries
  stats()                             -> dict     store health
  router                                          GET /api/memory · POST /api/memory/rebuild
"""
from __future__ import annotations

import json
import math
import os
import time
from typing import Any, Dict, List, Optional, Set

from fastapi import APIRouter, Query
from pydantic import BaseModel

from . import db  # noqa: F401  (read-only; kept for parity / future use)

try:
    from . import whys
except Exception:  # pragma: no cover
    whys = None  # type: ignore
try:
    from . import rootcause
except Exception:  # pragma: no cover
    rootcause = None  # type: ignore
try:
    from . import llm
except Exception:  # pragma: no cover
    llm = None  # type: ignore

router = APIRouter()

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_STORE = os.path.join(_DATA_DIR, "memory_light.json")

# Hyperparameters (mirroring the paper's knobs, scoped to segment granularity).
RELEVANCE_MIN = 1        # min shared dominant-vocab terms to keep a segment (Light1 compression)
DEDUP_JACCARD = 0.82     # near-duplicate segment threshold (Light1 compression)
MAX_TOPICS = 8           # topic groups kept per cluster (Light1 segmentation)
QUOTES_PER_TOPIC = 2     # representative quotes per consolidated entry (Light2)
SEGMENTS_PER_CLUSTER = 200


# =========================================================================== #
# Tokenisation helpers (reuse the Arabic-aware tokenizer from whys).          #
# =========================================================================== #
def _tok(text: Optional[str]) -> List[str]:
    if not text or whys is None:
        return []
    try:
        return whys._tokenize(text)
    except Exception:
        return [t for t in str(text).split() if len(t) > 2]


def _tokset(text: Optional[str]) -> Set[str]:
    return set(_tok(text))


def _jaccard(a: Set[str], b: Set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _char_ngrams(text: str, n: int = 3) -> Set[str]:
    s = "".join(ch for ch in (text or "") if not ch.isspace())
    return {s[i:i + n] for i in range(max(0, len(s) - n + 1))}


def _ngram_cosine(a: str, b: str) -> float:
    A, B = _char_ngrams(a), _char_ngrams(b)
    if not A or not B:
        return 0.0
    inter = len(A & B)
    return inter / math.sqrt(len(A) * len(B))


# =========================================================================== #
# Light1 — Sensory: compression (relevance filter + dedup) + topic grouping.  #
# =========================================================================== #
def _compress_and_group(cluster_id: str) -> List[Dict[str, Any]]:
    """Return topic groups: [{topic, terms, segments:[{text,confidence}]}].

    1. fetch member segments (most-representative first),
    2. derive the cluster's dominant vocabulary (sub-themes),
    3. COMPRESS: drop segments that share no dominant term (off-topic noise) and
       drop near-duplicates,
    4. SEGMENT: assign each kept segment to the dominant sub-theme it contains.
    """
    if whys is None:
        return []
    try:
        rows = whys._fetch_member_segments(cluster_id, limit=SEGMENTS_PER_CLUSTER)
    except Exception:
        rows = []
    texts = [r.get("segment_text") for r in rows if r.get("segment_text")]
    if not texts:
        return []

    # dominant vocabulary of the cluster (the "topics")
    try:
        themes = whys.extract_subthemes(texts, n=MAX_TOPICS, ngram=1)
    except Exception:
        themes = []
    topic_terms = [t.get("term") for t in themes if t.get("term")]
    dominant: Set[str] = set(topic_terms)
    if not dominant:
        # fall back: most frequent tokens overall
        freq: Dict[str, int] = {}
        for tx in texts:
            for w in _tokset(tx):
                freq[w] = freq.get(w, 0) + 1
        dominant = {w for w, _ in sorted(freq.items(), key=lambda kv: -kv[1])[:MAX_TOPICS]}
        topic_terms = list(dominant)

    # COMPRESS: relevance filter + dedup
    kept: List[Dict[str, Any]] = []
    seen: List[Set[str]] = []
    for r in rows:
        tx = r.get("segment_text")
        if not tx:
            continue
        ts = _tokset(tx)
        if len(ts & dominant) < RELEVANCE_MIN:
            continue  # off-topic noise → dropped (compression)
        if any(_jaccard(ts, prev) >= DEDUP_JACCARD for prev in seen):
            continue  # near-duplicate → dropped (compression)
        seen.append(ts)
        kept.append({"text": tx, "confidence": r.get("confidence"), "tokset": ts})

    # SEGMENT: group kept segments under the strongest dominant term they contain
    groups: Dict[str, Dict[str, Any]] = {}
    for seg in kept:
        topic = next((term for term in topic_terms if term in seg["tokset"]), topic_terms[0] if topic_terms else "عام")
        g = groups.setdefault(topic, {"topic": topic, "segments": []})
        g["segments"].append({"text": seg["text"], "confidence": seg["confidence"]})

    # keep the largest topic groups
    out = sorted(groups.values(), key=lambda g: -len(g["segments"]))[:MAX_TOPICS]
    for g in out:
        g["terms"] = topic_terms
    return out


# =========================================================================== #
# Light2 — Short-term: consolidate each topic group → one memory entry.        #
# =========================================================================== #
def _summarize_group(topic: str, label: str, segs: List[Dict[str, Any]]) -> str:
    """Arabic-first consolidated summary — local model when up, deterministic else."""
    count = len(segs)
    quotes = [s["text"] for s in segs[:3] if s.get("text")]
    if llm is not None and llm.available():
        joined = "\n".join(f"- «{q[:160]}»" for q in quotes)
        sys = (
            "أنت تلخّص شكاوى المواطنين في جملة عربية واحدة واضحة لمستخدم عادي. "
            "اعتمد فقط على النص المعطى ولا تختلق."
        )
        user = f"المحور: {topic} (ضمن «{label}»). عيّنات ({count} بلاغًا):\n{joined}\n\nلخّص جوهر الشكوى في جملة واحدة."
        try:
            t = llm.chat(sys, user, temperature=0.2, max_tokens=80, timeout=10)
            if t:
                return t.strip()
        except Exception:
            pass
    head = quotes[0][:120] if quotes else ""
    return f"تتركّز شكاوى «{topic}» على {count} بلاغًا" + (f"؛ من أبرزها: «{head}»." if head else ".")


def _consolidate(cluster_id: str, label: str, severity: float, groups: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    for g in groups:
        segs = g["segments"]
        if not segs:
            continue
        # representative quotes: most-representative first (already ordered), prefer shorter
        ordered = sorted(segs, key=lambda s: len(s.get("text") or ""))[:QUOTES_PER_TOPIC * 2]
        quotes = [s["text"] for s in (segs[:QUOTES_PER_TOPIC] or ordered[:QUOTES_PER_TOPIC])]
        # keywords for retrieval = top tokens of the group
        kw: Dict[str, int] = {}
        for s in segs:
            for w in _tokset(s.get("text")):
                kw[w] = kw.get(w, 0) + 1
        keywords = [w for w, _ in sorted(kw.items(), key=lambda kv: -kv[1])[:8]]
        entries.append({
            "cluster_id": cluster_id,
            "label": label,
            "topic": g["topic"],
            "summary": _summarize_group(g["topic"], label, segs),
            "quotes": quotes,
            "keywords": keywords,
            "count": len(segs),
            "severity": round(float(severity or 0), 2),
            "ts": int(time.time()),
        })
    return entries


# =========================================================================== #
# Light3 — Long-term store: offline build + SOFT update + hybrid retrieval.    #
# =========================================================================== #
def _load() -> List[Dict[str, Any]]:
    try:
        with open(_STORE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save(entries: List[Dict[str, Any]]) -> None:
    try:
        os.makedirs(_DATA_DIR, exist_ok=True)
        with open(_STORE, "w", encoding="utf-8") as fh:
            json.dump(entries, fh, ensure_ascii=False, indent=1)
    except Exception:
        pass


def _soft_merge(store: List[Dict[str, Any]], fresh: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """SOFT update (paper §Light3): append/merge, never overwrite. Entries with the
    same (cluster_id, topic) are merged — union quotes/keywords, max count, newest
    summary — so accumulated information is preserved rather than deleted."""
    index: Dict[tuple, Dict[str, Any]] = {(e["cluster_id"], e["topic"]): e for e in store}
    for e in fresh:
        key = (e["cluster_id"], e["topic"])
        if key in index:
            old = index[key]
            merged_quotes = list(dict.fromkeys((e["quotes"] or []) + (old.get("quotes") or [])))[:4]
            merged_kw = list(dict.fromkeys((e["keywords"] or []) + (old.get("keywords") or [])))[:12]
            old.update({
                "summary": e["summary"],          # newest consolidated summary
                "quotes": merged_quotes,
                "keywords": merged_kw,
                "count": max(int(e["count"]), int(old.get("count") or 0)),
                "severity": e["severity"],
                "ts": e["ts"],
            })
        else:
            index[key] = e
            store.append(e)
    return store


def build_for_cluster(cluster_id: str, label: str = "", severity: float = 0.0) -> List[Dict[str, Any]]:
    """Stages Light1→Light2 for one cluster → consolidated entries (no persist)."""
    if not label and whys is not None:
        try:
            c = whys._fetch_cluster(cluster_id) or {}
            label = c.get("canonical_label_ar") or c.get("canonical_label_en") or cluster_id[:8]
            severity = c.get("severity_avg") or severity
        except Exception:
            label = label or cluster_id[:8]
    groups = _compress_and_group(cluster_id)
    return _consolidate(cluster_id, label, severity, groups)


def rebuild(top_n: int = 8) -> Dict[str, Any]:
    """Offline 'sleep-time' build over the top root-cause clusters, soft-merged
    into the persistent store. Decoupled from inference — call from a cron/script
    or the POST /api/memory/rebuild route."""
    clusters: List[Dict[str, Any]] = []
    if rootcause is not None:
        try:
            clusters = rootcause.rank_root_causes(top_n) or []
        except Exception:
            clusters = []
    store = _load()
    built = 0
    for c in clusters:
        cid = c.get("cluster_id")
        if not cid:
            continue
        fresh = build_for_cluster(
            cid,
            label=c.get("label_ar") or c.get("label_en") or "",
            severity=c.get("severity_avg") or 0.0,
        )
        if fresh:
            store = _soft_merge(store, fresh)
            built += len(fresh)
    _save(store)
    return {"ok": True, "clusters": len(clusters), "entries_built": built, "store_size": len(store)}


def memory_for_cluster(cluster_id: str, limit: int = 6) -> List[Dict[str, Any]]:
    """Consolidated entries for a cluster — from the store, or built on the fly if
    the store is cold (so inference never blocks on an empty store)."""
    hits = [e for e in _load() if e.get("cluster_id") == cluster_id]
    if not hits:
        hits = build_for_cluster(cluster_id)
    return sorted(hits, key=lambda e: -int(e.get("count") or 0))[:limit]


def retrieve(query: str, cluster_id: Optional[str] = None, limit: int = 5,
             strategy: str = "hybrid") -> List[Dict[str, Any]]:
    """Hybrid retrieval (paper §retrieval): BM25-lite keyword overlap + char-ngram
    embedding similarity over consolidated entries. Returns compact summaries."""
    store = _load()
    if cluster_id:
        store = [e for e in store if e.get("cluster_id") == cluster_id]
    if not store:
        return []
    qtok = _tokset(query)
    scored: List[tuple] = []
    for e in store:
        etok = set(e.get("keywords") or []) | _tokset(e.get("summary"))
        bm25 = len(qtok & etok) / (1 + math.log(1 + len(etok)))  # keyword overlap, length-normalised
        emb = _ngram_cosine(query, (e.get("summary") or "") + " " + e.get("topic", ""))
        score = (0.6 * bm25 + 0.4 * emb) if strategy == "hybrid" else (bm25 if strategy == "context" else emb)
        scored.append((score, e))
    scored.sort(key=lambda x: -x[0])
    return [e for s, e in scored[:limit] if s > 0] or [e for _, e in scored[:limit]]


def stats() -> Dict[str, Any]:
    store = _load()
    clusters = {e.get("cluster_id") for e in store}
    return {
        "ok": True,
        "store_size": len(store),
        "clusters": len(clusters),
        "exists": os.path.exists(_STORE),
        "params": {"relevance_min": RELEVANCE_MIN, "dedup_jaccard": DEDUP_JACCARD,
                   "max_topics": MAX_TOPICS, "quotes_per_topic": QUOTES_PER_TOPIC},
    }


# =========================================================================== #
# Routes.                                                                      #
# =========================================================================== #
class RebuildIn(BaseModel):
    top_n: int = 8


@router.get("/api/memory")
def get_memory(cluster_id: Optional[str] = Query(default=None),
               q: Optional[str] = Query(default=None),
               limit: int = Query(6, ge=1, le=30)) -> Dict[str, Any]:
    if q:
        return {"ok": True, "query": q, "entries": retrieve(q, cluster_id, limit)}
    if cluster_id:
        return {"ok": True, "cluster_id": cluster_id, "entries": memory_for_cluster(cluster_id, limit)}
    return stats()


@router.post("/api/memory/rebuild")
def post_rebuild(body: RebuildIn) -> Dict[str, Any]:
    return rebuild(body.top_n)


__all__ = ["router", "rebuild", "memory_for_cluster", "retrieve", "stats", "build_for_cluster"]
