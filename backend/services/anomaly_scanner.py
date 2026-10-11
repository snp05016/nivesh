"""Market anomaly detection engine.

This module scans daily market data to identify statistical, volume, and options anomalies
for the configured NSE universe.
"""
import logging
from datetime import datetime, date, timedelta, timezone
from zoneinfo import ZoneInfo
import pandas as pd
from typing import Optional, List, Dict, Any

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, func
from database import Base, get_session, ENGINE
from models.db_models import MarketAnomaly
from helpers import NSE_TICKERS
from services.nse_data_provider import get_price_history, fetch_info
from services.factor_engine import compute_indicators
from services.options_scraper import fetch_option_chain, compute_derivatives_metrics

logger = logging.getLogger(__name__)

_IST = ZoneInfo("Asia/Kolkata")
_RETENTION_DAYS = 30

def _determine_severity(anomaly_type: str, magnitude: float) -> str:
    """Determines the severity level of an anomaly based on its type and magnitude.

    Args:
        anomaly_type (str): The type of the anomaly (e.g., 'VOLUME_SPIKE', 'GAP_UP').
        magnitude (float): The numerical magnitude associated with the anomaly.

    Returns:
        str: The severity level, such as 'HIGH', 'MEDIUM', or 'LOW'.
    """
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

def _detect_anomalies_for_ticker(ticker: str, company: str) -> List[dict]:
    """Scans historical and options data for a specific ticker to detect anomalies.

    Args:
        ticker (str): The NSE ticker symbol.
        company (str): The name of the company.

    Returns:
        List[dict]: A list of detected anomaly dictionaries for the ticker.
    """
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
        
    # NSE's option-chain API takes the bare symbol ("RELIANCE"), not the yfinance "RELIANCE.NS".
    chain = fetch_option_chain(ticker.split(".")[0], use_cache=True)
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
    """Runs a comprehensive scan across the entire defined universe of NSE tickers.

    Evaluates each ticker for anomalies and upserts findings so each
    (ticker, anomaly_type) is stored at most once per IST trading day; rows
    older than _RETENTION_DAYS are pruned. Results are sorted by severity.

    Returns:
        List[dict]: The complete list of sorted anomalies detected during the scan.
    """
    all_anomalies = []
    
    for name, ticker in NSE_TICKERS.items():
        try:
            anomalies = _detect_anomalies_for_ticker(ticker, name)
            all_anomalies.extend(anomalies)
        except Exception as e:
            logger.error(f"Error scanning {ticker}: {e}")

    try:
        now = datetime.now(timezone.utc)
        day_start = datetime.now(_IST).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
        with get_session() as db:
            existing = {
                (r.ticker, r.anomaly_type): r
                for r in db.query(MarketAnomaly).filter(MarketAnomaly.timestamp >= day_start)
            }
            for a in all_anomalies:
                row = existing.get((a["ticker"], a["anomaly_type"]))
                if row is None:
                    row = MarketAnomaly(ticker=a["ticker"], anomaly_type=a["anomaly_type"])
                    db.add(row)
                    existing[(a["ticker"], a["anomaly_type"])] = row
                row.company = a["company"]
                row.severity = a["severity"]
                row.detail = a["detail"]
                row.price = a["price"]
                row.change_pct = a["change_pct"]
                row.timestamp = now  # type: ignore[assignment]
            db.query(MarketAnomaly).filter(
                MarketAnomaly.timestamp < now - timedelta(days=_RETENTION_DAYS)
            ).delete(synchronize_session=False)
            db.commit()
    except Exception as e:
        logger.error(f"Failed to save anomalies to DB: {e}")

    severity_rank = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
    all_anomalies.sort(key=lambda x: severity_rank.get(x["severity"], 0), reverse=True)
    
    return all_anomalies

def get_latest_anomalies(limit: int = 10) -> List[dict]:
    """Retrieves the most recent market anomalies from the database.

    Fetches anomalies from the 24 hours before the most recent scan (not wall-clock
    now), so the last trading day stays visible over weekends and exchange holidays
    when the weekday-only scan does not run. Results are weighted by severity.

    Args:
        limit (int): The maximum number of anomalies to return. Defaults to 10.

    Returns:
        List[dict]: A list of recent, high-priority anomaly records.
    """
    try:
        with get_session() as db:
            # Anchor the 24 h window to the latest scan: the scan runs Mon-Fri only.
            latest = db.query(func.max(MarketAnomaly.timestamp)).scalar()
            if latest is None:
                return []
            records = db.query(MarketAnomaly).filter(MarketAnomaly.timestamp >= latest - timedelta(days=1)).order_by(MarketAnomaly.timestamp.desc()).limit(limit * 2).all()
            
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
