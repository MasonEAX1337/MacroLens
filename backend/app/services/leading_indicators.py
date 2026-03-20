from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class LeadingIndicatorSupport:
    target_cluster_id: int
    target_anomaly_id: int
    target_dataset_id: int
    target_dataset_name: str
    target_timestamp: object
    target_direction: str | None
    target_detection_method: str
    target_severity_score: float
    target_cluster_start_timestamp: object
    target_cluster_end_timestamp: object
    target_cluster_anomaly_count: int
    target_cluster_dataset_count: int
    target_cluster_peak_severity_score: float
    target_dataset_frequency: str
    related_dataset_id: int
    related_dataset_name: str
    related_dataset_frequency: str
    correlation_score: float
    lag_days: int


@dataclass(frozen=True)
class LeadingIndicatorAggregate:
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
    supporting_episodes: list[LeadingIndicatorSupport]


FREQUENCY_RANK = {
    "daily": 0,
    "weekly": 1,
    "monthly": 2,
}


def compute_frequency_alignment(
    related_frequency: str,
    target_frequency: str,
) -> float:
    related_rank = FREQUENCY_RANK.get(related_frequency)
    target_rank = FREQUENCY_RANK.get(target_frequency)
    if related_rank is None or target_rank is None:
        return 0.8

    distance = abs(related_rank - target_rank)
    if distance == 0:
        return 1.0
    if distance == 1:
        return 0.85
    return 0.65


def compute_support_confidence(supporting_cluster_count: int) -> float:
    if supporting_cluster_count >= 4:
        return 1.0
    if supporting_cluster_count == 3:
        return 0.8
    if supporting_cluster_count == 2:
        return 0.55
    if supporting_cluster_count == 1:
        return 0.2
    return 0.0


def load_leading_indicator_support(
    db: Session,
    dataset_id: int,
) -> tuple[int, list[LeadingIndicatorSupport]]:
    query = text(
        """
        SELECT
            COALESCE(acm.cluster_id, -a.id) AS target_cluster_id,
            a.id AS target_anomaly_id,
            a.dataset_id AS target_dataset_id,
            td.name AS target_dataset_name,
            a.timestamp AS target_timestamp,
            a.direction AS target_direction,
            a.detection_method AS target_detection_method,
            a.severity_score AS target_severity_score,
            COALESCE(ac.start_timestamp, a.timestamp) AS target_cluster_start_timestamp,
            COALESCE(ac.end_timestamp, a.timestamp) AS target_cluster_end_timestamp,
            COALESCE(ac.anomaly_count, 1) AS target_cluster_anomaly_count,
            COALESCE(ac.dataset_count, 1) AS target_cluster_dataset_count,
            COALESCE(ac.peak_severity_score, a.severity_score) AS target_cluster_peak_severity_score,
            td.frequency AS target_dataset_frequency,
            c.related_dataset_id,
            d.name AS related_dataset_name,
            d.frequency AS related_dataset_frequency,
            c.correlation_score,
            c.lag_days
        FROM anomalies AS a
        LEFT JOIN anomaly_cluster_members AS acm ON acm.anomaly_id = a.id
        LEFT JOIN anomaly_clusters AS ac ON ac.id = acm.cluster_id
        JOIN correlations AS c ON c.anomaly_id = a.id
        JOIN datasets AS td ON td.id = a.dataset_id
        JOIN datasets AS d ON d.id = c.related_dataset_id
        WHERE a.dataset_id = :dataset_id
          AND c.lag_days < 0
        ORDER BY
            COALESCE(acm.cluster_id, -a.id) ASC,
            c.related_dataset_id ASC,
            ABS(c.correlation_score) DESC,
            c.lag_days ASC
        """
    )
    rows = db.execute(query, {"dataset_id": dataset_id}).mappings().all()
    supports = [LeadingIndicatorSupport(**row) for row in rows]
    target_cluster_count = len({item.target_cluster_id for item in supports})
    if target_cluster_count == 0:
        cluster_count_query = text(
            """
            SELECT COUNT(DISTINCT COALESCE(acm.cluster_id, -a.id))
            FROM anomalies AS a
            LEFT JOIN anomaly_cluster_members AS acm ON acm.anomaly_id = a.id
            WHERE a.dataset_id = :dataset_id
            """
        )
        target_cluster_count = int(db.execute(cluster_count_query, {"dataset_id": dataset_id}).scalar_one() or 0)
    return target_cluster_count, supports


def collapse_support_by_cluster(
    supports: list[LeadingIndicatorSupport],
) -> list[LeadingIndicatorSupport]:
    strongest_by_cluster: dict[tuple[int, int], LeadingIndicatorSupport] = {}
    for support in supports:
        key = (support.target_cluster_id, support.related_dataset_id)
        existing = strongest_by_cluster.get(key)
        if existing is None or abs(support.correlation_score) > abs(existing.correlation_score):
            strongest_by_cluster[key] = support
    return list(strongest_by_cluster.values())


def aggregate_leading_indicators(
    supports: list[LeadingIndicatorSupport],
    *,
    target_cluster_count: int,
) -> list[LeadingIndicatorAggregate]:
    grouped: dict[int, list[LeadingIndicatorSupport]] = {}
    collapsed_support = collapse_support_by_cluster(supports)
    for support in collapsed_support:
        grouped.setdefault(support.related_dataset_id, []).append(support)

    aggregates: list[LeadingIndicatorAggregate] = []
    for related_dataset_id, items in grouped.items():
        supporting_cluster_count = len({item.target_cluster_id for item in items})
        cluster_coverage = (
            supporting_cluster_count / target_cluster_count if target_cluster_count > 0 else 0.0
        )
        positive_count = sum(1 for item in items if item.correlation_score >= 0)
        negative_count = len(items) - positive_count
        dominant_count = max(positive_count, negative_count)
        sign_consistency = dominant_count / len(items)
        dominant_direction = "positive" if positive_count >= negative_count else "negative"
        average_lead_days = round(sum(abs(item.lag_days) for item in items) / len(items))
        average_correlation_score = sum(item.correlation_score for item in items) / len(items)
        average_abs_correlation_score = sum(abs(item.correlation_score) for item in items) / len(items)
        strongest_correlation = max(items, key=lambda item: abs(item.correlation_score)).correlation_score
        frequency_alignment = compute_frequency_alignment(
            items[0].related_dataset_frequency,
            items[0].target_dataset_frequency,
        )
        support_confidence = compute_support_confidence(supporting_cluster_count)
        consistency_score = round(
            (cluster_coverage * 0.25)
            + (average_abs_correlation_score * 0.2)
            + (sign_consistency * 0.15)
            + (frequency_alignment * 0.1)
            + (support_confidence * 0.3),
            6,
        )
        aggregates.append(
            LeadingIndicatorAggregate(
                related_dataset_id=related_dataset_id,
                related_dataset_name=items[0].related_dataset_name,
                related_dataset_frequency=items[0].related_dataset_frequency,
                target_dataset_frequency=items[0].target_dataset_frequency,
                supporting_cluster_count=supporting_cluster_count,
                target_cluster_count=target_cluster_count,
                cluster_coverage=round(cluster_coverage, 6),
                average_lead_days=average_lead_days,
                average_correlation_score=round(average_correlation_score, 6),
                average_abs_correlation_score=round(average_abs_correlation_score, 6),
                strongest_correlation_score=round(strongest_correlation, 6),
                sign_consistency=round(sign_consistency, 6),
                dominant_direction=dominant_direction,
                frequency_alignment=round(frequency_alignment, 6),
                support_confidence=round(support_confidence, 6),
                consistency_score=consistency_score,
                supporting_episodes=sorted(
                    items,
                    key=lambda item: item.target_timestamp,
                    reverse=True,
                ),
            )
        )

    return sorted(
        aggregates,
        key=lambda item: (
            item.consistency_score,
            item.supporting_cluster_count,
            item.average_abs_correlation_score,
        ),
        reverse=True,
    )


def build_leading_indicators(
    db: Session,
    dataset_id: int,
    *,
    limit: int,
) -> list[LeadingIndicatorAggregate]:
    target_cluster_count, supports = load_leading_indicator_support(db, dataset_id)
    aggregates = aggregate_leading_indicators(supports, target_cluster_count=target_cluster_count)
    return aggregates[:limit]
