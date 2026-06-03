import pytest
import os
import sys
import json
from unittest.mock import MagicMock, patch

# Add current directory to sys.path to allow imports like 'database' or 'services'
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from database import Base, User, Portfolio

# Mocking external services globally for the test suite
@pytest.fixture(autouse=True)
def mock_external_apis():
    # Using the same names that main.py and other services use
    with patch("services.sentiment_engine.score_articles_batch") as mock_sentiment, \
         patch("services.news_harvester.harvest_news") as mock_news, \
         patch("services.youtube_harvester.harvest_youtube_metadata") as mock_youtube, \
         patch("services.advisor_harvester.harvest_all_advisors") as mock_advisor, \
         patch("services.nse_data_provider.get_price_history") as mock_nse_history, \
         patch("services.nse_data_provider.get_fundamentals") as mock_nse_funds, \
         patch("services.scraper.fetch_market_pulse") as mock_scraper, \
         patch("yfinance.Ticker") as mock_yf, \
         patch("requests.get") as mock_get, \
         patch("requests.post") as mock_post, \
         patch("main._check_rate_limit") as mock_rate_limit:
        
        # Setup basic mock returns to prevent crashes
        mock_yf.return_value.info = {"regularMarketPrice": 100.0, "shortName": "Mock Stock"}
        mock_yf.return_value.history.return_value = MagicMock()
        
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {}
        
        mock_rate_limit.return_value = True # Always allow
        
        yield {
            "sentiment": mock_sentiment,
            "news": mock_news,
            "youtube": mock_youtube,
            "advisor": mock_advisor,
            "nse_history": mock_nse_history,
            "nse_funds": mock_nse_funds,
            "scraper": mock_scraper,
            "yf": mock_yf
        }

@pytest.fixture
def db_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from database import get_session
    from main import app
    
    # Use in-memory SQLite for speed and isolation
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Dependency override for FastAPI
    def override_get_session():
        try:
            yield session
        finally:
            pass # Keep it open for the duration of the fixture
            
    # Note: main.py might not use app.dependency_overrides if it calls get_session() directly
    # We might need to patch database.get_session
    with patch("database.get_session", side_effect=lambda: session):
        # Seed a test user
        from database import User, _hash_password
        test_user = User(username="testuser", password_hash=_hash_password("password"), display_name="Test User")
        session.add(test_user)
        session.commit()
        
        yield session
        session.close()
        Base.metadata.drop_all(engine)

@pytest.fixture
def test_user(db_session):
    from database import User
    return db_session.query(User).filter_by(username="testuser").first()
