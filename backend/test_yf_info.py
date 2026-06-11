import yfinance as yf
from pprint import pprint

try:
    ticker = yf.Ticker("RELIANCE.NS")
    info = ticker.info
    print("KEYS:", info.keys())
    print("currentPrice:", info.get("currentPrice"))
    print("regularMarketPrice:", info.get("regularMarketPrice"))
    print("previousClose:", info.get("previousClose"))
except Exception as e:
    print("ERROR:", e)
