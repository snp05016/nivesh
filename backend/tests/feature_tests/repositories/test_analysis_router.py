import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from routers.analysis import router

app = FastAPI()
app.include_router(router)

client = TestClient(app)

@patch("routers.analysis.yf.Ticker")
@patch("routers.analysis._dcache_get")
@patch("routers.analysis._dcache_set")
def test_quick_info_cache_miss(mock_set, mock_get, mock_ticker):
    mock_get.return_value = None
    
    mock_tk = MagicMock()
    mock_tk.info = {"currentPrice": 100, "longName": "Reliance Industries"}
    import pandas as pd
    mock_tk.history.return_value = pd.DataFrame({"Close": [100], "Volume": [1000]}, index=pd.to_datetime(["2026-01-01"]))
    mock_ticker.return_value = mock_tk
    
    res = client.get("/quick-info?ticker=RELIANCE")
    assert res.status_code == 200
    data = res.json()
    assert data["ticker"] == "RELIANCE"
    assert data["company_name"] == "Reliance Industries"
    assert data["current_price"] == 100

@patch("routers.analysis._dcache_get")
def test_quick_info_cache_hit(mock_get):
    mock_get.return_value = {"ticker": "RELIANCE", "company_name": "Reliance Cache"}
    
    res = client.get("/quick-info?ticker=RELIANCE")
    assert res.status_code == 200
    assert res.json()["company_name"] == "Reliance Cache"

@patch("routers.analysis.database.create_job")
@patch("services.job_manager.spawn_job")
def test_analyze_endpoint(mock_spawn_job, mock_create_job):
    mock_create_job.return_value = {"job_id": "job123"}
    
    with patch("routers.analysis.get_analysis_for_date") as mock_get_analysis:
        mock_get_analysis.return_value = None  # Cache miss
        with patch("routers.analysis.get_session") as mock_session_ctx:
            mock_session_ctx.return_value.__enter__.return_value = MagicMock()
            
            with patch("routers.analysis.database.get_active_job_for_user_and_type") as mock_active:
                mock_active.return_value = None
                
                res = client.post("/analyze", json={
                    "ticker": "RELIANCE",
                    "exchange": "NSE",
                    "scan_type": "standard",
                    "deep_scan": False
                })
                
                assert res.status_code == 202
                data = res.json()
                assert data["job_id"] == "job123"
                assert data["status"] == "QUEUED"

@patch("routers.analysis.database.get_job")
def test_get_job_status(mock_get_job):
    mock_get_job.return_value = {"job_id": "job123", "status": "SUCCEEDED"}
    
    res = client.get("/analyze/job/job123")
    assert res.status_code == 200
    assert res.json()["status"] == "SUCCEEDED"
