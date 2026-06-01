"""AEGIS Deer Graph — T1 real-pipeline augmentation.

Adds the *recovered* root-cause edges to an already-built graph so the chain
`Signal(the_data) → Segment(ril_text_segments) → Cluster(ril_problem_clusters)
→ Service(the_data.service_id)` is genuine rather than keyword-guessed.

This module does NOT rebuild the graph. It takes the dict produced by
``graph_builder.build_graph(case)`` and, in place:

  1. adds ``kind='root_cause_real'`` edges ``svc::<service_id> → cl::<cluster_id[:8]>``
     whose weight is the number of distinct recovered records bridging that
     (service, cluster) pair (from ``linker``/``links.json``);
  2. sets each cluster node's ``signal_count`` (a.k.a. ``signals``) from the
     recovered per-cluster record counts;
  3. drops the keyword ``kind='root_cause'`` fallback edges for any cluster that
     now has at least one real edge (keyword edges stay only where recovery
     produced nothing — so the graph never loses connectivity);
  4. records provenance in ``g['stats']`` (``real_links``, ``real_edges``,
     ``clusters_hit``, ``real_source``).

Import-safe: the linker module, its data cache, and the DB may all be absent.
Every failure mode degrades to "no augmentation" and returns the graph untouched.

Public API:
    augment_graph_real(g: dict, case: str | None = None) -> dict
"""
from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Resolve the recovery backend. The canonical module is ``linker`` (per
# D-pipeline); some build branches name it ``cluster_link``. Function names may
# also vary (cluster_service_edges / service_cluster_edges, cluster_signal_counts
# / cluster_counts). We bind to whatever exists and degrade if nothing does.
# ---------------------------------------------------------------------------
_LINKER: Any = None
_LINKER_NAME: str | None = None

for _modname in ("linker", "cluster_link"):
    try:
        _mod = __import__(f"{__package__}.{_modname}", fromlist=[_modname]) if __package__ \
            else __import__(_modname)
    except Exception:
        continue
    if _mod is not None:
        _LINKER = _mod
        _LINKER_NAME = _modname
        break


def _load_links() -> dict | None:
    """Return the parsed link cache (links.json) or None. Never raises."""
    if _LINKER is None:
        return None
    loader = getattr(_LINKER, "load_links", None)
    if not callable(loader):
        return None
    try:
        links = loader()
    except Exception:
        return None
    return links if isinstance(links, dict) else None


def _edges_from_links(links: dict) -> list[dict]:
    """Service→Cluster edge records: [{cluster_id, service_id, records, severity_avg}].

    Prefers a linker helper; falls back to the pre-computed ``cluster_service``
    array embedded in links.json. Never raises.
    """
    for fn_name in ("cluster_service_edges", "service_cluster_edges"):
        fn = getattr(_LINKER, fn_name, None) if _LINKER is not None else None
        if callable(fn):
            try:
                rows = fn(links)
                if isinstance(rows, list):
                    return [r for r in rows if isinstance(r, dict)]
            except Exception:
                pass  # fall through to the embedded array
    rows = links.get("cluster_service") if isinstance(links, dict) else None
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def _counts_from_links(links: dict) -> dict[str, int]:
    """Per-cluster recovered record counts: {cluster_id: int}. Never raises."""
    for fn_name in ("cluster_signal_counts", "cluster_counts"):
        fn = getattr(_LINKER, fn_name, None) if _LINKER is not None else None
        if callable(fn):
            try:
                d = fn(links)
                if isinstance(d, dict):
                    return {str(k): int(v) for k, v in d.items()}
            except Exception:
                pass
    d = links.get("cluster_counts") if isinstance(links, dict) else None
    if isinstance(d, dict):
        out: dict[str, int] = {}
        for k, v in d.items():
            try:
                out[str(k)] = int(v)
            except (TypeError, ValueError):
                continue
        return out
    return {}


def _cl8(cluster_id: str) -> str:
    """Node-id form of a cluster id — must match graph_builder (`cl::<id[:8]>`)."""
    return f"cl::{str(cluster_id)[:8]}"


def augment_graph_real(g: dict[str, Any], case: str | None = None) -> dict[str, Any]:
    """Augment a built graph with real, text-recovered Service→Cluster edges.

    Mutates and returns ``g`` (the dict from ``graph_builder.build_graph``).
    Safe to call on any graph; if recovery data is unavailable the graph is
    returned with ``stats.real_source == 'none'`` and otherwise unchanged.

    Args:
        g:    graph dict with ``nodes``, ``edges``, ``stats`` (see graph_builder).
        case: the active case/service filter (accepted for signature parity; the
              recovered links are global, so they're filtered against the nodes
              already present in ``g`` rather than re-queried per case).
    """
    if not isinstance(g, dict):
        return g
    nodes = g.get("nodes")
    edges = g.get("edges")
    stats = g.get("stats")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return g
    if not isinstance(stats, dict):
        stats = {}
        g["stats"] = stats

    # Index nodes by id for O(1) lookup. Build the reverse map cl8 → full id so
    # we can attribute per-cluster counts even though edges carry the short id.
    node_by_id: dict[str, dict] = {}
    cl8_to_node: dict[str, dict] = {}
    for n in nodes:
        if not isinstance(n, dict):
            continue
        nid = n.get("id")
        if not isinstance(nid, str):
            continue
        node_by_id[nid] = n
        if n.get("type") == "cluster":
            cl8_to_node[nid] = n  # cluster node ids are already the cl:: short form

    links = _load_links()
    if not links:
        # No recovery available — keep keyword fallback edges, mark provenance.
        stats.setdefault("real_links", 0)
        stats.setdefault("real_edges", 0)
        stats.setdefault("clusters_hit", 0)
        stats["real_source"] = "none"
        return g

    counts = _counts_from_links(links)
    real_edge_specs = _edges_from_links(links)

    # 1) Stamp per-cluster recovered signal counts onto cluster nodes.
    #    Expose under both 'signal_count' (D-pipeline) and 'signals' (task) so
    #    either frontend contract resolves; default any cluster node to 0.
    for n in cl8_to_node.values():
        n.setdefault("signal_count", 0)
        n.setdefault("signals", 0)
    for cid, cnt in counts.items():
        node = cl8_to_node.get(_cl8(cid))
        if node is not None:
            node["signal_count"] = cnt
            node["signals"] = cnt

    # 2) Add real Service→Cluster edges; dedupe (service, cluster) pairs.
    seen_pairs: set[tuple[str, str]] = set()
    clusters_with_real: set[str] = set()
    real_records_total = 0
    real_edges_added = 0

    for spec in real_edge_specs:
        service_id = spec.get("service_id")
        cluster_id = spec.get("cluster_id")
        if service_id is None or cluster_id is None:
            continue
        svc_nid = f"svc::{service_id}"
        cl_nid = _cl8(cluster_id)
        # Only emit edges whose endpoints exist in THIS (possibly case-filtered)
        # graph — no dangling edges (verification §7).
        if svc_nid not in node_by_id or cl_nid not in node_by_id:
            continue
        pair = (svc_nid, cl_nid)
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)

        try:
            weight = int(spec.get("records") or 0)
        except (TypeError, ValueError):
            weight = 0
        sev_avg = spec.get("severity_avg")

        edge: dict[str, Any] = {
            "source": svc_nid,
            "target": cl_nid,
            "weight": weight,
            "kind": "root_cause_real",
        }
        if sev_avg is not None:
            try:
                edge["severity_avg"] = round(float(sev_avg), 2)
            except (TypeError, ValueError):
                pass
        edges.append(edge)

        clusters_with_real.add(cl_nid)
        real_records_total += weight
        real_edges_added += 1

    # 3) Drop keyword 'root_cause' fallback edges for clusters that now have a
    #    real edge. Keep them where recovery produced nothing, so connectivity
    #    is never lost.
    if clusters_with_real:
        g["edges"] = [
            e for e in edges
            if not (
                isinstance(e, dict)
                and e.get("kind") == "root_cause"
                and e.get("target") in clusters_with_real
            )
        ]

    # 4) Provenance for the UI / debugging.
    stats["real_links"] = real_records_total
    stats["real_edges"] = real_edges_added
    stats["clusters_hit"] = len(clusters_with_real)
    stats["real_source"] = _LINKER_NAME or "links.json"

    return g
