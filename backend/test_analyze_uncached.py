import logging
import os
import asyncio
from services.orchestrator import analyze

result = analyze('BAJFINANCE', 'NSE', 1, deep_scan=True)
logging.info(result['signal'])
