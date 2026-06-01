"""VOC360 API — Voice of Citizen data endpoints."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.voc import queries

router = APIRouter(prefix="/voc", tags=["voc"])


# ─── Dashboard / Summary ────────────────────────────────────────────

@router.get("/summary")
async def voc_summary(db: AsyncSession = Depends(get_db)):
    """High-level VOC dashboard summary."""
    return await queries.voc_summary(db)


@router.get("/kpi")
async def ministry_kpis(db: AsyncSession = Depends(get_db)):
    """All ministry KPI scorecards."""
    return await queries.get_kpi_summary(db)


# ─── Unified Citizen Records ────────────────────────────────────────

@router.get("/records")
async def list_records(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    governorate: str | None = None,
    entity_id: str | None = None,
    service_id: str | None = None,
    severity: str | None = None,
    source_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Paginated citizen feedback records with filters."""
    rows = await queries.get_records(
        db, limit=limit, offset=offset,
        governorate=governorate, entity_id=entity_id,
        service_id=service_id, severity=severity,
        source_type=source_type, date_from=date_from, date_to=date_to,
    )
    total = await queries.count_records(
        db, governorate=governorate, entity_id=entity_id, severity=severity,
    )
    return {"total": total, "limit": limit, "offset": offset, "data": rows}


# ─── Social Sentiment Signals ───────────────────────────────────────

@router.get("/signals")
async def list_signals(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    entity_id: str | None = None,
    severity: str | None = None,
    signal_type: str | None = None,
    governorate: str | None = None,
    since: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Social media sentiment signals with filters."""
    return await queries.get_signals(
        db, limit=limit, offset=offset,
        entity_id=entity_id, severity=severity,
        signal_type=signal_type, governorate=governorate, since=since,
    )


# ─── Government Complaints ──────────────────────────────────────────

@router.get("/complaints")
async def list_complaints(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    ministry: str | None = None,
    governorate: str | None = None,
    category: str | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Bekhedmetkom platform complaints."""
    return await queries.get_complaints(
        db, limit=limit, offset=offset,
        ministry=ministry, governorate=governorate,
        category=category, status=status,
    )


# ─── Problem Clusters ───────────────────────────────────────────────

@router.get("/clusters")
async def list_clusters(
    status: str | None = "active",
    db: AsyncSession = Depends(get_db),
):
    """AI-identified problem clusters."""
    return await queries.get_clusters(db, status=status)


@router.get("/clusters/{cluster_id}/members")
async def cluster_members(
    cluster_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Text segments belonging to a specific cluster."""
    return await queries.get_cluster_members(db, cluster_id)


# ─── Forecasts ──────────────────────────────────────────────────────

@router.get("/forecasts")
async def list_forecasts(db: AsyncSession = Depends(get_db)):
    """AI-generated forecast questions and answers."""
    return await queries.get_forecasts(db)


# ─── Analytics / Trends ─────────────────────────────────────────────

@router.get("/analytics/severity")
async def severity_dist(
    table: str = Query("social_sentiment_signals"),
    db: AsyncSession = Depends(get_db),
):
    """Severity distribution across signals or records."""
    return await queries.severity_distribution(db, table=table)


@router.get("/analytics/governorates")
async def governorate_stats(db: AsyncSession = Depends(get_db)):
    """Signal counts and averages by governorate."""
    return await queries.governorate_breakdown(db)


@router.get("/analytics/entities")
async def entity_stats(db: AsyncSession = Depends(get_db)):
    """Signal counts by entity (ministry/agency)."""
    return await queries.entity_breakdown(db)


@router.get("/analytics/trend")
async def signal_trend(
    days: int = Query(30, le=365),
    entity_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Daily signal count trend."""
    return await queries.daily_signal_trend(db, days=days, entity_id=entity_id)
