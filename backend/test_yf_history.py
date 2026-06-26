import logging
"""
Test script to verify historical data fetching using yfinance with fallback mechanisms.
"""
import yfinance as yf
import pandas as pd

def _yf_price(ticker_sym: str):
    """
    Fetches the current and previous closing prices for a given ticker symbol using yfinance.

    Args:
        ticker_sym (str): The ticker symbol to query.

    Returns:
        tuple: A tuple containing (current_price, previous_price), or (None, None) if unavailable.
    """
    def _fetch(sym: str):
        """
        Helper to fetch recent history for a symbol and extract closing prices.

        Args:
            sym (str): The specific symbol to fetch data for.

        Returns:
            tuple: A tuple of (current_price, previous_price).
        """
        try:
            hist = yf.Ticker(sym).history(period="5d")
            if hist.empty:
                return None, None
            if isinstance(hist.columns, pd.MultiIndex):
                hist.columns = [c[0] for c in hist.columns]
            
            closes = hist["Close"].dropna().values
            if len(closes) == 0:
                return None, None
            
            current = float(closes[-1])
            prev = float(closes[-2]) if len(closes) >= 2 else current
            return current, prev
        except Exception as e:
            logging.info(f"[YF Price Error] {sym}: {e}")
            return None, None

    current, prev = _fetch(ticker_sym)
    if current is None and ticker_sym.upper().endswith(".BO"):
        ns_sym = ticker_sym[:-3] + ".NS"
        logging.info(f"[BSE FALLBACK] No data for {ticker_sym}, trying {ns_sym}")
        current, prev = _fetch(ns_sym)
    return current, prev

logging.info("ICICIBANK.NS:", _yf_price("ICICIBANK.NS"))
logging.info("RELIANCE.NS:", _yf_price("RELIANCE.NS"))
logging.info("SUZLON.NS:", _yf_price("SUZLON.NS"))
