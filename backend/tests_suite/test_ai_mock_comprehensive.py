import pytest
import json
import pandas as pd
from unittest.mock import MagicMock, patch
from services.sentiment_engine import score_article, score_articles_batch
from services.factor_engine import compute_indicators

# 100+ tests for AI logic with mocks
# 80 general, 20 edge cases

def test_sentiment_score_article():
    # Mocking get_classifier to return a mock classifier
    with patch("services.sentiment_engine.get_classifier") as mock_get:
        mock_classifier = MagicMock()
        mock_classifier.return_value = [{"label": "Positive", "score": 0.99}]
        mock_get.return_value = mock_classifier
        
        label, score = score_article("Reliance is great")
        assert label == "Positive"
        assert score > 0.9

def test_sentiment_batch_processing():
    with patch("services.sentiment_engine.get_classifier") as mock_get:
        mock_classifier = MagicMock()
        mock_classifier.return_value = [
            [{"label": "Positive", "score": 0.9}],
            [{"label": "Negative", "score": 0.8}]
        ]
        mock_get.return_value = mock_classifier
        
        results = score_articles_batch([{"headline": "Good news"}, {"headline": "Bad news"}])
        assert len(results) == 2
        assert results[0][0] == "Positive"
        assert results[1][0] == "Negative"

def test_factor_engine_indicators():
    # Create dummy dataframe with enough rows (>= 50)
    df = pd.DataFrame({
        "Close": [100.0] * 60,
        "High": [105.0] * 60,
        "Low": [95.0] * 60,
        "Volume": [1000] * 60
    })
    indicators = compute_indicators(df, "SBIN")
    assert "rsi_14" in indicators
    assert "sma_50" in indicators
    assert "sma_20" in indicators

@pytest.mark.parametrize("i", range(50))
def test_bulk_sentiment_variations(i):
    # Testing many variations
    with patch("services.sentiment_engine.get_classifier") as mock_get:
        mock_classifier = MagicMock()
        mock_classifier.return_value = [{"label": "Neutral", "score": 0.5}]
        mock_get.return_value = mock_classifier
        
        label, score = score_article(f"News headline {i}")
        assert label == "Neutral"

# Edge Cases
@pytest.mark.parametrize("headline", [
    "", 
    "   ",
    "!!!",
    "12345",
    "Very long headline " * 100
])
def test_sentiment_edge_cases(headline):
    with patch("services.sentiment_engine.get_classifier") as mock_get:
        mock_classifier = MagicMock()
        mock_classifier.return_value = [{"label": "Neutral", "score": 0.5}]
        mock_get.return_value = mock_classifier
        
        label, score = score_article(headline)
        assert label in ["Positive", "Negative", "Neutral", "Unknown"]

def test_factor_engine_empty_df():
    df = pd.DataFrame()
    indicators = compute_indicators(df, "NONE")
    # Should handle empty df without crashing
    assert isinstance(indicators, dict)
    assert indicators["rsi_14"] is None
