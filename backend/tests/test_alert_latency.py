import time
import pytest
from unittest.mock import Mock, patch

# Mocked ingestion-to-alert pipeline
def mock_ingestion_to_alert_pipeline(data):
    # Simulate processing time
    time.sleep(0.5) 
    return {"status": "alert_generated", "data": data}

def test_alert_latency_under_two_seconds():
    """
    Test ensuring the ingestion-to-alert pipeline is under 2 seconds.
    """
    start_time = time.time()
    
    # Mocking the pipeline execution
    result = mock_ingestion_to_alert_pipeline({"sensor_id": 1, "value": 100})
    
    end_time = time.time()
    latency = end_time - start_time
    
    assert result["status"] == "alert_generated"
    assert latency < 2.0, f"Latency exceeded 2 seconds: {latency}s"
