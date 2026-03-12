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


class AnomalyDetail(AnomalySummary):
    dataset_name: str
    correlations: list[CorrelationRecord]
    explanations: list[ExplanationRecord]
