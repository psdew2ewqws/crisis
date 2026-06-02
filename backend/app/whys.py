"""5-Whys WHY-CHAIN engine — iteratively ask 'why' from a service/cluster down to a
specific root cause, every step grounded in REAL voc360 counts + evidence, producing
a why-chain + a ROOT-CAUSE GRAPH.

Per D-whys. Entry point ``ask_whys(start, max_depth=5, lang='ar')``:

  start = {"type": "service"|"cluster"|"all", "key": <service_id|cluster_id|None>}

Returns:
  {start, chain:[step], root, graph:{nodes,edges,stats}, narration, method}

The chain is the graph SPINE (symptom → dominant cluster → sub-theme → specific
phrase → root); sibling clusters / sub-themes are side branches, so it reads as a
tree. Every ``because`` / ``evidence`` is a RETRIEVED real Arabic string; the LLM
(``llm.narrate``) only PHRASES the retrieved facts — counts/labels/segments are the
source of truth and the function NEVER fabricates.

Grounding (all real voc360 columns, verified against the existing backend):
  - depth 1 service → dominant cluster: ``cluster_link.service_cluster_edges()``
    (already ``(service, cluster_id, weight)`` recovered by text match), pick the
    max-weight cluster, enrich from ``ril_problem_clusters``; signals via
    ``cluster_link.cluster_signals(cid)``. A ``cluster`` start skips to depth 2.
  - depth 2 cluster → sub-theme: ``extract_subthemes`` over member ``segment_text``
    (``ril_cluster_members ⋈ ril_text_segments where cluster_id=%(cid)s``).
  - depth 3 sub-theme → specific phrase: filter member segments containing the term,
    re-run the extractor on BIGRAMS + a responsible-factor keyword map.

Import-safe: db / cluster_link / rootcause / llm / main_v2 are all imported behind
try/except, so a missing dependency (or DB outage) degrades to fewer steps + a
deterministic grounded summary, and never raises. No hard torch/timesfm/llm dep.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

# --- import-safe optional dependencies -------------------------------------
try:
    from . import db  # db.fetchall(sql, params)->list[dict]; psycopg %(name)s params
except Exception:  # pragma: no cover - import-safety
    db = None  # type: ignore

try:
    from . import cluster_link  # recovered cluster→service edges + signal counts
except Exception:  # pragma: no cover
    cluster_link = None  # type: ignore

try:
    from . import rootcause  # rank_root_causes(limit) — for type='all' resolution
except Exception:  # pragma: no cover
    rootcause = None  # type: ignore

try:
    from . import llm  # narrate(prompt, context) — presentation only
except Exception:  # pragma: no cover
    llm = None  # type: ignore

try:
    from . import main_v2  # translate_label(ar, en)
except Exception:  # pragma: no cover
    main_v2 = None  # type: ignore


# ===========================================================================
# AEGIS design tokens (severity → tone), mirroring graph_builder._tone_from_sev
# so the why-graph renders consistently with the existing reactflow graph.
# ===========================================================================
TONE_ALERT = "alert"   # danger  #F04359
TONE_WARN = "warn"     # warn    #FBBF24
TONE_CALM = "calm"     # good    #34D399
TONE_NEUTRAL = "neutral"


def _tone_from_sev(sev: float) -> str:
    """severity_avg (0..~1) → AEGIS tone, matching graph_builder._tone_from_sev."""
    try:
        s = float(sev)
    except Exception:
        return TONE_NEUTRAL
    return TONE_ALERT if s >= 0.5 else TONE_WARN if s >= 0.3 else TONE_CALM


def _clamp01(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def _en(label_ar: Optional[str], label_en: Optional[str] = None) -> str:
    """English gloss for an Arabic label, via main_v2.translate_label when present."""
    if main_v2 is not None:
        try:
            return main_v2.translate_label(label_ar, label_en)
        except Exception:
            pass
    if label_en and str(label_en).strip():
        return str(label_en).strip()
    return (str(label_ar).strip() if label_ar else "") or "Unlabelled problem"


# ===========================================================================
# Arabic-aware sub-theme extractor (pure-python; no external NLP dep)
# ===========================================================================
# Tashkeel (diacritics) + tatweel — stripped before tokenising.
_TASHKEEL = re.compile(r"[ؗ-ًؚ-ْـٰۖ-ۭ]")
_NONWORD = re.compile(r"[^؀-ۿ\w]+", re.UNICODE)

# Arabic stopwords (function words / connectors) — never a sub-theme on their own.
_AR_STOP = {
    "في", "من", "على", "عن", "الى", "إلى", "مع", "هذا", "هذه", "ذلك", "التي",
    "الذي", "ان", "أن", "إن", "كان", "كانت", "قد", "لا", "ما", "هو", "هي",
    "هم", "نحن", "انا", "أنا", "او", "أو", "ثم", "كل", "بعض", "غير", "بين",
    "عند", "حتى", "اذا", "إذا", "لكن", "بل", "كما", "حيث", "كي", "لان", "لأن",
    "اي", "أي", "بعد", "قبل", "فوق", "تحت", "هناك", "هنا", "الان", "الآن",
    "ولا", "ولم", "ولن", "فلا", "وما", "وان", "وفي", "ومن", "وعلى",
    "يوم", "جدا", "جداً", "ايضا", "أيضا", "كذلك", "نفس", "تم", "يتم", "به",
    "له", "لها", "لهم", "منها", "منه", "عليه", "عليها", "فيه", "فيها", "وهو",
    "وهي", "وقد", "وكان", "الا", "إلا", "شي", "شيء", "اكثر", "أكثر", "خلال",
    "the", "and", "for", "with", "this", "that", "are", "was", "not", "you",
    "from", "have", "has", "but", "all", "can", "our", "their", "they",
}

# Generic service-name tokens — drop so the sub-theme is the PROBLEM, not the app.
_SERVICE_STOP = {
    "سند", "sanad", "باص", "عمان", "amman", "bus", "تطبيق", "خدمة", "خدمات",
    "نظام", "منصة", "موقع", "app", "service", "bekhedmetkom", "takaful",
    "البرنامج", "برنامج",
}

# Responsible-factor keyword map (depth-3): each maps an Arabic cue → the
# accountable mechanism, so the deepest 'why' names a SPECIFIC root, not a symptom.
_FACTOR_MAP: List[Tuple[Tuple[str, ...], str, str]] = [
    (("تاخير", "تأخير", "بطيء", "بطء", "ينتظر", "انتظار", "delay", "slow"),
     "SLA / process latency", "بطء الإجراءات وتجاوز مدة الخدمة"),
    (("رسوم", "رسم", "دفع", "سعر", "تكلفة", "مبلغ", "fee", "cost", "price"),
     "Pricing / fees policy", "سياسة الرسوم والتكاليف"),
    (("منصة", "تطبيق", "نظام", "موقع", "خطا", "خطأ", "error", "bug", "crash", "تحديث"),
     "Platform / IT reliability", "خلل المنصة والأنظمة الإلكترونية"),
    (("رد", "اجابة", "إجابة", "تواصل", "اتصال", "موظف", "خدمة العملاء", "response", "staff"),
     "Staffing / responsiveness", "ضعف الرد والتواصل مع المواطن"),
    (("ازدحام", "زحمة", "طابور", "صف", "اكتظاظ", "queue", "crowd"),
     "Capacity / crowding", "الازدحام ونقص الطاقة الاستيعابية"),
]


def _normalize_ar(text: str) -> str:
    """Strip tashkeel/tatweel, unify alef/ya/ta-marbuta, lower-case latin."""
    if not text:
        return ""
    t = _TASHKEEL.sub("", str(text))
    t = (t.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
           .replace("ى", "ي").replace("ة", "ه").replace("ؤ", "و").replace("ئ", "ي"))
    return t.lower().strip()


def _tokenize(text: str) -> List[str]:
    norm = _normalize_ar(text)
    raw = _NONWORD.split(norm)
    out: List[str] = []
    for w in raw:
        w = w.strip()
        if len(w) < 3:
            continue
        if w in _AR_STOP or w in _SERVICE_STOP:
            continue
        if w.isdigit():
            continue
        out.append(w)
    return out


def extract_subthemes(segments: List[str], n: int = 8, ngram: int = 1) -> List[Dict[str, Any]]:
    """Pure-python sub-theme extractor over a list of problem ``segment_text``.

    Normalise Arabic → tokenize → drop short/stopword/service tokens → count
    uni-grams (``ngram=1``) or bi-grams (``ngram=2``) → rank by frequency.

    Returns ``[{term, count, weight, samples}]`` where ``weight = count/total``
    and ``samples`` are ≤2 RAW (un-normalised) segments containing the term —
    real evidence, never synthesised.
    """
    segs = [s for s in (segments or []) if s and str(s).strip()]
    if not segs:
        return []

    counts: Dict[str, int] = {}
    # Track one or two raw sample segments per term for evidence.
    samples: Dict[str, List[str]] = {}

    for seg in segs:
        toks = _tokenize(seg)
        if ngram >= 2:
            terms = [f"{toks[i]} {toks[i + 1]}" for i in range(len(toks) - 1)]
        else:
            terms = toks
        seen_in_seg = set()
        for term in terms:
            if term in seen_in_seg:
                continue  # count each term once per segment (document frequency)
            seen_in_seg.add(term)
            counts[term] = counts.get(term, 0) + 1
            if len(samples.get(term, [])) < 2:
                samples.setdefault(term, []).append(str(seg).strip()[:160])

    total = float(len(segs)) or 1.0
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    out: List[Dict[str, Any]] = []
    for term, c in ranked[: max(0, n)]:
        out.append({
            "term": term,
            "count": int(c),
            "weight": round(c / total, 3),
            "samples": samples.get(term, []),
        })
    return out


def _map_factor(term: str, segments: List[str]) -> Optional[Tuple[str, str]]:
    """Map a sub-theme term (+ its segments) to a responsible factor (en, ar).

    The term's OWN cue takes priority; only if the term itself matches no factor
    do we fall back to scanning its supporting segments.
    """
    norm_term = _normalize_ar(term)
    for cues, en, ar in _FACTOR_MAP:
        if any(_normalize_ar(c) in norm_term for c in cues):
            return en, ar
    hay = _normalize_ar(" ".join(segments[:6]))
    for cues, en, ar in _FACTOR_MAP:
        if any(_normalize_ar(c) in hay for c in cues):
            return en, ar
    return None


# ===========================================================================
# Real-data retrieval helpers (all read-only, %(name)s params; never raise)
# ===========================================================================
def _fetch_cluster(cluster_id: str) -> Optional[Dict[str, Any]]:
    """Enrich a cluster from ril_problem_clusters (real columns only)."""
    if db is None or not cluster_id:
        return None
    try:
        return db.fetchone(
            """
            select cluster_id, canonical_label_ar, canonical_label_en,
                   coalesce(member_count, 0) as member_count,
                   coalesce(severity_avg, 0) as severity_avg,
                   first_seen, last_seen
            from ril_problem_clusters
            where cluster_id = %(cid)s
            """,
            {"cid": cluster_id},
        )
    except Exception:
        return None


def _fetch_member_segments(cluster_id: str, limit: int = 600) -> List[Dict[str, Any]]:
    """Member problem-segments for a cluster, most representative first.

    ``ril_cluster_members ⋈ ril_text_segments``; ordered by
    ``distance_to_centroid`` (closest = most representative).
    """
    if db is None or not cluster_id:
        return []
    try:
        return db.fetchall(
            """
            select s.segment_text, s.confidence, m.distance_to_centroid
            from ril_cluster_members m
            join ril_text_segments s on s.segment_id = m.segment_id
            where m.cluster_id = %(cid)s
              and length(s.segment_text) > 8
            order by m.distance_to_centroid asc nulls last
            limit %(lim)s
            """,
            {"cid": cluster_id, "lim": limit},
        )
    except Exception:
        return []


def _service_signal_count(service_id: str) -> int:
    """Total the_data signals for a service (denominator for confidence share)."""
    if db is None or not service_id:
        return 0
    try:
        row = db.fetchone(
            "select count(*) as n from the_data where service_id = %(svc)s",
            {"svc": service_id},
        )
        return int(row["n"]) if row else 0
    except Exception:
        return 0


def _dominant_cluster_for_service(service_id: str) -> Optional[Dict[str, Any]]:
    """Depth-1 link: pick the max-weight cluster for a service.

    Reuses ``cluster_link.service_cluster_edges()`` (already recovered
    ``(service, cluster_id, weight)`` by text match), then enriches from
    ``ril_problem_clusters``.
    """
    if cluster_link is None or not service_id:
        return None
    try:
        edges = cluster_link.service_cluster_edges()
    except Exception:
        edges = []
    best: Optional[Tuple[str, int]] = None
    for svc, cid, w in edges:
        if svc == service_id and (best is None or w > best[1]):
            best = (cid, int(w))
    if best is None:
        # Fallback: ask rootcause for top clusters, keep ones owning this service.
        if rootcause is not None and cluster_link is not None:
            try:
                for rc in rootcause.rank_root_causes(20):
                    svcs = [s for s, _ in cluster_link.cluster_services(rc["cluster_id"])]
                    if service_id in svcs:
                        info = _fetch_cluster(rc["cluster_id"]) or {}
                        info["_weight"] = int(rc.get("members") or 0)
                        return info
            except Exception:
                pass
        return None
    info = _fetch_cluster(best[0]) or {"cluster_id": best[0]}
    info["_weight"] = best[1]
    return info


def _cluster_signals(cluster_id: str) -> int:
    if cluster_link is None or not cluster_id:
        return 0
    try:
        return int(cluster_link.cluster_signals(cluster_id))
    except Exception:
        return 0


def _cluster_services(cluster_id: str) -> List[Tuple[str, int]]:
    if cluster_link is None or not cluster_id:
        return []
    try:
        return [tuple(x) for x in cluster_link.cluster_services(cluster_id)]
    except Exception:
        return []


def _top_cluster_overall() -> Optional[Dict[str, Any]]:
    """type='all' → the top-ranked root-cause cluster nationally."""
    if rootcause is not None:
        try:
            ranked = rootcause.rank_root_causes(1)
            if ranked:
                info = _fetch_cluster(ranked[0]["cluster_id"]) or {}
                info.setdefault("cluster_id", ranked[0]["cluster_id"])
                info.setdefault("canonical_label_ar", ranked[0].get("label_ar"))
                info.setdefault("canonical_label_en", ranked[0].get("label_en"))
                info.setdefault("member_count", ranked[0].get("members"))
                info.setdefault("severity_avg", ranked[0].get("severity_avg"))
                info["_weight"] = int(ranked[0].get("members") or 0)
                return info
        except Exception:
            pass
    return None


# ===========================================================================
# Confidence + node/edge helpers
# ===========================================================================
def _step_confidence(signals: int, share: float, severity_avg: float) -> float:
    """clamp01(0.45·min(1, signals/60) + 0.35·share + 0.20·severity_avg)."""
    sig = min(1.0, (signals or 0) / 60.0)
    sh = _clamp01(share or 0.0)
    sev = _clamp01(severity_avg or 0.0)
    return round(_clamp01(0.45 * sig + 0.35 * sh + 0.20 * sev), 3)


def _short(text: str, n: int = 160) -> str:
    t = (text or "").strip()
    return t[:n]


# ===========================================================================
# Main entry point
# ===========================================================================
def ask_whys(start: Dict[str, Any], max_depth: int = 5, lang: str = "ar") -> Dict[str, Any]:
    """Build the grounded 5-Whys why-chain + root-cause graph.

    Args:
        start: {"type": "service"|"cluster"|"all", "key": <id|None>}.
        max_depth: cap on chain length (default 5).
        lang: 'ar' (Arabic ``because`` is primary) — 'en' still returns both.

    Returns:
        {start, chain:[step], root, graph:{nodes,edges,stats}, narration, method}.
        Never raises; degrades to fewer steps + a deterministic grounded summary.
    """
    start = start or {}
    stype = str(start.get("type") or "all").lower()
    skey = start.get("key")
    max_depth = max(1, int(max_depth or 5))

    chain: List[Dict[str, Any]] = []
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    seen_nodes: set = set()
    method = "grounded"

    def add_node(nid: str, **kw) -> str:
        if nid not in seen_nodes:
            seen_nodes.add(nid)
            nodes.append({"id": nid, **kw})
        return nid

    # ---- root / symptom node --------------------------------------------
    if stype == "service" and skey:
        sym_label = skey
        sym_signals = _service_signal_count(skey)
        symptom_id = add_node(
            f"service::{skey}", type="service", label=sym_label,
            label_ar=sym_label, value=sym_signals, signals=sym_signals,
            severity=TONE_NEUTRAL, depth=0,
        )
    elif stype == "cluster" and skey:
        cinfo = _fetch_cluster(skey) or {"cluster_id": skey}
        sym_label = _en(cinfo.get("canonical_label_ar"), cinfo.get("canonical_label_en"))
        sym_signals = _cluster_signals(skey)
        symptom_id = add_node(
            f"cluster::{skey}", type="cluster", label=sym_label,
            label_ar=cinfo.get("canonical_label_ar") or "", value=cinfo.get("member_count") or 0,
            members=cinfo.get("member_count") or 0, signals=sym_signals,
            severity=_tone_from_sev(cinfo.get("severity_avg") or 0), depth=0,
        )
    else:  # 'all' or unresolved → national symptom root
        sym_label = "VOC 360 · Jordan Public Services"
        sym_signals = 0
        symptom_id = add_node(
            "service::all", type="service", label=sym_label,
            label_ar="الخدمات العامة", value=0, signals=0,
            severity=TONE_NEUTRAL, depth=0,
        )

    # ---- resolve the dominant cluster (depth 1; cluster-start skips this) -
    cluster: Optional[Dict[str, Any]] = None
    cluster_node_id: Optional[str] = None

    if stype == "cluster" and skey:
        cluster = _fetch_cluster(skey) or {"cluster_id": skey}
        cluster_node_id = symptom_id  # the start node already IS the cluster
    else:
        if stype == "service" and skey:
            cluster = _dominant_cluster_for_service(skey)
        if cluster is None:
            cluster = _top_cluster_overall()

        if cluster and cluster.get("cluster_id"):
            cid = cluster["cluster_id"]
            sev = cluster.get("severity_avg") or 0
            members = cluster.get("member_count") or 0
            csignals = _cluster_signals(cid)
            label_ar = cluster.get("canonical_label_ar") or ""
            label_en = _en(label_ar, cluster.get("canonical_label_en"))
            # share = this cluster's recovered signals / the service's total signals
            share = (csignals / sym_signals) if (stype == "service" and sym_signals) else \
                    _clamp01(members / 60.0)
            conf = _step_confidence(csignals or members, share, sev)
            cluster_node_id = add_node(
                f"cluster::{cid}", type="cluster", label=label_en, label_ar=label_ar,
                value=members, members=members, signals=csignals,
                severity=_tone_from_sev(sev), severity_avg=round(float(sev), 2), depth=1,
            )
            edges.append({
                "source": symptom_id, "target": cluster_node_id,
                "weight": int(cluster.get("_weight") or members or csignals or 1),
                "kind": "dominant_cluster",
            })
            evidence: List[str] = []
            if rootcause is not None:
                try:
                    for rc in rootcause.rank_root_causes(20):
                        if rc["cluster_id"] == cid:
                            evidence = [e for e in rc.get("evidence", [])][:3]
                            break
                except Exception:
                    evidence = []
            if not evidence:
                segs = _fetch_member_segments(cid, limit=3)
                evidence = [_short(s.get("segment_text", "")) for s in segs][:3]

            q = (f"لماذا تتركّز شكاوى {sym_label} في هذا المحور؟"
                 if (stype == "service") else
                 "لماذا يُعدّ هذا المحور سبباً جذرياً؟")
            chain.append({
                "depth": 1,
                "node_id": cluster_node_id,
                "question": q,
                "answer": label_ar or label_en,
                "because": label_ar or label_en,
                "because_en": label_en,
                "evidence": evidence,
                "signals": int(csignals),
                "members": int(members),
                "severity_avg": round(float(sev), 2),
                "confidence": conf,
                "kind": "dominant_cluster",
            })

    # ---- depth 2: cluster → dominant sub-theme --------------------------
    sub_term: Optional[str] = None
    sub_segments_all: List[str] = []
    cluster_severity = float((cluster or {}).get("severity_avg") or 0)
    cluster_signals_n = _cluster_signals((cluster or {}).get("cluster_id", "")) if cluster else 0

    if cluster and cluster.get("cluster_id") and len(chain) < max_depth:
        cid = cluster["cluster_id"]
        seg_rows = _fetch_member_segments(cid, limit=600)
        sub_segments_all = [r.get("segment_text", "") for r in seg_rows if r.get("segment_text")]
        subthemes = extract_subthemes(sub_segments_all, n=8, ngram=1)
        # node-level subthemes for the UI side-branches
        if cluster_node_id and subthemes:
            try:
                for st in subthemes[:5]:
                    nodes_for = next((nn for nn in nodes if nn["id"] == cluster_node_id), None)
                    if nodes_for is not None:
                        nodes_for.setdefault("subthemes", [])
                        nodes_for["subthemes"].append({"term": st["term"], "count": st["count"]})
            except Exception:
                pass

        if subthemes and subthemes[0]["count"] >= 3:
            top = subthemes[0]
            sub_term = top["term"]
            base_depth = (chain[-1]["depth"] + 1) if chain else 2
            total_segs = max(1, len(sub_segments_all))
            share = top["count"] / total_segs
            supporting = top["count"]
            conf = _step_confidence(supporting * 4, share, cluster_severity)
            sub_node_id = add_node(
                f"subtheme::{cid}::{sub_term}", type="subtheme", label=sub_term,
                label_ar=sub_term, value=top["count"], signals=supporting,
                severity=_tone_from_sev(cluster_severity), depth=base_depth,
            )
            edges.append({
                "source": cluster_node_id, "target": sub_node_id,
                "weight": int(top["count"]), "kind": "subtheme",
            })
            # sibling sub-themes as side branches (tree shape)
            for st in subthemes[1:4]:
                if st["count"] < 2:
                    continue
                sib = add_node(
                    f"subtheme::{cid}::{st['term']}", type="subtheme", label=st["term"],
                    label_ar=st["term"], value=st["count"], signals=st["count"],
                    severity=TONE_WARN if st["count"] >= 5 else TONE_NEUTRAL,
                    depth=base_depth,
                )
                edges.append({
                    "source": cluster_node_id, "target": sib,
                    "weight": int(st["count"]), "kind": "subtheme",
                })

            chain.append({
                "depth": base_depth,
                "node_id": sub_node_id,
                "question": f"لماذا يتكرّر «{sub_term}» داخل هذا المحور؟",
                "answer": sub_term,
                "because": sub_term,
                "because_en": _en(sub_term),
                "evidence": top.get("samples", [])[:3],
                "signals": int(supporting),
                "subthemes": [{"term": s["term"], "count": s["count"]} for s in subthemes[:6]],
                "confidence": conf,
                "kind": "subtheme",
            })

    # ---- depth 3+: sub-theme → specific phrase / responsible factor ------
    if sub_term and sub_segments_all and len(chain) < max_depth:
        norm_term = _normalize_ar(sub_term)
        hit_segments = [s for s in sub_segments_all if norm_term and norm_term in _normalize_ar(s)]
        if hit_segments:
            bigrams = extract_subthemes(hit_segments, n=6, ngram=2)
            factor = _map_factor(sub_term, hit_segments)
            base_depth = chain[-1]["depth"] + 1
            cid = (cluster or {}).get("cluster_id", "x")

            if factor is not None:
                factor_en, factor_ar = factor
                supporting = len(hit_segments)
                share = supporting / max(1, len(sub_segments_all))
                conf = _step_confidence(supporting * 4, share, cluster_severity)
                # thin confidence with depth so the chain doesn't over-assert
                conf = round(conf * 0.9, 3)
                phrase_id = add_node(
                    f"phrase::{cid}::factor", type="phrase", label=factor_en,
                    label_ar=factor_ar, value=supporting, signals=supporting,
                    severity=_tone_from_sev(cluster_severity), depth=base_depth,
                )
                edges.append({
                    "source": chain[-1]["node_id"], "target": phrase_id,
                    "weight": int(supporting), "kind": "root_phrase",
                })
                chain.append({
                    "depth": base_depth,
                    "node_id": phrase_id,
                    "question": f"لماذا ينشأ «{sub_term}» تحديداً؟",
                    "answer": factor_ar,
                    "because": factor_ar,
                    "because_en": factor_en,
                    "evidence": [_short(s) for s in hit_segments[:3]],
                    "signals": int(supporting),
                    "confidence": conf,
                    "kind": "root_phrase",
                })
            elif bigrams and bigrams[0]["count"] >= 3:
                bg = bigrams[0]
                supporting = bg["count"]
                share = supporting / max(1, len(hit_segments))
                conf = round(_step_confidence(supporting * 4, share, cluster_severity) * 0.9, 3)
                phrase_id = add_node(
                    f"phrase::{cid}::{bg['term']}", type="phrase", label=bg["term"],
                    label_ar=bg["term"], value=supporting, signals=supporting,
                    severity=_tone_from_sev(cluster_severity), depth=base_depth,
                )
                edges.append({
                    "source": chain[-1]["node_id"], "target": phrase_id,
                    "weight": int(supporting), "kind": "root_phrase",
                })
                chain.append({
                    "depth": base_depth,
                    "node_id": phrase_id,
                    "question": f"لماذا ينشأ «{sub_term}» تحديداً؟",
                    "answer": bg["term"],
                    "because": bg["term"],
                    "because_en": _en(bg["term"]),
                    "evidence": bg.get("samples", [])[:3],
                    "signals": int(supporting),
                    "confidence": conf,
                    "kind": "root_phrase",
                })

    # ---- root = deepest valid step (drop steps below confidence floor) ---
    # Honour the stop conditions: keep steps with confidence>=0.15 & signals>=3.
    kept: List[Dict[str, Any]] = []
    for st in chain:
        if st["confidence"] < 0.15 and kept:
            break
        if st.get("signals", 0) < 3 and st["depth"] > 1 and kept:
            break
        kept.append(st)
    chain = kept if kept else chain[:1]
    root = chain[-1] if chain else None

    # ---- graph stats -----------------------------------------------------
    max_d = max([n.get("depth", 0) for n in nodes], default=0)
    graph = {
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "nodes": len(nodes),
            "edges": len(edges),
            "depth": int(max_d),
            "chain_len": len(chain),
        },
    }

    # ---- narration: LLM phrases the RETRIEVED facts only -----------------
    narration = _narrate(start, sym_label, chain, root)
    if narration and "::llm::" in narration:
        method = "llm"
        narration = narration.replace("::llm::", "")

    return {
        "start": {"type": stype, "key": skey, "label": sym_label},
        "chain": chain,
        "root": root,
        "graph": graph,
        "narration": narration,
        "method": method,
    }


# ===========================================================================
# Narration (LLM trust boundary: phrasing only; deterministic fallback)
# ===========================================================================
def _grounded_summary(label: str, chain: List[Dict[str, Any]], root: Optional[Dict[str, Any]]) -> str:
    """Deterministic brief composed ONLY from the retrieved chain facts."""
    if not chain:
        return f"لا توجد إشارات voc360 كافية لبناء سلسلة الأسباب لـ«{label}»."
    lines = [f"سلسلة الأسباب لـ«{label}» ({len(chain)} خطوة، من العَرَض إلى الجذر):"]
    for st in chain:
        ev = ""
        if st.get("evidence"):
            ev = f" مثال: «{_short(st['evidence'][0], 100)}»"
        lines.append(
            f"  {st['depth']}. {st['question']} ← لأن {st['because']} "
            f"— {st.get('signals', 0)} إشارة، ثقة {st.get('confidence', 0)}.{ev}"
        )
    if root is not None:
        lines.append(
            f"السبب الجذري (العمق {root['depth']}): {root.get('because', '')} "
            f"بثقة {root.get('confidence', 0)}."
        )
    return "\n".join(lines)


def _narrate(start: Dict[str, Any], label: str, chain: List[Dict[str, Any]],
             root: Optional[Dict[str, Any]]) -> str:
    """Pass ONLY retrieved facts to llm.narrate; deterministic summary on failure.

    The LLM never invents counts/labels/segments — it rephrases the chain. A
    failure (or missing local model) returns the grounded summary unchanged.
    """
    fallback = _grounded_summary(label, chain, root)
    if llm is None or not chain:
        return fallback
    chain_facts = [{
        "question": st["question"],
        "because": st["because"],
        "because_en": st.get("because_en", ""),
        "signals": st.get("signals", 0),
        "severity_avg": st.get("severity_avg"),
        "confidence": st.get("confidence", 0),
        "evidence": st.get("evidence", [])[:2],
    } for st in chain]
    context = {
        "case": start.get("key") or label,
        "chain_facts": chain_facts,
        "root_causes": [{
            "label_en": (root or {}).get("because_en", ""),
            "label_ar": (root or {}).get("because", ""),
            "members": (root or {}).get("members", 0),
            "severity_avg": (root or {}).get("severity_avg", 0),
            "evidence": (root or {}).get("evidence", []),
        }] if root else [],
        "recommendation": fallback,
    }
    prompt = (
        "أعد صياغة خطوات «لماذا» التالية فقط في سلسلة واضحة بالعربية من العَرَض إلى "
        "الجذر يفهمها مستخدم عادي. اذكر الأعداد كما هي تمامًا، ولا تُضِف أي سبب أو "
        "رقم غير مذكور، وأبقِ التسميات العربية كما وردت، وإن غابت خطوة فاذكر أن "
        "الأدلة تخفّ عندها."
    )
    try:
        text = llm.narrate(prompt, context)
        if text and str(text).strip():
            return "::llm::" + str(text).strip()
    except Exception:
        pass
    return fallback


__all__ = ["ask_whys", "extract_subthemes"]
