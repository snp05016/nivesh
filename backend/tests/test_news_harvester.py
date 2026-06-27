"""
Unit tests for news harvester: market relevance filter, ticker extraction, dedup.
"""
import pytest
from unittest.mock import MagicMock


# ── Market Relevance Filter ────────────────────────────────────────────────

def test_is_market_relevant_accepts_stock_headlines():
    from services.news_harvester import is_market_relevant
    assert is_market_relevant("Nifty 50 surges 2% on FII buying, Sensex at record high")
    assert is_market_relevant("HDFC Bank Q1 profit rises 20%, beats estimates")
    assert is_market_relevant("Reliance AGM: Mukesh Ambani announces new energy business")
    assert is_market_relevant("RBI cuts repo rate by 25 bps to boost growth")


def test_is_market_relevant_rejects_non_financial():
    from services.news_harvester import is_market_relevant
    assert not is_market_relevant("India wins cricket world cup final")
    assert not is_market_relevant("Bollywood actor launches new restaurant in Mumbai")
    assert not is_market_relevant("Weather forecast: heavy rains expected in Kerala")


def test_is_market_relevant_accepts_sector_specific():
    from services.news_harvester import is_market_relevant
    assert is_market_relevant("Pharma sector sees 15% growth in exports")
    assert is_market_relevant("Real estate demand surges in tier-2 cities")


def test_is_market_relevant_empty_text_returns_false():
    from services.news_harvester import is_market_relevant
    assert not is_market_relevant("")


# ── Ticker Extraction ──────────────────────────────────────────────────────

def test_extract_tickers_returns_list():
    """extract_tickers_from_text returns a list (may be empty without DB)."""
    from services.news_harvester import extract_tickers_from_text
    result = extract_tickers_from_text("RELIANCE and TCS lead the market rally", MagicMock())
    assert isinstance(result, list)


def test_extract_tickers_empty_text():
    """Empty text should return empty list."""
    from services.news_harvester import extract_tickers_from_text
    assert extract_tickers_from_text("", MagicMock()) == []


# ── Content Filter ─────────────────────────────────────────────────────────

def test_harvest_news_skips_non_market_articles():
    from services.news_harvester import is_market_relevant
    assert not is_market_relevant("Local municipality election results declared today")


def test_harvest_news_accepts_ipo_news():
    from services.news_harvester import is_market_relevant
    assert is_market_relevant("Tata Technologies IPO subscribed 69 times on final day")
    assert is_market_relevant("LIC listing: shares debut at 8% discount to issue price")
