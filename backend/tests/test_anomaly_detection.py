from datetime import datetime, timedelta, timezone

import pandas as pd

from app.services.anomaly_detection import (
    ChangePointConfig,
    DetectionPoint,
    apply_change_point_transform,
    collapse_flagged_points,
    detect_change_point_anomalies,
    detect_anomalies,
    get_detection_config,
    get_change_point_config,
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
    weekly = get_detection_config("weekly")
    monthly = get_detection_config("monthly")

    assert daily.window_size == 30
    assert weekly.window_size == 12
    assert weekly.threshold == 3.0
    assert monthly.window_size == 12
    assert monthly.threshold == 2.5


def test_get_detection_config_supports_dataset_override() -> None:
    cpi = get_detection_config("monthly", dataset_symbol="CPIAUCSL")
    house_prices = get_detection_config("monthly", dataset_symbol="CSUSHPISA")

    assert cpi.threshold == 2.2
    assert house_prices.threshold == 2.15
    assert cpi.window_size == 12


def test_get_change_point_config_uses_frequency_defaults() -> None:
    daily = get_change_point_config("daily")
    weekly = get_change_point_config("weekly")
    monthly = get_change_point_config("monthly")

    assert daily.algorithm == "binseg"
    assert daily.jump == 5
    assert weekly.min_size == 10
    assert weekly.severity_threshold == 0.25
    assert monthly.smoothing_window == 2
    assert monthly.transform == "raw_level"


def test_get_change_point_config_supports_dataset_override() -> None:
    btc = get_change_point_config("daily", dataset_symbol="BTC")
    wti = get_change_point_config("daily", dataset_symbol="DCOILWTICO")
    cpi = get_change_point_config("monthly", dataset_symbol="CPIAUCSL")
    house_prices = get_change_point_config("monthly", dataset_symbol="CSUSHPISA")

    assert btc.penalty == 4.0
    assert wti.penalty == 3.0
    assert cpi.transform == "percent_change"
    assert house_prices.penalty == 1.8
    assert house_prices.transform == "percent_change"


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


def test_detect_anomalies_uses_dataset_specific_monthly_threshold() -> None:
    values = [100.0, 101.0, 99.0, 102.0, 98.0, 101.0, 100.0, 99.0, 103.0, 97.0, 100.0, 101.0, 106.0]
    generic = detect_anomalies(build_points(values), "monthly")
    cpi = detect_anomalies(build_points(values), "monthly", dataset_symbol="CPIAUCSL")

    assert generic == []
    assert len(cpi) == 1
    assert cpi[0].metadata["threshold"] == 2.2


def test_detect_anomalies_uses_weekly_defaults() -> None:
    values = [6.5] * 12 + [9.8]
    anomalies = detect_anomalies(build_points(values), "weekly")

    assert len(anomalies) == 1
    assert anomalies[0].direction == "up"
    assert anomalies[0].metadata["window_size"] == 12


def test_detect_change_point_anomalies_flags_level_shift() -> None:
    values = [100.0] * 40 + [145.0] * 40
    anomalies = detect_change_point_anomalies(build_points(values), "daily")

    assert len(anomalies) >= 1
    assert anomalies[0].detection_method == "change_point"
    assert anomalies[0].metadata["event_type"] == "level_shift"
    assert anomalies[0].metadata["algorithm"] == "binseg"
    assert anomalies[0].severity_score > 0.75


def test_detect_change_point_anomalies_uses_monthly_defaults() -> None:
    values = [100.0] * 18 + [125.0] * 18
    anomalies = detect_change_point_anomalies(build_points(values), "monthly")

    assert len(anomalies) >= 1
    assert anomalies[0].metadata["min_size"] == 6
    assert anomalies[0].metadata["smoothing_window"] == 2
    assert anomalies[0].metadata["transform"] == "raw_level"


def test_apply_change_point_transform_supports_percent_change() -> None:
    frame = pd.DataFrame(build_points([100.0, 105.0, 110.25]))
    transformed = apply_change_point_transform(frame, transform="percent_change")

    assert list(transformed["signal_value"].round(6)) == [0.05, 0.05]


def test_apply_change_point_transform_supports_first_difference() -> None:
    frame = pd.DataFrame(build_points([100.0, 104.0, 111.0]))
    transformed = apply_change_point_transform(frame, transform="first_difference")

    assert list(transformed["signal_value"]) == [4.0, 7.0]


def test_detect_change_point_anomalies_uses_dataset_specific_penalty(monkeypatch) -> None:
    class MockAlgo:
        def __init__(self, *args, **kwargs):  # noqa: ANN002, ANN003
            self.signal_length = 0

        def fit(self, signal):  # noqa: ANN001
            self.signal_length = len(signal)
            return self

        def predict(self, pen):  # noqa: ANN001
            if pen <= 1.8:
                return [24, self.signal_length]
            return [self.signal_length]

    monkeypatch.setattr("app.services.anomaly_detection.rpt.Binseg", MockAlgo)

    values = [100.0] * 24 + [112.0] * 24
    generic = detect_change_point_anomalies(build_points(values), "monthly")
    house_prices = detect_change_point_anomalies(
        build_points(values),
        "monthly",
        dataset_symbol="CSUSHPISA",
    )

    assert generic == []
    assert len(house_prices) == 1
    assert house_prices[0].metadata["penalty"] == 1.8
    assert house_prices[0].metadata["transform"] == "percent_change"


def test_detect_change_point_anomalies_uses_dataset_specific_transform(monkeypatch) -> None:
    class MockAlgo:
        def __init__(self, *args, **kwargs):  # noqa: ANN002, ANN003
            self.signal_length = 0

        def fit(self, signal):  # noqa: ANN001
            self.signal_length = len(signal)
            return self

        def predict(self, pen):  # noqa: ANN001
            return [5, self.signal_length]

    monkeypatch.setattr(
        "app.services.anomaly_detection.get_change_point_config",
        lambda frequency, dataset_symbol=None: ChangePointConfig(
            algorithm="binseg",
            model="l2",
            penalty=0.1,
            min_size=4,
            jump=1,
            smoothing_window=2,
            severity_threshold=0.0,
            transform="percent_change",
        ),
    )
    monkeypatch.setattr("app.services.anomaly_detection.rpt.Binseg", MockAlgo)

    values = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 126.0, 151.2, 181.44, 217.728, 261.2736, 313.52832]
    anomalies = detect_change_point_anomalies(
        build_points(values),
        "monthly",
        dataset_symbol="CPIAUCSL",
        penalty=0.1,
    )

    assert len(anomalies) == 1
    assert anomalies[0].metadata["transform"] == "percent_change"
    assert "transformed_value" in anomalies[0].metadata


def test_transformed_change_point_detection_ignores_flat_periods(monkeypatch) -> None:
    class MockAlgo:
        def __init__(self, *args, **kwargs):  # noqa: ANN002, ANN003
            self.signal_length = 0

        def fit(self, signal):  # noqa: ANN001
            self.signal_length = len(signal)
            return self

        def predict(self, pen):  # noqa: ANN001
            return [4, self.signal_length]

    monkeypatch.setattr(
        "app.services.anomaly_detection.get_change_point_config",
        lambda frequency, dataset_symbol=None: ChangePointConfig(
            algorithm="binseg",
            model="l2",
            penalty=0.1,
            min_size=4,
            jump=1,
            smoothing_window=2,
            severity_threshold=0.1,
            transform="percent_change",
        ),
    )
    monkeypatch.setattr("app.services.anomaly_detection.rpt.Binseg", MockAlgo)

    anomalies = detect_change_point_anomalies(
        build_points([100.0] * 12),
        "monthly",
        dataset_symbol="CPIAUCSL",
        penalty=0.1,
    )

    assert anomalies == []


def test_transformed_change_point_detection_ignores_small_growth_changes(monkeypatch) -> None:
    class MockAlgo:
        def __init__(self, *args, **kwargs):  # noqa: ANN002, ANN003
            self.signal_length = 0

        def fit(self, signal):  # noqa: ANN001
            self.signal_length = len(signal)
            return self

        def predict(self, pen):  # noqa: ANN001
            return [4, self.signal_length]

    monkeypatch.setattr(
        "app.services.anomaly_detection.get_change_point_config",
        lambda frequency, dataset_symbol=None: ChangePointConfig(
            algorithm="binseg",
            model="l2",
            penalty=0.1,
            min_size=4,
            jump=1,
            smoothing_window=2,
            severity_threshold=0.25,
            transform="percent_change",
        ),
    )
    monkeypatch.setattr("app.services.anomaly_detection.rpt.Binseg", MockAlgo)

    values = [100.0, 100.5, 101.0, 101.6, 102.1, 102.6, 103.2, 103.7, 104.2, 104.8]
    anomalies = detect_change_point_anomalies(
        build_points(values),
        "monthly",
        dataset_symbol="CSUSHPISA",
        penalty=0.1,
    )

    assert anomalies == []


def test_transformed_change_point_detection_ignores_small_noisy_months(monkeypatch) -> None:
    class MockAlgo:
        def __init__(self, *args, **kwargs):  # noqa: ANN002, ANN003
            self.signal_length = 0

        def fit(self, signal):  # noqa: ANN001
            self.signal_length = len(signal)
            return self

        def predict(self, pen):  # noqa: ANN001
            return [5, self.signal_length]

    monkeypatch.setattr(
        "app.services.anomaly_detection.get_change_point_config",
        lambda frequency, dataset_symbol=None: ChangePointConfig(
            algorithm="binseg",
            model="l2",
            penalty=0.1,
            min_size=4,
            jump=1,
            smoothing_window=2,
            severity_threshold=0.3,
            transform="percent_change",
        ),
    )
    monkeypatch.setattr("app.services.anomaly_detection.rpt.Binseg", MockAlgo)

    values = [100.0, 100.9, 100.2, 101.1, 100.4, 101.3, 100.7, 101.4, 100.9, 101.6, 101.0]
    anomalies = detect_change_point_anomalies(
        build_points(values),
        "monthly",
        dataset_symbol="CPIAUCSL",
        penalty=0.1,
    )

    assert anomalies == []
