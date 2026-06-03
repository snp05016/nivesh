import yfinance as yf
t = yf.Ticker("RELIANCE.NS")
print("News directly from yf:", t.news)
