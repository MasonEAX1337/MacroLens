from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.api import AnomalyDetail
from app.services.repository import fetch_anomaly_detail


router = APIRouter()


@router.get("/{anomaly_id}", response_model=AnomalyDetail)
def get_anomaly(anomaly_id: int, db: Session = Depends(get_db)) -> AnomalyDetail:
    return fetch_anomaly_detail(db, anomaly_id=anomaly_id)
