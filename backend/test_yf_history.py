import yfinance as yf
import pandas as pd

def _yf_price(ticker_sym: str):
    def _fetch(sym: str):
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
            print(f"[YF Price Error] {sym}: {e}")
            return None, None

    current, prev = _fetch(ticker_sym)
    if current is None and ticker_sym.upper().endswith(".BO"):
        ns_sym = ticker_sym[:-3] + ".NS"
        print(f"[BSE FALLBACK] No data for {ticker_sym}, trying {ns_sym}")
        current, prev = _fetch(ns_sym)
    return current, prev

print("ICICIBANK.NS:", _yf_price("ICICIBANK.NS"))
print("RELIANCE.NS:", _yf_price("RELIANCE.NS"))
print("SUZLON.NS:", _yf_price("SUZLON.NS"))
