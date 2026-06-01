"""Pydantic schemas for VOC360 data returned by the API."""
from __future__ import annotations
from pydantic import BaseModel


# --- Unified citizen feedback record ---
class CitizenRecord(BaseModel):
    record_id: str
    source_type: str | None = None
    source_platform: str | None = None
    source_channel: str | None = None
    entity_id: str | None = None
    service_id: str | None = None
    governorate: str | None = None
    district: str | None = None
    text: str | None = None
    text_clean: str | None = None
    observed_at: str | None = None
    date: str | None = None
    sentiment_label: str | None = None
    confidence: float | None = None
    severity: str | None = None
    rating: float | None = None
    signal_value: float | None = None


# --- Social sentiment signal ---
class SentimentSignal(BaseModel):
    id: int
    source_id: str | None = None
    source_mode: str | None = None
    signal_type: str | None = None
    entity_id: str | None = None
    service_id: str | None = None
    channel_id: str | None = None
    governorate: str | None = None
    district: str | None = None
    signal_timestamp: str | None = None
    signal_value: int | None = None
    signal_scale: str | None = None
    interpretation: str | None = None
    confidence: float | None = None
    severity: str | None = None
    raw_text: str | None = None
    likes: float | None = None
    retweets: float | None = None
    is_reply: bool | None = None
    real_world_topic_link: str | None = None
    created_at: str | None = None


# --- Bekhedmetkom government complaint ---
class Complaint(BaseModel):
    id: int | None = None
    complaint_id: str | None = None
    ministry: str | None = None
    description: str | None = None
    category: str | None = None
    subcategory: str | None = None
    request_type: str | None = None
    status: str | None = None
    rating: float | None = None
    governorate: str | None = None
    municipality: str | None = None
    service_name: str | None = None
    gender: str | None = None
    resolution_text: str | None = None
    resolution_days: float | None = None
    created_date: str | None = None
    resolved_date: str | None = None
    ticket_status: str | None = None


# --- Ministry KPI Summary ---
class MinistryKPI(BaseModel):
    id: int
    ministry: str
    total_complaints: int | None = None
    resolved: int | None = None
    resolution_rate_pct: float | None = None
    avg_resolution_days: float | None = None
    avg_rating_1_5: float | None = None
    rating_coverage_pct: float | None = None
    survey_mean_score: float | None = None
    ticket_status: str | None = None


# --- Problem Cluster ---
class ProblemCluster(BaseModel):
    cluster_id: str
    canonical_label_ar: str | None = None
    canonical_label_en: str | None = None
    description: str | None = None
    parent_cluster_id: str | None = None
    entity_id: str | None = None
    service_id: str | None = None
    member_count: int | None = None
    severity_avg: float | None = None
    status: str | None = None
    first_seen: str | None = None
    last_seen: str | None = None


# --- Forecast Question ---
class ForecastQuestion(BaseModel):
    id: int | None = None
    project_id: str | None = None
    question_ar: str | None = None
    answer_ar: str | None = None
    summary_ar: str | None = None
    predicted_impact_ar: str | None = None
    affected_groups_ar: str | None = None
    recommended_actions_ar: str | None = None
    confidence: str | None = None
    model: str | None = None
    created_at: str | None = None


# --- Aggregation responses ---
class SeverityDistribution(BaseModel):
    severity: str
    count: int


class GovernorateBreakdown(BaseModel):
    governorate: str
    count: int
    avg_severity_value: float | None = None


class EntityBreakdown(BaseModel):
    entity_id: str
    count: int
    avg_confidence: float | None = None


class TimeSeriesPoint(BaseModel):
    date: str
    count: int
    avg_signal_value: float | None = None


class VocSummary(BaseModel):
    total_records: int
    total_signals: int
    total_complaints: int
    total_clusters: int
    severity_distribution: list[SeverityDistribution]
    top_entities: list[EntityBreakdown]
    top_governorates: list[GovernorateBreakdown]
