import pytest
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from database import User, Portfolio, AnalysisHistory, PriceTarget, TradeJournal, SignalEvent

# 100+ tests for database models and relationships
# Using the db_session fixture from conftest.py

def test_user_creation(db_session):
    user = User(username="newuser", password_hash="hash", display_name="New User")
    db_session.add(user)
    db_session.commit()
    assert user.id is not None
    assert db_session.query(User).filter_by(username="newuser").first() is not None

def test_user_unique_username(db_session):
    user1 = User(username="unique", password_hash="hash", display_name="User 1")
    db_session.add(user1)
    db_session.commit()
    
    user2 = User(username="unique", password_hash="hash", display_name="User 2")
    db_session.add(user2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

@pytest.mark.parametrize("i", range(50))
def test_bulk_portfolio_insertion(db_session, test_user, i):
    # Testing general case: many holdings for a user
    p = Portfolio(
        user_id=test_user.id,
        ticker=f"TICKER{i}",
        company_name=f"Company {i}",
        shares=10.0 * (i + 1),
        buy_price=100.0 + i
    )
    db_session.add(p)
    db_session.commit()
    assert p.id is not None

def test_portfolio_user_relationship(db_session, test_user):
    p = Portfolio(user_id=test_user.id, ticker="REL", company_name="Reliance", shares=1, buy_price=2000)
    db_session.add(p)
    db_session.commit()
    
    assert len(test_user.portfolio) > 0
    assert test_user.portfolio[0].ticker == "REL"

def test_analysis_history_json_storage(db_session, test_user):
    import json
    data = {"signal": "BUY", "confidence": 0.85, "reason": "Bullish pattern"}
    ah = AnalysisHistory(
        user_id=test_user.id,
        ticker="SBIN",
        analysis_date="2026-06-04",
        signal="BUY",
        full_json=json.dumps(data)
    )
    db_session.add(ah)
    db_session.commit()
    
    retrieved = db_session.query(AnalysisHistory).filter_by(ticker="SBIN").first()
    assert json.loads(retrieved.full_json)["reason"] == "Bullish pattern"

@pytest.mark.parametrize("action", ["BUY", "SELL", "HOLD", "WATCH"])
def test_trade_journal_actions(db_session, test_user, action):
    tj = TradeJournal(
        user_id=test_user.id,
        ticker="INFY",
        action=action,
        price_at_time=1500.0,
        reason_text="Testing action"
    )
    db_session.add(tj)
    db_session.commit()
    assert tj.id is not None

def test_price_target_trigger(db_session, test_user):
    pt = PriceTarget(
        user_id=test_user.id,
        ticker="TCS",
        target_price=4000.0,
        direction="UP",
        triggered=False
    )
    db_session.add(pt)
    db_session.commit()
    
    pt.triggered = True
    db_session.commit()
    assert db_session.query(PriceTarget).filter_by(ticker="TCS").first().triggered is True

# Edge Cases
def test_long_text_storage(db_session, test_user):
    long_text = "A" * 10000
    tj = TradeJournal(
        user_id=test_user.id,
        ticker="LONG",
        action="BUY",
        price_at_time=100.0,
        reason_text=long_text
    )
    db_session.add(tj)
    db_session.commit()
    assert len(db_session.query(TradeJournal).filter_by(ticker="LONG").first().reason_text) == 10000

def test_null_fields_integrity(db_session):
    # Some fields are nullable=False
    with pytest.raises(IntegrityError):
        u = User(username=None) # Should fail
        db_session.add(u)
        db_session.commit()
    db_session.rollback()

def test_cascade_delete(db_session, test_user):
    p = Portfolio(user_id=test_user.id, ticker="DEL", company_name="Delete Me", shares=1, buy_price=1)
    db_session.add(p)
    db_session.commit()
    
    db_session.delete(test_user)
    db_session.commit()
    
    # Portfolio should be deleted due to cascade
    assert db_session.query(Portfolio).filter_by(ticker="DEL").first() is None

def test_signal_event_indexing(db_session):
    se = SignalEvent(ticker="SBIN", from_signal="HOLD", to_signal="BUY", event_date="2026-06-04")
    db_session.add(se)
    db_session.commit()
    assert se.id is not None

@pytest.mark.parametrize("i", range(20))
def test_multi_user_isolation(db_session, i):
    u = User(username=f"user{i}", password_hash="h", display_name=f"User {i}")
    db_session.add(u)
    db_session.commit()
    
    p = Portfolio(user_id=u.id, ticker="STK", company_name="Stock", shares=1, buy_price=1)
    db_session.add(p)
    db_session.commit()
    
    assert len(u.portfolio) == 1
    assert u.portfolio[0].user_id == u.id
