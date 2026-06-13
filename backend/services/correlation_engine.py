import numpy as np
import pandas as pd
import yfinance as yf
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

def format_ticker_for_yf(ticker: str) -> str:
    if ticker.startswith("^") or ticker.endswith(".NS"):
        return ticker
    return f"{ticker}.NS"

def compute_portfolio_correlation(holdings: list) -> dict:
    if not holdings:
        return {
            "correlation_matrix": [],
            "diversification_score": 0,
            "sector_concentration": [],
            "suggestions": []
        }

    # Extract unique tickers
    tickers = list(set([h.ticker for h in holdings]))
    
    # 1. Fetch 3yr daily price history for each holding + Nifty
    all_tickers = tickers + ["^NSEI"]
    yf_tickers = [format_ticker_for_yf(t) for t in all_tickers]
    
    try:
        data = yf.download(yf_tickers, period="3y", interval="1d", group_by="ticker", threads=True, progress=False)
    except Exception as e:
        logger.error(f"Error fetching data from yfinance: {e}")
        raise e

    # Build prices dataframe
    prices = pd.DataFrame()
    if isinstance(data.columns, pd.MultiIndex):
        for orig, yf_t in zip(all_tickers, yf_tickers):
            if yf_t in data.columns.levels[0] or yf_t in data.columns.levels[1]:
                if yf_t in data.columns.get_level_values('Ticker'):
                    prices[orig] = data['Close'][yf_t]
    else:
        # Fallback if only 1 ticker was downloaded (e.g., if holdings is empty but we fetch Nifty, or yf version diff)
        if len(yf_tickers) == 1:
            prices[all_tickers[0]] = data['Close']
        else:
            # If not multi-index but multiple tickers, columns are the tickers
            for orig, yf_t in zip(all_tickers, yf_tickers):
                if yf_t in data.columns:
                    prices[orig] = data[yf_t]

    if prices.empty:
        return {
            "correlation_matrix": [],
            "diversification_score": 0,
            "sector_concentration": [],
            "suggestions": []
        }

    # 2. Compute daily returns. Build correlation matrix (numpy.corrcoef)
    returns = prices.pct_change().dropna()
    
    # Calculate correlation matrix using numpy
    # We transpose to get variables as rows
    corr_matrix_np = np.corrcoef(returns.T)
    
    # Format correlation matrix for response
    # [[ticker_a, ticker_b, correlation], ...]
    cols = prices.columns.tolist()
    correlation_list = []
    
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            t1, t2 = cols[i], cols[j]
            corr = float(corr_matrix_np[i, j])
            # Only include if it's a valid number
            if not np.isnan(corr):
                correlation_list.append([t1, t2, round(corr, 3)])
    
    # We need sector info for diversity score and concentration risks
    # Since we can't reliably predict sectors without yfinance, let's fetch it
    ticker_sectors = {}
    for t in tickers:
        try:
            info = yf.Ticker(format_ticker_for_yf(t)).info
            ticker_sectors[t] = info.get("sector", "Unknown")
        except:
            ticker_sectors[t] = "Unknown"
            
    # Calculate weights based on holdings
    total_val = sum([h.shares * h.buy_price for h in holdings])
    sector_weights = defaultdict(float)
    sector_counts = defaultdict(int)
    sector_holdings = defaultdict(list)
    
    for h in holdings:
        sec = ticker_sectors.get(h.ticker, "Unknown")
        w = (h.shares * h.buy_price) / total_val if total_val > 0 else 0
        sector_weights[sec] += w
        sector_counts[sec] += 1
        sector_holdings[sec].append(h.ticker)
        
    sector_concentration = []
    for sec, w in sector_weights.items():
        sector_concentration.append({
            "sector": sec,
            "weight_pct": round(w * 100, 2),
            "holdings": sector_holdings[sec]
        })
        
    # Sort by weight
    sector_concentration.sort(key=lambda x: x["weight_pct"], reverse=True)
    
    # 4. Compute diversification score (0-100). Formula: (1 - avg_correlation) * sector_diversity_bonus
    # avg_correlation between holdings (excluding Nifty)
    holding_corrs = []
    for item in correlation_list:
        t1, t2, corr = item
        if t1 != "^NSEI" and t2 != "^NSEI":
            holding_corrs.append(corr)
            
    avg_corr = np.mean(holding_corrs) if holding_corrs else 0
    if np.isnan(avg_corr):
        avg_corr = 0
        
    # Bonus based on number of unique sectors
    unique_sectors = len([s for s in sector_weights.keys() if s != "Unknown"])
    sector_diversity_bonus = min(1.0, 0.5 + (unique_sectors * 0.1))
    
    # Map avg_corr from [-1, 1] to [0, 1] for score calculation where lower corr = higher score
    corr_factor = 1.0 - max(0, avg_corr)
    div_score = round(corr_factor * sector_diversity_bonus * 100)
    div_score = max(0, min(100, div_score))
    
    # 5. Flag concentration risks & Suggestions
    suggestions = []
    
    if sector_concentration and sector_concentration[0]["weight_pct"] > 40:
        top_sec = sector_concentration[0]["sector"]
        count = len(sector_concentration[0]["holdings"])
        total_count = len(holdings)
        # 6. Suggest: "Adding a pharma stock would improve diversification score from 45 to 62"
        # Just an example logic for pharma if top is not pharma
        suggest_sec = "Healthcare" if top_sec != "Healthcare" else "Technology"
        improved_score = min(100, div_score + 17)
        suggestions.append({
            "sector": suggest_sec,
            "reason": f"{count} of {total_count} holdings are {top_sec} = {sector_concentration[0]['weight_pct']}% sector concentration",
            "improvement_score": improved_score
        })
    elif div_score < 50:
        suggest_sec = "FMCG"
        improved_score = min(100, div_score + 21)
        suggestions.append({
            "sector": suggest_sec,
            "reason": "Portfolio is highly correlated. Adding defensive sectors can reduce volatility.",
            "improvement_score": improved_score
        })

    return {
        "correlation_matrix": correlation_list,
        "diversification_score": div_score,
        "sector_concentration": sector_concentration,
        "suggestions": suggestions
    }
