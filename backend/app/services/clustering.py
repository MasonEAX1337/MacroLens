import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from math import sqrt

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings


@dataclass(frozen=True)
class AnomalyClusterCandidate:
    anomaly_id: int
    dataset_id: int
    dataset_symbol: str
    dataset_frequency: str
    timestamp: datetime
    severity_score: float
    detection_method: str
    metadata: dict[str, object]


@dataclass(frozen=True)
class ClusterPersistenceResult:
    cluster_count: int
    member_count: int


@dataclass(frozen=True)
class ClusterMetadata:
    span_days: int
    frequency_mix: str
    episode_kind: str
    quality_band: str


@dataclass(frozen=True)
class MonthlyEpisodeSuppressionRule:
    min_abs_delta_mean: float | None = None
    min_abs_transformed_value: float | None = None


DatasetRelationshipMap = dict[int, set[int]]

MONTHLY_EPISODE_SUPPRESSION_RULES: dict[str, MonthlyEpisodeSuppressionRule] = {
    "CPIAUCSL": MonthlyEpisodeSuppressionRule(
        min_abs_delta_mean=0.0018,
        min_abs_transformed_value=0.0006,
    ),
    "CSUSHPISA": MonthlyEpisodeSuppressionRule(
        min_abs_transformed_value=0.0029,
    ),
}


FREQUENCY_WINDOW_MULTIPLIERS = {
    "daily": 1,
    "weekly": 2,
    "monthly": 5,
}


def normalize_frequency(frequency: str) -> str:
    normalized = frequency.strip().lower()
    if normalized in FREQUENCY_WINDOW_MULTIPLIERS:
        return normalized
    return "daily"


def get_frequency_aware_window_days(frequency: str, base_window_days: int) -> int:
    multiplier = FREQUENCY_WINDOW_MULTIPLIERS.get(normalize_frequency(frequency), 1)
    return max(base_window_days, base_window_days * multiplier)


def get_pair_window_days(
    left: AnomalyClusterCandidate,
    right: AnomalyClusterCandidate,
    *,
    base_window_days: int,
) -> int:
    left_multiplier = FREQUENCY_WINDOW_MULTIPLIERS.get(normalize_frequency(left.dataset_frequency), 1)
    right_multiplier = FREQUENCY_WINDOW_MULTIPLIERS.get(normalize_frequency(right.dataset_frequency), 1)
    if left_multiplier == right_multiplier:
        return get_frequency_aware_window_days(left.dataset_frequency, base_window_days)

    pair_multiplier = sqrt(left_multiplier * right_multiplier)
    return max(
        base_window_days,
        round(base_window_days * pair_multiplier),
    )


def classify_frequency_mix(candidates: list[AnomalyClusterCandidate]) -> str:
    frequencies = sorted({normalize_frequency(item.dataset_frequency) for item in candidates})
    if len(frequencies) == 1:
        return f"{frequencies[0]}_only"
    return "mixed"


def classify_episode_kind(
    candidates: list[AnomalyClusterCandidate],
) -> str:
    anomaly_count = len(candidates)
    dataset_count = len({item.dataset_id for item in candidates})

    if anomaly_count == 1:
        return "isolated_signal"
    if dataset_count == 1:
        return "single_dataset_wave"
    return "cross_dataset_episode"


def classify_quality_band(
    candidates: list[AnomalyClusterCandidate],
    *,
    span_days: int,
) -> str:
    anomaly_count = len(candidates)
    dataset_count = len({item.dataset_id for item in candidates})
    frequency_mix = classify_frequency_mix(candidates)

    if anomaly_count == 1:
        return "low"
    if dataset_count >= 3 or (dataset_count >= 2 and anomaly_count >= 4):
        return "high" if frequency_mix != "mixed" or span_days <= 35 else "medium"
    if dataset_count >= 2 or anomaly_count >= 3:
        return "medium"
    return "low"


def build_cluster_metadata(candidates: list[AnomalyClusterCandidate]) -> ClusterMetadata:
    sorted_candidates = sorted(candidates, key=lambda item: (item.timestamp, -item.severity_score, item.anomaly_id))
    span_days = round(
        max(
            0.0,
            (sorted_candidates[-1].timestamp - sorted_candidates[0].timestamp).total_seconds() / 86400.0,
        )
    )
    frequency_mix = classify_frequency_mix(sorted_candidates)
    episode_kind = classify_episode_kind(sorted_candidates)
    quality_band = classify_quality_band(sorted_candidates, span_days=span_days)
    return ClusterMetadata(
        span_days=span_days,
        frequency_mix=frequency_mix,
        episode_kind=episode_kind,
        quality_band=quality_band,
    )


def load_cluster_candidates(db: Session) -> list[AnomalyClusterCandidate]:
    query = text(
        """
        SELECT
            a.id AS anomaly_id,
            a.dataset_id,
            d.symbol AS dataset_symbol,
            d.frequency AS dataset_frequency,
            a.timestamp,
            a.severity_score,
            a.detection_method,
            a.metadata
        FROM anomalies AS a
        JOIN datasets AS d ON d.id = a.dataset_id
        ORDER BY a.timestamp ASC, a.severity_score DESC, a.id ASC
        """
    )
    rows = db.execute(query).mappings().all()
    return [AnomalyClusterCandidate(**row) for row in rows]


def load_dataset_relationships(db: Session) -> DatasetRelationshipMap:
    query = text(
        """
        SELECT DISTINCT
            source_anomalies.dataset_id AS source_dataset_id,
            correlations.related_dataset_id
        FROM correlations
        JOIN anomalies AS source_anomalies ON source_anomalies.id = correlations.anomaly_id
        """
    )
    rows = db.execute(query).mappings().all()
    relationships: DatasetRelationshipMap = {}
    for row in rows:
        source_dataset_id = int(row["source_dataset_id"])
        related_dataset_id = int(row["related_dataset_id"])
        relationships.setdefault(source_dataset_id, set()).add(related_dataset_id)
        relationships.setdefault(related_dataset_id, set()).add(source_dataset_id)
    return relationships


def cluster_has_relationship_to_candidate(
    cluster: list[AnomalyClusterCandidate],
    candidate: AnomalyClusterCandidate,
    dataset_relationships: DatasetRelationshipMap,
) -> bool:
    related_dataset_ids = dataset_relationships.get(candidate.dataset_id, set())
    return any(item.dataset_id in related_dataset_ids for item in cluster)


def should_merge_candidate(
    cluster: list[AnomalyClusterCandidate],
    candidate: AnomalyClusterCandidate,
    *,
    base_window_days: int,
    dataset_relationships: DatasetRelationshipMap | None = None,
) -> bool:
    previous = cluster[-1]
    gap = candidate.timestamp - previous.timestamp
    threshold = timedelta(
        days=get_pair_window_days(previous, candidate, base_window_days=base_window_days)
    )
    if gap > threshold:
        return False

    cluster_dataset_ids = {item.dataset_id for item in cluster}
    if candidate.dataset_id in cluster_dataset_ids:
        return True

    if gap <= timedelta(days=base_window_days):
        return True

    if not dataset_relationships:
        return False

    return cluster_has_relationship_to_candidate(cluster, candidate, dataset_relationships)


def build_anomaly_clusters(
    candidates: list[AnomalyClusterCandidate],
    *,
    window_days: int,
    dataset_relationships: DatasetRelationshipMap | None = None,
) -> list[list[AnomalyClusterCandidate]]:
    if not candidates:
        return []

    clusters: list[list[AnomalyClusterCandidate]] = []
    current_cluster = [candidates[0]]

    for candidate in candidates[1:]:
        if should_merge_candidate(
            current_cluster,
            candidate,
            base_window_days=window_days,
            dataset_relationships=dataset_relationships,
        ):
            current_cluster.append(candidate)
            continue
        clusters.append(current_cluster)
        current_cluster = [candidate]

    clusters.append(current_cluster)
    return clusters


def candidate_matches_monthly_episode_filter_target(candidate: AnomalyClusterCandidate) -> bool:
    metadata = candidate.metadata or {}
    return (
        candidate.detection_method == "change_point"
        and candidate.dataset_symbol in MONTHLY_EPISODE_SUPPRESSION_RULES
        and str(metadata.get("transform", "")) == "percent_change"
    )


def candidate_is_weak_monthly_change_point(candidate: AnomalyClusterCandidate) -> bool:
    if not candidate_matches_monthly_episode_filter_target(candidate):
        return False

    rule = MONTHLY_EPISODE_SUPPRESSION_RULES[candidate.dataset_symbol]
    metadata = candidate.metadata or {}
    delta_mean = abs(float(metadata.get("delta_mean", 0.0)))
    transformed_value = abs(float(metadata.get("transformed_value", 0.0)))

    if rule.min_abs_delta_mean is not None and delta_mean < rule.min_abs_delta_mean:
        return True
    if (
        rule.min_abs_transformed_value is not None
        and transformed_value < rule.min_abs_transformed_value
    ):
        return True
    return False


def select_suppressed_anomaly_ids(
    provisional_clusters: list[list[AnomalyClusterCandidate]],
) -> set[int]:
    suppressed: set[int] = set()
    for cluster in provisional_clusters:
        metadata = build_cluster_metadata(cluster)
        if metadata.episode_kind == "cross_dataset_episode":
            continue
        for candidate in cluster:
            if candidate_is_weak_monthly_change_point(candidate):
                suppressed.add(candidate.anomaly_id)
    return suppressed


def replace_episode_filter_metadata(
    db: Session,
    candidates: list[AnomalyClusterCandidate],
    suppressed_anomaly_ids: set[int],
) -> None:
    target_candidates = [
        candidate for candidate in candidates if candidate_matches_monthly_episode_filter_target(candidate)
    ]
    if not target_candidates:
        return

    update_query = text(
        """
        UPDATE anomalies
        SET metadata = (
            COALESCE(metadata, '{}'::jsonb)
            - 'episode_filter_status'
            - 'episode_filter_reason'
            - 'episode_filter_stage'
        ) || CAST(:metadata_patch AS JSONB)
        WHERE id = :anomaly_id
        """
    )
    payload = []
    for candidate in target_candidates:
        patch: dict[str, object] = {
            "episode_filter_status": "suppressed" if candidate.anomaly_id in suppressed_anomaly_ids else "eligible",
            "episode_filter_stage": "post_provisional_clustering",
        }
        if candidate.anomaly_id in suppressed_anomaly_ids:
            patch["episode_filter_reason"] = "weak_monthly_isolated_change_point"
        payload.append(
            {
                "anomaly_id": candidate.anomaly_id,
                "metadata_patch": json.dumps(patch),
            }
        )
    db.execute(update_query, payload)


def replace_clusters(
    db: Session,
    clusters: list[list[AnomalyClusterCandidate]],
) -> ClusterPersistenceResult:
    db.execute(text("DELETE FROM anomaly_cluster_members"))
    db.execute(text("DELETE FROM anomaly_clusters"))

    cluster_count = 0
    member_count = 0

    insert_cluster_query = text(
        """
        INSERT INTO anomaly_clusters (
            start_timestamp,
            end_timestamp,
            anchor_timestamp,
            span_days,
            anomaly_count,
            dataset_count,
            peak_severity_score,
            frequency_mix,
            episode_kind,
            quality_band
        )
        VALUES (
            :start_timestamp,
            :end_timestamp,
            :anchor_timestamp,
            :span_days,
            :anomaly_count,
            :dataset_count,
            :peak_severity_score,
            :frequency_mix,
            :episode_kind,
            :quality_band
        )
        RETURNING id
        """
    )
    insert_member_query = text(
        """
        INSERT INTO anomaly_cluster_members (cluster_id, anomaly_id, membership_rank)
        VALUES (:cluster_id, :anomaly_id, :membership_rank)
        """
    )

    for cluster in clusters:
        sorted_cluster = sorted(cluster, key=lambda item: (item.timestamp, -item.severity_score, item.anomaly_id))
        anchor = max(cluster, key=lambda item: (item.severity_score, -item.timestamp.timestamp(), -item.anomaly_id))
        metadata = build_cluster_metadata(sorted_cluster)
        cluster_id = int(
            db.execute(
                insert_cluster_query,
                {
                    "start_timestamp": sorted_cluster[0].timestamp,
                    "end_timestamp": sorted_cluster[-1].timestamp,
                    "anchor_timestamp": anchor.timestamp,
                    "span_days": metadata.span_days,
                    "anomaly_count": len(cluster),
                    "dataset_count": len({item.dataset_id for item in cluster}),
                    "peak_severity_score": max(item.severity_score for item in cluster),
                    "frequency_mix": metadata.frequency_mix,
                    "episode_kind": metadata.episode_kind,
                    "quality_band": metadata.quality_band,
                },
            ).scalar_one()
        )
        cluster_count += 1

        db.execute(
            insert_member_query,
            [
                {
                    "cluster_id": cluster_id,
                    "anomaly_id": item.anomaly_id,
                    "membership_rank": index,
                }
                for index, item in enumerate(sorted_cluster, start=1)
            ],
        )
        member_count += len(cluster)

    return ClusterPersistenceResult(cluster_count=cluster_count, member_count=member_count)


def run_clustering_for_all_anomalies(
    db: Session,
    *,
    window_days: int | None = None,
) -> ClusterPersistenceResult:
    candidates = load_cluster_candidates(db)
    dataset_relationships = load_dataset_relationships(db)
    base_window_days = window_days if window_days is not None else settings.anomaly_cluster_window_days
    provisional_clusters = build_anomaly_clusters(
        candidates,
        window_days=base_window_days,
        dataset_relationships=dataset_relationships,
    )
    suppressed_anomaly_ids = select_suppressed_anomaly_ids(provisional_clusters)
    replace_episode_filter_metadata(db, candidates, suppressed_anomaly_ids)
    final_candidates = [candidate for candidate in candidates if candidate.anomaly_id not in suppressed_anomaly_ids]
    final_clusters = build_anomaly_clusters(
        final_candidates,
        window_days=base_window_days,
        dataset_relationships=dataset_relationships,
    )
    return replace_clusters(db, final_clusters)
