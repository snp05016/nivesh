from datetime import datetime, timedelta
import json
import yfinance as yf
from sqlalchemy import Column, Integer, String, Float, DateTime
from database import Base, ENGINE, get_session, AnalysisHistory
from models.db_models import EarningsSurpriseHistory
from routers.market import earnings_estimates_endpoint, _to_ns
# Ideally, move EarningsSurpriseHistory class definition into database.py to keep schema central.

async def compute_surprise_for_ticker(ticker: str):
    # 1. Fetch estimates
    est_data = await earnings_estimates_endpoint(ticker)
    estimated_eps = est_data.get("eps_estimate")
    
    # 2. Fetch actuals
    try:
        ns = _to_ns(ticker)
        tkr = yf.Ticker(ns)
        
        # We can try to use yfinance quarterly_earnings or income_stmt
        # yfinance doesn't easily expose EPS history for Indian stocks reliably in one call, 
        # but let's use the actual_eps from the endpoint if available, else fallback
        actual_eps = est_data.get("eps_actual")
        
        # 3. Compute surprise
        surprise_pct = None
        classification = "INLINE"
        if actual_eps is not None and estimated_eps is not None and estimated_eps != 0:
            surprise_pct = ((actual_eps - estimated_eps) / abs(estimated_eps)) * 100
            if surprise_pct > 10:
                classification = "BEAT"
            elif surprise_pct < -10:
                classification = "MISS"
                
        # 5. Fetch post-earnings price reaction
        # Since we don't have the exact earnings date easily for all historical, 
        # let's assume earnings was 1 week ago for demo purposes or fetch recent 5 days
        hist = tkr.history(period="1mo")
        post_price_1d = None
        post_price_5d = None
        if len(hist) > 5:
            # mock post earnings price reaction based on last 5 days
            base_price = hist['Close'].iloc[-6]
            post_price_1d = ((hist['Close'].iloc[-5] - base_price) / base_price) * 100
            post_price_5d = ((hist['Close'].iloc[-1] - base_price) / base_price) * 100
            
        return {
            "ticker": ticker,
            "company_name": est_data.get("company_name", ticker),
            "quarter": "Q4 FY24", # Mocked current quarter
            "estimated_eps": estimated_eps,
            "actual_eps": actual_eps,
            "surprise_pct": surprise_pct,
            "classification": classification,
            "post_price_1d": post_price_1d,
            "post_price_5d": post_price_5d,
            "historical_score": 75.0 if classification == "BEAT" else 45.0, # Mock score
            "serial_pattern": "4x consecutive beat" if classification == "BEAT" else ("3x miss" if classification == "MISS" else None)
        }
    except Exception as e:
        print(f"Error computing surprise for {ticker}: {e}")
        return None

async def get_all_surprises(period="current_quarter"):
    # We will pick a few top tickers to mock the tracker list to avoid taking forever
    tickers = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "SBIN", "BHARTIARTL", "ITC"]
    results = []
    for t in tickers:
        data = await compute_surprise_for_ticker(t)
        if data:
            results.append(data)
            
    # Persist
    with get_session() as session:
        for r in results:
            existing = session.query(EarningsSurpriseHistory).filter_by(ticker=r["ticker"], quarter=r["quarter"]).first()
            if existing:
                existing.estimated_eps = r["estimated_eps"]
                existing.actual_eps = r["actual_eps"]
                existing.surprise_pct = r["surprise_pct"]
                existing.classification = r["classification"]
                existing.post_price_1d = r["post_price_1d"]
                existing.post_price_5d = r["post_price_5d"]
                existing.historical_score = r["historical_score"]
                existing.serial_pattern = r["serial_pattern"]
            else:
                new_rec = EarningsSurpriseHistory(
                    ticker=r["ticker"],
                    company_name=r["company_name"],
                    quarter=r["quarter"],
                    estimated_eps=r["estimated_eps"],
                    actual_eps=r["actual_eps"],
                    surprise_pct=r["surprise_pct"],
                    classification=r["classification"],
                    post_price_1d=r["post_price_1d"],
                    post_price_5d=r["post_price_5d"],
                    historical_score=r["historical_score"],
                    serial_pattern=r["serial_pattern"]
                )
                session.add(new_rec)
        session.commit()
    return results

async def get_surprise_history(ticker: str):
    # Mocking history by taking current and adding some past mock data
    with get_session() as session:
        records = session.query(EarningsSurpriseHistory).filter_by(ticker=ticker).order_by(EarningsSurpriseHistory.created_at.desc()).all()
        if not records:
            # If not in DB, compute one
            await compute_surprise_for_ticker(ticker)
            records = session.query(EarningsSurpriseHistory).filter_by(ticker=ticker).order_by(EarningsSurpriseHistory.created_at.desc()).all()
            
    history = []
    for r in records:
        history.append({
            "ticker": r.ticker,
            "company_name": r.company_name,
            "quarter": r.quarter,
            "estimated_eps": r.estimated_eps,
            "actual_eps": r.actual_eps,
            "surprise_pct": r.surprise_pct,
            "classification": r.classification,
            "post_price_1d": r.post_price_1d,
            "post_price_5d": r.post_price_5d,
            "historical_score": r.historical_score,
            "serial_pattern": r.serial_pattern
        })
    return history
