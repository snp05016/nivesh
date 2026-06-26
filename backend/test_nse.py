import logging
"""
Test script for testing HTTP requests to the NSE India API using a custom session and headers.
"""
import requests
s = requests.Session()
s.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://www.nseindia.com/"
})
s.get("https://www.nseindia.com", timeout=5)
r = s.get("https://www.nseindia.com/api/historical/bulk-deals", timeout=5)
logging.info(r.text[:200])
