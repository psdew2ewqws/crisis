"""Build the live VOC dependency graph: Source → Service → Governorate, plus the
RIL root-cause Problem Clusters — entirely from real voc360 data."""
from __future__ import annotations
from typing import Any

from . import db

# ---- column-grounded queries ---------------------------------------------

Q_SRC_SVC = """
  with top_svc as (
    select service_id from the_data where service_id is not null
      and (%(svc)s::text is null or service_id = %(svc)s::text)
    group by 1 order by count(*) desc limit 16
  )
  select source_type, service_id, count(*) c
  from the_data
  where service_id in (select service_id from top_svc) and source_type is not null
  group by 1, 2 order by c desc
"""
Q_SVC_GOV = """
  with top_svc as (
    select service_id from the_data where service_id is not null
    group by 1 order by count(*) desc limit 16
  )
  select service_id, governorate, count(*) c
  from the_data
  where governorate is not null and service_id in (select service_id from top_svc)
    and (%(svc)s::text is null or service_id = %(svc)s::text)
  group by 1, 2 order by c desc limit 18
"""
Q_SVC_SEV = """
  select service_id,
         count(*) filter (where severity in ('high','critical')) bad,
         count(*) filter (where severity is not null) tot
  from the_data where service_id is not null group by 1
"""
Q_CLUSTERS = """
  select cluster_id, canonical_label_ar, canonical_label_en,
         coalesce(member_count,0) member_count, coalesce(severity_avg,0) severity_avg
  from ril_problem_clusters
  where coalesce(member_count,0) > 1
  order by member_count desc limit 14
"""

LAYER_X = {"case": 40, "source": 320, "service": 660, "governorate": 1000, "rchub": 1000, "cluster": 1300}

# heuristic links from a root-cause cluster to a service (Arabic keywords)
_KW = [
    (("باص", "الباص", "brt", "نقل", "مواقف", "دوار"), "Amman Bus"),
    (("معونة", "تكافل", "دعم", "صندوق"), None),  # National Aid — no top service node
    (("الكتروني", "إلكترون", "منصة", "تطبيق", "sanad"), "Sanad"),
    (("شارع", "طريق", "بنية", "حفر"), "طرق_وبنية_تحتية"),
]


def _tone_from_ratio(bad: int, tot: int) -> str:
    if not tot:
        return "neutral"
    r = bad / tot
    return "alert" if r >= 0.30 else "warn" if r >= 0.10 else "calm"


def _tone_from_sev(sev: float) -> str:
    return "alert" if sev >= 0.5 else "warn" if sev >= 0.3 else "calm"


def _layout(nodes: list[dict]) -> None:
    by_type: dict[str, list[dict]] = {}
    for n in nodes:
        by_type.setdefault(n["type"], []).append(n)
    for typ, items in by_type.items():
        x = LAYER_X.get(typ, 660)
        gap = max(70, min(150, 760 / max(1, len(items))))
        offset = (len(items) - 1) * gap / 2
        for i, n in enumerate(items):
            n["x"] = x
            n["y"] = 430 + i * gap - offset


def _match_service(label_ar: str, services: set[str]) -> str | None:
    low = (label_ar or "").lower()
    for kws, svc in _KW:
        if any(k in low for k in kws):
            if svc and svc in services:
                return svc
    return None


def build_graph(case: str | None = None) -> dict[str, Any]:
    svc_filter = None if not case or case == "all" else case
    src_svc = db.fetchall(Q_SRC_SVC, ({"svc": svc_filter}))
    svc_gov = db.fetchall(Q_SVC_GOV, ({"svc": svc_filter}))
    sev = {r["service_id"]: r for r in db.fetchall(Q_SVC_SEV)}
    clusters = db.fetchall(Q_CLUSTERS)

    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    def add(nid: str, **kw):
        if nid not in nodes:
            nodes[nid] = {"id": nid, **kw}
        return nodes[nid]

    # case root
    total = sum(r["c"] for r in src_svc)
    add(f"case::{svc_filter or 'all'}", type="case",
        label=svc_filter or "VOC 360 · Jordan Public Services", value=total, severity="neutral")
    case_id = f"case::{svc_filter or 'all'}"

    src_tot: dict[str, int] = {}
    svc_tot: dict[str, int] = {}
    for r in src_svc:
        s, v, c = r["source_type"], r["service_id"], r["c"]
        src_tot[s] = src_tot.get(s, 0) + c
        svc_tot[v] = svc_tot.get(v, 0) + c
        add(f"src::{s}", type="source", label=s, value=0, severity="neutral")
        sv = sev.get(v, {})
        add(f"svc::{v}", type="service", label=v, value=0,
            severity=_tone_from_ratio(sv.get("bad", 0), sv.get("tot", 0)))
        edges.append({"source": f"src::{s}", "target": f"svc::{v}", "weight": c, "kind": "reports"})
    for s, c in src_tot.items():
        nodes[f"src::{s}"]["value"] = c
        edges.append({"source": case_id, "target": f"src::{s}", "weight": c, "kind": "channel"})
    for v, c in svc_tot.items():
        if f"svc::{v}" in nodes:
            nodes[f"svc::{v}"]["value"] = c

    for r in svc_gov:
        v, g, c = r["service_id"], r["governorate"], r["c"]
        if f"svc::{v}" not in nodes:
            continue
        add(f"gov::{g}", type="governorate", label=g, value=0, severity="neutral")
        nodes[f"gov::{g}"]["value"] += c
        edges.append({"source": f"svc::{v}", "target": f"gov::{g}", "weight": c, "kind": "affects"})

    # root-cause clusters (RIL)
    if clusters:
        add("rchub", type="rchub", label="Root Causes · RIL", value=sum(c["member_count"] for c in clusters), severity="alert")
        edges.append({"source": case_id, "target": "rchub", "weight": sum(c["member_count"] for c in clusters), "kind": "diagnoses"})
        services = {v for v in svc_tot}
        for c in clusters:
            lbl = (c["canonical_label_en"] or c["canonical_label_ar"] or "problem")[:46]
            cid = f"cl::{c['cluster_id'][:8]}"
            add(cid, type="cluster", label=lbl, value=c["member_count"],
                severity=_tone_from_sev(c["severity_avg"]), label_ar=(c["canonical_label_ar"] or "")[:80],
                members=c["member_count"], severity_avg=round(c["severity_avg"], 2))
            edges.append({"source": "rchub", "target": cid, "weight": c["member_count"], "kind": "cluster"})
            m = _match_service(c["canonical_label_ar"] or "", services)
            if m:
                edges.append({"source": f"svc::{m}", "target": cid, "weight": c["member_count"], "kind": "root_cause"})

    node_list = list(nodes.values())
    _layout(node_list)
    return {
        "case": svc_filter or "all",
        "nodes": node_list,
        "edges": edges,
        "stats": {"signals": total, "services": len(svc_tot), "sources": len(src_tot), "clusters": len(clusters)},
    }
