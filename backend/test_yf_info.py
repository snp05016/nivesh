import logging
"""
Test script to fetch and print basic ticker information using yfinance.
"""
import yfinance as yf
from pprint import pprint

try:
    ticker = yf.Ticker("RELIANCE.NS")
    info = ticker.info
    logging.info("KEYS:", info.keys())
    logging.info("currentPrice:", info.get("currentPrice"))
    logging.info("regularMarketPrice:", info.get("regularMarketPrice"))
    logging.info("previousClose:", info.get("previousClose"))
except Exception as e:
    logging.info("ERROR:", e)
