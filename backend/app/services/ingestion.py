from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class DatasetDefinition:
    key: str
    name: str
    symbol: str
    source: str
    description: str
    frequency: str


@dataclass(frozen=True)
class DataPointRecord:
    timestamp: datetime
    value: float


def ensure_utc(timestamp: datetime) -> datetime:
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc)


def upsert_dataset(db: Session, dataset: DatasetDefinition) -> int:
    query = text(
        """
        INSERT INTO datasets (name, symbol, source, description, frequency)
        VALUES (:name, :symbol, :source, :description, :frequency)
        ON CONFLICT (source, symbol)
        DO UPDATE SET
            name = EXCLUDED.name,
            description = EXCLUDED.description,
            frequency = EXCLUDED.frequency,
            updated_at = NOW()
        RETURNING id
        """
    )
    dataset_id = db.execute(
        query,
        {
            "name": dataset.name,
            "symbol": dataset.symbol,
            "source": dataset.source,
            "description": dataset.description,
            "frequency": dataset.frequency,
        },
    ).scalar_one()
    return int(dataset_id)


def upsert_data_points(
    db: Session,
    dataset_id: int,
    points: list[DataPointRecord],
    *,
    replace_existing: bool = False,
) -> int:
    if not points:
        return 0

    if replace_existing:
        delete_query = text(
            """
            DELETE FROM data_points
            WHERE dataset_id = :dataset_id
            """
        )
        db.execute(delete_query, {"dataset_id": dataset_id})

    query = text(
        """
        INSERT INTO data_points (dataset_id, timestamp, value)
        VALUES (:dataset_id, :timestamp, :value)
        ON CONFLICT (dataset_id, timestamp)
        DO UPDATE SET value = EXCLUDED.value
        """
    )

    payload = [
        {
            "dataset_id": dataset_id,
            "timestamp": ensure_utc(point.timestamp),
            "value": point.value,
        }
        for point in points
    ]
    db.execute(query, payload)
    return len(payload)


def create_ingestion_run(db: Session, source: str, dataset_key: str, status: str, message: str | None) -> None:
    query = text(
        """
        INSERT INTO ingestion_runs (source, dataset_key, status, message, finished_at)
        VALUES (:source, :dataset_key, :status, :message, NOW())
        """
    )
    db.execute(
        query,
        {
            "source": source,
            "dataset_key": dataset_key,
            "status": status,
            "message": message,
        },
    )
