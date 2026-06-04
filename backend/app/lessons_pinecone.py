"""Pinecone vector store for crisis lessons (success + failure cases).

This replaces the PostgreSQL ``successful_lessons`` table as the primary store:
lessons already carry an embedding, and Pinecone does the cosine ranking +
metadata filtering server-side. The full lesson lives in the vector's metadata;
the embedding is the vector itself.

Dimension adaptivity: our embeddings come from ``nomic-embed-text`` (768-dim) but
the target index may be a different size (the ``simulation`` index is 1024-dim).
Zero-padding a 768-vector up to the index dimension is exact for cosine similarity
(the appended zeros change neither the dot product nor the norm), so retrieval
quality is identical. Over-long vectors are truncated as a safety net.

Config (backend/.env):
    PINECONE_API_KEY=...
    PINECONE_INDEX=simulation        # default: simulation
    PINECONE_NAMESPACE=              # optional, default ""

Failures degrade gracefully — ``lessons`` falls back to its JSON store.
"""
from __future__ import annotations

import hashlib
import os
from typing import Any, List, Optional

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except Exception:  # pragma: no cover
    pass

API_KEY = os.environ.get("PINECONE_API_KEY", "")
INDEX_NAME = os.environ.get("PINECONE_INDEX", "simulation")
NAMESPACE = os.environ.get("PINECONE_NAMESPACE", "")

# Metadata keys that hold the lesson payload (everything except the embedding).
_META_STR = [
    "kind", "domain", "root_cause_category", "root_cause_details", "intervention",
    "outcome", "lesson_text", "why_it_worked", "applicable_when", "source_case_id",
    "ts", "risk_source", "meta_json",
]
_META_NUM = ["risk_before", "risk_after", "risk_delta", "confidence"]

_pc: Any = None      # None=uninit, False=unavailable, else Pinecone client
_index: Any = None   # cached Index handle
_dim: Optional[int] = None  # cached index dimension
_metric: Optional[str] = None  # cached index metric (must be 'cosine' for the pad)


def available() -> bool:
    return bool(API_KEY) and _client() is not False


def _client():
    global _pc
    if _pc is not None:
        return _pc
    if not API_KEY:
        _pc = False
        return _pc
    try:
        from pinecone import Pinecone

        _pc = Pinecone(api_key=API_KEY)
    except Exception:
        _pc = False
    return _pc


def _get_index():
    """Return (index, dimension) or (None, None) on any failure."""
    global _index, _dim, _metric
    if _index is not None:
        return _index, _dim
    pc = _client()
    if not pc:
        return None, None
    try:
        desc = pc.describe_index(INDEX_NAME)
        _dim = int(desc.dimension)
        _metric = str(getattr(desc, "metric", "") or "").lower()
        _index = pc.Index(INDEX_NAME)
        return _index, _dim
    except Exception:
        return None, None


def _fit(vec: List[float], dim: int) -> List[float]:
    """Pad with zeros (cosine-exact) or truncate so the vector matches the index."""
    vec = [float(x) for x in (vec or [])]
    if len(vec) == dim:
        return vec
    if len(vec) < dim:
        return vec + [0.0] * (dim - len(vec))
    return vec[:dim]


def ensure_schema() -> dict[str, Any]:
    """Parity with lessons_db.ensure_schema(): verify the index is reachable."""
    if not API_KEY:
        return {"ok": False, "error": "PINECONE_API_KEY is not set"}
    idx, dim = _get_index()
    if idx is None:
        return {"ok": False, "error": f"Pinecone index '{INDEX_NAME}' unreachable"}
    try:
        st = idx.describe_index_stats()
        total = int(getattr(st, "total_vector_count", 0) or 0)
        return {
            "ok": True,
            "index": INDEX_NAME,
            "dimension": dim,
            "count": total,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _to_metadata(row: dict[str, Any]) -> dict[str, Any]:
    md: dict[str, Any] = {}
    for k in _META_STR:
        v = row.get(k)
        if k == "meta_json":
            v = row.get("metadata")
        if v is not None:
            md[k] = str(v)
    md.setdefault("kind", "success")
    for k in _META_NUM:
        if row.get(k) is not None:
            try:
                md[k] = float(row[k])
            except (TypeError, ValueError):
                pass
    return md


def _vector_id(row: dict[str, Any]) -> str:
    """Deterministic id derived from source_case_id so re-ingesting a case
    OVERWRITES its vector instead of duplicating the corpus on every backfill run.
    Falls back to row['id'] only when no source id is present."""
    src = str(row.get("source_case_id") or "").strip()
    if src:
        return "lesson_" + hashlib.sha256(src.encode("utf-8")).hexdigest()[:24]
    return str(row.get("id"))


def insert_lesson(row: dict[str, Any]) -> dict[str, Any]:
    idx, dim = _get_index()
    if idx is None:
        raise RuntimeError("Pinecone index unavailable")
    # The 768->1024 zero-pad is cosine-EXACT only under a cosine index. Refuse to
    # write into a non-cosine index rather than silently corrupting similarity.
    if _metric and _metric != "cosine":
        raise RuntimeError(
            f"Pinecone index '{INDEX_NAME}' metric is '{_metric}', expected 'cosine'"
        )
    emb = row.get("embedding")
    if not emb:
        raise ValueError("lesson row has no embedding to upsert")
    idx.upsert(
        vectors=[{
            "id": _vector_id(row),
            "values": _fit(emb, dim),
            "metadata": _to_metadata(row),
        }],
        namespace=NAMESPACE,
    )
    return row


def _match_to_row(m: Any) -> dict[str, Any]:
    md = dict(getattr(m, "metadata", None) or {})
    row: dict[str, Any] = {
        "id": getattr(m, "id", None),
        "score": float(getattr(m, "score", 0.0) or 0.0),
    }
    for k in _META_STR:
        if k == "meta_json":
            if "meta_json" in md:
                row["metadata"] = md["meta_json"]
            continue
        if k in md:
            row[k] = md[k]
    for k in _META_NUM:
        if k in md:
            row[k] = md[k]
    return row


def _zero_query_vec(dim: int) -> List[float]:
    # A tiny constant vector to "browse" (Pinecone requires a query vector even
    # when you only want a metadata-filtered slice). Order is not meaningful here.
    return [1e-6] * dim


def query(
    qvec: Optional[List[float]] = None,
    *,
    domain: Optional[str] = None,
    category: Optional[str] = None,
    kind: Optional[str] = None,
    top_k: int = 5,
) -> List[dict[str, Any]]:
    idx, dim = _get_index()
    if idx is None:
        return []
    flt: dict[str, Any] = {}
    if domain:
        flt["domain"] = {"$eq": domain}
    if kind:
        flt["kind"] = {"$eq": kind}
    # Pinecone has no substring match; category is matched server-side on exact
    # value and the caller (lessons.py) still does keyword blending in Python.
    vec = _fit(qvec, dim) if qvec else _zero_query_vec(dim)
    try:
        res = idx.query(
            vector=vec,
            top_k=max(1, min(top_k, 100)),
            include_metadata=True,
            namespace=NAMESPACE,
            filter=flt or None,
        )
        return [_match_to_row(m) for m in (res.matches or [])]
    except Exception:
        return []


def list_lessons(limit: int = 50) -> List[dict[str, Any]]:
    """Best-effort browse (Pinecone is not ordered storage)."""
    return query(qvec=None, top_k=limit)


def fetch_candidates(
    domain: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 200,
    kind: Optional[str] = None,
) -> List[dict[str, Any]]:
    """Parity with lessons_db.fetch_candidates — but Pinecone ranks server-side."""
    return query(qvec=None, domain=domain, category=category, kind=kind, top_k=limit)


def counts() -> dict[str, int]:
    """Total + per-kind counts (per-kind is best-effort via filtered queries)."""
    idx, dim = _get_index()
    if idx is None:
        return {"total": 0, "success": 0, "failure": 0}
    total = 0
    try:
        st = idx.describe_index_stats()
        total = int(getattr(st, "total_vector_count", 0) or 0)
    except Exception:
        pass
    out = {"total": total, "success": 0, "failure": 0}
    for k in ("success", "failure"):
        out[k] = len(query(qvec=None, kind=k, top_k=min(max(total, 1), 100)))
    return out


def delete(ids: List[str]) -> None:
    idx, _ = _get_index()
    if idx is not None and ids:
        try:
            idx.delete(ids=[str(i) for i in ids], namespace=NAMESPACE)
        except Exception:
            pass
