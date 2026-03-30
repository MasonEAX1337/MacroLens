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
    LeadingIndicatorClusterMemberPreview,
    LeadingIndicatorRecord,
    LeadingIndicatorSupportRecord,
    NewsContextRecord,
    NewsContextStatus,
    PropagationEdgeRecord,
    TimeSeriesPoint,
)
from app.services.leading_indicators import build_leading_indicators
from app.services.news_context import NewsContextRequest, get_active_news_context_provider_names, get_news_context_status
from app.services.propagation import build_propagation_timeline


def load_cluster_member_previews(
    db: Session,
    cluster_ids: list[int],
) -> dict[int, list[LeadingIndicatorClusterMemberPreview]]:
    positive_cluster_ids = sorted({cluster_id for cluster_id in cluster_ids if cluster_id > 0})
    if not positive_cluster_ids:
        return {}

    query = text(
        """
        SELECT
            acm.cluster_id,
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
        WHERE acm.cluster_id = ANY(:cluster_ids)
        ORDER BY acm.cluster_id ASC, a.timestamp ASC, a.severity_score DESC, a.id ASC
        """
    )
    rows = db.execute(query, {"cluster_ids": positive_cluster_ids}).mappings().all()
    members_by_cluster: dict[int, list[LeadingIndicatorClusterMemberPreview]] = {}
    for row in rows:
        cluster_id = int(row["cluster_id"])
        payload = dict(row)
        payload.pop("cluster_id", None)
        members_by_cluster.setdefault(cluster_id, []).append(
            LeadingIndicatorClusterMemberPreview.model_validate(payload)
        )
    return members_by_cluster


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
            a.metadata ->> 'episode_filter_status' AS episode_filter_status,
            a.metadata ->> 'episode_filter_reason' AS episode_filter_reason,
            acm.cluster_id,
            ac.anomaly_count AS cluster_anomaly_count,
            ac.episode_kind AS cluster_episode_kind,
            ac.quality_band AS cluster_quality_band
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


def fetch_dataset_leading_indicators(
    db: Session,
    dataset_id: int,
    limit: int,
) -> list[LeadingIndicatorRecord]:
    aggregates = build_leading_indicators(db, dataset_id, limit=limit)
    members_by_cluster = load_cluster_member_previews(
        db,
        [episode.target_cluster_id for item in aggregates for episode in item.supporting_episodes],
    )
    records: list[LeadingIndicatorRecord] = []
    for item in aggregates:
        payload = vars(item) | {
            "supporting_episodes": [
                LeadingIndicatorSupportRecord.model_validate(
                    vars(episode)
                    | {
                        "cluster_members": members_by_cluster.get(
                            episode.target_cluster_id,
                            [
                                LeadingIndicatorClusterMemberPreview.model_validate(
                                    {
                                        "anomaly_id": episode.target_anomaly_id,
                                        "dataset_id": episode.target_dataset_id,
                                        "dataset_name": episode.target_dataset_name,
                                        "timestamp": episode.target_timestamp,
                                        "severity_score": episode.target_severity_score,
                                        "direction": episode.target_direction,
                                        "detection_method": episode.target_detection_method,
                                    }
                                )
                            ],
                        )
                    }
                )
                for episode in item.supporting_episodes
            ]
        }
        records.append(LeadingIndicatorRecord.model_validate(payload))
    return records


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
            a.metadata ->> 'episode_filter_status' AS episode_filter_status,
            a.metadata ->> 'episode_filter_reason' AS episode_filter_reason,
            acm.cluster_id,
            ac.anomaly_count AS cluster_anomaly_count,
            ac.episode_kind AS cluster_episode_kind,
            ac.quality_band AS cluster_quality_band,
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
            ac.span_days,
            ac.anomaly_count,
            ac.dataset_count,
            ac.peak_severity_score,
            ac.frequency_mix,
            ac.episode_kind,
            ac.quality_band
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
            relevance_rank,
            metadata ->> 'retrieval_scope' AS retrieval_scope,
            metadata ->> 'timing_relation' AS timing_relation,
            CAST(metadata ->> 'context_window_start' AS TIMESTAMPTZ) AS context_window_start,
            CAST(metadata ->> 'context_window_end' AS TIMESTAMPTZ) AS context_window_end,
            COALESCE(metadata -> 'event_themes', '[]'::jsonb) AS event_themes,
            metadata ->> 'primary_theme' AS primary_theme,
            metadata ->> 'source_kind' AS source_kind,
            metadata ->> 'driver_summary' AS driver_summary,
            metadata ->> 'historical_event_id' AS historical_event_id,
            metadata ->> 'historical_event_summary' AS historical_event_summary,
            metadata ->> 'historical_event_type' AS historical_event_type,
            COALESCE(metadata -> 'historical_event_regions', '[]'::jsonb) AS historical_event_regions,
            CAST(metadata ->> 'historical_event_confidence' AS DOUBLE PRECISION) AS historical_event_confidence,
            CAST(metadata ->> 'context_score' AS DOUBLE PRECISION) AS context_score
        FROM news_context
        WHERE anomaly_id = :anomaly_id
        ORDER BY
            CAST(COALESCE(metadata ->> 'context_score', '0') AS DOUBLE PRECISION) DESC,
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

    attempted_provider_names = get_active_news_context_provider_names(
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
