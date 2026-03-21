from datetime import datetime, timezone

from app.services.leading_indicators import (
    LeadingIndicatorSupport,
    aggregate_leading_indicators,
    collapse_support_by_cluster,
    compute_frequency_alignment,
    compute_support_confidence,
)


def make_support(
    *,
    target_cluster_id: int,
    target_anomaly_id: int,
    target_timestamp: datetime,
    target_cluster_start_timestamp: datetime,
    target_cluster_end_timestamp: datetime,
    target_cluster_anomaly_count: int,
    target_cluster_dataset_count: int,
    target_cluster_peak_severity_score: float,
    related_dataset_id: int,
    related_dataset_name: str,
    related_dataset_frequency: str,
    correlation_score: float,
    lag_days: int,
    target_direction: str = "up",
    target_detection_method: str = "z_score",
    target_severity_score: float = 3.1,
    target_dataset_id: int = 1,
    target_dataset_name: str = "Consumer Price Index",
    target_dataset_frequency: str = "monthly",
    target_cluster_frequency_mix: str = "monthly_only",
    target_cluster_episode_kind: str = "isolated_signal",
    target_cluster_quality_band: str = "low",
) -> LeadingIndicatorSupport:
    span_days = round(
        max(
            0.0,
            (target_cluster_end_timestamp - target_cluster_start_timestamp).total_seconds() / 86400.0,
        )
    )
    return LeadingIndicatorSupport(
        target_cluster_id=target_cluster_id,
        target_anomaly_id=target_anomaly_id,
        target_dataset_id=target_dataset_id,
        target_dataset_name=target_dataset_name,
        target_timestamp=target_timestamp,
        target_direction=target_direction,
        target_detection_method=target_detection_method,
        target_severity_score=target_severity_score,
        target_cluster_start_timestamp=target_cluster_start_timestamp,
        target_cluster_end_timestamp=target_cluster_end_timestamp,
        target_cluster_span_days=span_days,
        target_cluster_anomaly_count=target_cluster_anomaly_count,
        target_cluster_dataset_count=target_cluster_dataset_count,
        target_cluster_peak_severity_score=target_cluster_peak_severity_score,
        target_cluster_frequency_mix=target_cluster_frequency_mix,
        target_cluster_episode_kind=target_cluster_episode_kind,
        target_cluster_quality_band=target_cluster_quality_band,
        target_dataset_frequency=target_dataset_frequency,
        related_dataset_id=related_dataset_id,
        related_dataset_name=related_dataset_name,
        related_dataset_frequency=related_dataset_frequency,
        correlation_score=correlation_score,
        lag_days=lag_days,
    )


def test_collapse_support_by_cluster_keeps_strongest_correlation_per_target_cluster() -> None:
    collapsed = collapse_support_by_cluster(
        [
            make_support(
                target_cluster_id=10,
                target_anomaly_id=100,
                target_timestamp=datetime(2025, 1, 15, tzinfo=timezone.utc),
                target_cluster_start_timestamp=datetime(2025, 1, 15, tzinfo=timezone.utc),
                target_cluster_end_timestamp=datetime(2025, 1, 18, tzinfo=timezone.utc),
                target_cluster_anomaly_count=2,
                target_cluster_dataset_count=1,
                target_cluster_peak_severity_score=3.2,
                target_cluster_episode_kind="single_dataset_wave",
                related_dataset_id=2,
                related_dataset_name="WTI Oil Price",
                related_dataset_frequency="daily",
                correlation_score=0.61,
                lag_days=-20,
            ),
            make_support(
                target_cluster_id=10,
                target_anomaly_id=101,
                target_timestamp=datetime(2025, 1, 16, tzinfo=timezone.utc),
                target_cluster_start_timestamp=datetime(2025, 1, 15, tzinfo=timezone.utc),
                target_cluster_end_timestamp=datetime(2025, 1, 18, tzinfo=timezone.utc),
                target_cluster_anomaly_count=2,
                target_cluster_dataset_count=1,
                target_cluster_peak_severity_score=3.2,
                target_cluster_episode_kind="single_dataset_wave",
                target_detection_method="change_point",
                target_severity_score=2.8,
                related_dataset_id=2,
                related_dataset_name="WTI Oil Price",
                related_dataset_frequency="daily",
                correlation_score=0.82,
                lag_days=-18,
            ),
        ]
    )

    assert len(collapsed) == 1
    assert collapsed[0].correlation_score == 0.82
    assert collapsed[0].lag_days == -18
    assert collapsed[0].target_anomaly_id == 101
    assert collapsed[0].target_cluster_episode_kind == "single_dataset_wave"


def test_aggregate_leading_indicators_ranks_by_coverage_and_strength() -> None:
    aggregates = aggregate_leading_indicators(
        [
            make_support(
                target_cluster_id=1,
                target_anomaly_id=100,
                target_timestamp=datetime(2025, 1, 15, tzinfo=timezone.utc),
                target_cluster_start_timestamp=datetime(2025, 1, 15, tzinfo=timezone.utc),
                target_cluster_end_timestamp=datetime(2025, 1, 15, tzinfo=timezone.utc),
                target_cluster_anomaly_count=1,
                target_cluster_dataset_count=1,
                target_cluster_peak_severity_score=3.1,
                related_dataset_id=2,
                related_dataset_name="WTI Oil Price",
                related_dataset_frequency="daily",
                correlation_score=0.72,
                lag_days=-20,
            ),
            make_support(
                target_cluster_id=2,
                target_anomaly_id=101,
                target_timestamp=datetime(2025, 4, 15, tzinfo=timezone.utc),
                target_cluster_start_timestamp=datetime(2025, 4, 15, tzinfo=timezone.utc),
                target_cluster_end_timestamp=datetime(2025, 4, 18, tzinfo=timezone.utc),
                target_cluster_anomaly_count=2,
                target_cluster_dataset_count=1,
                target_cluster_peak_severity_score=3.0,
                target_cluster_episode_kind="single_dataset_wave",
                related_dataset_id=2,
                related_dataset_name="WTI Oil Price",
                related_dataset_frequency="daily",
                correlation_score=0.81,
                lag_days=-18,
            ),
            make_support(
                target_cluster_id=1,
                target_anomaly_id=100,
                target_timestamp=datetime(2025, 1, 15, tzinfo=timezone.utc),
                target_cluster_start_timestamp=datetime(2025, 1, 15, tzinfo=timezone.utc),
                target_cluster_end_timestamp=datetime(2025, 1, 15, tzinfo=timezone.utc),
                target_cluster_anomaly_count=1,
                target_cluster_dataset_count=1,
                target_cluster_peak_severity_score=3.1,
                related_dataset_id=3,
                related_dataset_name="Federal Funds Rate",
                related_dataset_frequency="monthly",
                correlation_score=0.44,
                lag_days=-9,
            ),
        ],
        target_cluster_count=2,
    )

    assert len(aggregates) == 2
    assert aggregates[0].related_dataset_name == "WTI Oil Price"
    assert aggregates[0].supporting_cluster_count == 2
    assert aggregates[0].cluster_coverage == 1.0
    assert aggregates[0].average_lead_days == 19
    assert aggregates[0].sign_consistency == 1.0
    assert aggregates[0].dominant_direction == "positive"
    assert aggregates[0].frequency_alignment == 0.65
    assert aggregates[0].support_confidence == 0.55
    assert len(aggregates[0].supporting_episodes) == 2
    assert aggregates[0].supporting_episodes[0].target_cluster_episode_kind == "single_dataset_wave"
    assert aggregates[0].average_abs_correlation_score > aggregates[1].average_abs_correlation_score


def test_aggregate_leading_indicators_penalizes_mixed_sign_relationships() -> None:
    aggregates = aggregate_leading_indicators(
        [
            make_support(
                target_cluster_id=1,
                target_anomaly_id=100,
                target_timestamp=datetime(2025, 1, 15, tzinfo=timezone.utc),
                target_cluster_start_timestamp=datetime(2025, 1, 15, tzinfo=timezone.utc),
                target_cluster_end_timestamp=datetime(2025, 1, 15, tzinfo=timezone.utc),
                target_cluster_anomaly_count=1,
                target_cluster_dataset_count=1,
                target_cluster_peak_severity_score=3.1,
                related_dataset_id=2,
                related_dataset_name="WTI Oil Price",
                related_dataset_frequency="daily",
                correlation_score=0.7,
                lag_days=-12,
            ),
            make_support(
                target_cluster_id=2,
                target_anomaly_id=101,
                target_timestamp=datetime(2025, 4, 15, tzinfo=timezone.utc),
                target_cluster_start_timestamp=datetime(2025, 4, 15, tzinfo=timezone.utc),
                target_cluster_end_timestamp=datetime(2025, 4, 18, tzinfo=timezone.utc),
                target_cluster_anomaly_count=2,
                target_cluster_dataset_count=1,
                target_cluster_peak_severity_score=3.0,
                target_cluster_episode_kind="single_dataset_wave",
                related_dataset_id=2,
                related_dataset_name="WTI Oil Price",
                related_dataset_frequency="daily",
                correlation_score=-0.75,
                lag_days=-15,
            ),
        ],
        target_cluster_count=2,
    )

    assert len(aggregates) == 1
    assert aggregates[0].sign_consistency == 0.5
    assert aggregates[0].dominant_direction == "positive"


def test_compute_frequency_alignment_applies_smaller_penalty_to_adjacent_frequencies() -> None:
    assert compute_frequency_alignment("monthly", "monthly") == 1.0
    assert compute_frequency_alignment("weekly", "monthly") == 0.85
    assert compute_frequency_alignment("daily", "monthly") == 0.65


def test_compute_support_confidence_penalizes_one_cluster_leaders() -> None:
    assert compute_support_confidence(1) == 0.2
    assert compute_support_confidence(2) == 0.55
    assert compute_support_confidence(3) == 0.8
    assert compute_support_confidence(4) == 1.0


def test_aggregate_leading_indicators_penalizes_one_cluster_leaders() -> None:
    aggregates = aggregate_leading_indicators(
        [
            make_support(
                target_cluster_id=1,
                target_anomaly_id=100,
                target_timestamp=datetime(2025, 1, 15, tzinfo=timezone.utc),
                target_cluster_start_timestamp=datetime(2025, 1, 15, tzinfo=timezone.utc),
                target_cluster_end_timestamp=datetime(2025, 1, 15, tzinfo=timezone.utc),
                target_cluster_anomaly_count=1,
                target_cluster_dataset_count=1,
                target_cluster_peak_severity_score=3.1,
                related_dataset_id=2,
                related_dataset_name="WTI Oil Price",
                related_dataset_frequency="monthly",
                correlation_score=0.95,
                lag_days=-12,
            ),
            make_support(
                target_cluster_id=1,
                target_anomaly_id=100,
                target_timestamp=datetime(2025, 1, 15, tzinfo=timezone.utc),
                target_cluster_start_timestamp=datetime(2025, 1, 15, tzinfo=timezone.utc),
                target_cluster_end_timestamp=datetime(2025, 1, 15, tzinfo=timezone.utc),
                target_cluster_anomaly_count=1,
                target_cluster_dataset_count=1,
                target_cluster_peak_severity_score=3.1,
                related_dataset_id=3,
                related_dataset_name="Federal Funds Rate",
                related_dataset_frequency="monthly",
                correlation_score=0.74,
                lag_days=-10,
            ),
            make_support(
                target_cluster_id=2,
                target_anomaly_id=101,
                target_timestamp=datetime(2025, 4, 15, tzinfo=timezone.utc),
                target_cluster_start_timestamp=datetime(2025, 4, 15, tzinfo=timezone.utc),
                target_cluster_end_timestamp=datetime(2025, 4, 15, tzinfo=timezone.utc),
                target_cluster_anomaly_count=1,
                target_cluster_dataset_count=1,
                target_cluster_peak_severity_score=2.9,
                related_dataset_id=3,
                related_dataset_name="Federal Funds Rate",
                related_dataset_frequency="monthly",
                correlation_score=0.71,
                lag_days=-11,
            ),
        ],
        target_cluster_count=2,
    )

    assert aggregates[0].related_dataset_name == "Federal Funds Rate"
    assert aggregates[0].support_confidence == 0.55
    assert aggregates[1].related_dataset_name == "WTI Oil Price"
    assert aggregates[1].support_confidence == 0.2
