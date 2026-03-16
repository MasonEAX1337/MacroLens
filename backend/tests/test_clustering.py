from datetime import datetime, timezone

from app.services.clustering import AnomalyClusterCandidate, build_anomaly_clusters


def make_candidate(anomaly_id: int, dataset_id: int, year: int, month: int, day: int, severity: float) -> AnomalyClusterCandidate:
    return AnomalyClusterCandidate(
        anomaly_id=anomaly_id,
        dataset_id=dataset_id,
        timestamp=datetime(year, month, day, tzinfo=timezone.utc),
        severity_score=severity,
    )


def test_build_anomaly_clusters_groups_events_within_window() -> None:
    clusters = build_anomaly_clusters(
        [
            make_candidate(1, 1, 2026, 3, 1, 3.2),
            make_candidate(2, 2, 2026, 3, 4, 2.9),
            make_candidate(3, 3, 2026, 3, 12, 3.5),
        ],
        window_days=7,
    )

    assert len(clusters) == 2
    assert [item.anomaly_id for item in clusters[0]] == [1, 2]
    assert [item.anomaly_id for item in clusters[1]] == [3]


def test_build_anomaly_clusters_uses_transitive_time_connectivity() -> None:
    clusters = build_anomaly_clusters(
        [
            make_candidate(1, 1, 2026, 3, 1, 3.2),
            make_candidate(2, 2, 2026, 3, 7, 2.9),
            make_candidate(3, 3, 2026, 3, 13, 3.5),
        ],
        window_days=7,
    )

    assert len(clusters) == 1
    assert [item.anomaly_id for item in clusters[0]] == [1, 2, 3]
