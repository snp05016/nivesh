import logging
"""
Test script for invoking the /analyze endpoint with deep scan and mock options enabled.
"""
import requests

url = "http://localhost:8000/analyze"
payload = {
    "ticker": "WIPRO",
    "exchange": "NSE",
    "deep_scan": True,
    "use_mock": True
}
try:
    logging.info("Calling POST /analyze...")
    res = requests.post(url, json=payload, timeout=30)
    logging.info("Status:", res.status_code)
    logging.info("Response:", res.text[:500])
except Exception as e:
    logging.info("Error:", e)
