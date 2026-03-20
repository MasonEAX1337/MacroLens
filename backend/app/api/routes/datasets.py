from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.api import AnomalySummary, DatasetSummary, LeadingIndicatorRecord, TimeSeriesPoint
from app.services.repository import (
    fetch_dataset_anomalies,
    fetch_dataset_leading_indicators,
    fetch_dataset_timeseries,
    fetch_datasets,
)


router = APIRouter()


@router.get("", response_model=list[DatasetSummary])
def list_datasets(db: Session = Depends(get_db)) -> list[DatasetSummary]:
    return fetch_datasets(db)


@router.get("/{dataset_id}/timeseries", response_model=list[TimeSeriesPoint])
def get_timeseries(
    dataset_id: int,
    limit: int = Query(default=500, ge=1, le=5000),
    db: Session = Depends(get_db),
) -> list[TimeSeriesPoint]:
    return fetch_dataset_timeseries(db, dataset_id=dataset_id, limit=limit)


@router.get("/{dataset_id}/anomalies", response_model=list[AnomalySummary])
def get_anomalies(
    dataset_id: int,
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[AnomalySummary]:
    return fetch_dataset_anomalies(db, dataset_id=dataset_id, limit=limit)


@router.get("/{dataset_id}/leading-indicators", response_model=list[LeadingIndicatorRecord])
def get_leading_indicators(
    dataset_id: int,
    limit: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db),
) -> list[LeadingIndicatorRecord]:
    return fetch_dataset_leading_indicators(db, dataset_id=dataset_id, limit=limit)
