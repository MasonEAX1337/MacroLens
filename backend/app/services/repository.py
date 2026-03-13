from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.api import (
    AnomalyDetail,
    AnomalySummary,
    CorrelationRecord,
    DatasetSummary,
    ExplanationRecord,
    NewsContextRecord,
    TimeSeriesPoint,
)


def fetch_datasets(db: Session) -> list[DatasetSummary]:
    query = text(
        """
        SELECT id, name, symbol, source, description, frequency
        FROM datasets
        ORDER BY name ASC
        """
    )
    rows = db.execute(query).mappings().all()
    return [DatasetSummary.model_validate(row) for row in rows]


def fetch_dataset_timeseries(db: Session, dataset_id: int, limit: int) -> list[TimeSeriesPoint]:
    query = text(
        """
        SELECT timestamp, value
        FROM data_points
        WHERE dataset_id = :dataset_id
        ORDER BY timestamp DESC
        LIMIT :limit
        """
    )
    rows = db.execute(query, {"dataset_id": dataset_id, "limit": limit}).mappings().all()
    return [TimeSeriesPoint.model_validate(row) for row in reversed(rows)]


def fetch_dataset_anomalies(db: Session, dataset_id: int, limit: int) -> list[AnomalySummary]:
    query = text(
        """
        SELECT id, dataset_id, timestamp, severity_score, direction, detection_method
        FROM anomalies
        WHERE dataset_id = :dataset_id
        ORDER BY timestamp DESC
        LIMIT :limit
        """
    )
    rows = db.execute(query, {"dataset_id": dataset_id, "limit": limit}).mappings().all()
    return [AnomalySummary.model_validate(row) for row in rows]


def fetch_anomaly_detail(db: Session, anomaly_id: int) -> AnomalyDetail:
    anomaly_query = text(
        """
        SELECT
            a.id,
            a.dataset_id,
            a.timestamp,
            a.severity_score,
            a.direction,
            a.detection_method,
            d.name AS dataset_name
        FROM anomalies AS a
        JOIN datasets AS d ON d.id = a.dataset_id
        WHERE a.id = :anomaly_id
        """
    )
    anomaly = db.execute(anomaly_query, {"anomaly_id": anomaly_id}).mappings().first()
    if anomaly is None:
        raise HTTPException(status_code=404, detail="Anomaly not found")

    correlation_query = text(
        """
        SELECT
            c.related_dataset_id,
            d.name AS related_dataset_name,
            c.correlation_score,
            c.lag_days,
            c.method
        FROM correlations AS c
        JOIN datasets AS d ON d.id = c.related_dataset_id
        WHERE c.anomaly_id = :anomaly_id
        ORDER BY ABS(c.correlation_score) DESC, c.related_dataset_id ASC
        """
    )
    explanation_query = text(
        """
        SELECT provider, model, generated_text, created_at
        FROM explanations
        WHERE anomaly_id = :anomaly_id
        ORDER BY created_at DESC
        """
    )
    news_context_query = text(
        """
        SELECT
            provider,
            article_url,
            title,
            domain,
            language,
            source_country,
            published_at,
            search_query,
            relevance_rank
        FROM news_context
        WHERE anomaly_id = :anomaly_id
        ORDER BY relevance_rank ASC, published_at DESC, id ASC
        """
    )

    correlations = db.execute(correlation_query, {"anomaly_id": anomaly_id}).mappings().all()
    explanations = db.execute(explanation_query, {"anomaly_id": anomaly_id}).mappings().all()
    news_context = db.execute(news_context_query, {"anomaly_id": anomaly_id}).mappings().all()

    return AnomalyDetail(
        **anomaly,
        correlations=[CorrelationRecord.model_validate(row) for row in correlations],
        explanations=[ExplanationRecord.model_validate(row) for row in explanations],
        news_context=[NewsContextRecord.model_validate(row) for row in news_context],
    )
