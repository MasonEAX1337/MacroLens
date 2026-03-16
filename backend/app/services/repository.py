from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.api import (
    AnomalyDetail,
    AnomalyClusterRecord,
    AnomalySummary,
    ClusterMemberRecord,
    CorrelationRecord,
    DatasetSummary,
    ExplanationRecord,
    NewsContextRecord,
    NewsContextStatus,
    PropagationEdgeRecord,
    TimeSeriesPoint,
)
from app.services.news_context import NewsContextRequest, get_news_context_provider_names, get_news_context_status
from app.services.propagation import build_propagation_timeline


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
        SELECT
            a.id,
            a.dataset_id,
            a.timestamp,
            a.severity_score,
            a.direction,
            a.detection_method,
            acm.cluster_id,
            ac.anomaly_count AS cluster_anomaly_count
        FROM anomalies AS a
        LEFT JOIN anomaly_cluster_members AS acm ON acm.anomaly_id = a.id
        LEFT JOIN anomaly_clusters AS ac ON ac.id = acm.cluster_id
        WHERE a.dataset_id = :dataset_id
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
            acm.cluster_id,
            ac.anomaly_count AS cluster_anomaly_count,
            d.name AS dataset_name,
            d.symbol AS dataset_symbol,
            d.frequency AS dataset_frequency
        FROM anomalies AS a
        JOIN datasets AS d ON d.id = a.dataset_id
        LEFT JOIN anomaly_cluster_members AS acm ON acm.anomaly_id = a.id
        LEFT JOIN anomaly_clusters AS ac ON ac.id = acm.cluster_id
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
    cluster_query = text(
        """
        SELECT
            ac.id,
            ac.start_timestamp,
            ac.end_timestamp,
            ac.anchor_timestamp,
            ac.anomaly_count,
            ac.dataset_count,
            ac.peak_severity_score
        FROM anomaly_cluster_members AS acm
        JOIN anomaly_clusters AS ac ON ac.id = acm.cluster_id
        WHERE acm.anomaly_id = :anomaly_id
        """
    )
    cluster_members_query = text(
        """
        SELECT
            a.id AS anomaly_id,
            a.dataset_id,
            d.name AS dataset_name,
            a.timestamp,
            a.severity_score,
            a.direction,
            a.detection_method
        FROM anomaly_cluster_members AS acm
        JOIN anomalies AS a ON a.id = acm.anomaly_id
        JOIN datasets AS d ON d.id = a.dataset_id
        WHERE acm.cluster_id = :cluster_id
        ORDER BY a.timestamp ASC, a.severity_score DESC, a.id ASC
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
        ORDER BY
            CASE provider
                WHEN 'macro_timeline' THEN 0
                WHEN 'gdelt' THEN 1
                ELSE 2
            END ASC,
            relevance_rank ASC,
            published_at DESC,
            id ASC
        """
    )

    attempted_provider_names = get_news_context_provider_names(
        NewsContextRequest(
            anomaly_id=int(anomaly["id"]),
            dataset_name=str(anomaly["dataset_name"]),
            dataset_symbol=str(anomaly["dataset_symbol"]),
            dataset_frequency=str(anomaly["dataset_frequency"]),
            timestamp=anomaly["timestamp"],
        )
    )
    correlations = db.execute(correlation_query, {"anomaly_id": anomaly_id}).mappings().all()
    cluster_row = db.execute(cluster_query, {"anomaly_id": anomaly_id}).mappings().first()
    explanations = db.execute(explanation_query, {"anomaly_id": anomaly_id}).mappings().all()
    news_context = db.execute(news_context_query, {"anomaly_id": anomaly_id}).mappings().all()
    article_provider_names = list(dict.fromkeys(str(row["provider"]) for row in news_context))
    news_context_status = get_news_context_status(
        dataset_symbol=str(anomaly["dataset_symbol"]),
        dataset_frequency=str(anomaly["dataset_frequency"]),
        has_articles=bool(news_context),
        attempted_provider_names=attempted_provider_names,
        article_provider_names=article_provider_names,
    )
    cluster = None
    propagation_timeline: list[PropagationEdgeRecord] = []
    if cluster_row is not None:
        cluster_members = db.execute(
            cluster_members_query,
            {"cluster_id": cluster_row["id"]},
        ).mappings().all()
        cluster = AnomalyClusterRecord(
            **cluster_row,
            members=[ClusterMemberRecord.model_validate(row) for row in cluster_members],
        )
        propagation_timeline = [
            PropagationEdgeRecord.model_validate(item)
            for item in build_propagation_timeline(db, int(cluster_row["id"]))
        ]

    return AnomalyDetail(
        **anomaly,
        cluster=cluster,
        propagation_timeline=propagation_timeline,
        correlations=[CorrelationRecord.model_validate(row) for row in correlations],
        explanations=[ExplanationRecord.model_validate(row) for row in explanations],
        news_context=[NewsContextRecord.model_validate(row) for row in news_context],
        news_context_status=NewsContextStatus.model_validate(news_context_status),
    )
