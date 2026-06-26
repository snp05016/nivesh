import logging
"""
Test script for executing an analysis via the orchestrator and printing the JSON result.
"""
import json
from services.orchestrator import analyze

result = analyze("SUZLON", "NSE")
logging.info(json.dumps(result, indent=2, ensure_ascii=False))
