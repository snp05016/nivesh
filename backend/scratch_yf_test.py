import yfinance as yf
import pandas as pd
import numpy as np

tickers = ["RELIANCE", "TCS", "^NSEI"]
yf_tickers = ["RELIANCE.NS", "TCS.NS", "^NSEI"]
data = yf.download(yf_tickers, period="1y", interval="1d", progress=False)
print("Data columns:", data.columns)

prices = pd.DataFrame()
if isinstance(data.columns, pd.MultiIndex):
    for t in yf_tickers:
        if t in data.columns.levels[1]:
            prices[t] = data['Close'][t]
else:
    # Single ticker or different format
    if len(yf_tickers) == 1:
        prices[yf_tickers[0]] = data['Close']

print("Prices head:")
print(prices.head())

# Compute daily returns
returns = prices.pct_change().dropna()
print("Returns head:")
print(returns.head())

# Correlation matrix
corr_matrix = returns.corr()
print("Correlation matrix:")
print(corr_matrix)
