import logging
from datetime import datetime, date, timedelta
import pandas as pd
from typing import Optional, List, Dict, Any

from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from database import Base, get_session, ENGINE
from helpers import NSE_TICKERS
from services.nse_data_provider import get_price_history, fetch_info, download_bhavcopy
from services.factor_engine import compute_indicators
from services.options_scraper import fetch_option_chain, compute_derivatives_metrics

logger = logging.getLogger(__name__)

class MarketAnomaly(Base):
    __tablename__ = "market_anomalies"
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True)
    company = Column(String, nullable=True)
    anomaly_type = Column(String, index=True)
    severity = Column(String) # HIGH, MEDIUM, LOW
    detail = Column(Text)
    price = Column(Float)
    change_pct = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

# Ensure table exists safely without touching base setup
MarketAnomaly.__table__.create(bind=ENGINE, checkfirst=True)

def _determine_severity(anomaly_type: str, magnitude: float) -> str:
    if anomaly_type == "VOLUME_SPIKE":
        if magnitude > 5: return "HIGH"
        if magnitude > 4: return "MEDIUM"
        return "LOW"
    elif anomaly_type in ("GAP_UP", "GAP_DOWN"):
        if abs(magnitude) > 7: return "HIGH"
        if abs(magnitude) > 5: return "MEDIUM"
        return "LOW"
    elif anomaly_type == "LOW_FLOAT_SURGE":
        if magnitude > 8: return "HIGH"
        if magnitude > 6: return "MEDIUM"
        return "LOW"
    elif anomaly_type == "CONSECUTIVE_DIRECTION":
        if magnitude >= 7: return "HIGH"
        if magnitude == 6: return "MEDIUM"
        return "LOW"
    elif anomaly_type == "UNUSUAL_OPTIONS":
        if magnitude > 2.5 or magnitude < 0.3: return "HIGH"
        if magnitude > 2.0 or magnitude < 0.4: return "MEDIUM"
        return "LOW"
    elif anomaly_type == "DELIVERY_SPIKE":
        if magnitude > 90: return "HIGH"
        if magnitude > 85: return "MEDIUM"
        return "LOW"
    return "MEDIUM"

def _detect_anomalies_for_ticker(ticker: str, company: str, bhavcopy_data: dict) -> List[dict]:
    anomalies = []
    
    df = get_price_history(ticker, period_days=365)
    if df is None or len(df) < 50:
        return anomalies

    curr_close = float(df['Close'].iloc[-1])
    prev_close = float(df['Close'].iloc[-2])
    curr_open = float(df['Open'].iloc[-1])
    curr_vol = float(df['Volume'].iloc[-1])
    
    change_pct = ((curr_close - prev_close) / prev_close) * 100

    vol_20d = df['Volume'].rolling(20).mean().iloc[-2]
    if vol_20d > 0 and curr_vol > 3 * vol_20d:
        mult = curr_vol / vol_20d
        anomalies.append({
            "anomaly_type": "VOLUME_SPIKE",
            "severity": _determine_severity("VOLUME_SPIKE", mult),
            "detail": f"Volume is {mult:.1f}x the 20-day average.",
            "price": curr_close,
            "change_pct": change_pct
        })
    
    delta = df['Close'].diff().dropna()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, pd.NA)
    df['RSI'] = 100 - (100 / (1 + rs))
    
    if pd.notna(df['RSI'].iloc[-1]) and pd.notna(df['RSI'].iloc[-14]):
        price_14d_max = df['Close'].iloc[-14:-1].max()
        price_14d_min = df['Close'].iloc[-14:-1].min()
        
        if curr_close >= price_14d_max and df['RSI'].iloc[-1] < df['RSI'].iloc[-14]:
            anomalies.append({
                "anomaly_type": "RSI_DIVERGENCE",
                "severity": "HIGH",
                "detail": "Bearish divergence: Price making new highs while RSI declines.",
                "price": curr_close,
                "change_pct": change_pct
            })
        elif curr_close <= price_14d_min and df['RSI'].iloc[-1] > df['RSI'].iloc[-14]:
            anomalies.append({
                "anomaly_type": "RSI_DIVERGENCE",
                "severity": "HIGH",
                "detail": "Bullish divergence: Price making new lows while RSI increases.",
                "price": curr_close,
                "change_pct": change_pct
            })

    if change_pct > 5 and curr_vol < df['Volume'].iloc[-2]:
        anomalies.append({
            "anomaly_type": "PRICE_VOLUME_DIVERGENCE",
            "severity": "MEDIUM",
            "detail": f"Price up {change_pct:.1f}% but volume declined from previous day.",
            "price": curr_close,
            "change_pct": change_pct
        })
        
    gap_pct = ((curr_open - prev_close) / prev_close) * 100
    if gap_pct > 3:
        anomalies.append({
            "anomaly_type": "GAP_UP",
            "severity": _determine_severity("GAP_UP", gap_pct),
            "detail": f"Gap up of {gap_pct:.1f}% at open.",
            "price": curr_close,
            "change_pct": change_pct
        })
    elif gap_pct < -3:
        anomalies.append({
            "anomaly_type": "GAP_DOWN",
            "severity": _determine_severity("GAP_DOWN", gap_pct),
            "detail": f"Gap down of {gap_pct:.1f}% at open.",
            "price": curr_close,
            "change_pct": change_pct
        })
        
    chain = fetch_option_chain(ticker, use_cache=True)
    if chain:
        try:
            metrics = compute_derivatives_metrics(chain, curr_close)
            pcr = metrics.get('pcr_oi', 1.0)
            if pcr > 2.0 or pcr < 0.4:
                anomalies.append({
                    "anomaly_type": "UNUSUAL_OPTIONS",
                    "severity": _determine_severity("UNUSUAL_OPTIONS", pcr),
                    "detail": f"Extreme Put-Call Ratio of {pcr:.2f}.",
                    "price": curr_close,
                    "change_pct": change_pct
                })
        except Exception as e:
            logger.debug(f"Option metrics failed for {ticker}: {e}")

    symbol = ticker.replace(".NS", "")
    if symbol in bhavcopy_data:
        delivery_pct = bhavcopy_data[symbol]
        if delivery_pct > 80 and curr_vol > vol_20d:
            anomalies.append({
                "anomaly_type": "DELIVERY_SPIKE",
                "severity": _determine_severity("DELIVERY_SPIKE", delivery_pct),
                "detail": f"Delivery volume spiked to {delivery_pct:.1f}% on high volume.",
                "price": curr_close,
                "change_pct": change_pct
            })

    high_52w = df['High'].iloc[-252:].max() if len(df) >= 252 else df['High'].max()
    low_52w = df['Low'].iloc[-252:].min() if len(df) >= 252 else df['Low'].min()
    if curr_close > high_52w:
        anomalies.append({
            "anomaly_type": "52W_BREAKOUT",
            "severity": "HIGH",
            "detail": "Price broke above 52-week high.",
            "price": curr_close,
            "change_pct": change_pct
        })
    elif curr_close < low_52w:
        anomalies.append({
            "anomaly_type": "52W_BREAKOUT",
            "severity": "HIGH",
            "detail": "Price broke below 52-week low.",
            "price": curr_close,
            "change_pct": change_pct
        })

    direction = 1 if change_pct > 0 else -1
    consecutive = 0
    vol_increasing = True
    for i in range(1, min(10, len(df))):
        day_chg = df['Close'].iloc[-i] - df['Close'].iloc[-(i+1)]
        day_dir = 1 if day_chg > 0 else -1
        if day_dir == direction:
            consecutive += 1
            if i > 1 and df['Volume'].iloc[-i] < df['Volume'].iloc[-(i+1)]:
                vol_increasing = False
        else:
            break
            
    if consecutive >= 5 and vol_increasing:
        anomalies.append({
            "anomaly_type": "CONSECUTIVE_DIRECTION",
            "severity": _determine_severity("CONSECUTIVE_DIRECTION", consecutive),
            "detail": f"{consecutive} consecutive days closing in the same direction with increasing volume.",
            "price": curr_close,
            "change_pct": change_pct
        })

    if vol_20d > 0 and curr_vol > 5 * vol_20d:
        info = fetch_info(ticker)
        mcap = info.get("marketCap", 0)
        mcap_cr = mcap / 10000000
        if 0 < mcap_cr < 1000:
            anomalies.append({
                "anomaly_type": "LOW_FLOAT_SURGE",
                "severity": _determine_severity("LOW_FLOAT_SURGE", curr_vol / vol_20d),
                "detail": f"Market Cap < 1000Cr and volume is {(curr_vol/vol_20d):.1f}x avg.",
                "price": curr_close,
                "change_pct": change_pct
            })

    for a in anomalies:
        a["ticker"] = ticker
        a["company"] = company
        
    return anomalies

def run_anomaly_scan() -> List[dict]:
    bhav_res = download_bhavcopy()
    
    bhavcopy_data = {}
    if bhav_res and "rows" in bhav_res and isinstance(bhav_res["rows"], list):
        for row in bhav_res["rows"]:
            sym = row.get("SYMBOL")
            dlv_pct = row.get("DELIV_PER")
            if sym and dlv_pct:
                try:
                    bhavcopy_data[sym] = float(dlv_pct)
                except ValueError:
                    pass

    all_anomalies = []
    
    for name, ticker in NSE_TICKERS.items():
        try:
            anomalies = _detect_anomalies_for_ticker(ticker, name, bhavcopy_data)
            all_anomalies.extend(anomalies)
        except Exception as e:
            logger.error(f"Error scanning {ticker}: {e}")

    try:
        with get_session() as db:
            for a in all_anomalies:
                db_record = MarketAnomaly(
                    ticker=a["ticker"],
                    company=a["company"],
                    anomaly_type=a["anomaly_type"],
                    severity=a["severity"],
                    detail=a["detail"],
                    price=a["price"],
                    change_pct=a["change_pct"],
                    timestamp=datetime.utcnow()
                )
                db.add(db_record)
            db.commit()
    except Exception as e:
        logger.error(f"Failed to save anomalies to DB: {e}")

    severity_rank = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
    all_anomalies.sort(key=lambda x: severity_rank.get(x["severity"], 0), reverse=True)
    
    return all_anomalies

def get_latest_anomalies(limit: int = 10) -> List[dict]:
    try:
        with get_session() as db:
            # We want recent anomalies, past 24 hours ideally
            yesterday = datetime.utcnow() - timedelta(days=1)
            records = db.query(MarketAnomaly).filter(MarketAnomaly.timestamp > yesterday).order_by(MarketAnomaly.timestamp.desc()).limit(limit * 2).all()
            
            results = []
            for r in records:
                results.append({
                    "ticker": r.ticker,
                    "company": r.company,
                    "anomaly_type": r.anomaly_type,
                    "severity": r.severity,
                    "detail": r.detail,
                    "price": r.price,
                    "change_pct": r.change_pct,
                    "timestamp": r.timestamp.isoformat()
                })
            
            # Sort heavily by severity
            severity_rank = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
            results.sort(key=lambda x: severity_rank.get(x["severity"], 0), reverse=True)
            return results[:limit]
    except Exception as e:
        logger.error(f"Error fetching anomalies: {e}")
        return []
