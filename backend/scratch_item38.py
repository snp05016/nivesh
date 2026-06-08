import yfinance as yf
from datetime import datetime, timedelta
import json
import gzip
from database import AnalysisHistory, get_session
import logging

async def check_signal_outcomes():
    try:
        with get_session() as db:
            cutoff = datetime.utcnow() - timedelta(days=30)
            pending = (
                db.query(AnalysisHistory)
                .filter(AnalysisHistory.was_correct == None)
                .filter(AnalysisHistory.created_at < cutoff)
                .limit(50)
                .all()
            )
            for row in pending:
                try:
                    info = yf.Ticker(row.ticker).info
                    current_price = info.get('currentPrice') or info.get('regularMarketPrice')
                    if not current_price:
                        continue
                    
                    raw = row.full_json
                    if isinstance(raw, (bytes, bytearray, memoryview)):
                        report = json.loads(gzip.decompress(bytes(raw)))
                    else:
                        report = json.loads(raw)
                    
                    price_at_signal_date = report.get("current_price") or report.get("price")
                    if not price_at_signal_date:
                        continue
                    
                    outcome_delta_pct = (current_price - price_at_signal_date) / price_at_signal_date * 100
                    row.outcome_delta_pct = outcome_delta_pct
                    row.outcome_checked_at = datetime.utcnow()
                    
                    signal = row.signal.upper() if row.signal else "HOLD"
                    if signal == "BUY" and outcome_delta_pct > 0:
                        row.was_correct = True
                    elif signal == "SELL" and outcome_delta_pct < 0:
                        row.was_correct = True
                    elif signal == "HOLD" and abs(outcome_delta_pct) < 5:
                        row.was_correct = True
                    else:
                        row.was_correct = False
                        
                except Exception as e:
                    logging.error(f"Error checking outcome for {row.ticker}: {e}")
                    
            db.commit()
    except Exception as e:
        logging.error(f"Error in check_signal_outcomes: {e}")
