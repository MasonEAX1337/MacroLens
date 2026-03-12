from fastapi import APIRouter

from app.api.routes import anomalies, datasets


api_router = APIRouter()
api_router.include_router(datasets.router, prefix="/datasets", tags=["datasets"])
api_router.include_router(anomalies.router, prefix="/anomalies", tags=["anomalies"])
