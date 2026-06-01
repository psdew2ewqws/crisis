"""Rank the RIL problem clusters as root causes, with real sample evidence."""
from __future__ import annotations
from typing import Any

from . import db

Q_RANK = """
  select cluster_id, canonical_label_ar, canonical_label_en,
         coalesce(member_count,0) member_count, coalesce(severity_avg,0) severity_avg,
         coalesce(member_count,0) * (0.5 + coalesce(severity_avg,0)) as score
  from ril_problem_clusters
  where coalesce(member_count,0) > 1
  order by score desc limit %(lim)s
"""
Q_SAMPLE = """
  select s.segment_text
  from ril_cluster_members m
  join ril_text_segments s on s.segment_id = m.segment_id
  where m.cluster_id = %(cid)s
  limit 3
"""


def rank_root_causes(limit: int = 10) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for rank, r in enumerate(db.fetchall(Q_RANK, {"lim": limit}), start=1):
        samples = [x["segment_text"][:140] for x in db.fetchall(Q_SAMPLE, {"cid": r["cluster_id"]})]
        out.append({
            "rank": rank,
            "cluster_id": r["cluster_id"],
            "label_ar": r["canonical_label_ar"],
            "label_en": r["canonical_label_en"] or None,
            "members": r["member_count"],
            "severity_avg": round(r["severity_avg"], 2),
            "score": round(r["score"], 1),
            "evidence": samples,
        })
    return out


def recommend(top: dict[str, Any]) -> str:
    lbl = top.get("label_en") or top.get("label_ar") or "the dominant problem cluster"
    return (
        f"Prioritise the root cause '{lbl}' ({top['members']} citizen reports, "
        f"severity {top['severity_avg']}). Route to the owning agency, brief the relevant "
        f"service team, and track whether complaint volume on this cluster falls after action."
    )
