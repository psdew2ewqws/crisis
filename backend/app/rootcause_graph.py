"""Root-Cause Graph builder (voc360, grounded).

Turns a 5-Whys why-chain into a reactflow-ready ROOT-CAUSE GRAPH:

    symptom (service/case) → dominant cluster → sub-theme → root phrase

Each node carries real counts + evidence (sample ``segment_text``); each edge is
a grounded ``because``/``why`` link. Nodes are laid out left→right by chain depth
so the frontend (reactflow) renders the why-chain as a tree spine with sibling
clusters/sub-themes as side branches.

This module does NOT invent anything. It reuses ``whys.ask_whys`` (the grounded
5-Whys engine) for the chain + raw graph and re-projects it into reactflow shape
with AEGIS severity tones. If ``whys`` is unavailable, it degrades to a direct,
still-grounded build from ``cluster_link`` + ``ril_problem_clusters`` (real
columns only). Every failure mode returns an empty-but-valid graph — never raises.

Public API:
    build_rootcause_graph(start: dict | None = None, *, case=None, cluster_id=None,
                          max_depth=5, lang="ar") -> dict
        -> {start, nodes:[RcNode], edges:[RcEdge], chain:[...], root, stats, method, narration}

Grounding boundary: counts/labels/segments are the source of truth; the LLM
(``llm.narrate``) only phrases them in ``narration``. No torch/timesfm/llm hard dep.
"""
from __future__ import annotations

from typing import Any

# --- optional, import-safe dependencies -----------------------------------
# whys.ask_whys is the primary grounded chain source. cluster_link / db back the
# direct-fallback build. All are optional: a missing module degrades, never 500s.
try:  # the grounded 5-Whys engine (preferred path)
    from . import whys as _whys  # type: ignore
except Exception:  # pragma: no cover - import-safe
    _whys = None  # type: ignore

try:
    from . import cluster_link as _cluster_link  # type: ignore
except Exception:  # pragma: no cover
    _cluster_link = None  # type: ignore

try:
    from . import db as _db  # type: ignore
except Exception:  # pragma: no cover
    _db = None  # type: ignore

try:
    from . import llm as _llm  # type: ignore
except Exception:  # pragma: no cover
    _llm = None  # type: ignore

try:  # EN labels for Arabic cluster names (best-effort)
    from .main_v2 import translate_label as _translate_label  # type: ignore
except Exception:  # pragma: no cover
    _translate_label = None  # type: ignore


# --- AEGIS tokens (match frontend lib/voc2.ts + graph_builder tones) -------
# Background/structure tokens kept for parity; the load-bearing ones here are the
# severity → colour map used to tone each node.
AEGIS = {
    "bg": "#0A0A0B",
    "card": "#131417",
    "cardhi": "#181A1E",
    "border": "#212228",
    "txt": "#ECEDEE",
    "muted": "#8B8D96",
    "blue": "#3B82F6",
    "danger": "#F04359",
    "good": "#34D399",
    "warn": "#FBBF24",
}

# tone → AEGIS colour (mirrors voc2.ts toneColor)
_TONE_COLOR = {
    "danger": AEGIS["danger"],
    "alert": AEGIS["danger"],
    "warn": AEGIS["warn"],
    "good": AEGIS["good"],
    "calm": AEGIS["good"],
    "neutral": AEGIS["muted"],
}

# node type → glyph/role colour fallback (the "lane" colour by layer)
_TYPE_COLOR = {
    "symptom": AEGIS["blue"],
    "service": AEGIS["blue"],
    "case": AEGIS["blue"],
    "cluster": AEGIS["danger"],
    "subtheme": AEGIS["warn"],
    "phrase": AEGIS["warn"],
    "root": AEGIS["danger"],
}

# how raw whys/graph_builder node types map onto the 4 root-cause-graph lanes
_TYPE_REMAP = {
    "service": "symptom",
    "case": "symptom",
    "symptom": "symptom",
    "source": "symptom",
    "cluster": "cluster",
    "rchub": "cluster",
    "subtheme": "subtheme",
    "phrase": "phrase",
    "root": "root",
}

# x position by chain depth (left = symptom, right = root). Matches the
# graph_builder LAYER_X spacing scale so both graphs feel consistent.
_DEPTH_X = {0: 40, 1: 360, 2: 680, 3: 1000, 4: 1320, 5: 1640}
_Y_BASE = 430
_Y_GAP = 130


def _clamp01(x: float) -> float:
    try:
        return max(0.0, min(1.0, float(x)))
    except Exception:
        return 0.0


def _depth_x(depth: int) -> int:
    if depth in _DEPTH_X:
        return _DEPTH_X[depth]
    return _DEPTH_X[max(_DEPTH_X)] + (depth - max(_DEPTH_X)) * 320


def _tone_from_severity_avg(sev: float | None) -> str:
    """severity_avg is ~0..1 (or 0..4 if raw). Normalise then bucket → AEGIS tone."""
    if sev is None:
        return "neutral"
    try:
        s = float(sev)
    except Exception:
        return "neutral"
    if s > 1.0:  # raw low/med/high/critical → 1..4, normalise
        s = s / 4.0
    return "danger" if s >= 0.5 else "warn" if s >= 0.3 else "good"


def _tone_color(tone: str, ntype: str) -> str:
    return _TONE_COLOR.get(tone) or _TYPE_COLOR.get(ntype, AEGIS["muted"])


def _short(text: Any, n: int = 140) -> str:
    s = str(text or "").strip().replace("\n", " ")
    return (s[: n - 1] + "…") if len(s) > n else s


def _en_label(label_ar: str | None, label_en: str | None) -> str:
    if label_en:
        return str(label_en)
    if _translate_label and label_ar:
        try:
            t = _translate_label(label_ar)
            if t:
                return str(t)
        except Exception:
            pass
    return str(label_ar or "")


# ---------------------------------------------------------------------------
# Primary path: project whys.ask_whys() output into a reactflow root-cause graph
# ---------------------------------------------------------------------------

def _project_chain(chain: list[dict], start: dict) -> tuple[list[dict], list[dict], dict | None]:
    """Build reactflow nodes/edges from the grounded chain (the graph spine).

    Each chain step becomes one node at x=depth; consecutive steps are linked by a
    ``because``/``why`` edge carrying the grounded label + counts. Sub-themes of a
    step (``subthemes[]``) are attached as sibling side-branches so the layout
    reads as a tree. Returns (nodes, edges, root_node)."""
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    order: list[str] = []

    def add(nid: str, **kw) -> dict:
        if nid not in nodes:
            nodes[nid] = {"id": nid, **kw}
            order.append(nid)
        else:
            nodes[nid].update({k: v for k, v in kw.items() if v is not None})
        return nodes[nid]

    # symptom root (depth 0) — the case/service the chain starts from
    skey = str(start.get("key") or "all")
    stype = str(start.get("type") or "service")
    symptom_id = f"symptom::{skey}"
    add(
        symptom_id,
        type="symptom",
        label=skey if stype != "cluster" else f"cluster {skey[:8]}",
        label_ar=None,
        value=0,
        severity="neutral",
        tone="neutral",
        depth=0,
        signals=0,
        evidence=[],
        kind="symptom",
    )

    prev_id = symptom_id
    last_step_id = symptom_id

    for step in chain or []:
        depth = int(step.get("depth", 0) or 0)
        nid = str(step.get("node_id") or f"why::{depth}")
        because = step.get("because") or step.get("answer") or step.get("question") or ""
        because_en = step.get("because_en") or _en_label(step.get("because"), None)
        raw_type = str(step.get("kind", "")).split("→")[-1].strip() or "cluster"
        ntype = _TYPE_REMAP.get(raw_type, "cluster")
        signals = int(step.get("signals") or step.get("members") or 0)
        sev_avg = step.get("severity_avg")
        tone = _tone_from_severity_avg(sev_avg)
        conf = _clamp01(step.get("confidence", 0.0))
        evidence = [_short(e) for e in (step.get("evidence") or [])][:3]

        add(
            nid,
            type=ntype,
            label=_short(because_en or because, 46) or f"why {depth}",
            label_ar=_short(because, 80),
            value=signals,
            signals=signals,
            members=step.get("members"),
            severity_avg=round(float(sev_avg), 2) if sev_avg is not None else None,
            severity=tone,
            tone=tone,
            depth=depth,
            confidence=round(conf, 2),
            evidence=evidence,
            question=step.get("question"),
            answer=step.get("answer"),
            kind=raw_type,
        )

        # spine edge: prev why → this why, labelled with the grounded 'because'
        edges.append(
            {
                "source": prev_id,
                "target": nid,
                "weight": signals,
                "kind": "because",
                "label": _short(because_en or because, 40),
                "label_ar": _short(because, 60),
                "confidence": round(conf, 2),
            }
        )
        prev_id = nid
        last_step_id = nid

        # sibling sub-themes (side branches), grounded, not on the spine
        for st in (step.get("subthemes") or [])[:5]:
            term = st.get("term") or ""
            if not term:
                continue
            sid = f"st::{depth}::{term}"
            cnt = int(st.get("count") or 0)
            samples = [_short(x) for x in (st.get("samples") or [])][:2]
            add(
                sid,
                type="subtheme",
                label=_short(term, 30),
                label_ar=_short(term, 40),
                value=cnt,
                signals=cnt,
                severity="warn",
                tone="warn",
                depth=depth + 1,
                confidence=round(_clamp01(st.get("weight", 0.0)), 2),
                evidence=samples,
                kind="subtheme",
                sibling=True,
            )
            edges.append(
                {
                    "source": nid,
                    "target": sid,
                    "weight": cnt,
                    "kind": "subtheme",
                    "label": _short(term, 24),
                }
            )

    # mark the deepest spine step as the root cause
    root_node = None
    if last_step_id != symptom_id and last_step_id in nodes:
        nodes[last_step_id]["is_root"] = True
        rn = nodes[last_step_id]
        # keep its lane colour but flag as root for the UI
        root_node = {
            "node_id": rn["id"],
            "because": rn.get("label_ar"),
            "because_en": rn.get("label"),
            "depth": rn.get("depth"),
            "confidence": rn.get("confidence"),
            "signals": rn.get("signals"),
        }

    _layout(list(nodes.values()))
    return [nodes[i] for i in order], edges, root_node


def _layout(nodes: list[dict]) -> None:
    """x by depth; y stacked within each depth column (siblings spread vertically)."""
    by_depth: dict[int, list[dict]] = {}
    for n in nodes:
        n["x"] = _depth_x(int(n.get("depth", 0) or 0))
        by_depth.setdefault(int(n.get("depth", 0) or 0), []).append(n)
    for _depth, items in by_depth.items():
        offset = (len(items) - 1) * _Y_GAP / 2
        for i, n in enumerate(items):
            n["y"] = _Y_BASE + i * _Y_GAP - offset
        # attach the resolved render colour now that tone+type are known
    for n in nodes:
        n["color"] = _tone_color(n.get("tone") or n.get("severity") or "neutral", n.get("type", "cluster"))


# ---------------------------------------------------------------------------
# Fallback path: build a grounded graph directly (no whys engine available)
# ---------------------------------------------------------------------------

_Q_CLUSTER = """
  select cluster_id, canonical_label_ar, canonical_label_en,
         coalesce(member_count,0) member_count, coalesce(severity_avg,0) severity_avg
  from ril_problem_clusters
  where cluster_id = %(cid)s
"""
_Q_TOP_CLUSTER_FOR_SVC = """
  select cluster_id, canonical_label_ar, canonical_label_en,
         coalesce(member_count,0) member_count, coalesce(severity_avg,0) severity_avg
  from ril_problem_clusters
  where coalesce(member_count,0) > 1 and service_id = %(svc)s
  order by member_count desc limit 1
"""
_Q_SAMPLES = """
  select s.segment_text
  from ril_cluster_members m join ril_text_segments s on s.segment_id = m.segment_id
  where m.cluster_id = %(cid)s and length(s.segment_text) > 12
  order by m.distance_to_centroid asc nulls last
  limit 3
"""


def _resolve_cluster(start: dict) -> dict | None:
    """Resolve start → a real cluster row (symptom→dominant cluster) for the
    fallback build. Returns None if nothing grounds (never fabricates)."""
    if _db is None:
        return None
    stype = start.get("type")
    key = start.get("key")
    if not key:
        return None
    try:
        if stype == "cluster":
            rows = _db.fetchall(_Q_CLUSTER, {"cid": str(key)})
            return rows[0] if rows else None
        # service → dominant cluster: prefer the recovered text-link, else SQL
        if _cluster_link is not None:
            try:
                edges = _cluster_link.service_cluster_edges()
                cands = [(cid, w) for svc, cid, w in edges if svc == key]
                if cands:
                    cands.sort(key=lambda x: x[1], reverse=True)
                    rows = _db.fetchall(_Q_CLUSTER, {"cid": cands[0][0]})
                    if rows:
                        return rows[0]
            except Exception:
                pass
        rows = _db.fetchall(_Q_TOP_CLUSTER_FOR_SVC, {"svc": str(key)})
        return rows[0] if rows else None
    except Exception:
        return None


def _fallback_graph(start: dict) -> dict:
    """Two-node grounded graph (symptom → dominant cluster) when whys is absent.

    Still real: cluster row from ril_problem_clusters, signal count + evidence
    from cluster_link / ril_text_segments. Degrades to symptom-only if no cluster."""
    skey = str(start.get("key") or "all")
    stype = str(start.get("type") or "service")
    symptom_id = f"symptom::{skey}"
    nodes: list[dict] = [
        {
            "id": symptom_id,
            "type": "symptom",
            "label": skey if stype != "cluster" else f"cluster {skey[:8]}",
            "value": 0,
            "signals": 0,
            "severity": "neutral",
            "tone": "neutral",
            "depth": 0,
            "evidence": [],
            "kind": "symptom",
        }
    ]
    edges: list[dict] = []
    chain: list[dict] = []
    root_node: dict | None = None

    cl = _resolve_cluster(start)
    if cl:
        cid = str(cl["cluster_id"])
        signals = 0
        if _cluster_link is not None:
            try:
                signals = _cluster_link.cluster_signals(cid)
            except Exception:
                signals = 0
        signals = signals or int(cl.get("member_count") or 0)
        evidence: list[str] = []
        if _db is not None:
            try:
                evidence = [_short(r["segment_text"]) for r in _db.fetchall(_Q_SAMPLES, {"cid": cid})][:3]
            except Exception:
                evidence = []
        sev_avg = cl.get("severity_avg")
        tone = _tone_from_severity_avg(sev_avg)
        because = cl.get("canonical_label_ar") or ""
        because_en = _en_label(cl.get("canonical_label_ar"), cl.get("canonical_label_en"))
        nid = f"cl::{cid[:8]}"
        conf = round(_clamp01(0.45 * min(1.0, signals / 60.0) + 0.20 * (
            (float(sev_avg) / 4.0) if (sev_avg and float(sev_avg) > 1) else float(sev_avg or 0))), 2)
        nodes.append(
            {
                "id": nid,
                "type": "cluster",
                "label": _short(because_en or because, 46),
                "label_ar": _short(because, 80),
                "value": int(cl.get("member_count") or 0),
                "signals": signals,
                "members": int(cl.get("member_count") or 0),
                "severity_avg": round(float(sev_avg), 2) if sev_avg is not None else None,
                "severity": tone,
                "tone": tone,
                "depth": 1,
                "confidence": conf,
                "evidence": evidence,
                "is_root": True,
                "kind": "cluster",
            }
        )
        edges.append(
            {
                "source": symptom_id,
                "target": nid,
                "weight": signals,
                "kind": "because",
                "label": _short(because_en or because, 40),
                "label_ar": _short(because, 60),
                "confidence": conf,
            }
        )
        chain = [
            {
                "depth": 1,
                "node_id": nid,
                "question": f"Why is {skey} generating negative signals?",
                "because": because,
                "because_en": because_en,
                "evidence": evidence,
                "signals": signals,
                "members": int(cl.get("member_count") or 0),
                "severity_avg": round(float(sev_avg), 2) if sev_avg is not None else None,
                "confidence": conf,
                "kind": "service→cluster",
            }
        ]
        root_node = {
            "node_id": nid,
            "because": because,
            "because_en": because_en,
            "depth": 1,
            "confidence": conf,
            "signals": signals,
        }

    _layout(nodes)
    depth = max((int(n.get("depth", 0) or 0) for n in nodes), default=0)
    return {
        "start": {"type": stype, "key": skey},
        "nodes": nodes,
        "edges": edges,
        "chain": chain,
        "root": root_node,
        "stats": {
            "depth": depth,
            "nodes": len(nodes),
            "edges": len(edges),
            "signals": sum(int(n.get("signals") or 0) for n in nodes),
        },
        "method": "grounded-fallback" if cl else "empty",
        "narration": "",
    }


# ---------------------------------------------------------------------------
# Narration (LLM only phrases the retrieved chain facts; deterministic fallback)
# ---------------------------------------------------------------------------

def _narrate(start: dict, chain: list[dict], root: dict | None) -> str:
    facts = [
        {
            "question": s.get("question"),
            "because": s.get("because") or s.get("label_ar"),
            "because_en": s.get("because_en") or s.get("label"),
            "signals": s.get("signals"),
            "severity_avg": s.get("severity_avg"),
            "confidence": s.get("confidence"),
            "evidence": (s.get("evidence") or [])[:1],
        }
        for s in (chain or [])
    ]
    # deterministic grounded summary (this IS the answer if the LLM is down)
    if facts:
        spine = " → ".join(
            f"{f.get('because_en') or f.get('because') or '?'} ({f.get('signals') or 0} signals)"
            for f in facts
        )
        det = f"Why-chain for {start.get('key')}: {spine}."
        if root:
            det += f" Root cause: {root.get('because_en') or root.get('because')} (depth {root.get('depth')}, confidence {root.get('confidence')})."
    else:
        det = f"No grounded why-chain available for {start.get('key')}."

    if _llm is None:
        return det
    try:
        out = _llm.narrate(
            "Narrate ONLY these grounded why-steps as a root-cause chain; cite the "
            "signal counts exactly; do not add any why or number not listed; if a step "
            "is unknown say so.",
            {"case": start.get("key"), "chain_facts": facts, "root": root},
        )
        return out or det
    except Exception:
        return det


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build_rootcause_graph(
    start: dict | None = None,
    *,
    case: str | None = None,
    cluster_id: str | None = None,
    max_depth: int = 5,
    lang: str = "ar",
) -> dict[str, Any]:
    """Build the reactflow ROOT-CAUSE GRAPH from a grounded 5-Whys why-chain.

    Args (any one resolves the start entity):
      start      = {"type": "service"|"cluster", "key": <service_id|cluster_id>}
      case       = a service_id (or "all") — convenience for the graph endpoint
      cluster_id = a cluster_id — convenience for cluster-rooted graphs

    Returns {start, nodes, edges, chain, root, stats, method, narration}.
    nodes are reactflow-ready: {id,type,label,label_ar?,value,signals,severity,
    tone,color,depth,x,y,confidence,evidence[],is_root?,...}; edges
    {source,target,weight,kind∈{because,subtheme},label,...}. Never raises."""
    # resolve the start spec
    if not start:
        if cluster_id:
            start = {"type": "cluster", "key": cluster_id}
        elif case and case != "all":
            start = {"type": "service", "key": case}
        else:
            start = {"type": "service", "key": case or "all"}
    start = {"type": start.get("type", "service"), "key": start.get("key")}

    # primary: delegate to the grounded whys engine, then re-project to reactflow
    if _whys is not None and getattr(_whys, "ask_whys", None):
        try:
            res = _whys.ask_whys(dict(start), max_depth=max_depth, lang=lang)
            chain = res.get("chain") or []
            if chain:
                nodes, edges, root_node = _project_chain(chain, start)
                depth = max((int(n.get("depth", 0) or 0) for n in nodes), default=0)
                narration = res.get("narration") or _narrate(start, chain, root_node or res.get("root"))
                return {
                    "start": start,
                    "nodes": nodes,
                    "edges": edges,
                    "chain": chain,
                    "root": root_node or res.get("root"),
                    "stats": {
                        "depth": depth,
                        "nodes": len(nodes),
                        "edges": len(edges),
                        "signals": sum(int(n.get("signals") or 0) for n in nodes if not n.get("sibling")),
                    },
                    "method": res.get("method") or "grounded",
                    "narration": narration,
                }
        except Exception:
            pass  # fall through to the direct grounded build

    # fallback: build a grounded graph straight from cluster_link + ril tables
    g = _fallback_graph(start)
    g["narration"] = _narrate(start, g.get("chain") or [], g.get("root"))
    return g


__all__ = ["build_rootcause_graph", "AEGIS"]
