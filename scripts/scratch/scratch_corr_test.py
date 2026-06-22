import sys
import asyncio

# Setup path so we can import from backend
sys.path.append("/Users/saumya/Desktop/nivesh/backend")

from services.correlation_engine import compute_portfolio_correlation

class MockHolding:
    def __init__(self, ticker, shares, buy_price):
        self.ticker = ticker
        self.shares = shares
        self.buy_price = buy_price

holdings = [
    MockHolding("TCS", 10, 3000),
    MockHolding("RELIANCE", 5, 2500)
]

try:
    result = compute_portfolio_correlation(holdings)
    print("SUCCESS")
    print(result)
except Exception as e:
    print("ERROR")
    import traceback
    traceback.print_exc()
