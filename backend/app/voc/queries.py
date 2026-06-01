"""VOC360 async database queries."""
from __future__ import annotations
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


# ──────────────────────────────────────────────────────────────────────
# Unified records (the_data)
# ──────────────────────────────────────────────────────────────────────

async def get_records(
    db: AsyncSession,
    *,
    limit: int = 50,
    offset: int = 0,
    governorate: str | None = None,
    entity_id: str | None = None,
    service_id: str | None = None,
    severity: str | None = None,
    source_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict]:
    clauses = []
    params: dict = {"limit": limit, "offset": offset}

    if governorate:
        clauses.append("governorate = :governorate")
        params["governorate"] = governorate
    if entity_id:
        clauses.append("entity_id = :entity_id")
        params["entity_id"] = entity_id
    if service_id:
        clauses.append("service_id = :service_id")
        params["service_id"] = service_id
    if severity:
        clauses.append("severity = :severity")
        params["severity"] = severity
    if source_type:
        clauses.append("source_type = :source_type")
        params["source_type"] = source_type
    if date_from:
        clauses.append("date >= :date_from")
        params["date_from"] = date_from
    if date_to:
        clauses.append("date <= :date_to")
        params["date_to"] = date_to

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"""
        SELECT record_id, source_type, source_platform, source_channel,
               entity_id, service_id, governorate, district,
               text, text_clean, observed_at, date,
               sentiment_label, confidence, severity, rating, signal_value
        FROM the_data
        {where}
        ORDER BY observed_at DESC NULLS LAST
        LIMIT :limit OFFSET :offset
    """
    result = await db.execute(text(sql), params)
    return [dict(row._mapping) for row in result]


async def count_records(
    db: AsyncSession,
    *,
    governorate: str | None = None,
    entity_id: str | None = None,
    severity: str | None = None,
) -> int:
    clauses = []
    params: dict = {}
    if governorate:
        clauses.append("governorate = :governorate")
        params["governorate"] = governorate
    if entity_id:
        clauses.append("entity_id = :entity_id")
        params["entity_id"] = entity_id
    if severity:
        clauses.append("severity = :severity")
        params["severity"] = severity
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"SELECT COUNT(*) FROM the_data {where}"
    result = await db.execute(text(sql), params)
    return result.scalar_one()


# ──────────────────────────────────────────────────────────────────────
# Social Sentiment Signals
# ──────────────────────────────────────────────────────────────────────

async def get_signals(
    db: AsyncSession,
    *,
    limit: int = 50,
    offset: int = 0,
    entity_id: str | None = None,
    severity: str | None = None,
    signal_type: str | None = None,
    governorate: str | None = None,
    since: str | None = None,
) -> list[dict]:
    clauses = []
    params: dict = {"limit": limit, "offset": offset}

    if entity_id:
        clauses.append("entity_id = :entity_id")
        params["entity_id"] = entity_id
    if severity:
        clauses.append("severity = :severity")
        params["severity"] = severity
    if signal_type:
        clauses.append("signal_type = :signal_type")
        params["signal_type"] = signal_type
    if governorate:
        clauses.append("governorate = :governorate")
        params["governorate"] = governorate
    if since:
        clauses.append("signal_timestamp >= :since")
        params["since"] = since

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"""
        SELECT id, source_id, source_mode, signal_type, entity_id, service_id,
               channel_id, governorate, district, signal_timestamp,
               signal_value, signal_scale, interpretation, confidence,
               severity, raw_text, likes, retweets, is_reply,
               real_world_topic_link, created_at
        FROM social_sentiment_signals
        {where}
        ORDER BY signal_timestamp DESC NULLS LAST
        LIMIT :limit OFFSET :offset
    """
    result = await db.execute(text(sql), params)
    return [dict(row._mapping) for row in result]


# ──────────────────────────────────────────────────────────────────────
# Complaints (Bekhedmetkom)
# ──────────────────────────────────────────────────────────────────────

async def get_complaints(
    db: AsyncSession,
    *,
    limit: int = 50,
    offset: int = 0,
    ministry: str | None = None,
    governorate: str | None = None,
    category: str | None = None,
    status: str | None = None,
) -> list[dict]:
    clauses = []
    params: dict = {"limit": limit, "offset": offset}

    if ministry:
        clauses.append("ministry = :ministry")
        params["ministry"] = ministry
    if governorate:
        clauses.append("governorate = :governorate")
        params["governorate"] = governorate
    if category:
        clauses.append("category = :category")
        params["category"] = category
    if status:
        clauses.append("status = :status")
        params["status"] = status

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"""
        SELECT id, complaint_id, ministry, description, category, subcategory,
               request_type, status, rating, governorate, municipality,
               service_name, gender, resolution_text, resolution_days,
               created_date, resolved_date, ticket_status
        FROM pm_bkhidmatkom_complaints
        {where}
        ORDER BY created_date DESC NULLS LAST
        LIMIT :limit OFFSET :offset
    """
    result = await db.execute(text(sql), params)
    return [dict(row._mapping) for row in result]


# ──────────────────────────────────────────────────────────────────────
# Ministry KPIs
# ──────────────────────────────────────────────────────────────────────

async def get_kpi_summary(db: AsyncSession) -> list[dict]:
    sql = "SELECT * FROM pm_kpi_summary ORDER BY ministry"
    result = await db.execute(text(sql))
    return [dict(row._mapping) for row in result]


# ──────────────────────────────────────────────────────────────────────
# Problem Clusters
# ──────────────────────────────────────────────────────────────────────

async def get_clusters(
    db: AsyncSession,
    *,
    status: str | None = "active",
) -> list[dict]:
    clauses = []
    params: dict = {}
    if status:
        clauses.append("status = :status")
        params["status"] = status
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"""
        SELECT cluster_id, canonical_label_ar, canonical_label_en, description,
               parent_cluster_id, entity_id, service_id, member_count,
               severity_avg, status, first_seen, last_seen, created_at, updated_at
        FROM ril_problem_clusters
        {where}
        ORDER BY member_count DESC NULLS LAST
    """
    result = await db.execute(text(sql), params)
    return [dict(row._mapping) for row in result]


async def get_cluster_members(db: AsyncSession, cluster_id: str) -> list[dict]:
    sql = """
        SELECT cm.segment_id, cm.distance_to_centroid, ts.segment_text, ts.language
        FROM ril_cluster_members cm
        LEFT JOIN ril_text_segments ts ON cm.segment_id = ts.segment_id
        WHERE cm.cluster_id = :cluster_id
        ORDER BY cm.distance_to_centroid ASC
    """
    result = await db.execute(text(sql), {"cluster_id": cluster_id})
    return [dict(row._mapping) for row in result]


# ──────────────────────────────────────────────────────────────────────
# Forecast Questions
# ──────────────────────────────────────────────────────────────────────

async def get_forecasts(db: AsyncSession) -> list[dict]:
    sql = """
        SELECT id, project_id, question_ar, answer_ar, summary_ar,
               predicted_impact_ar, affected_groups_ar, recommended_actions_ar,
               confidence, model, created_at
        FROM forecast_questions
        ORDER BY created_at DESC NULLS LAST
    """
    result = await db.execute(text(sql))
    return [dict(row._mapping) for row in result]


# ──────────────────────────────────────────────────────────────────────
# Aggregations / Dashboard
# ──────────────────────────────────────────────────────────────────────

async def severity_distribution(db: AsyncSession, table: str = "social_sentiment_signals") -> list[dict]:
    allowed = {"social_sentiment_signals", "the_data"}
    if table not in allowed:
        table = "social_sentiment_signals"
    sql = f"""
        SELECT severity, COUNT(*) as count
        FROM {table}
        WHERE severity IS NOT NULL
        GROUP BY severity
        ORDER BY count DESC
    """
    result = await db.execute(text(sql))
    return [dict(row._mapping) for row in result]


async def governorate_breakdown(db: AsyncSession) -> list[dict]:
    sql = """
        SELECT governorate, COUNT(*) as count,
               AVG(signal_value) as avg_signal_value
        FROM social_sentiment_signals
        WHERE governorate IS NOT NULL
        GROUP BY governorate
        ORDER BY count DESC
    """
    result = await db.execute(text(sql))
    return [dict(row._mapping) for row in result]


async def entity_breakdown(db: AsyncSession) -> list[dict]:
    sql = """
        SELECT entity_id, COUNT(*) as count,
               AVG(confidence) as avg_confidence
        FROM social_sentiment_signals
        WHERE entity_id IS NOT NULL
        GROUP BY entity_id
        ORDER BY count DESC
        LIMIT 20
    """
    result = await db.execute(text(sql))
    return [dict(row._mapping) for row in result]


async def daily_signal_trend(
    db: AsyncSession,
    *,
    days: int = 30,
    entity_id: str | None = None,
) -> list[dict]:
    clauses = ["signal_timestamp IS NOT NULL"]
    params: dict = {"days": days}
    if entity_id:
        clauses.append("entity_id = :entity_id")
        params["entity_id"] = entity_id
    where = "WHERE " + " AND ".join(clauses)
    sql = f"""
        SELECT DATE(signal_timestamp::timestamp) as date,
               COUNT(*) as count,
               AVG(signal_value) as avg_signal_value
        FROM social_sentiment_signals
        {where}
        GROUP BY DATE(signal_timestamp::timestamp)
        ORDER BY date DESC
        LIMIT :days
    """
    result = await db.execute(text(sql), params)
    return [dict(row._mapping) for row in result]


async def voc_summary(db: AsyncSession) -> dict:
    """High-level summary across all VOC tables."""
    r1 = await db.execute(text("SELECT COUNT(*) FROM the_data"))
    r2 = await db.execute(text("SELECT COUNT(*) FROM social_sentiment_signals"))
    r3 = await db.execute(text("SELECT COUNT(*) FROM pm_bkhidmatkom_complaints"))
    r4 = await db.execute(text("SELECT COUNT(*) FROM ril_problem_clusters"))

    sev = await severity_distribution(db, "social_sentiment_signals")
    ent = await entity_breakdown(db)
    gov = await governorate_breakdown(db)

    return {
        "total_records": r1.scalar_one(),
        "total_signals": r2.scalar_one(),
        "total_complaints": r3.scalar_one(),
        "total_clusters": r4.scalar_one(),
        "severity_distribution": sev,
        "top_entities": ent,
        "top_governorates": gov,
    }
