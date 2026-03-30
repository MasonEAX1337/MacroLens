from datetime import datetime

from pydantic import BaseModel


class DatasetSummary(BaseModel):
    id: int
    name: str
    symbol: str
    source: str
    description: str | None = None
    frequency: str


class LeadingIndicatorRecord(BaseModel):
    related_dataset_id: int
    related_dataset_name: str
    related_dataset_frequency: str
    target_dataset_frequency: str
    supporting_cluster_count: int
    target_cluster_count: int
    cluster_coverage: float
    average_lead_days: int
    average_correlation_score: float
    average_abs_correlation_score: float
    strongest_correlation_score: float
    sign_consistency: float
    dominant_direction: str
    frequency_alignment: float
    support_confidence: float
    consistency_score: float
    supporting_episodes: list["LeadingIndicatorSupportRecord"]


class LeadingIndicatorSupportRecord(BaseModel):
    target_cluster_id: int
    target_anomaly_id: int
    target_dataset_name: str
    target_timestamp: datetime
    target_direction: str | None = None
    target_detection_method: str
    target_severity_score: float
    target_cluster_start_timestamp: datetime
    target_cluster_end_timestamp: datetime
    target_cluster_span_days: int
    target_cluster_anomaly_count: int
    target_cluster_dataset_count: int
    target_cluster_peak_severity_score: float
    target_cluster_frequency_mix: str
    target_cluster_episode_kind: str
    target_cluster_quality_band: str
    correlation_score: float
    lag_days: int
    cluster_members: list["LeadingIndicatorClusterMemberPreview"]


class LeadingIndicatorClusterMemberPreview(BaseModel):
    anomaly_id: int
    dataset_id: int
    dataset_name: str
    timestamp: datetime
    severity_score: float
    direction: str | None = None
    detection_method: str


class TimeSeriesPoint(BaseModel):
    timestamp: datetime
    value: float


class AnomalySummary(BaseModel):
    id: int
    dataset_id: int
    timestamp: datetime
    severity_score: float
    direction: str | None = None
    detection_method: str
    episode_filter_status: str | None = None
    episode_filter_reason: str | None = None
    cluster_id: int | None = None
    cluster_anomaly_count: int | None = None
    cluster_episode_kind: str | None = None
    cluster_quality_band: str | None = None


class CorrelationRecord(BaseModel):
    related_dataset_id: int
    related_dataset_name: str
    correlation_score: float
    lag_days: int
    method: str


class ExplanationRecord(BaseModel):
    provider: str
    model: str
    generated_text: str
    created_at: datetime


class NewsContextRecord(BaseModel):
    provider: str
    article_url: str
    title: str
    domain: str | None = None
    language: str | None = None
    source_country: str | None = None
    published_at: datetime | None = None
    search_query: str
    relevance_rank: int
    retrieval_scope: str | None = None
    timing_relation: str | None = None
    context_window_start: datetime | None = None
    context_window_end: datetime | None = None
    event_themes: list[str] = []
    primary_theme: str | None = None
    source_kind: str | None = None
    historical_event_id: str | None = None
    historical_event_summary: str | None = None
    historical_event_type: str | None = None
    historical_event_regions: list[str] = []
    historical_event_confidence: float | None = None
    context_score: float | None = None


class NewsContextStatus(BaseModel):
    provider: str
    status: str
    note: str


class ClusterMemberRecord(BaseModel):
    anomaly_id: int
    dataset_id: int
    dataset_name: str
    timestamp: datetime
    severity_score: float
    direction: str | None = None
    detection_method: str


class AnomalyClusterRecord(BaseModel):
    id: int
    start_timestamp: datetime
    end_timestamp: datetime
    anchor_timestamp: datetime
    span_days: int
    anomaly_count: int
    dataset_count: int
    peak_severity_score: float
    frequency_mix: str
    episode_kind: str
    quality_band: str
    members: list[ClusterMemberRecord]


class PropagationEvidenceRecord(BaseModel):
    source_anomaly_id: int
    source_dataset_name: str
    source_timestamp: datetime
    target_anomaly_id: int
    target_dataset_id: int
    target_dataset_name: str
    target_timestamp: datetime
    correlation_score: float
    lag_days: int
    method: str
    match_gap_days: float
    tolerance_days: int


class PropagationStrengthComponents(BaseModel):
    correlation_strength: float
    support_density: float
    temporal_alignment: float
    target_scale: float
    episode_quality: float
    overall: float


class PropagationEdgeRecord(BaseModel):
    source_cluster_id: int
    target_cluster_id: int
    target_start_timestamp: datetime
    target_end_timestamp: datetime
    target_anchor_timestamp: datetime
    target_anchor_anomaly_id: int
    target_anchor_dataset_id: int
    target_span_days: int
    target_anomaly_count: int
    target_dataset_count: int
    target_peak_severity_score: float
    target_frequency_mix: str
    target_episode_kind: str
    target_quality_band: str
    average_lag_days: int
    strongest_correlation_score: float
    supporting_link_count: int
    evidence_strength: float
    evidence_strength_components: PropagationStrengthComponents
    source_dataset_names: list[str]
    target_dataset_names: list[str]
    evidence: list[PropagationEvidenceRecord]


class AnomalyDetail(AnomalySummary):
    dataset_name: str
    cluster: AnomalyClusterRecord | None = None
    propagation_timeline: list[PropagationEdgeRecord]
    correlations: list[CorrelationRecord]
    explanations: list[ExplanationRecord]
    news_context: list[NewsContextRecord]
    news_context_status: NewsContextStatus
