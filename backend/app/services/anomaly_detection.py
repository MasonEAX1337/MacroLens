import json
from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd
import ruptures as rpt
from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class DetectionConfig:
    window_size: int
    threshold: float
    min_periods: int


@dataclass(frozen=True)
class ChangePointConfig:
    algorithm: str
    model: str
    penalty: float
    min_size: int
    jump: int
    smoothing_window: int
    severity_threshold: float


@dataclass(frozen=True)
class DetectionPoint:
    index: int
    timestamp: datetime
    value: float
    z_score: float
    rolling_mean: float
    rolling_std: float


@dataclass(frozen=True)
class PersistedAnomaly:
    timestamp: datetime
    severity_score: float
    direction: str
    detection_method: str
    metadata: dict[str, float | int | str]


DEFAULT_CONFIGS: dict[str, DetectionConfig] = {
    "daily": DetectionConfig(window_size=30, threshold=3.0, min_periods=30),
    "weekly": DetectionConfig(window_size=12, threshold=3.0, min_periods=12),
    "monthly": DetectionConfig(window_size=12, threshold=2.5, min_periods=12),
}

CHANGE_POINT_CONFIGS: dict[str, ChangePointConfig] = {
    "daily": ChangePointConfig(
        algorithm="binseg",
        model="l2",
        penalty=5.0,
        min_size=14,
        jump=5,
        smoothing_window=3,
        severity_threshold=0.9,
    ),
    "weekly": ChangePointConfig(
        algorithm="binseg",
        model="l2",
        penalty=2.5,
        min_size=10,
        jump=3,
        smoothing_window=3,
        severity_threshold=0.25,
    ),
    "monthly": ChangePointConfig(
        algorithm="binseg",
        model="l2",
        penalty=3.0,
        min_size=6,
        jump=1,
        smoothing_window=2,
        severity_threshold=0.45,
    ),
}


def get_detection_config(frequency: str) -> DetectionConfig:
    return DEFAULT_CONFIGS.get(frequency, DEFAULT_CONFIGS["daily"])


def get_change_point_config(frequency: str) -> ChangePointConfig:
    return CHANGE_POINT_CONFIGS.get(frequency, CHANGE_POINT_CONFIGS["daily"])


def load_dataset_series(db: Session, dataset_id: int) -> tuple[str, list[dict[str, object]]]:
    dataset_query = text(
        """
        SELECT frequency
        FROM datasets
        WHERE id = :dataset_id
        """
    )
    frequency = db.execute(dataset_query, {"dataset_id": dataset_id}).scalar_one_or_none()
    if frequency is None:
        raise ValueError(f"Dataset {dataset_id} not found.")

    points_query = text(
        """
        SELECT timestamp, value
        FROM data_points
        WHERE dataset_id = :dataset_id
        ORDER BY timestamp ASC
        """
    )
    rows = db.execute(points_query, {"dataset_id": dataset_id}).mappings().all()
    return str(frequency), [dict(row) for row in rows]


def detect_anomalies(
    points: list[dict[str, object]],
    frequency: str,
    *,
    window_size: int | None = None,
    threshold: float | None = None,
) -> list[PersistedAnomaly]:
    return detect_z_score_anomalies(
        points,
        frequency,
        window_size=window_size,
        threshold=threshold,
    )


def detect_z_score_anomalies(
    points: list[dict[str, object]],
    frequency: str,
    *,
    window_size: int | None = None,
    threshold: float | None = None,
) -> list[PersistedAnomaly]:
    if not points:
        return []

    config = get_detection_config(frequency)
    active_window = window_size or config.window_size
    active_threshold = threshold or config.threshold
    min_periods = min(active_window, config.min_periods)

    frame = pd.DataFrame(points)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame["value"] = frame["value"].astype(float)
    frame["rolling_mean"] = frame["value"].rolling(window=active_window, min_periods=min_periods).mean()
    frame["rolling_std"] = frame["value"].rolling(window=active_window, min_periods=min_periods).std(ddof=0)

    denominator = frame["rolling_std"].replace(0, pd.NA)
    frame["z_score"] = (frame["value"] - frame["rolling_mean"]) / denominator
    frame["abs_z_score"] = frame["z_score"].abs()

    flagged: list[DetectionPoint] = []
    for row in frame.itertuples(index=True):
        z_score = getattr(row, "z_score")
        if pd.isna(z_score):
            continue
        if abs(float(z_score)) < active_threshold:
            continue
        flagged.append(
            DetectionPoint(
                index=int(row.Index),
                timestamp=row.timestamp.to_pydatetime(),
                value=float(row.value),
                z_score=float(z_score),
                rolling_mean=float(row.rolling_mean),
                rolling_std=float(row.rolling_std),
            )
        )

    return collapse_flagged_points(flagged, window_size=active_window, threshold=active_threshold)


def build_change_point_signal(values: pd.Series, *, smoothing_window: int) -> np.ndarray:
    smoothed_values = values.rolling(window=smoothing_window, min_periods=1).mean()
    standardized_values = (smoothed_values - smoothed_values.mean()) / max(float(smoothed_values.std(ddof=0)), 1e-9)
    return standardized_values.to_numpy().reshape(-1, 1)


def classify_change_point_event_type(
    *,
    before_values: np.ndarray,
    after_values: np.ndarray,
) -> str:
    mean_shift = abs(float(after_values.mean()) - float(before_values.mean()))
    volatility_shift = abs(float(after_values.std(ddof=0)) - float(before_values.std(ddof=0)))
    return "level_shift" if mean_shift >= volatility_shift else "volatility_shift"


def detect_change_point_anomalies(
    points: list[dict[str, object]],
    frequency: str,
    *,
    penalty: float | None = None,
) -> list[PersistedAnomaly]:
    if not points:
        return []

    config = get_change_point_config(frequency)
    active_penalty = penalty or config.penalty

    frame = pd.DataFrame(points)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame["value"] = frame["value"].astype(float)

    if len(frame) < max(config.min_size * 2, 8):
        return []

    signal = build_change_point_signal(frame["value"], smoothing_window=config.smoothing_window)
    if config.algorithm == "binseg":
        algo = rpt.Binseg(model=config.model, min_size=config.min_size, jump=config.jump).fit(signal)
    else:
        algo = rpt.Pelt(model=config.model, min_size=config.min_size, jump=config.jump).fit(signal)
    breakpoints = [int(item) for item in algo.predict(pen=active_penalty)[:-1]]

    anomalies: list[PersistedAnomaly] = []
    overall_std = max(float(frame["value"].std(ddof=0)), 1e-9)
    for breakpoint in breakpoints:
        if breakpoint <= 0 or breakpoint >= len(frame):
            continue

        before_start = max(0, breakpoint - config.min_size)
        after_end = min(len(frame), breakpoint + config.min_size)
        before_values = frame["value"].iloc[before_start:breakpoint].to_numpy()
        after_values = frame["value"].iloc[breakpoint:after_end].to_numpy()
        if len(before_values) < max(2, config.min_size // 2) or len(after_values) < max(2, config.min_size // 2):
            continue

        before_mean = float(before_values.mean())
        after_mean = float(after_values.mean())
        delta_mean = after_mean - before_mean
        event_type = classify_change_point_event_type(
            before_values=before_values,
            after_values=after_values,
        )
        severity_score = abs(delta_mean) / overall_std
        if severity_score < config.severity_threshold:
            continue

        timestamp = frame.iloc[breakpoint]["timestamp"].to_pydatetime()
        anomalies.append(
            PersistedAnomaly(
                timestamp=timestamp,
                severity_score=round(severity_score, 6),
                direction="up" if delta_mean >= 0 else "down",
                detection_method="change_point",
                metadata={
                    "event_type": event_type,
                    "algorithm": config.algorithm,
                    "model": config.model,
                    "penalty": active_penalty,
                    "min_size": config.min_size,
                    "jump": config.jump,
                    "smoothing_window": config.smoothing_window,
                    "severity_threshold": config.severity_threshold,
                    "before_mean": round(before_mean, 6),
                    "after_mean": round(after_mean, 6),
                    "delta_mean": round(delta_mean, 6),
                    "overall_std": round(overall_std, 6),
                    "value": round(float(frame.iloc[breakpoint]["value"]), 6),
                },
            )
        )

    return collapse_change_point_anomalies(anomalies, min_gap=config.min_size)


def collapse_change_point_anomalies(
    anomalies: list[PersistedAnomaly],
    *,
    min_gap: int,
) -> list[PersistedAnomaly]:
    if not anomalies:
        return []

    sorted_anomalies = sorted(anomalies, key=lambda item: item.timestamp)
    collapsed: list[PersistedAnomaly] = [sorted_anomalies[0]]
    for candidate in sorted_anomalies[1:]:
        previous = collapsed[-1]
        gap_days = abs((candidate.timestamp - previous.timestamp).days)
        if gap_days <= min_gap:
            if candidate.severity_score > previous.severity_score:
                collapsed[-1] = candidate
            continue
        collapsed.append(candidate)
    return collapsed


def collapse_flagged_points(
    flagged: list[DetectionPoint],
    *,
    window_size: int,
    threshold: float,
) -> list[PersistedAnomaly]:
    if not flagged:
        return []

    clusters: list[list[DetectionPoint]] = []
    current_cluster: list[DetectionPoint] = [flagged[0]]

    for candidate in flagged[1:]:
        previous = current_cluster[-1]
        if candidate.index == previous.index + 1:
            current_cluster.append(candidate)
            continue
        clusters.append(current_cluster)
        current_cluster = [candidate]
    clusters.append(current_cluster)

    anomalies: list[PersistedAnomaly] = []
    for cluster in clusters:
        strongest = max(cluster, key=lambda item: abs(item.z_score))
        anomalies.append(
            PersistedAnomaly(
                timestamp=strongest.timestamp,
                severity_score=abs(strongest.z_score),
                direction="up" if strongest.z_score > 0 else "down",
                detection_method="z_score",
                metadata={
                    "z_score": round(strongest.z_score, 6),
                    "window_size": window_size,
                    "threshold": threshold,
                    "rolling_mean": round(strongest.rolling_mean, 6),
                    "rolling_std": round(strongest.rolling_std, 6),
                    "value": round(strongest.value, 6),
                },
            )
        )
    return anomalies


def replace_dataset_anomalies_for_method(
    db: Session,
    dataset_id: int,
    detection_method: str,
    anomalies: list[PersistedAnomaly],
) -> int:
    delete_query = text(
        """
        DELETE FROM anomalies
        WHERE dataset_id = :dataset_id
          AND detection_method = :detection_method
        """
    )
    db.execute(delete_query, {"dataset_id": dataset_id, "detection_method": detection_method})

    if not anomalies:
        return 0

    insert_query = text(
        """
        INSERT INTO anomalies (dataset_id, timestamp, severity_score, direction, detection_method, metadata)
        VALUES (:dataset_id, :timestamp, :severity_score, :direction, :detection_method, CAST(:metadata AS JSONB))
        """
    )
    payload = [
        {
            "dataset_id": dataset_id,
            "timestamp": anomaly.timestamp,
            "severity_score": anomaly.severity_score,
            "direction": anomaly.direction,
            "detection_method": anomaly.detection_method,
            "metadata": json.dumps(anomaly.metadata),
        }
        for anomaly in anomalies
    ]
    db.execute(insert_query, payload)
    return len(payload)


def run_detection_for_dataset(
    db: Session,
    dataset_id: int,
    *,
    window_size: int | None = None,
    threshold: float | None = None,
) -> int:
    frequency, points = load_dataset_series(db, dataset_id)
    z_score_anomalies = detect_z_score_anomalies(
        points,
        frequency,
        window_size=window_size,
        threshold=threshold,
    )
    change_point_anomalies = detect_change_point_anomalies(points, frequency)
    inserted = 0
    inserted += replace_dataset_anomalies_for_method(db, dataset_id, "z_score", z_score_anomalies)
    inserted += replace_dataset_anomalies_for_method(db, dataset_id, "change_point", change_point_anomalies)
    return inserted
