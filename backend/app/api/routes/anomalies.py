from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.api import AnomalyDetail
from app.services.explanations import run_explanation_for_anomaly
from app.services.repository import fetch_anomaly_detail


router = APIRouter()


@router.get("/{anomaly_id}", response_model=AnomalyDetail)
def get_anomaly(anomaly_id: int, db: Session = Depends(get_db)) -> AnomalyDetail:
    return fetch_anomaly_detail(db, anomaly_id=anomaly_id)


@router.post("/{anomaly_id}/regenerate-explanation", response_model=AnomalyDetail)
def regenerate_explanation(anomaly_id: int, db: Session = Depends(get_db)) -> AnomalyDetail:
    run_explanation_for_anomaly(db, anomaly_id=anomaly_id)
    db.commit()
    return fetch_anomaly_detail(db, anomaly_id=anomaly_id)
