import os
import asyncio
from main import analyze

result = analyze('BAJFINANCE', 'NSE', 1, deep_scan=True)
print(result['signal'])
