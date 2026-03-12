from dataclasses import dataclass
from datetime import datetime, timedelta

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class CorrelationConfig:
    window_days: int
    max_lag_days: int
    min_overlap: int
    min_abs_correlation: float
    max_results: int


@dataclass(frozen=True)
class CorrelationCandidate:
    related_dataset_id: int
    correlation_score: float
    lag_days: int
    method: str


DEFAULT_CORRELATION_CONFIGS: dict[str, CorrelationConfig] = {
    "daily": CorrelationConfig(window_days=30, max_lag_days=30, min_overlap=5, min_abs_correlation=0.25, max_results=5),
    "weekly": CorrelationConfig(window_days=120, max_lag_days=42, min_overlap=5, min_abs_correlation=0.25, max_results=5),
    "monthly": CorrelationConfig(window_days=365, max_lag_days=90, min_overlap=4, min_abs_correlation=0.2, max_results=5),
}


def get_correlation_config(frequency: str) -> CorrelationConfig:
    return DEFAULT_CORRELATION_CONFIGS.get(frequency, DEFAULT_CORRELATION_CONFIGS["daily"])


def load_dataset_frequency(db: Session, dataset_id: int) -> str:
    query = text(
        """
        SELECT frequency
        FROM datasets
        WHERE id = :dataset_id
        """
    )
    frequency = db.execute(query, {"dataset_id": dataset_id}).scalar_one_or_none()
    if frequency is None:
        raise ValueError(f"Dataset {dataset_id} not found.")
    return str(frequency)


def load_points_in_window(
    db: Session,
    dataset_id: int,
    start_at: datetime,
    end_at: datetime,
) -> list[dict[str, object]]:
    query = text(
        """
        SELECT timestamp, value
        FROM data_points
        WHERE dataset_id = :dataset_id
          AND timestamp BETWEEN :start_at AND :end_at
        ORDER BY timestamp ASC
        """
    )
    rows = db.execute(
        query,
        {
            "dataset_id": dataset_id,
            "start_at": start_at,
            "end_at": end_at,
        },
    ).mappings().all()
    return [dict(row) for row in rows]


def load_other_dataset_ids(db: Session, dataset_id: int) -> list[int]:
    query = text(
        """
        SELECT id
        FROM datasets
        WHERE id <> :dataset_id
        ORDER BY id ASC
        """
    )
    rows = db.execute(query, {"dataset_id": dataset_id}).scalars().all()
    return [int(row) for row in rows]


def load_anomalies(db: Session, dataset_id: int | None = None) -> list[dict[str, object]]:
    if dataset_id is None:
        query = text(
            """
            SELECT id, dataset_id, timestamp
            FROM anomalies
            ORDER BY timestamp DESC
            """
        )
        rows = db.execute(query).mappings().all()
    else:
        query = text(
            """
            SELECT id, dataset_id, timestamp
            FROM anomalies
            WHERE dataset_id = :dataset_id
            ORDER BY timestamp DESC
            """
        )
        rows = db.execute(query, {"dataset_id": dataset_id}).mappings().all()
    return [dict(row) for row in rows]


def build_return_frame(points: list[dict[str, object]], value_column_name: str) -> pd.DataFrame:
    if not points:
        return pd.DataFrame(columns=["timestamp", value_column_name])

    frame = pd.DataFrame(points)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame["value"] = frame["value"].astype(float)
    frame[value_column_name] = frame["value"].pct_change()
    frame = frame[["timestamp", value_column_name]].replace([pd.NA, float("inf"), float("-inf")], pd.NA)
    return frame.dropna().reset_index(drop=True)


def compute_best_lag_correlation(
    base_points: list[dict[str, object]],
    related_points: list[dict[str, object]],
    *,
    max_lag_days: int,
    min_overlap: int,
) -> tuple[float, int] | None:
    base_frame = build_return_frame(base_points, "base_return")
    related_frame = build_return_frame(related_points, "related_return")

    if len(base_frame) < min_overlap or len(related_frame) < min_overlap:
        return None

    best_result: tuple[float, int] | None = None
    for lag_days in range(-max_lag_days, max_lag_days + 1):
        shifted = related_frame.copy()
        shifted["timestamp"] = shifted["timestamp"] - pd.to_timedelta(lag_days, unit="D")
        merged = base_frame.merge(shifted, on="timestamp", how="inner")
        if len(merged) < min_overlap:
            continue
        correlation = merged["base_return"].corr(merged["related_return"])
        if pd.isna(correlation):
            continue
        candidate = (float(correlation), lag_days)
        if best_result is None or abs(candidate[0]) > abs(best_result[0]):
            best_result = candidate
    return best_result


def compute_correlations_for_anomaly(
    db: Session,
    anomaly_id: int,
    dataset_id: int,
    anomaly_timestamp: datetime,
) -> list[CorrelationCandidate]:
    frequency = load_dataset_frequency(db, dataset_id)
    config = get_correlation_config(frequency)

    base_start = anomaly_timestamp - timedelta(days=config.window_days)
    base_end = anomaly_timestamp + timedelta(days=config.window_days)
    related_start = base_start - timedelta(days=config.max_lag_days)
    related_end = base_end + timedelta(days=config.max_lag_days)

    base_points = load_points_in_window(db, dataset_id, base_start, base_end)
    if not base_points:
        return []

    candidates: list[CorrelationCandidate] = []
    for related_dataset_id in load_other_dataset_ids(db, dataset_id):
        related_points = load_points_in_window(db, related_dataset_id, related_start, related_end)
        result = compute_best_lag_correlation(
            base_points,
            related_points,
            max_lag_days=config.max_lag_days,
            min_overlap=config.min_overlap,
        )
        if result is None:
            continue
        correlation_score, lag_days = result
        if abs(correlation_score) < config.min_abs_correlation:
            continue
        candidates.append(
            CorrelationCandidate(
                related_dataset_id=related_dataset_id,
                correlation_score=correlation_score,
                lag_days=lag_days,
                method="pearson_pct_change",
            )
        )

    candidates.sort(key=lambda item: abs(item.correlation_score), reverse=True)
    return candidates[: config.max_results]


def replace_anomaly_correlations(db: Session, anomaly_id: int, correlations: list[CorrelationCandidate]) -> int:
    delete_query = text(
        """
        DELETE FROM correlations
        WHERE anomaly_id = :anomaly_id
        """
    )
    db.execute(delete_query, {"anomaly_id": anomaly_id})

    if not correlations:
        return 0

    insert_query = text(
        """
        INSERT INTO correlations (anomaly_id, related_dataset_id, correlation_score, lag_days, method)
        VALUES (:anomaly_id, :related_dataset_id, :correlation_score, :lag_days, :method)
        """
    )
    payload = [
        {
            "anomaly_id": anomaly_id,
            "related_dataset_id": item.related_dataset_id,
            "correlation_score": item.correlation_score,
            "lag_days": item.lag_days,
            "method": item.method,
        }
        for item in correlations
    ]
    db.execute(insert_query, payload)
    return len(payload)


def run_correlation_for_anomaly(
    db: Session,
    anomaly_id: int,
    dataset_id: int,
    anomaly_timestamp: datetime,
) -> int:
    correlations = compute_correlations_for_anomaly(db, anomaly_id, dataset_id, anomaly_timestamp)
    return replace_anomaly_correlations(db, anomaly_id, correlations)


def run_correlation_for_dataset(db: Session, dataset_id: int) -> int:
    inserted = 0
    for anomaly in load_anomalies(db, dataset_id=dataset_id):
        inserted += run_correlation_for_anomaly(
            db,
            anomaly_id=int(anomaly["id"]),
            dataset_id=int(anomaly["dataset_id"]),
            anomaly_timestamp=anomaly["timestamp"],
        )
    return inserted


def run_correlation_for_all_anomalies(db: Session) -> int:
    inserted = 0
    for anomaly in load_anomalies(db):
        inserted += run_correlation_for_anomaly(
            db,
            anomaly_id=int(anomaly["id"]),
            dataset_id=int(anomaly["dataset_id"]),
            anomaly_timestamp=anomaly["timestamp"],
        )
    return inserted
