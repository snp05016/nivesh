import yfinance as yf
from datetime import datetime, timedelta
import math
from database import get_session, FIIDIIFlow
from routers.market import SECTOR_TICKERS

SECTOR_FII_WEIGHTS = {
    "PSU Bank": 0.05,
    "FMCG": 0.10,
    "IT": 0.20,
    "Pharma": 0.10,
    "Auto": 0.10,
    "Realty": 0.05,
    "Energy": 0.15,
    "Metal": 0.05,
    "Unknown": 0.20
}

def get_sector_rotation_data(period: str):
    yf_period = "3mo"
    if period.lower() == "1m": yf_period = "1mo"
    elif period.lower() == "3m": yf_period = "3mo"
    elif period.lower() == "6m": yf_period = "6mo"
    elif period.lower() == "1y": yf_period = "1y"

    with get_session() as db:
        recent_flows = db.query(FIIDIIFlow).order_by(FIIDIIFlow.date.desc()).limit(30).all()
        
    total_fii_net = sum(f.fii_net for f in recent_flows) if recent_flows else 0
    total_dii_net = sum(f.dii_net for f in recent_flows) if recent_flows else 0
    
    sectors = []
    
    for ticker, name in SECTOR_TICKERS:
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period=yf_period)
            
            # Using a date 7 days ago to find previous quadrant
            end_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            hist_prev_week = t.history(period=yf_period, end=end_date)
            
            if hist.empty or len(hist) < 2:
                continue
                
            start_price = float(hist["Close"].iloc[0])
            end_price = float(hist["Close"].iloc[-1])
            ret = ((end_price - start_price) / start_price) * 100
            
            recent_start = float(hist["Close"].iloc[max(0, len(hist)-5)])
            momentum = ((end_price - recent_start) / recent_start) * 100
            
            if not hist_prev_week.empty and len(hist_prev_week) >= 2:
                p_start = float(hist_prev_week["Close"].iloc[0])
                p_end = float(hist_prev_week["Close"].iloc[-1])
                p_ret = ((p_end - p_start) / p_start) * 100
                p_recent = float(hist_prev_week["Close"].iloc[max(0, len(hist_prev_week)-5)])
                p_mom = ((p_end - p_recent) / p_recent) * 100
            else:
                p_ret, p_mom = ret, momentum
                
            def get_quad(r, m):
                if r >= 0 and m >= 0: return "Leaders"
                if r < 0 and m < 0: return "Laggards"
                if r < 0 and m >= 0: return "Improving"
                return "Fading"
                
            quadrant = get_quad(ret, momentum)
            prev_quadrant = get_quad(p_ret, p_mom)
            
            weight = SECTOR_FII_WEIGHTS.get(name, 0.1)
            f_flow = total_fii_net * weight
            d_flow = total_dii_net * weight
            
            # Institutional conviction score
            # FII buying + DII buying in sector / total sector volume
            # Since we don't have sector volume, proxy conviction by absolute flows relative to total
            conviction = min(100, max(0, int(((abs(f_flow) + abs(d_flow)) / max(1, abs(total_fii_net) + abs(total_dii_net))) * 100)))
            if conviction == 0:
                conviction = 50 # Base value if no flows
            
            sectors.append({
                "name": name,
                "return_pct": round(ret, 2),
                "momentum_score": round(momentum, 2),
                "quadrant": quadrant,
                "prev_quadrant": prev_quadrant,
                "fii_flow_cr": round(f_flow, 2),
                "dii_flow_cr": round(d_flow, 2),
                "institutional_conviction": conviction,
                "holdings_in_sector": []
            })
            
        except Exception as e:
            print(f"Error processing sector {name}: {e}")
            
    return {"period": period, "sectors": sectors}
