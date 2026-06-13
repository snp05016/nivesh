from fastapi import APIRouter, Query
from typing import List, Dict, Any
from services.anomaly_scanner import get_latest_anomalies

router = APIRouter(prefix="/api/v1/market", tags=["anomalies"])

@router.get("/anomalies", response_model=List[Dict[str, Any]])
def read_anomalies(limit: int = Query(10, description="Max anomalies to return")):
    """
    Get the latest market anomalies, sorted by severity.
    """
    return get_latest_anomalies(limit=limit)
