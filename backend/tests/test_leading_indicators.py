from datetime import datetime, timezone

from app.services.leading_indicators import (
    LeadingIndicatorSupport,
    aggregate_leading_indicators,
    collapse_support_by_cluster,
    compute_frequency_alignment,
    compute_support_confidence,
)


def test_collapse_support_by_cluster_keeps_strongest_correlation_per_target_cluster() -> None:
    collapsed = collapse_support_by_cluster(
        [
            LeadingIndicatorSupport(
                target_cluster_id=10,
                target_anomaly_id=100,
                target_dataset_id=1,
                target_dataset_name="Consumer Price Index",
                target_timestamp=datetime(2025, 1, 15, tzinfo=timezone.utc),
                target_direction="up",
                target_detection_method="z_score",
                target_severity_score=3.2,
                target_cluster_start_timestamp=datetime(2025, 1, 15, tzinfo=timezone.utc),
                target_cluster_end_timestamp=datetime(2025, 1, 18, tzinfo=timezone.utc),
                target_cluster_anomaly_count=2,
                target_cluster_dataset_count=1,
                target_cluster_peak_severity_score=3.2,
                target_dataset_frequency="monthly",
                related_dataset_id=2,
                related_dataset_name="WTI Oil Price",
                related_dataset_frequency="daily",
                correlation_score=0.61,
                lag_days=-20,
            ),
            LeadingIndicatorSupport(
                target_cluster_id=10,
                target_anomaly_id=101,
                target_dataset_id=1,
                target_dataset_name="Consumer Price Index",
                target_timestamp=datetime(2025, 1, 16, tzinfo=timezone.utc),
                target_direction="up",
                target_detection_method="change_point",
                target_severity_score=2.8,
                target_cluster_start_timestamp=datetime(2025, 1, 15, tzinfo=timezone.utc),
                target_cluster_end_timestamp=datetime(2025, 1, 18, tzinfo=timezone.utc),
                target_cluster_anomaly_count=2,
                target_cluster_dataset_count=1,
                target_cluster_peak_severity_score=3.2,
                target_dataset_frequency="monthly",
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


def test_aggregate_leading_indicators_ranks_by_coverage_and_strength() -> None:
    aggregates = aggregate_leading_indicators(
        [
            LeadingIndicatorSupport(
                target_cluster_id=1,
                target_anomaly_id=100,
                target_dataset_id=1,
                target_dataset_name="Consumer Price Index",
                target_timestamp=datetime(2025, 1, 15, tzinfo=timezone.utc),
                target_direction="up",
                target_detection_method="z_score",
                target_severity_score=3.1,
                target_cluster_start_timestamp=datetime(2025, 1, 15, tzinfo=timezone.utc),
                target_cluster_end_timestamp=datetime(2025, 1, 15, tzinfo=timezone.utc),
                target_cluster_anomaly_count=1,
                target_cluster_dataset_count=1,
                target_cluster_peak_severity_score=3.1,
                target_dataset_frequency="monthly",
                related_dataset_id=2,
                related_dataset_name="WTI Oil Price",
                related_dataset_frequency="daily",
                correlation_score=0.72,
                lag_days=-20,
            ),
            LeadingIndicatorSupport(
                target_cluster_id=2,
                target_anomaly_id=101,
                target_dataset_id=1,
                target_dataset_name="Consumer Price Index",
                target_timestamp=datetime(2025, 4, 15, tzinfo=timezone.utc),
                target_direction="up",
                target_detection_method="z_score",
                target_severity_score=3.0,
                target_cluster_start_timestamp=datetime(2025, 4, 15, tzinfo=timezone.utc),
                target_cluster_end_timestamp=datetime(2025, 4, 18, tzinfo=timezone.utc),
                target_cluster_anomaly_count=2,
                target_cluster_dataset_count=1,
                target_cluster_peak_severity_score=3.0,
                target_dataset_frequency="monthly",
                related_dataset_id=2,
                related_dataset_name="WTI Oil Price",
                related_dataset_frequency="daily",
                correlation_score=0.81,
                lag_days=-18,
            ),
            LeadingIndicatorSupport(
                target_cluster_id=1,
                target_anomaly_id=100,
                target_dataset_id=1,
                target_dataset_name="Consumer Price Index",
                target_timestamp=datetime(2025, 1, 15, tzinfo=timezone.utc),
                target_direction="up",
                target_detection_method="z_score",
                target_severity_score=3.1,
                target_cluster_start_timestamp=datetime(2025, 1, 15, tzinfo=timezone.utc),
                target_cluster_end_timestamp=datetime(2025, 1, 15, tzinfo=timezone.utc),
                target_cluster_anomaly_count=1,
                target_cluster_dataset_count=1,
                target_cluster_peak_severity_score=3.1,
                target_dataset_frequency="monthly",
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
    assert aggregates[0].average_abs_correlation_score > aggregates[1].average_abs_correlation_score


def test_aggregate_leading_indicators_penalizes_mixed_sign_relationships() -> None:
    aggregates = aggregate_leading_indicators(
        [
            LeadingIndicatorSupport(
                target_cluster_id=1,
                target_anomaly_id=100,
                target_dataset_id=1,
                target_dataset_name="Consumer Price Index",
                target_timestamp=datetime(2025, 1, 15, tzinfo=timezone.utc),
                target_direction="up",
                target_detection_method="z_score",
                target_severity_score=3.1,
                target_cluster_start_timestamp=datetime(2025, 1, 15, tzinfo=timezone.utc),
                target_cluster_end_timestamp=datetime(2025, 1, 15, tzinfo=timezone.utc),
                target_cluster_anomaly_count=1,
                target_cluster_dataset_count=1,
                target_cluster_peak_severity_score=3.1,
                target_dataset_frequency="monthly",
                related_dataset_id=2,
                related_dataset_name="WTI Oil Price",
                related_dataset_frequency="daily",
                correlation_score=0.7,
                lag_days=-12,
            ),
            LeadingIndicatorSupport(
                target_cluster_id=2,
                target_anomaly_id=101,
                target_dataset_id=1,
                target_dataset_name="Consumer Price Index",
                target_timestamp=datetime(2025, 4, 15, tzinfo=timezone.utc),
                target_direction="up",
                target_detection_method="z_score",
                target_severity_score=3.0,
                target_cluster_start_timestamp=datetime(2025, 4, 15, tzinfo=timezone.utc),
                target_cluster_end_timestamp=datetime(2025, 4, 18, tzinfo=timezone.utc),
                target_cluster_anomaly_count=2,
                target_cluster_dataset_count=1,
                target_cluster_peak_severity_score=3.0,
                target_dataset_frequency="monthly",
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
            LeadingIndicatorSupport(
                target_cluster_id=1,
                target_anomaly_id=100,
                target_dataset_id=1,
                target_dataset_name="Consumer Price Index",
                target_timestamp=datetime(2025, 1, 15, tzinfo=timezone.utc),
                target_direction="up",
                target_detection_method="z_score",
                target_severity_score=3.1,
                target_cluster_start_timestamp=datetime(2025, 1, 15, tzinfo=timezone.utc),
                target_cluster_end_timestamp=datetime(2025, 1, 15, tzinfo=timezone.utc),
                target_cluster_anomaly_count=1,
                target_cluster_dataset_count=1,
                target_cluster_peak_severity_score=3.1,
                target_dataset_frequency="monthly",
                related_dataset_id=2,
                related_dataset_name="WTI Oil Price",
                related_dataset_frequency="monthly",
                correlation_score=0.95,
                lag_days=-12,
            ),
            LeadingIndicatorSupport(
                target_cluster_id=1,
                target_anomaly_id=100,
                target_dataset_id=1,
                target_dataset_name="Consumer Price Index",
                target_timestamp=datetime(2025, 1, 15, tzinfo=timezone.utc),
                target_direction="up",
                target_detection_method="z_score",
                target_severity_score=3.1,
                target_cluster_start_timestamp=datetime(2025, 1, 15, tzinfo=timezone.utc),
                target_cluster_end_timestamp=datetime(2025, 1, 15, tzinfo=timezone.utc),
                target_cluster_anomaly_count=1,
                target_cluster_dataset_count=1,
                target_cluster_peak_severity_score=3.1,
                target_dataset_frequency="monthly",
                related_dataset_id=3,
                related_dataset_name="Federal Funds Rate",
                related_dataset_frequency="monthly",
                correlation_score=0.74,
                lag_days=-10,
            ),
            LeadingIndicatorSupport(
                target_cluster_id=2,
                target_anomaly_id=101,
                target_dataset_id=1,
                target_dataset_name="Consumer Price Index",
                target_timestamp=datetime(2025, 4, 15, tzinfo=timezone.utc),
                target_direction="up",
                target_detection_method="z_score",
                target_severity_score=2.9,
                target_cluster_start_timestamp=datetime(2025, 4, 15, tzinfo=timezone.utc),
                target_cluster_end_timestamp=datetime(2025, 4, 15, tzinfo=timezone.utc),
                target_cluster_anomaly_count=1,
                target_cluster_dataset_count=1,
                target_cluster_peak_severity_score=2.9,
                target_dataset_frequency="monthly",
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
