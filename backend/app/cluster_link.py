"""Track 1 — recover the broken segment↔signal join BY TEXT, giving REAL
cluster → service / governorate edges (no embeddings, no API).

`ril_text_segments.record_id` does not match `the_data` (the RIL pipeline ran on
a separate snapshot), but each `segment_text` is a substring of a real
`the_data.text/text_clean` row — so we match by text and recover the chain
signal → segment → cluster → service. Result is cached to backend/data/.
"""
from __future__ import annotations
import json
import os
from collections import Counter, defaultdict

from . import db

_CACHE = os.path.join(os.path.dirname(__file__), "..", "data", "cluster_links.json")
_MEM: dict | None = None


def _compute() -> dict:
    segs = db.fetchall(
        """
        select cm.cluster_id, s.segment_text
        from ril_cluster_members cm
        join ril_text_segments s on s.segment_id = cm.segment_id
        where length(s.segment_text) > 12
        """
    )
    rows = db.fetchall(
        """
        select coalesce(text_clean, text) as txt, service_id, governorate
        from the_data
        where coalesce(text_clean, text) is not null and service_id is not null
        """
    )
    data = [(r["txt"], r["service_id"], r["governorate"]) for r in rows]

    cluster_svc: dict[str, Counter] = defaultdict(Counter)
    cluster_gov: dict[str, Counter] = defaultdict(Counter)
    cluster_sig: Counter = Counter()
    for seg in segs:
        cid = seg["cluster_id"]
        key = (seg["segment_text"] or "").strip()[:50]
        if not key:
            continue
        for txt, svc, gov in data:
            if key in txt:  # the segment was extracted from this signal
                cluster_svc[cid][svc] += 1
                if gov:
                    cluster_gov[cid][gov] += 1
                cluster_sig[cid] += 1
                break  # first matching signal per segment
    return {
        cid: {
            "services": cs.most_common(6),
            "governorates": cluster_gov[cid].most_common(4),
            "signals": cluster_sig[cid],
        }
        for cid, cs in cluster_svc.items()
    }


def links(refresh: bool = False) -> dict:
    global _MEM
    if _MEM is not None and not refresh:
        return _MEM
    if not refresh and os.path.exists(_CACHE):
        try:
            _MEM = json.load(open(_CACHE))
            return _MEM
        except Exception:
            pass
    _MEM = _compute()
    try:
        os.makedirs(os.path.dirname(_CACHE), exist_ok=True)
        json.dump(_MEM, open(_CACHE, "w"))
    except Exception:
        pass
    return _MEM


def cluster_services(cluster_id: str) -> list[tuple[str, int]]:
    return [tuple(x) for x in links().get(cluster_id, {}).get("services", [])]


def cluster_signals(cluster_id: str) -> int:
    return int(links().get(cluster_id, {}).get("signals", 0))


def cluster_signal_rows(cluster_id: str, limit: int = 50) -> list[dict]:
    """REAL the_data rows that prove a cluster, via the same segment_text→the_data
    text match used in _compute().

    Pull the cluster's member segment_texts, take ~60 distinct keys
    (``segment_text.strip()[:50]``), and LIKE-match each against
    ``coalesce(text_clean, text)`` to return the full real rows that the cluster's
    segments were extracted from. The join is O(segments×rows), so keys are capped
    and the result is LIMITed to stay fast.
    """
    if not cluster_id:
        return []
    seg_rows = db.fetchall(
        """
        select s.segment_text
        from ril_cluster_members m
        join ril_text_segments s on s.segment_id = m.segment_id
        where m.cluster_id = %(cid)s and length(s.segment_text) > 12
        order by m.distance_to_centroid asc nulls last
        limit 600
        """,
        {"cid": cluster_id},
    )
    keys: list[str] = []
    seen: set[str] = set()
    for r in seg_rows:
        key = (r["segment_text"] or "").strip()[:50]
        if not key or key in seen:
            continue
        seen.add(key)
        keys.append(key)
        if len(keys) >= 60:  # cap distinct keys — the match is O(segments×rows)
            break
    if not keys:
        return []
    # ILIKE-match each key as a substring of a real the_data row; one query.
    # Escape ILIKE wildcards so a literal %/_ in the segment matches literally.
    def _esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    conds = " or ".join(
        f"coalesce(text_clean, text) ilike %(k{i})s" for i in range(len(keys))
    )
    params: dict = {"lim": limit}
    for i, k in enumerate(keys):
        params[f"k{i}"] = f"%{_esc(k)}%"
    return db.fetchall(
        f"""
        select record_id, service_id, source_type,
               coalesce(text_clean, text) as text,
               sentiment_label, severity, observed_at
        from the_data
        where coalesce(text_clean, text) is not null
          and ({conds})
        limit %(lim)s
        """,
        params,
    )


def service_cluster_edges(min_weight: int = 2) -> list[tuple[str, str, int]]:
    out: list[tuple[str, str, int]] = []
    for cid, info in links().items():
        for svc, w in info.get("services", []):
            if w >= min_weight:
                out.append((svc, cid, int(w)))
    return out
