from datetime import datetime, timezone

from app.services.propagation import (
    ClusterNode,
    PropagationEvidence,
    build_propagation_edge_score,
    get_propagation_tolerance_days,
)


def test_propagation_tolerance_days_are_frequency_aware() -> None:
    assert get_propagation_tolerance_days("daily") == 7
    assert get_propagation_tolerance_days("weekly") == 14
    assert get_propagation_tolerance_days("monthly") == 21


def test_propagation_edge_score_exposes_components_conservatively() -> None:
    components = build_propagation_edge_score(
        [
            PropagationEvidence(
                source_anomaly_id=1,
                source_dataset_name="Bitcoin Price",
                source_timestamp=datetime(2026, 2, 6, tzinfo=timezone.utc),
                target_anomaly_id=2,
                target_dataset_id=10,
                target_dataset_name="S&P 500 Index",
                target_timestamp=datetime(2026, 2, 16, tzinfo=timezone.utc),
                correlation_score=0.66,
                lag_days=10,
                method="pearson_pct_change",
                match_gap_days=0.0,
                tolerance_days=7,
            )
        ],
        source_cluster=ClusterNode(
            cluster_id=1,
            start_timestamp=datetime(2026, 2, 6, tzinfo=timezone.utc),
            end_timestamp=datetime(2026, 2, 6, tzinfo=timezone.utc),
            anchor_timestamp=datetime(2026, 2, 6, tzinfo=timezone.utc),
            span_days=0,
            anomaly_count=1,
            dataset_count=1,
            peak_severity_score=3.24,
            frequency_mix="daily_only",
            episode_kind="isolated_signal",
            quality_band="low",
        ),
        target_cluster=ClusterNode(
            cluster_id=2,
            start_timestamp=datetime(2026, 2, 16, tzinfo=timezone.utc),
            end_timestamp=datetime(2026, 2, 16, tzinfo=timezone.utc),
            anchor_timestamp=datetime(2026, 2, 16, tzinfo=timezone.utc),
            span_days=0,
            anomaly_count=1,
            dataset_count=1,
            peak_severity_score=2.91,
            frequency_mix="daily_only",
            episode_kind="isolated_signal",
            quality_band="low",
        ),
    )

    assert components["correlation_strength"] == 0.66
    assert components["support_density"] == 0.5
    assert components["temporal_alignment"] == 1.0
    assert components["target_scale"] == round(1 / 3, 3)
    assert components["episode_quality"] == 0.8
    assert components["overall"] == 0.677
