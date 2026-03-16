from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings


@dataclass(frozen=True)
class AnomalyClusterCandidate:
    anomaly_id: int
    dataset_id: int
    timestamp: datetime
    severity_score: float


@dataclass(frozen=True)
class ClusterPersistenceResult:
    cluster_count: int
    member_count: int


def load_cluster_candidates(db: Session) -> list[AnomalyClusterCandidate]:
    query = text(
        """
        SELECT id AS anomaly_id, dataset_id, timestamp, severity_score
        FROM anomalies
        ORDER BY timestamp ASC, severity_score DESC, id ASC
        """
    )
    rows = db.execute(query).mappings().all()
    return [AnomalyClusterCandidate(**row) for row in rows]


def build_anomaly_clusters(
    candidates: list[AnomalyClusterCandidate],
    *,
    window_days: int,
) -> list[list[AnomalyClusterCandidate]]:
    if not candidates:
        return []

    threshold = timedelta(days=window_days)
    clusters: list[list[AnomalyClusterCandidate]] = []
    current_cluster = [candidates[0]]

    for candidate in candidates[1:]:
        gap = candidate.timestamp - current_cluster[-1].timestamp
        if gap <= threshold:
            current_cluster.append(candidate)
            continue
        clusters.append(current_cluster)
        current_cluster = [candidate]

    clusters.append(current_cluster)
    return clusters


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
            anomaly_count,
            dataset_count,
            peak_severity_score
        )
        VALUES (
            :start_timestamp,
            :end_timestamp,
            :anchor_timestamp,
            :anomaly_count,
            :dataset_count,
            :peak_severity_score
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
        cluster_id = int(
            db.execute(
                insert_cluster_query,
                {
                    "start_timestamp": sorted_cluster[0].timestamp,
                    "end_timestamp": sorted_cluster[-1].timestamp,
                    "anchor_timestamp": anchor.timestamp,
                    "anomaly_count": len(cluster),
                    "dataset_count": len({item.dataset_id for item in cluster}),
                    "peak_severity_score": max(item.severity_score for item in cluster),
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
    clusters = build_anomaly_clusters(
        candidates,
        window_days=window_days if window_days is not None else settings.anomaly_cluster_window_days,
    )
    return replace_clusters(db, clusters)
