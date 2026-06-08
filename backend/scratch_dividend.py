import yfinance as yf
t = yf.Ticker("RELIANCE.NS")
print(t.dividends)
print(t.calendar)
