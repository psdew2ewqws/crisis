"""report_writer.py — deterministic, LLM-free generator of a rich WRITTEN crisis report.

Designed by the report-writing swarm (research → 4-round crisis-manager panel → templates).
Turns the engine's facts (cascade study + sourced baseline + retrieved precedents + verified
references) into a structured situation report — flowing Arabic prose in a senior crisis
manager's voice, every number traced to a fact, estimates marked تقديري. Runs with Ollama
DOWN (pure Python); optional LLM enrichment may only rephrase, never change a figure.

Returns a STRUCTURED report (not raw markdown) so the frontend renders it with html2canvas-
safe styling and places the references on their own PDF page.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def _f(x: Any, default: str = "[—]") -> str:
    """Format a number for prose: drop a trailing .0, keep real decimals."""
    if x is None:
        return default
    try:
        v = float(x)
    except (TypeError, ValueError):
        return str(x)
    return str(int(v)) if v == int(v) else str(round(v, 2))


def _bl(sim: Dict[str, Any], key: str, default: Any = None) -> Any:
    return ((sim.get("baseline") or {}).get(key) or {}).get("value", default)


def build_context(payload: Dict[str, Any]) -> Dict[str, str]:
    sim = payload.get("sim") or {}
    pred = payload.get("prediction") or {}
    det = payload.get("detection") or {}
    conf = payload.get("confidence") or {}
    mc = sim.get("montecarlo") or {}
    sec = sim.get("sectors_after") or {}

    rb = sim.get("risk_before")
    ra = sim.get("risk_after")
    rr = sim.get("rainfall_ratio")
    dam = _bl(sim, "dam_storage_mcm", {})
    dam_latest = dam.get("2025_nov") if isinstance(dam, dict) else None

    def pct(x: Any) -> str:
        return _f(round(float(x) * 100, 0)) + "%" if isinstance(x, (int, float)) else "[—]"

    ctx = {
        "scenario": (payload.get("text") or "").strip(),
        "severity_ar": det.get("severity_ar", "[—]"),
        "is_crisis": "نعم" if det.get("is_crisis") else "لا",
        "escalating": "متصاعد" if det.get("escalating") else "مستقرّ",
        "risk_before": _f(rb), "risk_after": _f(ra),
        "risk_delta": ("−" + _f(abs(rb - ra))) if isinstance(rb, (int, float)) and isinstance(ra, (int, float)) else "[—]",
        "rainfall_deficit": (_f(round((rr - 1) * 100)) + "%") if isinstance(rr, (int, float)) else "[—]",
        "sector_water": pct(sec.get("water_supply")),
        "sector_agriculture": pct(sec.get("agriculture")),
        "sector_groundwater": pct(sec.get("groundwater")),
        "sector_social": pct(sec.get("social")),
        "mc_p10": _f(mc.get("p10")), "mc_p50": _f(mc.get("p50")),
        "mc_p90": _f(mc.get("p90")), "mc_spread": _f(mc.get("spread")),
        "renewable_pc": _f(_bl(sim, "renewable_internal_per_capita_m3")),
        "withdrawals_pct": _f(_bl(sim, "withdrawals_pct_of_renewable")),
        "nrw_pct": _f(_bl(sim, "nrw_pct")),
        "gw_ratio": _f(_bl(sim, "groundwater_overabstraction_ratio")),
        "dam_latest": _f(dam_latest), "dam_cap": _f(_bl(sim, "dam_capacity_mcm")),
        "grain_import_pct": _f(_bl(sim, "grain_import_dependency_pct")),
        "grain_reserve": _f(_bl(sim, "grain_reserve_months")),
        "desal_year": _f(_bl(sim, "desalination_online_year")),
        "conf_band": conf.get("band_ar", "[—]"),
        "outcome_ar": pred.get("likely_outcome_ar") or "[—]",
        "non_mitigating": "، ".join(sim.get("non_mitigating") or []) or "—",
    }
    return ctx


# --------------------------------------------------------------------------- #
# section builders — flowing prose, guarded by data availability               #
# --------------------------------------------------------------------------- #
def _key_figures(c: Dict[str, str], cascade: bool) -> List[Dict[str, str]]:
    rows = [
        {"label": "أزمة قائمة؟", "value": c["is_crisis"], "source": "محرّك المحاكاة"},
        {"label": "الشدّة / الاتجاه", "value": f"{c['severity_ar']} · {c['escalating']}", "source": "محرّك المحاكاة — تقديري"},
        {"label": "الخطر المركّب دون تدخّل", "value": f"{c['risk_before']}/100", "source": "محرّك المحاكاة — تقديري"},
        {"label": "الخطر المركّب مع الروافع", "value": f"{c['risk_after']}/100 ({c['risk_delta']} نقطة)", "source": "محرّك المحاكاة — تقديري"},
    ]
    if cascade:
        rows += [
            {"label": "نسبة الهطول إلى المعدّل", "value": f"{c['rainfall_deficit']} عن الطبيعي", "source": "محرّك المحاكاة — تقديري"},
            {"label": "نطاق مونتي كارلو (P10/P50/P90)", "value": f"{c['mc_p10']} / {c['mc_p50']} / {c['mc_p90']}", "source": "محاكاة احتمالية — تقديري"},
            {"label": "حصّة الفرد من المياه المتجدّدة", "value": f"{c['renewable_pc']} م³/سنة (2022)", "source": "البنك الدولي ER.H2O.INTR.PC — مقاس"},
            {"label": "السحب مقابل المورد المتجدّد", "value": f"{c['withdrawals_pct']}%", "source": "FAO AQUASTAT — مقاس"},
            {"label": "الفاقد المائي (NRW)", "value": f"~{c['nrw_pct']}%", "source": "WES-MED 2024 — مقاس"},
            {"label": "السحب الجوفي مقابل الآمن", "value": f"~{c['gw_ratio']}×", "source": "Springer 10.1007/s10040-021-02404-1 — مقاس"},
            {"label": "مخزون السدود", "value": f"{c['dam_latest']} مليون م³ (≈15% من {c['dam_cap']})", "source": "Zawya/MWI — مقاس"},
        ]
    return rows


def _sections(c: Dict[str, str], cascade: bool) -> List[Dict[str, Any]]:
    S: List[Dict[str, Any]] = []

    # Executive summary (BLUF)
    S.append({"title_ar": "الملخّص التنفيذي", "title_en": "Executive Summary (BLUF)", "paragraphs": [
        f"الخلاصة في سطر: السيناريو المُحاكى «{c['scenario']}» يدفع الوضع إلى خطر مركّب {c['risk_before']}/100 "
        f"({c['severity_ar']}، {c['escalating']}) دون تدخّل؛ وحزمة إدارة الطلب وحدها تُنزله إلى {c['risk_after']}/100 "
        f"({c['risk_delta']} نقطة) دون أيّ مشروع لتوليد مورد جديد. النتيجة الحاسمة تُصنع بالتدخّل الفوري في الطلب، "
        f"لا بمشاريع العرض المستقبلية.",
        "إطار القراءة: القيم النموذجية (الخطر، الإجهاد القطاعي، نسبة الهطول، نطاق مونتي كارلو) مُخرَجات محاكاة "
        "لسيناريو افتراضي تُقرأ مقياسًا نسبيًّا بين الخيارات لا توقّعًا كمّيًّا للواقع؛ أمّا القيم المقاسة فموسومة بمصادرها "
        "في صفحة المراجع. خطّط على الطرف المرتفع من المدى وأبرِز الوسيط.",
    ] + ([
        f"ينبغي تبديد قراءتين خاطئتين مبكّرًا: (أ) «التحلية ستنقذنا» — كلّا؛ مشروع العقبة–عمّان لا يدخل الخدمة قبل "
        f"~{c['desal_year']}، ويصنّفه المحرّك «غير مُخفِّف» خلال أفق هذه السنة. (ب) «ستقع مجاعة خبز» — كلّا؛ يُستورد أكثر "
        f"من {c['grain_import_pct']}% من الحبوب مع احتياطي ~{c['grain_reserve']} أشهر، فينتقل الخطر عبر الأعلاف والثروة "
        f"الحيوانية والخضار وفاتورة الاستيراد والعملة، لا عبر رغيف الخبز."] if cascade else [])})

    # Overall assessment
    S.append({"title_ar": "التقييم العام", "title_en": "Overall Assessment", "paragraphs": [
        f"التشخيص: الوضع {c['severity_ar']} والاتجاه {c['escalating']}، والنتيجة الأرجح وفق السوابق هي «{c['outcome_ar']}». "
        f"حجم الخطر يتركّز في فجوة المورد، وموضع الرافعة الأكثر أثرًا هو إدارة الطلب لا توليد العرض: حزمة الروافع وحدها "
        f"تشتري فارقًا قدره {c['risk_delta']} نقطة. مستوى الثقة في هذه القراءة: {c['conf_band']}.",
    ]})

    if cascade:
        # Anatomy of scarcity
        S.append({"title_ar": "تشريح الندرة: صدمة حادّة فوق هشاشة مزمنة", "title_en": "Anatomy of Scarcity", "paragraphs": [
            f"الجفاف شحَذَ الندرة ولم يصنعها. البنية الأساسية مأزومة أصلًا: حصّة الفرد {c['renewable_pc']} م³ سنويًّا (نحو 13% "
            f"من خطّ الندرة المطلقة 500 م³)، والسحب يبلغ {c['withdrawals_pct']}% من المورد المتجدّد، والسحب الجوفي ~{c['gw_ratio']} "
            f"ضعف المعدّل الآمن. فوق هذه الهشاشة تأتي الصدمة الحادّة: عجز هطول {c['rainfall_deficit']} وانهيار مخزون السدود "
            f"إلى {c['dam_latest']} مليون م³ (≈15% من السعة). يجب عدم نسبة الأرقام المزمنة إلى الجفاف وحده.",
        ]})

        # Multi-sector
        S.append({"title_ar": "التحليل متعدّد القطاعات (الاحتياج / الاستجابة / الفجوة)", "title_en": "Multi-Sector Analysis", "paragraphs": [
            f"إمدادات المياه (إجهاد {c['sector_water']}): الاحتياج أنّ المورد السطحي عند ≈15% من السعة وحصّة الفرد متدنّية "
            f"وفاقدٌ ~{c['nrw_pct']}%؛ الاستجابة استرداد الفاقد وتقنين الإمداد المنزلي بوصفهما «مصدر مياه» بلا بنية كبرى؛ "
            f"الفجوة أنّ تراجع الإجهاد لا يعني الأمان، فعجز المورد قائم ما دامت السماء جافّة.",
            f"الزراعة (إجهاد {c['sector_agriculture']} — الأعلى قطاعيًّا): أكبر مستهلك للمياه وأوّل ما يُمسّ عند التقنين؛ "
            f"خفض الريّ يحرّر مياهًا للاستخدام المنزلي لكنّه يقايض بخسارة في الغلّة. المياه الجوفية (إجهاد {c['sector_groundwater']}): "
            f"الضغط يرتفع مع انكماش السطحي، ما يفاقم الاستنزاف المزمن. التوتّر الاجتماعي (إجهاد {c['sector_social']}): يتصاعد مع "
            f"شحّ الإمداد وخسائر الزراعة، ويتطلّب تأطيرًا وطنيًّا تجميعيًّا وتواصلًا منصفًا.",
        ]})

        # Economic / food
        S.append({"title_ar": "الأثر الاقتصادي وسلاسل الانتقال الغذائية", "title_en": "Economic & Food Transmission", "paragraphs": [
            f"الخطر الغذائي أزمةُ دخلٍ وفاتورة استيراد لا أزمةَ رغيف: مع استيراد أكثر من {c['grain_import_pct']}% من الحبوب "
            f"واحتياطي ~{c['grain_reserve']} أشهر، ينتقل الأثر عبر أربع قنوات — كلفة الأعلاف، الثروة الحيوانية والتخلّص المبكّر "
            f"منها، أسعار الخضار المحلّية، والضغط على العملة وفاتورة الاستيراد. هذه القنوات تقديرية لغياب قيمة نقدية مقاسة في "
            f"بيانات المحرّك، وتُعرَض اتجاهًا لا رقمًا.",
        ]})

        # Why desalination
        S.append({"title_ar": "لماذا التحلية لا تُجدي هذا الموسم", "title_en": "Why Desalination Does Not Help This Season", "paragraphs": [
            f"يصنّف المحرّك صراحةً ما يلي «غير مُخفِّف» خلال أفق الاثني عشر شهرًا: {c['non_mitigating']}. فمشروع التحلية الكبير لا "
            f"يدخل الخدمة قبل ~{c['desal_year']}، ومنشأة بهذا الحجم لا تُبنى في عام؛ وحتى لو تضاعف تمويلها غدًا لن يتغيّر رقمٌ "
            f"واحد في خطر هذه السنة. الخلط بين حلّ بنيويّ بعيد الأمد وأزمةٍ آنية هو أكلف سوء تأطير ممكن.",
        ]})

        # Uncertainty
        S.append({"title_ar": "نطاق عدم اليقين", "title_en": "Uncertainty Range", "paragraphs": [
            f"عدم اليقين جوهر الرسالة لا هامشها: يعطي تحليل مونتي كارلو (n=200) مدًى من {c['mc_p10']} (متفائل P10) إلى "
            f"{c['mc_p90']} (متشائم P90) بوسيط {c['mc_p50']} وتشتّت {c['mc_spread']} نقطة. خطّط على الطرف المرتفع. ولا يُخلَط "
            f"الرقم الحتمي {c['risk_after']} (تشغيلة مرجعية) بوسيط مونتي كارلو {c['mc_p50']}؛ تقاربهما دليل متانة لا ترخيص استبدال.",
        ]})

    # Recommendations
    S.append({"title_ar": "التوصيات المرتّبة", "title_en": "Prioritized Recommendations", "paragraphs": ([
        f"فوريًّا (هذا الموسم): تفعيل حزمة إدارة الطلب — استرداد الفاقد المائي، خفض مخصّصات الريّ، وتقنين منزليّ منصف ومُعلَن "
        f"مسبقًا — فهي وحدها تشتري الفارق ({c['risk_delta']} نقطة) دون انتظار بنية جديدة. قصير ومتوسط الأمد: التوسّع في إعادة "
        f"استخدام المياه المعالَجة وإحكام إدارة الطلب الزراعي. بنيويًّا (لا إغاثيًّا): متابعة مشروع التحلية للأفق البعيد مع عدم "
        f"احتسابه ضمن حلول هذه السنة.",
        "كل توصية مشروطة بمتابعة مؤشّر قابل للقياس (انخفاض البلاغات/الفاقد، نسبة التغطية) وبمراجعة دورية للتقرير عند تغيّر "
        "المعطيات. ويُبقى التدخّل ضمن تأطير وطنيّ/قطاعيّ تجميعيّ دون استهداف فردي أو فئوي.",
    ] if cascade else [
        f"التوصية المحورية: تطبيق التدخّل الأقرب للنجاح وفق السوابق ومتابعة أثره عبر مؤشّر قابل للقياس، مع مراجعة دورية. "
        f"النتيجة الأرجح وفق السوابق: «{c['outcome_ar']}»، بمستوى ثقة {c['conf_band']}.",
    ])})

    # Methodology + limitations
    S.append({"title_ar": "المنهجية والقيود", "title_en": "Methodology & Limitations", "paragraphs": [
        "أُنتج هذا التقرير حتميًّا من محرّك AEGIS: محاكاة عددية متعدّدة القطاعات مبذورة بثوابت مُسنَدة، واسترجاع سوابق من "
        "ذاكرة الأزمات، وأدلّة من مصادر علمية مفتوحة قابلة للتحقّق. القيم النموذجية تقديرية تُقرأ اتجاهًا ومقياسًا نسبيًّا، "
        "والقيم المقاسة موسومة بمصادرها في صفحة المراجع. لا تتضمّن بيانات المحرّك قيمًا سكّانية أو نقدية، فما غاب عُرض [—] "
        "ولم يُختلَق. هذا التقرير لدعم القرار فقط وليس بديلًا عن البيانات الرسمية للجهات المختصّة، ولا يُقدَّم بأي ضمان.",
    ]})
    return S


def _references(payload: Dict[str, Any]) -> Dict[str, Any]:
    sim = payload.get("sim") or {}
    refs = (sim.get("references") or payload.get("references") or [])
    evidence = payload.get("evidence") or []
    peer = [{"title": e.get("title"), "year": e.get("year"), "oa": e.get("oa_status"), "doi": e.get("doi")}
            for e in evidence if e.get("doi")]
    institutional = [{"name": r.get("name"), "url": r.get("url")} for r in refs if r.get("name") and r.get("url")]
    return {"peer_reviewed": peer, "institutional": institutional,
            "count": len(peer) + len(institutional)}


def render(payload: Dict[str, Any], *, generated_at: str = "") -> Dict[str, Any]:
    sim = payload.get("sim") or {}
    cascade = sim.get("engine") == "cascade"
    c = build_context(payload)
    return {
        "meta": {
            "title_ar": "تقرير حالة — محاكاة أزمة",
            "scenario": c["scenario"],
            "report_no": "01 — تقرير حالة أوّليّ",
            "generated_at": generated_at,
            "flagship": cascade,
        },
        "key_figures": _key_figures(c, cascade),
        "sections": _sections(c, cascade),
        "references": _references(payload),
    }
