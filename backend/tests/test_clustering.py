from datetime import datetime, timezone

from app.services.clustering import (
    AnomalyClusterCandidate,
    build_anomaly_clusters,
    build_cluster_metadata,
    get_pair_window_days,
    should_merge_candidate,
)


def make_candidate(
    anomaly_id: int,
    dataset_id: int,
    year: int,
    month: int,
    day: int,
    severity: float,
    dataset_frequency: str = "daily",
) -> AnomalyClusterCandidate:
    return AnomalyClusterCandidate(
        anomaly_id=anomaly_id,
        dataset_id=dataset_id,
        dataset_frequency=dataset_frequency,
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


def test_build_anomaly_clusters_respects_frequency_aware_windows() -> None:
    clusters = build_anomaly_clusters(
        [
            make_candidate(1, 1, 2026, 3, 1, 2.8, dataset_frequency="monthly"),
            make_candidate(2, 2, 2026, 3, 20, 3.0, dataset_frequency="daily"),
            make_candidate(3, 3, 2026, 5, 1, 3.1, dataset_frequency="daily"),
        ],
        window_days=7,
    )

    assert len(clusters) == 3
    assert [item.anomaly_id for item in clusters[0]] == [1]
    assert [item.anomaly_id for item in clusters[1]] == [2]
    assert [item.anomaly_id for item in clusters[2]] == [3]


def test_pair_window_days_use_conservative_mixed_frequency_bridge() -> None:
    daily = make_candidate(1, 1, 2026, 3, 1, 2.8, dataset_frequency="daily")
    weekly = make_candidate(2, 2, 2026, 3, 1, 3.0, dataset_frequency="weekly")
    monthly = make_candidate(3, 3, 2026, 3, 1, 3.1, dataset_frequency="monthly")

    assert get_pair_window_days(daily, daily, base_window_days=7) == 7
    assert get_pair_window_days(weekly, weekly, base_window_days=7) == 14
    assert get_pair_window_days(monthly, monthly, base_window_days=7) == 35
    assert get_pair_window_days(daily, weekly, base_window_days=7) == 10
    assert get_pair_window_days(weekly, monthly, base_window_days=7) == 22
    assert get_pair_window_days(daily, monthly, base_window_days=7) == 16


def test_build_anomaly_clusters_splits_wide_daily_monthly_gap_under_new_rule() -> None:
    clusters = build_anomaly_clusters(
        [
            make_candidate(1, 1, 2026, 3, 1, 2.8, dataset_frequency="monthly"),
            make_candidate(2, 2, 2026, 3, 20, 3.0, dataset_frequency="daily"),
        ],
        window_days=7,
    )

    assert len(clusters) == 2
    assert [item.anomaly_id for item in clusters[0]] == [1]
    assert [item.anomaly_id for item in clusters[1]] == [2]


def test_build_anomaly_clusters_blocks_wide_cross_dataset_merge_without_relationship() -> None:
    clusters = build_anomaly_clusters(
        [
            make_candidate(1, 1, 2026, 3, 1, 2.8, dataset_frequency="monthly"),
            make_candidate(2, 2, 2026, 3, 13, 3.0, dataset_frequency="daily"),
        ],
        window_days=7,
        dataset_relationships={},
    )

    assert len(clusters) == 2
    assert [item.anomaly_id for item in clusters[0]] == [1]
    assert [item.anomaly_id for item in clusters[1]] == [2]


def test_build_anomaly_clusters_allows_wide_cross_dataset_merge_with_relationship() -> None:
    clusters = build_anomaly_clusters(
        [
            make_candidate(1, 1, 2026, 3, 1, 2.8, dataset_frequency="monthly"),
            make_candidate(2, 2, 2026, 3, 13, 3.0, dataset_frequency="daily"),
        ],
        window_days=7,
        dataset_relationships={1: {2}, 2: {1}},
    )

    assert len(clusters) == 1
    assert [item.anomaly_id for item in clusters[0]] == [1, 2]


def test_build_anomaly_clusters_keeps_weak_monthly_points_separate_without_relationship() -> None:
    clusters = build_anomaly_clusters(
        [
            make_candidate(1, 1, 2026, 3, 1, 2.8, dataset_frequency="monthly"),
            make_candidate(2, 2, 2026, 3, 20, 3.0, dataset_frequency="monthly"),
        ],
        window_days=7,
        dataset_relationships={},
    )

    assert len(clusters) == 2
    assert [item.anomaly_id for item in clusters[0]] == [1]
    assert [item.anomaly_id for item in clusters[1]] == [2]


def test_should_merge_candidate_keeps_tight_cross_dataset_events_without_relationship() -> None:
    cluster = [make_candidate(1, 1, 2026, 3, 1, 2.8, dataset_frequency="monthly")]
    candidate = make_candidate(2, 2, 2026, 3, 6, 3.0, dataset_frequency="daily")

    assert (
        should_merge_candidate(
            cluster,
            candidate,
            base_window_days=7,
            dataset_relationships={},
        )
        is True
    )


def test_should_merge_candidate_preserves_same_dataset_monthly_wave_without_relationship() -> None:
    cluster = [make_candidate(1, 1, 2026, 3, 1, 2.8, dataset_frequency="monthly")]
    candidate = make_candidate(2, 1, 2026, 3, 20, 3.0, dataset_frequency="monthly")

    assert (
        should_merge_candidate(
            cluster,
            candidate,
            base_window_days=7,
            dataset_relationships={},
        )
        is True
    )


def test_build_cluster_metadata_labels_sparse_and_broader_episodes() -> None:
    low_metadata = build_cluster_metadata(
        [make_candidate(1, 1, 2026, 3, 1, 3.2, dataset_frequency="monthly")]
    )
    assert low_metadata.span_days == 0
    assert low_metadata.frequency_mix == "monthly_only"
    assert low_metadata.episode_kind == "isolated_signal"
    assert low_metadata.quality_band == "low"

    high_metadata = build_cluster_metadata(
        [
            make_candidate(1, 1, 2026, 3, 1, 3.2, dataset_frequency="daily"),
            make_candidate(2, 2, 2026, 3, 2, 2.9, dataset_frequency="daily"),
            make_candidate(3, 3, 2026, 3, 4, 3.5, dataset_frequency="daily"),
            make_candidate(4, 4, 2026, 3, 6, 2.7, dataset_frequency="daily"),
        ]
    )
    assert high_metadata.frequency_mix == "daily_only"
    assert high_metadata.episode_kind == "cross_dataset_episode"
    assert high_metadata.quality_band == "high"
