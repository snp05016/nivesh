"""
Prediction Outcome Tracker

Nightly job to calculate actual returns for past predictions and compute 
hit rates and Brier scores for the ML feedback loop.
"""

from datetime import datetime, timezone, timedelta
import logging
import yfinance as yf
from database import get_session
from models.db_models import AnalysisPrediction

_LOG = logging.getLogger(__name__)

def update_prediction_outcomes(dry_run: bool = False) -> dict:
    """Calculates actual returns for predictions where the horizon has passed."""
    _LOG.info(f"Starting prediction outcome tracking (dry_run={dry_run})...")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    
    summary = {
        "eligible_predictions": 0,
        "updates_7d": 0,
        "updates_30d": 0,
        "updates_90d": 0,
        "missing_price_data": 0,
        "processed_symbols": 0
    }
    
    with get_session() as session:
        # We look for predictions that are at least 7 days old and lack 7d returns,
        # or 30 days old and lack 30d returns, or 90 days old and lack 90d returns.
        preds = session.query(AnalysisPrediction).filter(
            (AnalysisPrediction.actual_return_7d == None) |
            (AnalysisPrediction.actual_return_30d == None) |
            (AnalysisPrediction.actual_return_90d == None)
        ).all()
        
        summary["eligible_predictions"] = len(preds)
        
        # Group by symbol to batch yfinance calls
        symbol_map = {}
        for p in preds:
            symbol_map.setdefault(p.symbol, []).append(p)
            
        summary["processed_symbols"] = len(symbol_map)
            
        for symbol, pred_list in symbol_map.items():
            try:
                ticker_obj = yf.Ticker(f"{symbol}.NS")
                # Fetch last 2 years of data to back-calculate older predictions
                hist = ticker_obj.history(period="2y")
                if hist.empty:
                    summary["missing_price_data"] += 1
                    continue
                
                # Make tz-naive
                hist.index = hist.index.tz_localize(None)
                
                for p in pred_list:
                    age_days = (now - p.created_at).days
                    
                    # Need price at created_at. If entry_price is missing, try to find it.
                    entry_price = p.entry_price
                    if entry_price is None or entry_price <= 0:
                        # Find closest price on or before created_at
                        past_df = hist[hist.index <= p.created_at]
                        if not past_df.empty:
                            entry_price = past_df.iloc[-1]['Close']
                        else:
                            continue
                            
                    # Calculate 7d return
                    if age_days >= 7 and p.actual_return_7d is None:
                        target_date = p.created_at + timedelta(days=7)
                        future_df = hist[hist.index >= target_date]
                        if not future_df.empty:
                            price_7d = future_df.iloc[0]['Close']
                            p.actual_return_7d = (price_7d - entry_price) / entry_price
                            summary["updates_7d"] += 1
                            
                            actual_dir = 1 if p.actual_return_7d > 0 else (-1 if p.actual_return_7d < 0 else 0)
                            pred_dir = 1 if p.recommendation == "BULLISH" else (-1 if p.recommendation == "BEARISH" else 0)
                            if pred_dir != 0:
                                p.hit_direction_7d = (actual_dir == pred_dir)
                                outcome = 1.0 if p.hit_direction_7d else 0.0
                                conf_normalized = p.confidence_pct / 100.0
                                p.brier_score_7d = (conf_normalized - outcome) ** 2
                            
                    # Calculate 30d return
                    if age_days >= 30 and p.actual_return_30d is None:
                        target_date = p.created_at + timedelta(days=30)
                        future_df = hist[hist.index >= target_date]
                        if not future_df.empty:
                            price_30d = future_df.iloc[0]['Close']
                            p.actual_return_30d = (price_30d - entry_price) / entry_price
                            summary["updates_30d"] += 1
                            
                            # Hit direction: BULLISH must be > 0, BEARISH must be < 0
                            actual_dir = 1 if p.actual_return_30d > 0 else (-1 if p.actual_return_30d < 0 else 0)
                            pred_dir = 1 if p.recommendation == "BULLISH" else (-1 if p.recommendation == "BEARISH" else 0)
                            
                            if pred_dir != 0:
                                p.hit_direction_30d = (actual_dir == pred_dir)
                                
                                # Brier score: (confidence - outcome)^2
                                # Let outcome = 1 if hit, 0 if miss
                                outcome = 1.0 if p.hit_direction_30d else 0.0
                                conf_normalized = p.confidence_pct / 100.0
                                p.brier_score_30d = (conf_normalized - outcome) ** 2
                                
                    # Calculate 90d return
                    if age_days >= 90 and p.actual_return_90d is None:
                        target_date = p.created_at + timedelta(days=90)
                        future_df = hist[hist.index >= target_date]
                        if not future_df.empty:
                            price_90d = future_df.iloc[0]['Close']
                            p.actual_return_90d = (price_90d - entry_price) / entry_price
                            summary["updates_90d"] += 1
                            
                            actual_dir = 1 if p.actual_return_90d > 0 else (-1 if p.actual_return_90d < 0 else 0)
                            pred_dir = 1 if p.recommendation == "BULLISH" else (-1 if p.recommendation == "BEARISH" else 0)
                            if pred_dir != 0:
                                p.hit_direction_90d = (actual_dir == pred_dir)
                                outcome = 1.0 if p.hit_direction_90d else 0.0
                                conf_normalized = p.confidence_pct / 100.0
                                p.brier_score_90d = (conf_normalized - outcome) ** 2
                            
                if dry_run:
                    session.rollback()
                else:
                    session.commit()
            except Exception as e:
                _LOG.error(f"Error processing outcome for {symbol}: {e}")
                session.rollback()
                
    _LOG.info(f"Finished prediction outcome tracking. Summary: {summary}")
    return summary
