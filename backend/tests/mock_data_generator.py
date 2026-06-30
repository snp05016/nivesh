import random
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any

def generate_mock_stock_price(symbol: str, base_price: float = 100.0) -> Dict[str, Any]:
    """Generates a mock current stock price."""
    volatility = 0.02
    change = base_price * volatility * (random.random() - 0.5)
    current_price = base_price + change
    return {
        "symbol": symbol,
        "price": round(current_price, 2),
        "timestamp": datetime.utcnow().isoformat(),
        "currency": "USD"
    }

def generate_mock_historical_data(symbol: str, days: int = 30, base_price: float = 100.0) -> List[Dict[str, Any]]:
    """Generates mock historical price data for a given number of days."""
    history = []
    current_price = base_price
    for i in range(days):
        date = datetime.utcnow() - timedelta(days=days - i - 1)
        # Random walk
        change = current_price * 0.05 * (random.random() - 0.5)
        current_price += change
        history.append({
            "date": date.strftime("%Y-%m-%d"),
            "close": round(current_price, 2),
            "high": round(current_price * (1 + random.random() * 0.02), 2),
            "low": round(current_price * (1 - random.random() * 0.02), 2),
            "open": round(current_price + (change / 2), 2),
            "volume": int(random.random() * 1000000)
        })
    return history

def generate_mock_company_info(symbol: str) -> Dict[str, Any]:
    """Generates mock company profile information."""
    return {
        "symbol": symbol,
        "company_name": f"{symbol} Corp Mock",
        "industry": random.choice(["Technology", "Healthcare", "Finance", "Consumer Goods"]),
        "market_cap": round(random.uniform(1e9, 2e12), 2),
        "description": f"A mock description for {symbol}."
    }

def generate_mock_news(symbol: str, count: int = 5) -> List[Dict[str, Any]]:
    """Generates mock news articles for a symbol."""
    news = []
    for i in range(count):
        news.append({
            "id": str(uuid.uuid4()),
            "symbol": symbol,
            "headline": f"Mock News Headline {i+1} for {symbol}",
            "summary": f"This is a mock summary of the news article {i+1} concerning {symbol}.",
            "published_at": (datetime.utcnow() - timedelta(hours=random.randint(1, 48))).isoformat(),
            "source": random.choice(["Mock Reuters", "Mock Bloomberg", "Mock CNBC"])
        })
    return news


class MockMarketDataClient:
    """
    A mock client that can be used to replace the real market data client 
    in FastAPI dependency overrides to prevent hitting live APIs during tests.
    """
    def __init__(self):
        self._prices = {}
        
    async def get_current_price(self, symbol: str) -> Dict[str, Any]:
        if symbol not in self._prices:
            self._prices[symbol] = random.uniform(50, 500)
        return generate_mock_stock_price(symbol, self._prices[symbol])
        
    async def get_historical_data(self, symbol: str, days: int = 30) -> List[Dict[str, Any]]:
        base_price = self._prices.get(symbol, random.uniform(50, 500))
        return generate_mock_historical_data(symbol, days, base_price)
        
    async def get_company_info(self, symbol: str) -> Dict[str, Any]:
        return generate_mock_company_info(symbol)
        
    async def get_news(self, symbol: str) -> List[Dict[str, Any]]:
        return generate_mock_news(symbol)

# --- FastAPI Dependency Override Example ---
#
# from fastapi.testclient import TestClient
# from main import app
# from dependencies import get_market_data_client
#
# def override_get_market_data_client():
#     return MockMarketDataClient()
#
# app.dependency_overrides[get_market_data_client] = override_get_market_data_client
# client = TestClient(app)
