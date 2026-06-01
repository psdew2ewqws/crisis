"""
mesa_sim.py — Mesa 3 agent-based simulation of complaint/sentiment propagation
across the voc360 live graph (services × governorates × sources × root-cause
clusters), for the AEGIS crisis brain.

Design contract: docs/D-mesa.md.

This module builds a networkx DiGraph from the live voc360 graph (Source ->
Service -> Governorate, plus root-cause ProblemCluster -> Service), seats one
NodeAgent per node on a Mesa `NetworkGrid`, and propagates sentiment with a
weighted-contagion + decay + inflow dynamic. An intervention damps a single
node (e.g. fixing the dominant National-Aid-Fund / urgent-service-fee cluster
on Sanad) so the operator can A/B the lever.

Stack pins (load-bearing, from the Mesa guide / D-mesa):
  - mesa>=3.1,<4 : Mesa 3 API (`super().__init__(self)` agents w/ no unique_id,
    `super().__init__(seed=seed)` model, `agents.shuffle_do("step")`,
    `mesa.space.NetworkGrid`, `DataCollector`). Mesa 4 alpha changes the Model
    signature and removes `batch_run`, so it is explicitly NOT supported.
  - networkx for the graph.

Import-safety: if `mesa` (or `networkx`) is missing or the wrong major version,
a pure numpy / plain-python fallback (`_FallbackModel`) reproduces a comparable
time series with the identical schema, so the FastAPI route and the Deer Graph
`simulate_node` keep working with zero optional deps installed.

The two public entry points used by the rest of the system:
  - `build_graph_for_case(case, dsn)`     -> graph (networkx.DiGraph or dict)
  - `run_simulation(graph, ...)`          -> SimResult dict
  - `run_before_after(graph, ...)`        -> BeforeAfter dict
  - `simulate(case, intervene, ...)`      -> time-series dict (convenience)

All dict outputs are plain JSON-serializable Python (Arabic-safe; dump with
`ensure_ascii=False` upstream). Node ids are stable hashable strings shared
across networkx / Mesa / reactflow:
    src:<source_type>  svc:<service_id>  gov:<governorate>  cluster:<cluster_id>
"""

from __future__ import annotations

import math
import os
import random
from typing import Any, Dict, List, Optional, Sequence, Tuple

# --------------------------------------------------------------------------- #
# Optional dependency probing (import-safe).                                  #
# --------------------------------------------------------------------------- #

try:  # networkx is needed for the real graph + Mesa NetworkGrid.
    import networkx as nx  # type: ignore

    _HAVE_NX = True
except Exception:  # pragma: no cover - exercised only when nx absent
    nx = None  # type: ignore
    _HAVE_NX = False

try:  # numpy speeds up the fallback; we degrade to plain lists if absent.
    import numpy as np  # type: ignore

    _HAVE_NUMPY = True
except Exception:  # pragma: no cover
    np = None  # type: ignore
    _HAVE_NUMPY = False

# Mesa 3 probe. We require the 3.x API surface (Agent/Model/space.NetworkGrid/
# datacollection.DataCollector) AND major version < 4.
_HAVE_MESA = False
mesa = None  # type: ignore
NetworkGrid = None  # type: ignore
DataCollector = None  # type: ignore
try:  # pragma: no cover - depends on environment
    import mesa as _mesa  # type: ignore
    from mesa.space import NetworkGrid as _NetworkGrid  # type: ignore
    from mesa.datacollection import DataCollector as _DataCollector  # type: ignore

    _mver = getattr(_mesa, "__version__", "0")
    try:
        _major = int(str(_mver).split(".")[0])
    except Exception:
        _major = 0
    # Mesa 3 API has Model.agents (AgentSet). Mesa 4 alpha breaks Model.__init__.
    if 3 <= _major < 4 and _HAVE_NX:
        mesa = _mesa  # type: ignore
        NetworkGrid = _NetworkGrid  # type: ignore
        DataCollector = _DataCollector  # type: ignore
        _HAVE_MESA = True
except Exception:
    _HAVE_MESA = False


# --------------------------------------------------------------------------- #
# Defaults (mirror D-mesa signatures).                                        #
# --------------------------------------------------------------------------- #

DEFAULT_STEPS = 50
DEFAULT_SPREAD_RATE = 0.30
DEFAULT_DECAY = 0.985
DEFAULT_INFLOW = 0.05
DEFAULT_INTERVENTION_STRENGTH = 0.60
DEFAULT_SEED = 42
CRITICAL_THRESHOLD = 0.7  # sentiment > 0.7 == "critical" node

# Severity-string -> [0,1] for app_review NULLs etc. (the_data.severity).
_SEVERITY_MAP = {
    "low": 0.25,
    "medium": 0.5,
    "high": 0.75,
    "critical": 1.0,
    None: 0.0,
    "": 0.0,
}


def _sev_to_float(sev: Any) -> float:
    """Map a voc360 severity string/number to [0,1]; NULL/unknown -> 0.0."""
    if sev is None:
        return 0.0
    if isinstance(sev, (int, float)):
        try:
            v = float(sev)
        except Exception:
            return 0.0
        if v > 1.0:  # already 0..100 style
            v = v / 100.0
        return max(0.0, min(1.0, v))
    return _SEVERITY_MAP.get(str(sev).strip().lower(), 0.0)


def _sentiment_label_to_float(label: Any) -> Optional[float]:
    """Map a the_data.sentiment_label to a negativity prior in [0,1]."""
    if not label:
        return None
    s = str(label).strip().lower()
    if "high_severity" in s or "negative" in s:
        return 0.85 if "high_severity" in s else 0.7
    if "positive" in s:
        return 0.15
    if "neutral" in s:
        return 0.45
    return None


# --------------------------------------------------------------------------- #
# DSN resolution.                                                             #
# --------------------------------------------------------------------------- #

def _resolve_dsn(dsn: Optional[str]) -> Optional[str]:
    """Resolve the read-only voc360 DSN from arg or env (VOC360_DSN/VOC_DSN)."""
    if dsn:
        return dsn
    for key in ("VOC360_DSN", "VOC_DSN", "DATABASE_URL"):
        v = os.environ.get(key)
        if v:
            return v
    return None


# --------------------------------------------------------------------------- #
# SQL (READ-ONLY voc360). Named-param dicts; %(svc)s NULL -> "all".           #
# Mirrors D-graphmodel: top_svc CTE, keyword cluster bridge, score floor.     #
# --------------------------------------------------------------------------- #

# Source(source_type) -> Service(service_id), weighted by signal count.
_SQL_SRC_SVC = """
WITH top_svc AS (
    SELECT service_id
    FROM the_data
    WHERE service_id IS NOT NULL
      AND COALESCE(spam_flag, false) = false
      AND COALESCE(duplicate_flag, false) = false
      AND (%(svc)s IS NULL OR service_id = %(svc)s)
    GROUP BY service_id
    ORDER BY count(*) DESC
    LIMIT 16
)
SELECT d.source_type,
       d.service_id,
       count(*)                                   AS cnt,
       avg(
         CASE lower(coalesce(d.severity, ''))
           WHEN 'critical' THEN 1.0
           WHEN 'high'     THEN 0.75
           WHEN 'medium'   THEN 0.5
           WHEN 'low'      THEN 0.25
           ELSE 0.0 END
       )                                          AS sev_avg,
       sum(CASE WHEN lower(coalesce(d.sentiment_label,'')) LIKE '%%negative%%'
                  OR lower(coalesce(d.sentiment_label,'')) LIKE '%%high_severity%%'
                THEN 1 ELSE 0 END)::float
         / GREATEST(count(*), 1)                  AS neg_frac
FROM the_data d
JOIN top_svc t ON t.service_id = d.service_id
WHERE d.source_type IS NOT NULL
  AND COALESCE(d.spam_flag, false) = false
  AND COALESCE(d.duplicate_flag, false) = false
GROUP BY d.source_type, d.service_id
"""

# Service(service_id) -> Governorate (non-NULL govs only).
_SQL_SVC_GOV = """
WITH top_svc AS (
    SELECT service_id
    FROM the_data
    WHERE service_id IS NOT NULL
      AND COALESCE(spam_flag, false) = false
      AND COALESCE(duplicate_flag, false) = false
      AND (%(svc)s IS NULL OR service_id = %(svc)s)
    GROUP BY service_id
    ORDER BY count(*) DESC
    LIMIT 16
)
SELECT d.service_id,
       d.governorate,
       count(*)                                   AS cnt,
       avg(
         CASE lower(coalesce(d.severity, ''))
           WHEN 'critical' THEN 1.0
           WHEN 'high'     THEN 0.75
           WHEN 'medium'   THEN 0.5
           WHEN 'low'      THEN 0.25
           ELSE 0.0 END
       )                                          AS sev_avg
FROM the_data d
JOIN top_svc t ON t.service_id = d.service_id
WHERE d.governorate IS NOT NULL
  AND COALESCE(d.spam_flag, false) = false
  AND COALESCE(d.duplicate_flag, false) = false
GROUP BY d.service_id, d.governorate
"""

# Root-cause ProblemClusters (populated, ranked by member_count*(0.5+sev)).
_SQL_CLUSTERS = """
SELECT cluster_id,
       canonical_label_ar,
       canonical_label_en,
       member_count,
       COALESCE(severity_avg, 0.40)               AS severity_avg
FROM ril_problem_clusters
WHERE member_count > 1
ORDER BY member_count DESC
LIMIT 14
"""


# Keyword bridge: cluster -> service (D-graphmodel heuristic, first hit).
def _cluster_service_bridge(label_ar: str, service_ids: set) -> Optional[str]:
    """Map a cluster's Arabic label to a service node id via keyword heuristic."""
    if not label_ar:
        return None
    low = label_ar.lower()

    def _pick(*candidates: str) -> Optional[str]:
        for c in candidates:
            if c in service_ids:
                return c
        return None

    if any(k in low for k in ("الباص", "سريع", "brt", "باص")):
        return _pick("Amman Bus", "نقل_عام")
    if any(k in low for k in ("معونة", "صندوق")):
        return _pick("Sanad", "National Aid")
    if "تكافل" in low:
        return _pick("Takaful", "Sanad")
    if any(k in low for k in ("الكتروني", "إلكترون", "منصة", "sanad", "سند")):
        return _pick("Sanad", "الخدمات_الإلكترونية")
    if any(k in low for k in ("شارع", "حفريات", "طرق", "بنية")):
        return _pick("طرق_وبنية_تحتية")
    return None


def _rank_score(member_count: float, severity_avg: float) -> float:
    """Root-cause rank: member_count*(0.5+severity_avg) (the 0.5 floor matters)."""
    try:
        return float(member_count) * (0.5 + float(severity_avg))
    except Exception:
        return 0.0


# --------------------------------------------------------------------------- #
# Graph construction.                                                         #
#                                                                             #
# Returns a networkx.DiGraph when networkx is available, else a lightweight   #
# dict graph {"nodes": {id: attrs}, "edges": [(u, v, weight)], "root_cause":  #
# [...], "meta": {...}} that the fallback model understands. Both carry the   #
# same per-node attrs: kind, sentiment, severity, volume, is_root_cause,      #
# label_ar.                                                                   #
# --------------------------------------------------------------------------- #

def _new_node_attrs(
    kind: str,
    *,
    sentiment: float = 0.0,
    severity: float = 0.0,
    volume: int = 0,
    is_root_cause: bool = False,
    label_ar: str = "",
    **extra: Any,
) -> Dict[str, Any]:
    attrs = {
        "kind": kind,
        "sentiment": float(max(0.0, min(1.0, sentiment))),
        "severity": float(max(0.0, min(1.0, severity))),
        "volume": int(max(0, volume)),
        "is_root_cause": bool(is_root_cause),
        "label_ar": label_ar or "",
    }
    attrs.update(extra)
    return attrs


def _empty_graph():
    if _HAVE_NX:
        return nx.DiGraph()
    return {"nodes": {}, "edges": [], "root_cause": [], "meta": {}}


def _g_add_node(g, node_id: str, attrs: Dict[str, Any]) -> None:
    if _HAVE_NX:
        if node_id in g.nodes:
            # merge: keep max volume/severity/sentiment, OR root-cause flag
            cur = g.nodes[node_id]
            cur["volume"] = max(cur.get("volume", 0), attrs.get("volume", 0))
            cur["severity"] = max(cur.get("severity", 0.0), attrs.get("severity", 0.0))
            cur["sentiment"] = max(cur.get("sentiment", 0.0), attrs.get("sentiment", 0.0))
            cur["is_root_cause"] = cur.get("is_root_cause", False) or attrs.get("is_root_cause", False)
            if attrs.get("label_ar") and not cur.get("label_ar"):
                cur["label_ar"] = attrs["label_ar"]
        else:
            g.add_node(node_id, **attrs)
    else:
        if node_id in g["nodes"]:
            cur = g["nodes"][node_id]
            cur["volume"] = max(cur.get("volume", 0), attrs.get("volume", 0))
            cur["severity"] = max(cur.get("severity", 0.0), attrs.get("severity", 0.0))
            cur["sentiment"] = max(cur.get("sentiment", 0.0), attrs.get("sentiment", 0.0))
            cur["is_root_cause"] = cur.get("is_root_cause", False) or attrs.get("is_root_cause", False)
            if attrs.get("label_ar") and not cur.get("label_ar"):
                cur["label_ar"] = attrs["label_ar"]
        else:
            g["nodes"][node_id] = dict(attrs)


def _g_add_edge(g, u: str, v: str, weight: float) -> None:
    w = float(max(1.0, weight))
    if _HAVE_NX:
        if g.has_edge(u, v):
            g[u][v]["weight"] = g[u][v].get("weight", 0.0) + w
        else:
            g.add_edge(u, v, weight=w)
    else:
        g["edges"].append((u, v, w))


def _g_nodes(g):
    if _HAVE_NX:
        return list(g.nodes(data=True))
    return [(nid, attrs) for nid, attrs in g["nodes"].items()]


def _g_node_count(g) -> int:
    return g.number_of_nodes() if _HAVE_NX else len(g["nodes"])


def _g_has_node(g, node_id: str) -> bool:
    return (node_id in g.nodes) if _HAVE_NX else (node_id in g["nodes"])


def _g_root_cause_nodes(g) -> List[str]:
    return [nid for nid, a in _g_nodes(g) if a.get("is_root_cause")]


def _fetch_rows(dsn: str, sql: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Run a READ-ONLY SELECT against voc360 via psycopg v3, returning dicts.

    Returns [] (not raising) if psycopg is unavailable or the query fails, so
    graph construction degrades to the synthetic graph rather than 500-ing.
    """
    try:
        import psycopg  # type: ignore
        from psycopg.rows import dict_row  # type: ignore
    except Exception:
        return []
    try:
        with psycopg.connect(dsn, autocommit=True) as conn:
            try:
                conn.execute("SET default_transaction_read_only = on")
            except Exception:
                pass
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, params)
                return [dict(r) for r in cur.fetchall()]
    except Exception:
        return []


def _parse_case(case: Optional[str]) -> Tuple[str, Optional[str]]:
    """Parse an opaque case string into (kind, value).

    Accepts `service:<id>`, `svc:<id>`, `gov:<gov>`, `cluster:<id>`, or a bare
    service_id ("all"/None -> whole graph). Only the service value flows into
    the `%(svc)s` SQL filter.
    """
    if not case or str(case).strip().lower() in ("all", "*", "none"):
        return ("all", None)
    s = str(case).strip()
    for pref, kind in (
        ("service:", "service"),
        ("svc:", "service"),
        ("gov:", "governorate"),
        ("governorate:", "governorate"),
        ("cluster:", "cluster"),
        ("cl:", "cluster"),
    ):
        if s.startswith(pref):
            return (kind, s[len(pref):])
    # bare token -> treat as service_id
    return ("service", s)


def build_graph_for_case(case: Optional[str] = None, dsn: Optional[str] = None):
    """Build the propagation graph for a CASE from live voc360, or synthesize.

    Node ids: ``src:<source_type>``, ``svc:<service_id>``, ``gov:<gov>``,
    ``cluster:<cluster_id>``. Edges ``src->svc->gov`` weighted by count;
    root-cause ``cluster:<id>->svc:<service_id>`` attached via keyword bridge.

    Node attrs: ``kind`` in {service, governorate, source, cluster},
    ``sentiment`` (0..1 prior), ``severity`` (0..1, NULL->0.0), ``volume``
    (int signal count), ``is_root_cause`` (bool), ``label_ar`` (str).

    Falls back to a small deterministic synthetic graph grounded in the real
    voc360 entity names if the DB is unreachable / psycopg absent / empty.
    """
    kind, value = _parse_case(case)
    svc_filter = value if kind == "service" else None
    resolved = _resolve_dsn(dsn)

    g = _empty_graph()
    service_ids: set = set()

    rows_ss: List[Dict[str, Any]] = []
    rows_sg: List[Dict[str, Any]] = []
    rows_cl: List[Dict[str, Any]] = []

    if resolved:
        params = {"svc": svc_filter}
        rows_ss = _fetch_rows(resolved, _SQL_SRC_SVC, params)
        rows_sg = _fetch_rows(resolved, _SQL_SVC_GOV, params)
        rows_cl = _fetch_rows(resolved, _SQL_CLUSTERS, {})

    if not rows_ss and not rows_sg:
        # Could not read live data -> deterministic synthetic graph.
        return _synthetic_graph(case)

    # --- Source -> Service ------------------------------------------------- #
    for r in rows_ss:
        src = r.get("source_type")
        svc = r.get("service_id")
        if not src or not svc:
            continue
        cnt = int(r.get("cnt") or 0)
        sev = float(r.get("sev_avg") or 0.0)
        neg = float(r.get("neg_frac") or 0.0)
        service_ids.add(str(svc))

        src_id = f"src:{src}"
        svc_id = f"svc:{svc}"
        _g_add_node(
            g, src_id,
            _new_node_attrs("source", sentiment=min(1.0, 0.3 + 0.5 * neg),
                            severity=sev, volume=cnt, label_ar=str(src)),
        )
        _g_add_node(
            g, svc_id,
            _new_node_attrs("service", sentiment=min(1.0, 0.25 + 0.55 * neg),
                            severity=sev, volume=cnt, label_ar=str(svc)),
        )
        _g_add_edge(g, src_id, svc_id, cnt)

    # --- Service -> Governorate ------------------------------------------- #
    for r in rows_sg:
        svc = r.get("service_id")
        gov = r.get("governorate")
        if not svc or not gov:
            continue
        cnt = int(r.get("cnt") or 0)
        sev = float(r.get("sev_avg") or 0.0)
        service_ids.add(str(svc))

        svc_id = f"svc:{svc}"
        gov_id = f"gov:{gov}"
        _g_add_node(
            g, svc_id,
            _new_node_attrs("service", severity=sev, volume=cnt, label_ar=str(svc)),
        )
        _g_add_node(
            g, gov_id,
            _new_node_attrs("governorate", sentiment=0.2, severity=sev,
                            volume=cnt, label_ar=str(gov)),
        )
        _g_add_edge(g, svc_id, gov_id, cnt)

    # --- Root-cause clusters -> Service (keyword bridge) ------------------- #
    ranked: List[Dict[str, Any]] = []
    for r in rows_cl:
        cid = r.get("cluster_id")
        if not cid:
            continue
        label_ar = r.get("canonical_label_ar") or ""
        mc = int(r.get("member_count") or 0)
        sa = float(r.get("severity_avg") or 0.40)
        score = _rank_score(mc, sa)
        ranked.append(
            {
                "cluster_id": str(cid),
                "canonical_label_ar": label_ar,
                "canonical_label_en": r.get("canonical_label_en") or "",
                "member_count": mc,
                "severity_avg": sa,
                "score": score,
            }
        )
    ranked.sort(key=lambda x: x["score"], reverse=True)

    for rc in ranked:
        bridge_svc = _cluster_service_bridge(rc["canonical_label_ar"], service_ids)
        # Cluster node always materialized; flag as root cause if it bridges to
        # the case's service graph (so it can seed inflow on that service).
        cl_id = f"cluster:{rc['cluster_id']}"
        is_rc = bridge_svc is not None
        _g_add_node(
            g, cl_id,
            _new_node_attrs(
                "cluster",
                sentiment=min(1.0, 0.5 + 0.4 * rc["severity_avg"]),
                severity=rc["severity_avg"],
                volume=rc["member_count"],
                is_root_cause=is_rc,
                label_ar=rc["canonical_label_ar"],
                cluster_id=rc["cluster_id"],
                member_count=rc["member_count"],
                severity_avg=rc["severity_avg"],
                score=rc["score"],
            ),
        )
        if bridge_svc is not None:
            _g_add_edge(g, cl_id, f"svc:{bridge_svc}", rc["member_count"])

    _attach_meta(g, case=case, ranked=ranked)

    if _g_node_count(g) == 0:
        return _synthetic_graph(case)
    return g


def _attach_meta(g, *, case: Optional[str], ranked: List[Dict[str, Any]]) -> None:
    meta = {"case": case, "root_causes": ranked}
    if _HAVE_NX:
        g.graph["meta"] = meta
        g.graph["root_causes"] = ranked
    else:
        g["meta"] = meta
        g["root_cause"] = ranked


def _graph_meta(g) -> Dict[str, Any]:
    if _HAVE_NX:
        return g.graph.get("meta", {}) or {}
    return g.get("meta", {}) or {}


def _graph_root_causes(g) -> List[Dict[str, Any]]:
    if _HAVE_NX:
        return g.graph.get("root_causes", []) or []
    return g.get("root_cause", []) or []


# --------------------------------------------------------------------------- #
# Synthetic fallback graph (real voc360 entity names, no DB needed).          #
# Keeps the whole module + the simulate() contract working offline.           #
# --------------------------------------------------------------------------- #

def _synthetic_graph(case: Optional[str] = None):
    """Deterministic graph grounded in real voc360 entities (offline mode)."""
    g = _empty_graph()

    # (source_type, service_id, governorate, count, severity, neg_frac)
    seed_rows = [
        ("app_review", "Sanad", "العاصمة", 15800, 0.10, 0.55),
        ("social_media_sentiment", "Sanad", "إربد", 900, 0.45, 0.70),
        ("سوء_الخدمة", "Sanad", "الزرقاء", 410, 0.75, 0.85),
        ("app_review", "Amman Bus", "العاصمة", 2000, 0.30, 0.60),
        ("complaint", "Amman Bus", "الزرقاء", 320, 0.60, 0.65),
        ("عدم_الرد", "نقل_عام", "إربد", 180, 0.55, 0.75),
        ("complaint", "جوازات_السفر", "العقبة", 240, 0.65, 0.62),
        ("فساد_إداري", "مراكز_الخدمة", "السلط", 95, 0.90, 0.88),
        ("ces_survey", "الخدمات_الإلكترونية", "المفرق", 150, 0.40, 0.50),
        ("complaint", "طرق_وبنية_تحتية", "جرش", 130, 0.70, 0.72),
    ]
    service_ids = set()
    for src, svc, gov, cnt, sev, neg in seed_rows:
        service_ids.add(svc)
        src_id, svc_id, gov_id = f"src:{src}", f"svc:{svc}", f"gov:{gov}"
        _g_add_node(g, src_id, _new_node_attrs(
            "source", sentiment=min(1.0, 0.3 + 0.5 * neg), severity=sev,
            volume=cnt, label_ar=src))
        _g_add_node(g, svc_id, _new_node_attrs(
            "service", sentiment=min(1.0, 0.25 + 0.55 * neg), severity=sev,
            volume=cnt, label_ar=svc))
        _g_add_node(g, gov_id, _new_node_attrs(
            "governorate", sentiment=0.2, severity=sev, volume=cnt, label_ar=gov))
        _g_add_edge(g, src_id, svc_id, cnt)
        _g_add_edge(g, svc_id, gov_id, cnt)

    # Real top clusters (cluster_id8, label_ar, member_count, severity_avg).
    clusters = [
        ("b39d06f6", "رسوم الخدمة المستعجلة", 551, 0.40),
        ("a1c2e3f4", "تأخير دعم صندوق المعونة", 69, 0.55),
        ("c4d5e6a7", "الباص السريع", 64, 0.50),
        ("d7e8f9a0", "منصة تكافل", 55, 0.48),
        ("e0a1b2c3", "سوء الخدمة في مراكز الخدمة", 52, 0.60),
        ("f3a4b5c6", "حفريات الطرق والبنية التحتية", 23, 0.65),
    ]
    ranked = []
    for cid, label, mc, sa in clusters:
        score = _rank_score(mc, sa)
        ranked.append({
            "cluster_id": cid, "canonical_label_ar": label,
            "canonical_label_en": "", "member_count": mc,
            "severity_avg": sa, "score": score,
        })
    ranked.sort(key=lambda x: x["score"], reverse=True)

    for rc in ranked:
        bridge_svc = _cluster_service_bridge(rc["canonical_label_ar"], service_ids)
        cl_id = f"cluster:{rc['cluster_id']}"
        is_rc = bridge_svc is not None
        _g_add_node(g, cl_id, _new_node_attrs(
            "cluster",
            sentiment=min(1.0, 0.5 + 0.4 * rc["severity_avg"]),
            severity=rc["severity_avg"], volume=rc["member_count"],
            is_root_cause=is_rc, label_ar=rc["canonical_label_ar"],
            cluster_id=rc["cluster_id"], member_count=rc["member_count"],
            severity_avg=rc["severity_avg"], score=rc["score"]))
        if bridge_svc is not None:
            _g_add_edge(g, cl_id, f"svc:{bridge_svc}", rc["member_count"])

    _attach_meta(g, case=case, ranked=ranked)
    return g


# --------------------------------------------------------------------------- #
# Mesa 3 agent + model.                                                       #
# --------------------------------------------------------------------------- #

if _HAVE_MESA:

    class NodeAgent(mesa.Agent):  # type: ignore[misc]
        """One sentiment carrier per voc360 graph node.

        Mesa 3: ``super().__init__(model)`` — NO unique_id (auto-assigned),
        auto-registers into ``model.agents``. ``node_id == self.pos`` once
        placed on the NetworkGrid.
        """

        def __init__(self, model, node_id=None, kind="service", sentiment=0.0,
                     severity=0.0, volume=0, is_root_cause=False, label_ar=""):
            super().__init__(model)  # Mesa 3 signature
            self.node_id = node_id
            self.kind = kind
            self.sentiment = float(sentiment)
            self.severity = float(severity)
            self.volume = int(volume)
            self.is_root_cause = bool(is_root_cause)
            self.label_ar = label_ar

        def step(self):
            m = self.model
            # 1) inflow if this is an un-mitigated root cause (severity-scaled).
            if self.is_root_cause:
                inflow = m.inflow * (0.5 + self.severity) * (1.0 - m.intervention_for(self.pos))
                self.sentiment = min(1.0, self.sentiment + inflow)

            # 2) weighted contagion over neighbours (edge weight as influence).
            neighbors = m.grid.get_neighbors(self.pos, include_center=False)
            if neighbors:
                num = 0.0
                den = 0.0
                for nb in neighbors:
                    w = m.edge_weight(nb.pos, self.pos)
                    num += w * nb.sentiment
                    den += w
                if den > 0:
                    pull = num / den
                    self.sentiment += m.spread_rate * (pull - self.sentiment)

            # 3) decay toward calm.
            self.sentiment = max(0.0, min(1.0, self.sentiment * m.decay))

    class PropagationModel(mesa.Model):  # type: ignore[misc]
        """NetworkGrid model: sentiment contagion + inflow + decay + intervention."""

        def __init__(self, graph, spread_rate=DEFAULT_SPREAD_RATE,
                     decay=DEFAULT_DECAY, inflow=DEFAULT_INFLOW,
                     root_cause_nodes=None, intervention_node=None,
                     intervention_strength=0.0, seed=DEFAULT_SEED):
            super().__init__(seed=seed)  # MANDATORY in Mesa 3
            self.spread_rate = float(spread_rate)
            self.decay = float(decay)
            self.inflow = float(inflow)
            self.intervention_node = intervention_node
            self.intervention_strength = float(intervention_strength)

            self.grid = NetworkGrid(graph)

            # Precompute an undirected weight lookup for contagion influence.
            self._w: Dict[Tuple[Any, Any], float] = {}
            for u, v, data in graph.edges(data=True):
                w = float(data.get("weight", 1.0))
                # log-compress huge count weights so a 15.8k edge doesn't swamp.
                cw = math.log10(w + 1.0) + 1.0
                self._w[(u, v)] = cw
                self._w[(v, u)] = cw

            # Seat one agent per node, seeded from voc360 attrs.
            rc_override = set(root_cause_nodes or [])
            for node, data in graph.nodes(data=True):
                a = NodeAgent(
                    self,
                    node_id=node,
                    kind=data.get("kind", "service"),
                    sentiment=data.get("sentiment", 0.0),
                    severity=data.get("severity", 0.0),
                    volume=data.get("volume", 0),
                    is_root_cause=bool(data.get("is_root_cause", False)) or (node in rc_override),
                    label_ar=data.get("label_ar", ""),
                )
                self.grid.place_agent(a, node)

            # Apply an instantaneous damp at t0 on the intervention node.
            self.events: List[Dict[str, Any]] = []
            if intervention_node is not None and intervention_node in graph:
                for a in self.grid.get_cell_list_contents([intervention_node]):
                    a.sentiment = max(0.0, a.sentiment * (1.0 - self.intervention_strength))
                self.events.append({"step": 0, "node": intervention_node, "action": "intervene"})

            self.datacollector = DataCollector(
                model_reporters={
                    "step": "steps",
                    "mean_negativity": _r_mean_negativity,
                    "complaint_volume": _r_complaint_volume,
                    "n_critical": _r_n_critical,
                },
                agent_reporters={"sentiment": "sentiment", "kind": "kind"},
                tables={"Events": ["step", "node", "action"]},
            )
            for ev in self.events:
                self.datacollector.add_table_row("Events", ev)
            self.datacollector.collect(self)  # t0 snapshot

        def edge_weight(self, u, v) -> float:
            return self._w.get((u, v), 1.0)

        def intervention_for(self, node) -> float:
            """Per-step intervention multiplier (sustained damp on inflow)."""
            if self.intervention_node is not None and node == self.intervention_node:
                return self.intervention_strength
            return 0.0

        def step(self):
            self.agents.shuffle_do("step")
            self.datacollector.collect(self)


    def _r_mean_negativity(m) -> float:
        n = len(m.agents)
        return (sum(a.sentiment for a in m.agents) / n) if n else 0.0

    def _r_complaint_volume(m) -> float:
        return float(sum(a.sentiment * a.volume for a in m.agents))

    def _r_n_critical(m) -> int:
        return int(sum(1 for a in m.agents if a.sentiment > CRITICAL_THRESHOLD))


# --------------------------------------------------------------------------- #
# numpy / plain-python fallback model (comparable series, same schema).       #
# --------------------------------------------------------------------------- #

class _FallbackModel:
    """Pure numpy/plain dynamics mirroring PropagationModel's series.

    Implements the same contagion + inflow + decay + intervention update on the
    dict-or-networkx graph, producing the identical 3-series schema. Used when
    Mesa (or its Mesa-3 API / networkx) is unavailable, or as the numeric core
    for environments that just want determinism without Mesa installed.
    """

    def __init__(self, graph, spread_rate=DEFAULT_SPREAD_RATE,
                 decay=DEFAULT_DECAY, inflow=DEFAULT_INFLOW,
                 root_cause_nodes=None, intervention_node=None,
                 intervention_strength=0.0, seed=DEFAULT_SEED):
        self.spread_rate = float(spread_rate)
        self.decay = float(decay)
        self.inflow = float(inflow)
        self.intervention_node = intervention_node
        self.intervention_strength = float(intervention_strength)
        self.steps = 0
        self._rng = random.Random(seed)

        nodes = _g_nodes(graph)
        self.node_ids: List[str] = [nid for nid, _ in nodes]
        self.index = {nid: i for i, nid in enumerate(self.node_ids)}
        n = len(self.node_ids)

        rc_override = set(root_cause_nodes or [])
        self.kind = [a.get("kind", "service") for _, a in nodes]
        self.label_ar = [a.get("label_ar", "") for _, a in nodes]
        self.is_root = [
            bool(a.get("is_root_cause", False)) or (nid in rc_override)
            for nid, a in nodes
        ]
        sent0 = [float(a.get("sentiment", 0.0)) for _, a in nodes]
        sev0 = [float(a.get("severity", 0.0)) for _, a in nodes]
        vol0 = [float(a.get("volume", 0)) for _, a in nodes]

        # Build symmetric, log-compressed weight matrix (n x n).
        if _HAVE_NUMPY:
            self.sentiment = np.array(sent0, dtype=float)
            self.severity = np.array(sev0, dtype=float)
            self.volume = np.array(vol0, dtype=float)
            self.W = np.zeros((n, n), dtype=float)
        else:
            self.sentiment = list(sent0)
            self.severity = list(sev0)
            self.volume = list(vol0)
            self.W = [[0.0] * n for _ in range(n)]

        if _HAVE_NX and isinstance(graph, nx.DiGraph):  # type: ignore[arg-type]
            edge_iter = graph.edges(data=True)
            edges = [(u, v, d.get("weight", 1.0)) for u, v, d in edge_iter]
        else:
            edges = [(u, v, w) for (u, v, w) in graph["edges"]]
        for u, v, w in edges:
            if u not in self.index or v not in self.index:
                continue
            i, j = self.index[u], self.index[v]
            cw = math.log10(float(w) + 1.0) + 1.0
            if _HAVE_NUMPY:
                self.W[i, j] += cw
                self.W[j, i] += cw
            else:
                self.W[i][j] += cw
                self.W[j][i] += cw

        # row sums for normalization
        if _HAVE_NUMPY:
            self._rowsum = self.W.sum(axis=1)
        else:
            self._rowsum = [sum(row) for row in self.W]

        # intervention damp at t0
        self.events: List[Dict[str, Any]] = []
        if intervention_node is not None and intervention_node in self.index:
            k = self.index[intervention_node]
            factor = 1.0 - self.intervention_strength
            if _HAVE_NUMPY:
                self.sentiment[k] = max(0.0, self.sentiment[k] * factor)
            else:
                self.sentiment[k] = max(0.0, self.sentiment[k] * factor)
            self.events.append({"step": 0, "node": intervention_node, "action": "intervene"})

        self._series: List[Dict[str, Any]] = []
        self._collect()

    # --- reporters ---
    def _mean_negativity(self) -> float:
        if _HAVE_NUMPY:
            return float(self.sentiment.mean()) if len(self.sentiment) else 0.0
        return (sum(self.sentiment) / len(self.sentiment)) if self.sentiment else 0.0

    def _complaint_volume(self) -> float:
        if _HAVE_NUMPY:
            return float((self.sentiment * self.volume).sum())
        return float(sum(s * v for s, v in zip(self.sentiment, self.volume)))

    def _n_critical(self) -> int:
        if _HAVE_NUMPY:
            return int((self.sentiment > CRITICAL_THRESHOLD).sum())
        return int(sum(1 for s in self.sentiment if s > CRITICAL_THRESHOLD))

    def _collect(self) -> None:
        self._series.append({
            "step": self.steps,
            "mean_negativity": round(self._mean_negativity(), 6),
            "complaint_volume": round(self._complaint_volume(), 4),
            "n_critical": self._n_critical(),
        })

    def step(self) -> None:
        n = len(self.node_ids)
        iv_node = self.intervention_node
        iv_idx = self.index.get(iv_node) if iv_node is not None else None

        if _HAVE_NUMPY:
            s = self.sentiment
            # 1) inflow on root causes (sustained intervention damp).
            inflow_vec = np.zeros(n, dtype=float)
            for i in range(n):
                if self.is_root[i]:
                    damp = self.intervention_strength if (iv_idx == i) else 0.0
                    inflow_vec[i] = self.inflow * (0.5 + self.severity[i]) * (1.0 - damp)
            s = np.minimum(1.0, s + inflow_vec)
            # 2) weighted contagion.
            with np.errstate(divide="ignore", invalid="ignore"):
                pull = self.W.dot(s)
                rs = np.where(self._rowsum > 0, self._rowsum, 1.0)
                pull = pull / rs
            has_nbr = self._rowsum > 0
            s = np.where(has_nbr, s + self.spread_rate * (pull - s), s)
            # 3) decay.
            s = np.clip(s * self.decay, 0.0, 1.0)
            self.sentiment = s
        else:
            new = list(self.sentiment)
            for i in range(n):
                si = self.sentiment[i]
                if self.is_root[i]:
                    damp = self.intervention_strength if (iv_idx == i) else 0.0
                    si = min(1.0, si + self.inflow * (0.5 + self.severity[i]) * (1.0 - damp))
                rs = self._rowsum[i]
                if rs > 0:
                    pull = sum(self.W[i][j] * self.sentiment[j] for j in range(n)) / rs
                    si = si + self.spread_rate * (pull - si)
                new[i] = max(0.0, min(1.0, si * self.decay))
            self.sentiment = new

        self.steps += 1
        self._collect()

    # --- accessors matching the Mesa path ---
    def final_by_node(self) -> Dict[str, float]:
        out = {}
        for nid in self.node_ids:
            i = self.index[nid]
            v = self.sentiment[i]
            out[nid] = round(float(v), 6)
        return out

    def series(self) -> List[Dict[str, Any]]:
        return list(self._series)


# --------------------------------------------------------------------------- #
# Runners.                                                                     #
# --------------------------------------------------------------------------- #

def _series_from_mesa(model) -> List[Dict[str, Any]]:
    """Extract the 3-series list from a Mesa DataCollector dataframe (or dicts)."""
    dc = model.datacollector
    try:
        df = dc.get_model_vars_dataframe()
        recs = df.reset_index(drop=False).to_dict(orient="records")
        out = []
        for i, r in enumerate(recs):
            out.append({
                "step": int(r.get("step", i)),
                "mean_negativity": round(float(r.get("mean_negativity", 0.0)), 6),
                "complaint_volume": round(float(r.get("complaint_volume", 0.0)), 4),
                "n_critical": int(r.get("n_critical", 0)),
            })
        return out
    except Exception:
        # pandas unavailable -> rebuild from the collector's raw vars.
        out = []
        vars_ = getattr(dc, "model_vars", {}) or {}
        steps_col = vars_.get("step", [])
        mn = vars_.get("mean_negativity", [])
        cv = vars_.get("complaint_volume", [])
        nc = vars_.get("n_critical", [])
        for i in range(len(mn)):
            out.append({
                "step": int(steps_col[i]) if i < len(steps_col) else i,
                "mean_negativity": round(float(mn[i]), 6),
                "complaint_volume": round(float(cv[i]), 4) if i < len(cv) else 0.0,
                "n_critical": int(nc[i]) if i < len(nc) else 0,
            })
        return out


def _final_by_node_from_mesa(model) -> Dict[str, float]:
    out = {}
    for a in model.agents:
        out[a.pos] = round(float(a.sentiment), 6)
    return out


def run_simulation(
    graph,
    steps: int = DEFAULT_STEPS,
    spread_rate: float = DEFAULT_SPREAD_RATE,
    decay: float = DEFAULT_DECAY,
    inflow: float = DEFAULT_INFLOW,
    intervention_node: Optional[str] = None,
    intervention_strength: float = 0.0,
    seed: int = DEFAULT_SEED,
) -> Dict[str, Any]:
    """Run the propagation sim and return a SimResult dict.

    SimResult = {
        series: [{step, mean_negativity, complaint_volume, n_critical}],
        final_by_node: {node_id: float},
        critical_nodes: [node_id],
        params: {...},
        events: [{step, node, action}],
        engine: "mesa" | "fallback",
    }
    Construct a fresh model per call (stateful, not thread-safe to share).
    """
    steps = max(1, int(steps))
    root_cause_nodes = _g_root_cause_nodes(graph)

    if _HAVE_MESA and _HAVE_NX and isinstance(graph, nx.DiGraph):  # type: ignore[arg-type]
        model = PropagationModel(
            graph,
            spread_rate=spread_rate,
            decay=decay,
            inflow=inflow,
            root_cause_nodes=root_cause_nodes,
            intervention_node=intervention_node,
            intervention_strength=intervention_strength,
            seed=seed,
        )
        for _ in range(steps):  # manual loop — never run_model() in a request
            model.step()
        series = _series_from_mesa(model)
        final_by_node = _final_by_node_from_mesa(model)
        events = list(getattr(model, "events", []))
        engine = "mesa"
    else:
        model = _FallbackModel(
            graph,
            spread_rate=spread_rate,
            decay=decay,
            inflow=inflow,
            root_cause_nodes=root_cause_nodes,
            intervention_node=intervention_node,
            intervention_strength=intervention_strength,
            seed=seed,
        )
        for _ in range(steps):
            model.step()
        series = model.series()
        final_by_node = model.final_by_node()
        events = list(model.events)
        engine = "fallback"

    critical_nodes = sorted(
        (nid for nid, v in final_by_node.items() if v > CRITICAL_THRESHOLD),
        key=lambda nid: final_by_node[nid],
        reverse=True,
    )

    return {
        "series": series,
        "final_by_node": final_by_node,
        "critical_nodes": critical_nodes,
        "params": {
            "steps": steps,
            "spread_rate": spread_rate,
            "decay": decay,
            "inflow": inflow,
            "intervention_node": intervention_node,
            "intervention_strength": intervention_strength,
            "seed": seed,
        },
        "events": events,
        "engine": engine,
    }


def _peak(series: List[Dict[str, Any]], key: str) -> float:
    return max((float(p.get(key, 0.0)) for p in series), default=0.0)


def _ticks_to_settle(series: List[Dict[str, Any]], eps: float = 0.005) -> int:
    """First tick after which mean_negativity changes by < eps for the rest."""
    if len(series) < 2:
        return len(series)
    vals = [float(p.get("mean_negativity", 0.0)) for p in series]
    for t in range(1, len(vals)):
        if all(abs(vals[k] - vals[k - 1]) < eps for k in range(t, len(vals))):
            return t
    return len(vals)


def run_before_after(
    graph,
    *,
    intervention_node: Optional[str],
    intervention_strength: float = DEFAULT_INTERVENTION_STRENGTH,
    steps: int = DEFAULT_STEPS,
    spread_rate: float = DEFAULT_SPREAD_RATE,
    decay: float = DEFAULT_DECAY,
    inflow: float = DEFAULT_INFLOW,
    seed: int = DEFAULT_SEED,
) -> Dict[str, Any]:
    """A/B the intervention lever: identical seed, run with and without it.

    BeforeAfter = {before, after, delta:{...}, root_cause:{...}}.
    If `intervention_node` is None, auto-targets the top-ranked root-cause
    cluster node (`cluster:<id>`) for the graph's case.
    """
    ranked = _graph_root_causes(graph)
    target = intervention_node
    root_cause_meta: Dict[str, Any] = {}
    if ranked:
        top = ranked[0]
        root_cause_meta = {
            "cluster_id": top.get("cluster_id"),
            "canonical_label_ar": top.get("canonical_label_ar"),
            "member_count": top.get("member_count"),
            "severity_avg": top.get("severity_avg"),
            "score": top.get("score"),
        }
        if target is None:
            target = f"cluster:{top.get('cluster_id')}"

    # If the auto-target isn't actually a node, fall back to the worst service.
    if target is not None and not _g_has_node(graph, target):
        services = [nid for nid, a in _g_nodes(graph) if a.get("kind") == "service"]
        if services:
            services.sort(
                key=lambda nid: (_node_attr(graph, nid, "severity"),
                                 _node_attr(graph, nid, "volume")),
                reverse=True,
            )
            target = services[0]
        else:
            target = None

    before = run_simulation(
        graph, steps=steps, spread_rate=spread_rate, decay=decay, inflow=inflow,
        intervention_node=None, intervention_strength=0.0, seed=seed,
    )
    after = run_simulation(
        graph, steps=steps, spread_rate=spread_rate, decay=decay, inflow=inflow,
        intervention_node=target, intervention_strength=intervention_strength, seed=seed,
    )

    b_last = before["series"][-1] if before["series"] else {}
    a_last = after["series"][-1] if after["series"] else {}
    delta = {
        "mean_negativity_final": round(
            float(b_last.get("mean_negativity", 0.0)) - float(a_last.get("mean_negativity", 0.0)), 6),
        "n_critical_final": int(b_last.get("n_critical", 0)) - int(a_last.get("n_critical", 0)),
        "peak_mean_negativity": round(
            _peak(before["series"], "mean_negativity") - _peak(after["series"], "mean_negativity"), 6),
        "ticks_to_settle": _ticks_to_settle(after["series"]),
    }

    return {
        "before": before,
        "after": after,
        "delta": delta,
        "root_cause": root_cause_meta,
        "intervention_node": target,
    }


def _node_attr(graph, node_id: str, key: str, default: float = 0.0) -> float:
    if _HAVE_NX and isinstance(graph, nx.DiGraph):  # type: ignore[arg-type]
        return float(graph.nodes.get(node_id, {}).get(key, default))
    return float(graph["nodes"].get(node_id, {}).get(key, default))


# --------------------------------------------------------------------------- #
# Convenience entry point: simulate(case, intervene).                         #
# --------------------------------------------------------------------------- #

def simulate(
    case: Optional[str] = None,
    intervene: bool = True,
    *,
    dsn: Optional[str] = None,
    steps: int = DEFAULT_STEPS,
    spread_rate: float = DEFAULT_SPREAD_RATE,
    decay: float = DEFAULT_DECAY,
    inflow: float = DEFAULT_INFLOW,
    intervention_node: Optional[str] = None,
    intervention_strength: float = DEFAULT_INTERVENTION_STRENGTH,
    seed: int = DEFAULT_SEED,
) -> Dict[str, Any]:
    """Build the case graph from live voc360 and run the propagation sim.

    `simulate(case, intervene: bool) -> time series dict`.

    When `intervene` is True, returns the full BeforeAfter A/B (so the operator
    sees the lever's effect); when False, returns a single no-action SimResult.
    Always JSON-serializable and Arabic-safe.
    """
    graph = build_graph_for_case(case, dsn=dsn)

    if not intervene:
        result = run_simulation(
            graph, steps=steps, spread_rate=spread_rate, decay=decay, inflow=inflow,
            intervention_node=None, intervention_strength=0.0, seed=seed,
        )
        result["case"] = case
        result["root_causes"] = _graph_root_causes(graph)
        result["engine"] = result.get("engine")
        result["mesa_available"] = _HAVE_MESA
        return result

    ba = run_before_after(
        graph,
        intervention_node=intervention_node,
        intervention_strength=intervention_strength,
        steps=steps, spread_rate=spread_rate, decay=decay, inflow=inflow, seed=seed,
    )
    ba["case"] = case
    ba["root_causes"] = _graph_root_causes(graph)
    ba["mesa_available"] = _HAVE_MESA
    ba["engine"] = ba["after"].get("engine")
    return ba


# --------------------------------------------------------------------------- #
# Optional Mesa-native batch sweep (interventions test grid).                 #
# --------------------------------------------------------------------------- #

def run_batch_sweep(
    graph,
    spread_rates: Sequence[float] = (0.1, 0.3, 0.5),
    intervention_strengths: Sequence[float] = (0.0, 0.5),
    steps: int = DEFAULT_STEPS,
    repeats: int = 1,
) -> List[Dict[str, Any]]:
    """Full-factorial intervention sweep.

    Uses ``mesa.batch_run(number_processes=1)`` when Mesa is available (safe
    inside FastAPI), else replays the fallback model across the grid. Returns a
    list of records (one per run x step) suitable for a DataFrame.
    """
    if _HAVE_MESA and _HAVE_NX and isinstance(graph, nx.DiGraph):  # type: ignore[arg-type]
        try:
            rc_nodes = _g_root_cause_nodes(graph)
            params = {
                "graph": [graph],
                "spread_rate": list(spread_rates),
                "intervention_strength": list(intervention_strengths),
                "root_cause_nodes": [rc_nodes],
            }
            try:
                results = mesa.batch_run(
                    PropagationModel,
                    parameters=params,
                    rng=[None] * max(1, repeats),
                    max_steps=int(steps),
                    number_processes=1,  # =1 inside FastAPI (no spawn pitfalls)
                    data_collection_period=1,
                )
            except TypeError:
                # older signature uses iterations= instead of rng=
                results = mesa.batch_run(
                    PropagationModel,
                    parameters=params,
                    iterations=max(1, repeats),
                    max_steps=int(steps),
                    number_processes=1,
                    data_collection_period=1,
                )
            return list(results)
        except Exception:
            pass  # fall through to the fallback sweep

    # Fallback sweep (deterministic).
    out: List[Dict[str, Any]] = []
    run_id = 0
    for sr in spread_rates:
        for iv in intervention_strengths:
            for it in range(max(1, repeats)):
                res = run_simulation(
                    graph, steps=steps, spread_rate=sr,
                    intervention_node=None if iv == 0.0 else (_g_root_cause_nodes(graph)[:1] or [None])[0],
                    intervention_strength=iv, seed=DEFAULT_SEED + it,
                )
                for p in res["series"]:
                    out.append({
                        "RunId": run_id, "iteration": it, "Step": p["step"],
                        "spread_rate": sr, "intervention_strength": iv,
                        "mean_negativity": p["mean_negativity"],
                        "complaint_volume": p["complaint_volume"],
                        "n_critical": p["n_critical"],
                    })
                run_id += 1
    return out


# --------------------------------------------------------------------------- #
# Self-test (offline, no DB / no Mesa needed).                                #
# --------------------------------------------------------------------------- #

if __name__ == "__main__":  # pragma: no cover
    import json

    print(f"mesa available: {_HAVE_MESA} | networkx: {_HAVE_NX} | numpy: {_HAVE_NUMPY}")
    g = build_graph_for_case("service:Sanad")
    print(f"graph nodes: {_g_node_count(g)} | root-cause nodes: {_g_root_cause_nodes(g)[:3]}")

    res = simulate("service:Sanad", intervene=True, steps=24)
    print("before final:", res["before"]["series"][-1])
    print("after  final:", res["after"]["series"][-1])
    print("delta:", json.dumps(res["delta"], ensure_ascii=False))
    print("root_cause:", json.dumps(res["root_cause"], ensure_ascii=False))
