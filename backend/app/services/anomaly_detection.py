import json
from dataclasses import dataclass
from datetime import datetime

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class DetectionConfig:
    window_size: int
    threshold: float
    min_periods: int


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


def get_detection_config(frequency: str) -> DetectionConfig:
    return DEFAULT_CONFIGS.get(frequency, DEFAULT_CONFIGS["daily"])


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


def replace_dataset_anomalies(db: Session, dataset_id: int, anomalies: list[PersistedAnomaly]) -> int:
    delete_query = text(
        """
        DELETE FROM anomalies
        WHERE dataset_id = :dataset_id
          AND detection_method = 'z_score'
        """
    )
    db.execute(delete_query, {"dataset_id": dataset_id})

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
    anomalies = detect_anomalies(
        points,
        frequency,
        window_size=window_size,
        threshold=threshold,
    )
    return replace_dataset_anomalies(db, dataset_id, anomalies)
