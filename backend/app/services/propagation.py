from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class ClusterNode:
    cluster_id: int
    start_timestamp: datetime
    end_timestamp: datetime
    anchor_timestamp: datetime
    anomaly_count: int
    dataset_count: int
    peak_severity_score: float


@dataclass(frozen=True)
class SourceCorrelationCandidate:
    source_anomaly_id: int
    source_dataset_id: int
    source_dataset_name: str
    source_timestamp: datetime
    related_dataset_id: int
    related_dataset_name: str
    related_dataset_frequency: str
    correlation_score: float
    lag_days: int
    method: str


@dataclass(frozen=True)
class TargetAnomalyCandidate:
    anomaly_id: int
    dataset_id: int
    dataset_name: str
    dataset_frequency: str
    timestamp: datetime
    severity_score: float
    direction: str | None
    detection_method: str
    cluster_id: int
    cluster_start_timestamp: datetime
    cluster_end_timestamp: datetime
    cluster_anchor_timestamp: datetime
    cluster_anomaly_count: int
    cluster_dataset_count: int
    cluster_peak_severity_score: float


@dataclass(frozen=True)
class PropagationEvidence:
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


def build_propagation_edge_score(
    evidence_items: list[PropagationEvidence],
    *,
    source_cluster: ClusterNode,
    target_cluster: ClusterNode,
) -> dict[str, float]:
    if not evidence_items:
        return {
            "correlation_strength": 0.0,
            "support_density": 0.0,
            "temporal_alignment": 0.0,
            "target_scale": 0.0,
            "overall": 0.0,
        }

    correlation_strength = min(1.0, max(abs(item.correlation_score) for item in evidence_items))
    temporal_alignment = sum(
        max(0.0, 1.0 - (item.match_gap_days / max(1, item.tolerance_days)))
        for item in evidence_items
    ) / len(evidence_items)
    unique_source_anomalies = len({item.source_anomaly_id for item in evidence_items})
    support_density = min(
        1.0,
        unique_source_anomalies / max(2, min(source_cluster.anomaly_count, 4)),
    )
    target_scale = min(1.0, target_cluster.dataset_count / 3.0)
    overall = (
        (0.45 * correlation_strength)
        + (0.25 * support_density)
        + (0.20 * temporal_alignment)
        + (0.10 * target_scale)
    )
    return {
        "correlation_strength": round(correlation_strength, 3),
        "support_density": round(support_density, 3),
        "temporal_alignment": round(temporal_alignment, 3),
        "target_scale": round(target_scale, 3),
        "overall": round(overall, 3),
    }


def get_propagation_tolerance_days(frequency: str) -> int:
    normalized = frequency.strip().lower()
    if normalized == "monthly":
        return 21
    if normalized == "weekly":
        return 14
    return 7


def load_cluster_node(db: Session, cluster_id: int) -> ClusterNode | None:
    query = text(
        """
        SELECT
            id AS cluster_id,
            start_timestamp,
            end_timestamp,
            anchor_timestamp,
            anomaly_count,
            dataset_count,
            peak_severity_score
        FROM anomaly_clusters
        WHERE id = :cluster_id
        """
    )
    row = db.execute(query, {"cluster_id": cluster_id}).mappings().first()
    if row is None:
        return None
    return ClusterNode(**row)


def load_source_correlation_candidates(db: Session, cluster_id: int) -> list[SourceCorrelationCandidate]:
    query = text(
        """
        SELECT
            a.id AS source_anomaly_id,
            a.dataset_id AS source_dataset_id,
            d.name AS source_dataset_name,
            a.timestamp AS source_timestamp,
            c.related_dataset_id,
            rd.name AS related_dataset_name,
            rd.frequency AS related_dataset_frequency,
            c.correlation_score,
            c.lag_days,
            c.method
        FROM anomaly_cluster_members AS acm
        JOIN anomalies AS a ON a.id = acm.anomaly_id
        JOIN datasets AS d ON d.id = a.dataset_id
        JOIN correlations AS c ON c.anomaly_id = a.id
        JOIN datasets AS rd ON rd.id = c.related_dataset_id
        WHERE acm.cluster_id = :cluster_id
          AND c.lag_days > 0
        ORDER BY a.timestamp ASC, ABS(c.correlation_score) DESC, c.related_dataset_id ASC
        """
    )
    rows = db.execute(query, {"cluster_id": cluster_id}).mappings().all()
    return [SourceCorrelationCandidate(**row) for row in rows]


def load_target_anomaly_candidates(
    db: Session,
) -> tuple[dict[int, list[TargetAnomalyCandidate]], dict[int, list[TargetAnomalyCandidate]]]:
    query = text(
        """
        SELECT
            a.id AS anomaly_id,
            a.dataset_id,
            d.name AS dataset_name,
            d.frequency AS dataset_frequency,
            a.timestamp,
            a.severity_score,
            a.direction,
            a.detection_method,
            ac.id AS cluster_id,
            ac.start_timestamp AS cluster_start_timestamp,
            ac.end_timestamp AS cluster_end_timestamp,
            ac.anchor_timestamp AS cluster_anchor_timestamp,
            ac.anomaly_count AS cluster_anomaly_count,
            ac.dataset_count AS cluster_dataset_count,
            ac.peak_severity_score AS cluster_peak_severity_score
        FROM anomalies AS a
        JOIN datasets AS d ON d.id = a.dataset_id
        JOIN anomaly_cluster_members AS acm ON acm.anomaly_id = a.id
        JOIN anomaly_clusters AS ac ON ac.id = acm.cluster_id
        ORDER BY a.dataset_id ASC, a.timestamp ASC, a.id ASC
        """
    )
    rows = db.execute(query).mappings().all()
    grouped_by_dataset: dict[int, list[TargetAnomalyCandidate]] = {}
    grouped_by_cluster: dict[int, list[TargetAnomalyCandidate]] = {}
    for row in rows:
        candidate = TargetAnomalyCandidate(**row)
        grouped_by_dataset.setdefault(candidate.dataset_id, []).append(candidate)
        grouped_by_cluster.setdefault(candidate.cluster_id, []).append(candidate)
    return grouped_by_dataset, grouped_by_cluster


def select_cluster_anchor_anomaly_id(cluster_members: list[TargetAnomalyCandidate], anchor_timestamp: datetime) -> int:
    anchor_member = min(
        cluster_members,
        key=lambda item: (
            abs((item.timestamp - anchor_timestamp).total_seconds()),
            -item.severity_score,
            item.anomaly_id,
        ),
    )
    return anchor_member.anomaly_id


def pick_best_target_match(
    source: SourceCorrelationCandidate,
    target_candidates: list[TargetAnomalyCandidate],
    *,
    source_cluster_id: int,
) -> tuple[TargetAnomalyCandidate, float] | None:
    expected_timestamp = source.source_timestamp + timedelta(days=source.lag_days)
    tolerance_days = get_propagation_tolerance_days(source.related_dataset_frequency)
    best_match: tuple[TargetAnomalyCandidate, float] | None = None

    for target in target_candidates:
        if target.cluster_id == source_cluster_id:
            continue
        if target.timestamp < source.source_timestamp:
            continue
        gap_days = abs((target.timestamp - expected_timestamp).total_seconds()) / 86400.0
        if gap_days > tolerance_days:
            continue
        match_key = (
            gap_days,
            -abs(source.correlation_score),
            -target.severity_score,
            target.anomaly_id,
        )
        if best_match is None or match_key < (
            best_match[1],
            -abs(source.correlation_score),
            -best_match[0].severity_score,
            best_match[0].anomaly_id,
        ):
            best_match = (target, gap_days)

    return best_match


def build_propagation_timeline(
    db: Session,
    cluster_id: int,
    *,
    max_edges: int = 6,
    max_evidence_per_edge: int = 3,
) -> list[dict[str, object]]:
    source_cluster = load_cluster_node(db, cluster_id)
    if source_cluster is None:
        return []

    source_candidates = load_source_correlation_candidates(db, cluster_id)
    if not source_candidates:
        return []

    target_candidates_by_dataset, target_candidates_by_cluster = load_target_anomaly_candidates(db)
    edge_evidence: dict[int, list[PropagationEvidence]] = {}
    target_cluster_nodes: dict[int, ClusterNode] = {}

    for source in source_candidates:
        target_candidates = target_candidates_by_dataset.get(source.related_dataset_id, [])
        tolerance_days = get_propagation_tolerance_days(source.related_dataset_frequency)
        best_match = pick_best_target_match(
            source,
            target_candidates,
            source_cluster_id=cluster_id,
        )
        if best_match is None:
            continue

        target, gap_days = best_match
        edge_evidence.setdefault(target.cluster_id, []).append(
            PropagationEvidence(
                source_anomaly_id=source.source_anomaly_id,
                source_dataset_name=source.source_dataset_name,
                source_timestamp=source.source_timestamp,
                target_anomaly_id=target.anomaly_id,
                target_dataset_id=target.dataset_id,
                target_dataset_name=target.dataset_name,
                target_timestamp=target.timestamp,
                correlation_score=source.correlation_score,
                lag_days=source.lag_days,
                method=source.method,
                match_gap_days=gap_days,
                tolerance_days=tolerance_days,
            )
        )
        target_cluster_nodes[target.cluster_id] = ClusterNode(
            cluster_id=target.cluster_id,
            start_timestamp=target.cluster_start_timestamp,
            end_timestamp=target.cluster_end_timestamp,
            anchor_timestamp=target.cluster_anchor_timestamp,
            anomaly_count=target.cluster_anomaly_count,
            dataset_count=target.cluster_dataset_count,
            peak_severity_score=target.cluster_peak_severity_score,
        )

    edges: list[dict[str, object]] = []
    for target_cluster_id, evidence_items in edge_evidence.items():
        target_cluster = target_cluster_nodes[target_cluster_id]
        sorted_evidence = sorted(
            evidence_items,
            key=lambda item: (item.target_timestamp, -abs(item.correlation_score), item.target_anomaly_id),
        )
        strongest_item = max(sorted_evidence, key=lambda item: abs(item.correlation_score))
        evidence_strength_components = build_propagation_edge_score(
            sorted_evidence,
            source_cluster=source_cluster,
            target_cluster=target_cluster,
        )
        target_anchor_anomaly_id = select_cluster_anchor_anomaly_id(
            target_candidates_by_cluster[target_cluster_id],
            target_cluster.anchor_timestamp,
        )
        edges.append(
            {
                "source_cluster_id": cluster_id,
                "target_cluster_id": target_cluster_id,
                "target_start_timestamp": target_cluster.start_timestamp,
                "target_end_timestamp": target_cluster.end_timestamp,
                "target_anchor_timestamp": target_cluster.anchor_timestamp,
                "target_anchor_anomaly_id": target_anchor_anomaly_id,
                "target_anchor_dataset_id": next(
                    item.dataset_id
                    for item in target_candidates_by_cluster[target_cluster_id]
                    if item.anomaly_id == target_anchor_anomaly_id
                ),
                "target_anomaly_count": target_cluster.anomaly_count,
                "target_dataset_count": target_cluster.dataset_count,
                "target_peak_severity_score": target_cluster.peak_severity_score,
                "average_lag_days": round(sum(item.lag_days for item in sorted_evidence) / len(sorted_evidence)),
                "strongest_correlation_score": round(strongest_item.correlation_score, 3),
                "supporting_link_count": len(sorted_evidence),
                "evidence_strength": evidence_strength_components["overall"],
                "evidence_strength_components": evidence_strength_components,
                "source_dataset_names": sorted({item.source_dataset_name for item in sorted_evidence}),
                "target_dataset_names": sorted({item.target_dataset_name for item in sorted_evidence}),
                "evidence": [
                    {
                        "source_anomaly_id": item.source_anomaly_id,
                        "source_dataset_name": item.source_dataset_name,
                        "source_timestamp": item.source_timestamp,
                        "target_anomaly_id": item.target_anomaly_id,
                        "target_dataset_id": item.target_dataset_id,
                        "target_dataset_name": item.target_dataset_name,
                        "target_timestamp": item.target_timestamp,
                        "correlation_score": item.correlation_score,
                        "lag_days": item.lag_days,
                        "method": item.method,
                        "match_gap_days": round(item.match_gap_days, 3),
                        "tolerance_days": item.tolerance_days,
                    }
                    for item in sorted_evidence[:max_evidence_per_edge]
                ],
            }
        )

    return sorted(
        edges,
        key=lambda item: (
            item["target_start_timestamp"],
            -float(item["evidence_strength"]),
            -int(item["supporting_link_count"]),
        ),
    )[:max_edges]
