from datetime import datetime

from pydantic import BaseModel


class DatasetSummary(BaseModel):
    id: int
    name: str
    symbol: str
    source: str
    description: str | None = None
    frequency: str


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
    cluster_id: int | None = None
    cluster_anomaly_count: int | None = None


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
    anomaly_count: int
    dataset_count: int
    peak_severity_score: float
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


class PropagationEdgeRecord(BaseModel):
    source_cluster_id: int
    target_cluster_id: int
    target_start_timestamp: datetime
    target_end_timestamp: datetime
    target_anchor_timestamp: datetime
    target_anchor_anomaly_id: int
    target_anchor_dataset_id: int
    target_anomaly_count: int
    target_dataset_count: int
    target_peak_severity_score: float
    average_lag_days: int
    strongest_correlation_score: float
    supporting_link_count: int
    evidence_strength: float
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
