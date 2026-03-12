from datetime import datetime, timedelta, timezone

from app.services.anomaly_detection import (
    DetectionPoint,
    collapse_flagged_points,
    detect_anomalies,
    get_detection_config,
)


def build_points(values: list[float]) -> list[dict[str, object]]:
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return [
        {
            "timestamp": start + timedelta(days=index),
            "value": value,
        }
        for index, value in enumerate(values)
    ]


def test_get_detection_config_uses_frequency_defaults() -> None:
    daily = get_detection_config("daily")
    monthly = get_detection_config("monthly")

    assert daily.window_size == 30
    assert monthly.window_size == 12
    assert monthly.threshold == 2.5


def test_detect_anomalies_flags_large_spike() -> None:
    values = [100.0] * 30 + [500.0]
    anomalies = detect_anomalies(build_points(values), "daily")

    assert len(anomalies) == 1
    anomaly = anomalies[0]
    assert anomaly.direction == "up"
    assert anomaly.severity_score > 3.0
    assert anomaly.metadata["window_size"] == 30


def test_collapse_flagged_points_reduces_consecutive_flags_to_one_event() -> None:
    start = datetime(2024, 2, 1, tzinfo=timezone.utc)
    flagged = [
        DetectionPoint(
            index=30,
            timestamp=start,
            value=500.0,
            z_score=4.0,
            rolling_mean=100.0,
            rolling_std=20.0,
        ),
        DetectionPoint(
            index=31,
            timestamp=start + timedelta(days=1),
            value=520.0,
            z_score=5.0,
            rolling_mean=101.0,
            rolling_std=21.0,
        ),
    ]
    anomalies = collapse_flagged_points(flagged, window_size=30, threshold=3.0)

    assert len(anomalies) == 1
    assert anomalies[0].metadata["value"] == 520.0


def test_detect_anomalies_uses_lower_threshold_for_monthly_series() -> None:
    values = [100.0] * 12 + [300.0]
    anomalies = detect_anomalies(build_points(values), "monthly")

    assert len(anomalies) == 1
    assert anomalies[0].severity_score > 2.5
