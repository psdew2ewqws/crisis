"""D-suggest — grounded SUGGESTED QUESTIONS engine for the voc360 deep-analysis UI.

A question is *offered to the operator only if real voc360 data can answer it*.
Every candidate is templated from real entities (service_id / cluster label) and
gated by live counts (a "grounding gate"): if the backing signals/members/days do
not clear a floor, the question is dropped — so the UI never offers a dead-end.

Contract (D-suggest)::

    suggest(context: Context | None = None, limit: int = 8) -> list[Suggestion]

    Context    = {"type": "national"|"service"|"cluster"|"case", "key": str|None}
    Suggestion = {id, q, intent, params, why_useful, score, needs[]}

* ``id``        — stable hash for React keys / dedup.
* ``q``         — the display string (templated from real counts; never LLM-made).
* ``intent``    — the QA/whys/validate/forecast intent the chip dispatches on
                  (the vocabulary the D-qa engine + api_v3 router understand).
* ``params``    — consumed verbatim by the answering engine.
* ``why_useful``— a short grounded rationale (real numbers).
* ``score``     — ``log1p(signals) * sev_weight * answerability`` for ranking.
* ``needs``     — the data dependencies that passed the gate (provenance).

Trust boundary: questions are deterministic templates over real counts. The LLM
is NEVER required and NEVER invents a question. An optional ``phrase="llm"`` only
re-words the *display string* under a strict "use ONLY these facts" constraint —
``intent``/``params``/``score`` are never LLM-touched. Import-safe: any DB outage
or import failure degrades to ``[]`` (or to the un-phrased string for ``phrase``).

Real voc360 columns only (the_data, ril_problem_clusters, ril_cluster_members,
ril_text_segments) + the existing ``cluster_link`` recovered edges. Reuses the
exact negativity predicate from ``api_kpis`` (``lower(sentiment_label) like
'negative%%' or 'high_severity%%'``) so counts stay consistent with the KPI cards.
"""
from __future__ import annotations

import hashlib
import math
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Import-safe wiring. Everything optional so the module imports on a box with
# no DB / no LLM and `suggest()` simply returns [] rather than raising.
# ---------------------------------------------------------------------------
try:
    from . import db  # db.fetchall(sql, params) -> list[dict]; %(name)s params
except Exception:  # pragma: no cover
    db = None  # type: ignore

try:
    from . import cluster_link  # cluster_services / cluster_signals (recovered edges)
except Exception:  # pragma: no cover
    cluster_link = None  # type: ignore

try:
    from .main_v2 import translate_label as _translate_label  # ar -> en gloss
except Exception:  # pragma: no cover
    def _translate_label(label_ar: Optional[str], label_en: Optional[str] = None) -> str:
        if label_en and str(label_en).strip():
            return str(label_en).strip()
        return (str(label_ar).strip() if label_ar else "") or "problem cluster"

try:
    from . import llm as _llm  # only for the OPTIONAL display re-phrasing
except Exception:  # pragma: no cover
    _llm = None  # type: ignore

Suggestion = Dict[str, Any]
Context = Dict[str, Any]

# AEGIS / grounding floors — a question is emitted only if its backing counts
# clear these (so the chip never opens a dead-end panel).
GATE_SIGNALS = 20       # min the_data signals for a service/keyword question
GATE_MEMBERS = 3        # min ril_cluster_members for a cluster sub-theme question
GATE_FORECAST_DAYS = 21 # min distinct days for a forecast (>= 3 weekly seasons - a bit)
GATE_GOVS = 2           # min distinct non-null governorates for a geo question
GATE_CRITICAL = 1       # min high/critical signals for a severity question

# Negativity predicate — identical to api_kpis so the numbers match the KPI cards.
_NEG = ("(lower(sentiment_label) like 'negative%%' "
        "or lower(sentiment_label) like 'high_severity%%')")
_TS = "nullif(date::text, '')::timestamp"

# Severity weight applied to the answerability score — sharper problems rank up.
def _sev_weight(critical: int, total: int) -> float:
    if total <= 0:
        return 1.0
    r = critical / total
    return 1.0 + min(1.0, 2.0 * r)  # 1.0 .. ~3.0


def _safe_fetchall(sql: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """db.fetchall that never raises — outage / missing db -> []."""
    if db is None:
        return []
    try:
        return db.fetchall(sql, params or {})
    except Exception:
        return []


def _safe_fetchone(sql: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    rows = _safe_fetchall(sql, params)
    return rows[0] if rows else None


def _i(v: Any) -> int:
    try:
        return int(v or 0)
    except Exception:
        return 0


def _sid(intent: str, params: Dict[str, Any]) -> str:
    """Stable id for React keys / dedup — hash of intent + sorted params."""
    raw = intent + "|" + "&".join(f"{k}={params[k]}" for k in sorted(params))
    return "sg_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


# Arabic section label per intent — lets the frontend group suggestions.
_CATEGORY_BY_INTENT: Dict[str, str] = {
    "root_cause_rank": "الأسباب الجذرية",
    "why_chain": "الأسباب الجذرية",
    "cluster_subthemes": "الأسباب الجذرية",
    "root_cause": "الأسباب الجذرية",
    "forecast_volume": "التنبؤ والاتجاهات",
    "escalation_scan": "التنبؤ والاتجاهات",
    "trend": "التنبؤ والاتجاهات",
    "recent_spike": "التنبؤ والاتجاهات",
    "temporal_onset": "التنبؤ والاتجاهات",
    "compare_services": "المقارنة والقياس",
    "metric_breakdown": "المقارنة والقياس",
    "count": "المقارنة والقياس",
    "source_channel": "المقارنة والقياس",
    "citizen_voice": "أصوات المواطنين",
    "sentiment": "أصوات المواطنين",
    "validate": "التحقّق والحلول",
    "solution": "التحقّق والحلول",
    "owner": "التحقّق والحلول",
    "national_summary": "نظرة عامة",
    "top_problems": "نظرة عامة",
    # cluster / service-scoped intents
    "service_clusters": "الأسباب الجذرية",
    "cluster_services": "المقارنة والقياس",
    "case_validation": "التحقّق والحلول",
    "sim_impact": "التحقّق والحلول",
    "temporal_trend": "التنبؤ والاتجاهات",
    "forecast_sentiment": "التنبؤ والاتجاهات",
}


def _category(intent: str) -> str:
    """Arabic section label for an intent (frontend grouping); default 'عام'."""
    return _CATEGORY_BY_INTENT.get(intent, "عام")


def _mk(
    q: str,
    intent: str,
    params: Dict[str, Any],
    why_useful: str,
    signals: int,
    sev_weight: float = 1.0,
    answerability: float = 1.0,
    needs: Optional[List[str]] = None,
) -> Suggestion:
    """Assemble one Suggestion. score = log1p(signals)*sev_weight*answerability."""
    score = round(math.log1p(max(0, signals)) * float(sev_weight) * float(answerability), 4)
    return {
        "id": _sid(intent, params),
        "q": q,
        "intent": intent,
        "category": _category(intent),
        "params": params,
        "why_useful": why_useful,
        "score": score,
        "needs": needs or [],
    }


# ===========================================================================
# GROUNDING PROBES — 4 read-only %(name)s SQL probes + cluster_link helpers.
# Each returns the real counts a question's gate is tested against.
# ===========================================================================

def _probe_service(service: str) -> Dict[str, Any]:
    """Volume / negativity / severity / geo / temporal footprint of a service."""
    row = _safe_fetchone(
        f"""
        select count(*) as signals,
               count(*) filter (where sentiment_label is not null and {_NEG}) as negative,
               count(*) filter (where sentiment_label is not null)            as sentiment_known,
               count(*) filter (where severity in ('high','critical'))        as critical,
               count(distinct governorate) filter (where governorate is not null) as govs,
               count(distinct date_trunc('day', {_TS}))
                 filter (where {_TS} is not null)                             as days
        from the_data
        where service_id = %(svc)s
        """,
        {"svc": service},
    ) or {}
    return {
        "signals": _i(row.get("signals")),
        "negative": _i(row.get("negative")),
        "sentiment_known": _i(row.get("sentiment_known")),
        "critical": _i(row.get("critical")),
        "govs": _i(row.get("govs")),
        "days": _i(row.get("days")),
    }


def _probe_cluster(cluster_id: str) -> Dict[str, Any]:
    """Cluster size / severity + recovered signal coverage via cluster_link."""
    row = _safe_fetchone(
        """
        select c.canonical_label_ar, c.canonical_label_en,
               coalesce(c.member_count,0) as members,
               round(coalesce(c.severity_avg,0)::numeric,2) as severity_avg,
               count(distinct m.segment_id) as seg_members,
               count(distinct left(s.segment_text,60)) filter (where s.segment_text is not null) as distinct_texts
        from ril_problem_clusters c
        left join ril_cluster_members m on m.cluster_id = c.cluster_id
        left join ril_text_segments s on s.segment_id = m.segment_id
        where c.cluster_id = %(cid)s
        group by c.canonical_label_ar, c.canonical_label_en, c.member_count, c.severity_avg
        """,
        {"cid": cluster_id},
    ) or {}
    members = max(_i(row.get("members")), _i(row.get("seg_members")))
    signals = 0
    services: List[Tuple[str, int]] = []
    if cluster_link is not None:
        try:
            signals = int(cluster_link.cluster_signals(cluster_id) or 0)
        except Exception:
            signals = 0
        try:
            services = [tuple(x) for x in (cluster_link.cluster_services(cluster_id) or [])]
        except Exception:
            services = []
    return {
        "label_ar": row.get("canonical_label_ar"),
        "label_en": row.get("canonical_label_en"),
        "members": members,
        "severity_avg": float(row.get("severity_avg") or 0.0),
        "distinct_texts": _i(row.get("distinct_texts")),
        "signals": signals,
        "services": services,
        # forecast days for a cluster come from its mapped service set (parallel layer rule)
        "days": _cluster_days(services),
    }


def _cluster_days(services: List[Tuple[str, int]]) -> int:
    """Distinct daily points across a cluster's mapped service set (for forecast gate)."""
    svc = [s for s, _ in services[:3] if s]
    if not svc:
        return 0
    row = _safe_fetchone(
        f"""
        select count(distinct date_trunc('day', {_TS})) as days
        from the_data
        where service_id = any(%(svcs)s) and {_TS} is not null
        """,
        {"svcs": svc},
    ) or {}
    return _i(row.get("days"))


def _resolve_case(key: str) -> Tuple[str, str]:
    """Resolve a `case` key cluster-first (matching graph_builder), else service.

    Returns (kind, key) where kind in {"cluster","service"}.
    A cluster_id (uuid-ish / present in ril_problem_clusters) wins; otherwise we
    treat the key as a service_id present in the_data.
    """
    if key:
        hit = _safe_fetchone(
            "select cluster_id from ril_problem_clusters where cluster_id = %(k)s",
            {"k": key},
        )
        if hit:
            return ("cluster", key)
        hit = _safe_fetchone(
            "select service_id from the_data where service_id = %(k)s limit 1",
            {"k": key},
        )
        if hit:
            return ("service", key)
    return ("service", key)


# ===========================================================================
# SCOPE BUILDERS — each emits gated, templated questions for one scope.
# Intent vocabulary (D-suggest / D-qa): why_chain, root_cause_rank,
# cluster_subthemes, cluster_services, service_clusters, metric_breakdown,
# forecast_volume, forecast_sentiment, escalation_scan, temporal_trend,
# case_validation, sim_impact, compare_services.
# ===========================================================================

def _national() -> List[Suggestion]:
    out: List[Suggestion] = []

    # National signal totals + dominant clusters (so we know there IS data).
    tot = _safe_fetchone(
        f"""
        select count(*) as total,
               count(distinct service_id) filter (where service_id is not null) as services,
               count(*) filter (where severity in ('high','critical')) as critical
        from the_data
        """
    ) or {}
    total = _i(tot.get("total"))
    services_n = _i(tot.get("services"))
    critical = _i(tot.get("critical"))
    if total < GATE_SIGNALS:
        return out  # nothing to offer nationally

    sw = _sev_weight(critical, total)

    # Ranked root causes (rootcause-style probe on ril_problem_clusters).
    top = _safe_fetchall(
        """
        select cluster_id, canonical_label_ar, canonical_label_en,
               coalesce(member_count,0) as members,
               round(coalesce(severity_avg,0)::numeric,2) as severity_avg
        from ril_problem_clusters
        where coalesce(member_count,0) > 1
        order by coalesce(member_count,0)*(0.5+coalesce(severity_avg,0)) desc
        limit 3
        """
    )

    out.append(_mk(
        "ما هي أبرز مجموعات المشكلات ذات الأسباب الجذرية على المستوى الوطني الآن، مرتّبة حسب حجم بلاغات المواطنين وشدّتها؟",
        "root_cause_rank", {"limit": 5},
        f"يرتّب {len(top) or 'كل'} مجموعات RIL حقيقية عبر {total:,} إشارة على المستوى الوطني.",
        signals=total, sev_weight=sw, answerability=1.0,
        needs=["the_data", "ril_problem_clusters"],
    ))

    out.append(_mk(
        "بالنظر إلى الثلاثين يوماً القادمة، أي خدمة أو مجموعة مشكلات يُتوقّع أن تتصاعد بأسرع وتيرة في حجم الشكاوى؟",
        "escalation_scan", {"horizon": 14},
        f"يفحص {services_n} خدمة ومجموعة لرصد النمو المتوقّع (TimesFM أو البديل الإحصائي).",
        signals=total, sev_weight=sw, answerability=0.9,
        needs=["the_data", "forecaster"],
    ))

    out.append(_mk(
        "عبر جميع قنوات ملاحظات المواطنين، أين تتركّز أبرز نقطة ألم وطنية وأي نوع مصدر يقودها؟",
        "metric_breakdown", {"dim": "source_type"},
        f"يوزّع {total:,} إشارة حسب مصدر الاستقبال (تقييم تطبيق / تواصل اجتماعي / شكوى / استبيان).",
        signals=total, sev_weight=1.0, answerability=1.0,
        needs=["the_data"],
    ))

    if critical >= GATE_CRITICAL:
        out.append(_mk(
            "ما مدى خطورة الشكاوى على المستوى الوطني — ما نسبة الشكاوى ذات الشدّة العالية أو الحرجة، وأين تتركّز؟",
            "metric_breakdown", {"dim": "severity"},
            f"{critical:,} إشارة عالية/حرجة مسجّلة على المستوى الوطني.",
            signals=critical, sev_weight=sw, answerability=1.0,
            needs=["the_data"],
        ))

    # Compare the two busiest services (only if both clear the volume gate).
    busiest = _safe_fetchall(
        f"""
        select service_id, count(*) n,
               count(*) filter (where sentiment_label is not null and {_NEG}) neg
        from the_data
        where service_id is not null
        group by service_id order by n desc limit 2
        """
    )
    if len(busiest) == 2 and _i(busiest[0]["n"]) >= GATE_SIGNALS and _i(busiest[1]["n"]) >= GATE_SIGNALS:
        a, b = busiest[0]["service_id"], busiest[1]["service_id"]
        out.append(_mk(
            f"قارن بين {a} و{b} — أيّهما يحمل مشاعر مواطنين سلبية أكثر وأيّهما أسوأ حالاً الآن؟",
            "compare_services", {"a": a, "b": b, "metric": "negativity"},
            f"{a}: {_i(busiest[0]['n']):,} إشارة مقابل {b}: {_i(busiest[1]['n']):,}.",
            signals=_i(busiest[0]["n"]) + _i(busiest[1]["n"]),
            sev_weight=1.0, answerability=1.0,
            needs=["the_data"],
        ))

    # Forecast the busiest service's volume.
    if busiest and _i(busiest[0]["n"]) >= GATE_SIGNALS:
        a = busiest[0]["service_id"]
        out.append(_mk(
            f"تنبّأ بحجم الشكاوى لخدمة {a} خلال الثلاثين يوماً القادمة — هل ستواصل التصاعد؟",
            "forecast_volume", {"entity": "service", "id": a, "horizon": 30},
            f"{a} هي الخدمة الأكثر ازدحاماً ({_i(busiest[0]['n']):,} إشارة).",
            signals=_i(busiest[0]["n"]), sev_weight=1.0, answerability=0.9,
            needs=["the_data", "forecaster"],
        ))

    return out


def _service(service: str) -> List[Suggestion]:
    out: List[Suggestion] = []
    p = _probe_service(service)
    if p["signals"] < GATE_SIGNALS:
        return out  # not enough data to ground any service question

    sw = _sev_weight(p["critical"], p["signals"])

    # 1) why-chain (always offerable once the service has signals).
    out.append(_mk(
        f"تتبّع سلسلة \"الأسباب الخمسة\" لخدمة {service} — من العرض الظاهر وصولاً إلى السبب الجذري المحدّد.",
        "why_chain", {"type": "service", "key": service, "max_depth": 5},
        f"{p['signals']:,} إشارة من المواطنين تدعم سلسلة أسباب موثّقة لخدمة {service}.",
        signals=p["signals"], sev_weight=sw, answerability=1.0,
        needs=["the_data", "ril_problem_clusters"],
    ))

    # 2) service -> dominant root-cause clusters.
    out.append(_mk(
        f"أي مجموعة سبب جذري تقود أكثر الإشارات السلبية لخدمة {service}، وكم عدد البلاغات التي تدعمها؟",
        "service_clusters", {"service": service},
        f"يربط {p['signals']:,} إشارة لخدمة {service} بمجموعات RIL المهيمنة عليها.",
        signals=p["signals"], sev_weight=sw, answerability=1.0,
        needs=["the_data", "ril_problem_clusters", "cluster_link"],
    ))

    # 3) sentiment split.
    if p["sentiment_known"] >= 5:
        pct = round(100.0 * p["negative"] / p["sentiment_known"]) if p["sentiment_known"] else 0
        out.append(_mk(
            f"ما توزيع المشاعر السلبية مقابل الإيجابية لخدمة {service}، وأي اتجاه مشاعر هو المهيمن؟",
            "metric_breakdown", {"service": service, "dim": "sentiment"},
            f"{pct}% من {p['sentiment_known']:,} إشارة حاملة لمشاعر هي إشارات سلبية.",
            signals=p["sentiment_known"], sev_weight=1.0, answerability=1.0,
            needs=["the_data"],
        ))

    # 4) severity breakdown.
    if p["critical"] >= GATE_CRITICAL:
        out.append(_mk(
            f"ما مدى خطورة شكاوى خدمة {service} — ما نسبة الشكاوى ذات الشدّة العالية أو الحرجة؟",
            "metric_breakdown", {"service": service, "dim": "severity"},
            f"{p['critical']:,} من إشارات خدمة {service} عالية/حرجة.",
            signals=p["critical"], sev_weight=sw, answerability=1.0,
            needs=["the_data"],
        ))

    # 5) governorate breakdown (only if >=2 distinct govs — most are NULL).
    if p["govs"] >= GATE_GOVS:
        out.append(_mk(
            f"أي المحافظات تبلّغ عن أكبر عدد من المشكلات لخدمة {service}؟",
            "metric_breakdown", {"service": service, "dim": "governorate"},
            f"{p['govs']} محافظات تحمل إشارات موسومة لخدمة {service}.",
            signals=p["signals"], sev_weight=1.0, answerability=0.8,
            needs=["the_data"],
        ))

    # 6) source / channel breakdown.
    out.append(_mk(
        f"عبر أي قنوات وأنواع مصادر يبلّغ المواطنون عن مشكلات خدمة {service}؟",
        "metric_breakdown", {"service": service, "dim": "source_type"},
        f"يَنسب {p['signals']:,} إشارة لخدمة {service} إلى قنوات الاستقبال.",
        signals=p["signals"], sev_weight=1.0, answerability=1.0,
        needs=["the_data"],
    ))

    # 7) volume forecast (gated on enough distinct days).
    if p["days"] >= GATE_FORECAST_DAYS:
        out.append(_mk(
            f"كيف تطوّر حجم الإشارات اليومي لخدمة {service}، وهل يُتوقّع أن يتصاعد؟",
            "forecast_volume", {"entity": "service", "id": service, "horizon": 30},
            f"{p['days']} يوماً متمايزاً من السجل تدعم توقّع حجم خدمة {service}.",
            signals=p["signals"], sev_weight=sw, answerability=0.9,
            needs=["the_data", "forecaster"],
        ))
        # 8) sentiment forecast.
        if p["sentiment_known"] >= 5:
            out.append(_mk(
                f"هل نسبة المشاعر السلبية لخدمة {service} في تصاعد أم تراجع خلال الأسبوعين القادمين؟",
                "forecast_sentiment", {"entity": "service", "id": service, "horizon": 14},
                f"{p['days']} يوماً من سجل المشاعر لخدمة {service}.",
                signals=p["sentiment_known"], sev_weight=1.0, answerability=0.85,
                needs=["the_data", "forecaster"],
            ))
        # 9) temporal trend (recent vs prior window).
        out.append(_mk(
            f"هل تتحسّن خدمة {service} أم تتدهور — حجم وسلبية آخر 30 يوماً مقابل الفترة السابقة؟",
            "temporal_trend", {"service": service},
            f"{p['days']} يوماً تتيح لنا مقارنة الفترة الأخيرة بالفترة السابقة لخدمة {service}.",
            signals=p["signals"], sev_weight=sw, answerability=0.9,
            needs=["the_data"],
        ))

    return out


def _cluster(cluster_id: str) -> List[Suggestion]:
    out: List[Suggestion] = []
    p = _probe_cluster(cluster_id)
    if p["members"] < 1 and p["signals"] < GATE_SIGNALS:
        return out  # neither RIL members nor recovered signals -> dead end

    label = _translate_label(p.get("label_ar"), p.get("label_en"))
    sw = 1.0 + min(1.0, p["severity_avg"])  # severity_avg ~0..1 -> 1.0..2.0
    base_signals = max(p["members"], p["signals"])

    # 1) why-chain on the cluster.
    out.append(_mk(
        f"اشرح سلسلة الأسباب الكاملة لمجموعة '{label}' — من العرض الظاهر إلى السبب الجذري المحدّد.",
        "why_chain", {"type": "cluster", "key": cluster_id, "max_depth": 5},
        f"تضمّ '{label}' عدد {p['members']} مقطعاً مجمَّعاً من المواطنين ({p['signals']} إشارة مستردّة).",
        signals=base_signals, sev_weight=sw, answerability=1.0,
        needs=["ril_problem_clusters", "ril_cluster_members", "cluster_link"],
    ))

    # 2) sub-themes via TF-IDF over ril_text_segments (gated on members + distinct texts).
    if p["members"] >= GATE_MEMBERS and p["distinct_texts"] >= 3:
        out.append(_mk(
            f"ما الموضوعات الفرعية المهيمنة داخل مجموعة '{label}'، كما تظهر من كلمات المواطنين أنفسهم؟",
            "cluster_subthemes", {"cluster_id": cluster_id},
            f"{p['members']} مقطعاً عضواً ({p['distinct_texts']} نصاً متمايزاً) تغذّي مستخرِج الموضوعات الفرعية.",
            signals=p["members"], sev_weight=sw, answerability=1.0,
            needs=["ril_cluster_members", "ril_text_segments"],
        ))

    # 3) feeding services (only if cluster_link recovered any).
    if p["services"]:
        owner = p["services"][0][0]
        out.append(_mk(
            f"أي الخدمات تغذّي مجموعة '{label}'، ومن الجهة المالكة لها؟",
            "cluster_services", {"cluster_id": cluster_id},
            f"استُردّت إلى {len(p['services'])} خدمة؛ المالك الأبرز {owner} ({p['services'][0][1]} إشارة).",
            signals=p["signals"], sev_weight=sw, answerability=1.0,
            needs=["cluster_link", "the_data"],
        ))

    # 4) case validation (always — the verdict degrades gracefully).
    out.append(_mk(
        f"تحقّق: هل '{label}' سبب جذري فعلاً — من حيث التغطية والأدلة والاتجاه وأثر المحاكاة؟",
        "case_validation", {"cluster_id": cluster_id},
        f"{p['signals']} إشارة مستردّة و{p['members']} مقطعاً تدعم فحوص التحقّق.",
        signals=base_signals, sev_weight=sw, answerability=0.95,
        needs=["cluster_link", "ril_cluster_members", "forecaster", "mesa_sim"],
    ))

    # 5) sim impact (only if we have an owning service to intervene on).
    if p["services"]:
        owner = p["services"][0][0]
        out.append(_mk(
            f"لو عالجنا '{label}'، كم سينخفض حجم الإشارات السلبية في المحاكاة؟",
            "sim_impact", {"cluster_id": cluster_id, "service": owner},
            f"يحاكي التدخّل على '{label}' عبر الخدمة المالكة لها {owner}.",
            signals=p["signals"], sev_weight=sw, answerability=0.85,
            needs=["mesa_sim", "cluster_link"],
        ))

    # 6) forecast the cluster's volume (gated on its service set's history).
    if p["days"] >= GATE_FORECAST_DAYS:
        out.append(_mk(
            f"هل مجموعة '{label}' تتحسّن أم تتدهور — تنبّأ بحجمها وتحقّق من احتمال التصاعد.",
            "forecast_volume", {"entity": "cluster", "id": cluster_id, "horizon": 30},
            f"{p['days']} يوماً من السجل عبر مجموعة الخدمات التابعة لها.",
            signals=p["signals"], sev_weight=sw, answerability=0.9,
            needs=["the_data", "cluster_link", "forecaster"],
        ))

    return out


# ===========================================================================
# OPTIONAL display re-phrasing — re-words ONLY q under strict grounding.
# intent / params / score are never touched. Failure -> original q.
# ===========================================================================
_PHRASE_PROMPT = (
    "Rephrase the following suggested question into one clear, natural sentence. "
    "Use ONLY the facts in WHY_USEFUL; do not add any number, entity, or claim not "
    "present there; keep any Arabic labels verbatim; output the question only."
)


def _phrase_one(s: Suggestion) -> Suggestion:
    if _llm is None:
        return s
    try:
        ctx = {"question": s["q"], "facts": [{"label": "why_useful", "value": s.get("why_useful", "")}]}
        text = _llm.narrate(_PHRASE_PROMPT + "\nQUESTION: " + s["q"], context=ctx)
        if text and text.strip():
            s = dict(s)
            s["q"] = text.strip().splitlines()[0][:240]
    except Exception:
        pass
    return s


# ===========================================================================
# PUBLIC ENTRY POINT
# ===========================================================================

def suggest(context: Optional[Context] = None, limit: int = 8, phrase: Optional[str] = None) -> List[Suggestion]:
    """Return ``limit`` grounded, ranked suggested questions for ``context``.

    Args:
        context: ``{"type": "national"|"service"|"cluster"|"case", "key": str|None}``.
                 ``None`` / missing type -> national scope. A ``case`` key resolves
                 cluster-first (matching ``graph_builder.build_graph``), else service.
        limit:   max questions returned (always tries to yield >=5 when facts allow).
        phrase:  ``"llm"`` to re-word display strings under a strict grounding
                 constraint (intent/params/score untouched); anything else = no LLM.

    Returns:
        A list of Suggestion dicts, ranked by ``score`` desc, de-duplicated by id.
        Import-safe: on any DB outage / failure returns ``[]``.
    """
    ctx = context or {}
    ctype = (ctx.get("type") or "national").lower()
    key = ctx.get("key")

    try:
        if ctype == "case" and key:
            kind, rkey = _resolve_case(str(key))
            items = _cluster(rkey) if kind == "cluster" else _service(rkey)
            ctype, key = kind, rkey
        elif ctype == "cluster" and key:
            items = _cluster(str(key))
        elif ctype == "service" and key:
            items = _service(str(key))
        else:
            ctype = "national"
            items = _national()
    except Exception:
        return []

    # De-dup by id, rank by score desc, cap to limit.
    seen: set[str] = set()
    ranked: List[Suggestion] = []
    for s in sorted(items, key=lambda x: x.get("score", 0.0), reverse=True):
        if s["id"] in seen:
            continue
        seen.add(s["id"])
        ranked.append(s)

    ranked = ranked[: max(1, int(limit))] if ranked else ranked

    if phrase == "llm" and ranked:
        ranked = [_phrase_one(s) for s in ranked]

    return ranked


__all__ = ["suggest", "Suggestion", "Context"]
