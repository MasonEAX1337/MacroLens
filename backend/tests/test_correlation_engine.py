from datetime import datetime, timedelta, timezone

from app.services.correlation_engine import compute_best_lag_correlation, get_correlation_config


def build_points(values: list[float]) -> list[dict[str, object]]:
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return [
        {
            "timestamp": start + timedelta(days=index),
            "value": value,
        }
        for index, value in enumerate(values)
    ]


def test_get_correlation_config_uses_frequency_defaults() -> None:
    daily = get_correlation_config("daily")
    monthly = get_correlation_config("monthly")

    assert daily.window_days == 30
    assert daily.max_lag_days == 30
    assert monthly.window_days == 365
    assert monthly.min_overlap == 4


def test_compute_best_lag_correlation_detects_positive_lag() -> None:
    base_values = [100, 102, 101, 110, 103, 99, 104, 120, 107, 105, 109, 130]
    related_values = [100, 100, 100, 102, 101, 110, 103, 99, 104, 120, 107, 105, 109, 130]

    result = compute_best_lag_correlation(
        build_points(base_values),
        build_points(related_values),
        max_lag_days=3,
        min_overlap=5,
    )

    assert result is not None
    correlation_score, lag_days = result
    assert lag_days == 2
    assert correlation_score > 0.99


def test_compute_best_lag_correlation_returns_none_with_low_overlap() -> None:
    result = compute_best_lag_correlation(
        build_points([100, 101, 102]),
        build_points([100, 101, 102]),
        max_lag_days=3,
        min_overlap=5,
    )

    assert result is None
