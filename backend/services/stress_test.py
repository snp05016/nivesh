"""Indian Equity Stress Test Engine — Tier 2.5 Hybrid Architecture.

Implements: §5-12 of Indian_Equity_Stress_Test_Engine.md.
Core workflow: Beta Estimation → Shock Propagation → Portfolio Aggregation → 
Liquidity Penalty → Concentration Analysis → Scoring.
"""
from __future__ import annotations
import numpy as np
import threading
from typing import List, Dict, Any, Optional
from helpers import _yf_fetch_info, _yf_price

# ── Scenario Definitions (14 scenarios) ──────────────────────────────

SCENARIOS_DEF: dict[str, dict] = {
    "nifty_crash":       {"name": "NIFTY_CRASH",      "shocks": {"market": -20.0}},
    "sensex_crash":      {"name": "SENSEX_CRASH",     "shocks": {"market": -18.0}},
    "midcap_crash":      {"name": "MIDCAP_CRASH",     "shocks": {"midcap": -25.0}, "nifty": -10.0},
    "smallcap_crash":    {"name": "SMALLCAP_CRASH",   "shocks": {"smallcap": -30.0}, "nifty": -8.0},
    "oil_shock":         {"name": "OIL_SHOCK",         "shocks": {"oil": 50.0}, "nifty": -5.0},
    "rate_hike":         {"name": "RBI_RATE_HIKE",    "shocks": {"rates": 2.0}, "nifty": -5.0},
    "rate_cut":          {"name": "RBI_RATE_CUT",     "shocks": {"rates": -1.0}, "nifty": 3.0},
    "fii_exodus":        {"name": "FII_EXODUS",        "shocks": {"fii_flow": -5.0}, "nifty": -12.0},
    "dii_exodus":        {"name": "DII_EXODUS",        "shocks": {"dii_flow": -3.0}, "nifty": -6.0},
    "inflation_shock":   {"name": "INFLATION_SHOCK",  "shocks": {"inflation": 3.0}, "nifty": -8.0},
    "currency_crash":    {"name": "CURRENCY_CRASH",   "shocks": {"fx": 15.0}, "nifty": -10.0},
    "global_recession":  {"name": "GLOBAL_RECESSION",  "shocks": {"market": -25.0}},
    "banking_crisis":    {"name": "BANKING_CRISIS",    "shocks": {"rates": 1.0, "market": -15.0}, "sector": {"Banking": -30.0}},
    "policy_shock":      {"name": "POLICY_SHOCK",      "shocks": {"market": -18.0}, "sector": {"PSU": -30.0}},
}

FACTOR_CATEGORIES = {
    "market": ["market", "midcap", "smallcap"],
    "macro": ["oil", "rates", "fx", "inflation"],
    "flows": ["fii_flow", "dii_flow"],
}

# ── Sector Classification ────────────────────────────────────────────

def get_sector(company_name: str) -> str:
    """
    Map a company name to its primary sector.

    Args:
        company_name (str): The name of the company.

    Returns:
        str: The identified sector name, or "Other" if no match is found.
    """
    if not company_name: return "Other"
    name = company_name.lower()
    if any(x in name for x in ["infosys","tcs","wipro","tech mahindra","hcl","ltim","coforge","persistent","mphasis"]): return "IT"
    if any(x in name for x in ["bank","hdfc","icici","kotak","sbi","axis","federal","idfc","yes"]): return "Banking"
    if any(x in name for x in ["fmcg","itc","nestle","brit","hindustan unilever","hul","godrej","marico","dabur","tata consumer","colgate"]): return "FMCG"
    if any(x in name for x in ["auto","tata motors","maruti","mahindra","bajaj auto","eicher","tvs","ashok leyland"]): return "Auto"
    if any(x in name for x in ["pharma","sun pharma","cipla","dr reddy","lupin","divis","apollo hospitals","aurobindo","torrent","alkem"]): return "Pharma"
    if any(x in name for x in ["oil","reliance","ongc","bpcl","hpcl","ioc","petronet","gail"]): return "Oil & Gas"
    if any(x in name for x in ["power","ntpc","tata power","power grid","jsw energy","torrent power","nhpc"]): return "Power"
    if any(x in name for x in ["steel","tata steel","jsw","hindalco","vedanta","jindal"]): return "Metals"
    if any(x in name for x in ["cement","ultratech","shree","ambuja","acc","dalmia","ramco"]): return "Cement"
    if any(x in name for x in ["nbfc","bajaj finance","cholamandalam","shriram","muthoot"]): return "NBFC"
    if any(x in name for x in ["defence","hal","bel","mazagon","cochin","bharat dynamics","beml"]): return "Defence"
    if any(x in name for x in ["infra","larsen","l&t","gmr","irb"]): return "Infra"
    if any(x in name for x in ["real","dlf","godrej properties","oberoi","prestige","brigade","lodha"]): return "Real Estate"
    if any(x in name for x in ["telecom","bharti","vodafone","idea","tata comm","tejas"]): return "Telecom"
    return "Other"


# ── Core Engine ──────────────────────────────────────────────────────

def _call_with_timeout(fn, *args, default=None, timeout=30):
    """Call fn with timeout. Returns default on timeout/hang."""
    import queue
    result_queue = queue.Queue()
    def _worker():
        try:
            result_queue.put(("ok", fn(*args)))
        except Exception as e:
            result_queue.put(("err", str(e)))
    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    t.join(timeout=timeout)
    if t.is_alive():
        return default
    try:
        status, value = result_queue.get_nowait()
        if status == "ok":
            return value
    except Exception as _e:
        pass
    return default

from services.math_engines.vasicek import get_adjusted_macro_betas

def _estimate_betas(ticker: str, sector: str = "Other") -> dict[str, float]:
    """Fetch beta estimates using Vasicek Bayesian Shrinkage."""
    return get_adjusted_macro_betas(ticker, sector)


def _estimate_volatility(ticker: str) -> float:
    """Estimate annualized volatility. Falls back to 30%."""
    info = _call_with_timeout(_yf_fetch_info, ticker, default={}, timeout=30)
    beta = float(info.get("beta", 1.0) or 1.0)
    return round(0.20 * beta + 0.05, 4)


def _estimate_adv(ticker: str) -> float:
    """Estimate average daily volume."""
    info = _call_with_timeout(_yf_fetch_info, ticker, default={}, timeout=30)
    avg_vol = info.get("averageVolume") or info.get("averageDailyVolume10Day")
    if avg_vol and float(avg_vol) > 0:
        return float(avg_vol)
    return 1_000_000


def _build_fallback(h) -> dict:
    """Build a fallback enriched holding when yfinance fails."""
    ticker = h.ticker.upper() if hasattr(h, 'ticker') else str(h)
    name = h.company_name if hasattr(h, 'company_name') else ticker
    shares = float(h.shares) if hasattr(h, 'shares') else 0
    buy_price = float(h.buy_price) if hasattr(h, 'buy_price') else 0
    return {
        "ticker": ticker, "company_name": name or ticker,
        "shares": shares, "price": buy_price, "value": shares * buy_price,
        "betas": _estimate_betas(ticker), "sector": get_sector(name or ""),
        "volatility": 0.30, "avg_daily_volume": 1_000_000, "spread_bps": 0.005,
    }

def enrich_holdings(holdings, progress_callback=None) -> List[Dict[str, Any]]:
    """Enrich portfolio holdings with current price, beta factors, and liquidity params.
    
    Uses ThreadPoolExecutor (max 8 workers) to fetch yfinance data in parallel.
    progress_callback(done: int, total: int, current_ticker: str) called per holding.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    total = len(holdings)
    completed = [0]
    lock = threading.Lock()
    
    def _enrich_single(h):
        ticker = h.ticker.upper()
        
        if ticker in ("CASH", "INR"):
            price = h.shares if h.shares > 0 else 1.0
            result = {
                "ticker": ticker, "company_name": h.company_name or "Cash",
                "shares": h.shares, "price": price, "value": h.shares * price,
                "betas": {}, "sector": "Cash", "volatility": 0.0,
                "avg_daily_volume": 0, "spread_bps": 0.0,
            }
        else:
            try:
                price_info = _yf_price(ticker)
                price = float(price_info[0]) if price_info and price_info[0] and price_info[0] > 0 else float(h.buy_price)
            except Exception as _e:
                price = float(h.buy_price)
            
            value = float(h.shares) * price
            sector = get_sector(h.company_name or "")
            betas = _estimate_betas(ticker, sector)
            volatility = _estimate_volatility(ticker)
            adv = _estimate_adv(ticker)
            
            result = {
                "ticker": ticker,
                "company_name": h.company_name or ticker,
                "shares": float(h.shares),
                "price": price,
                "value": value,
                "betas": betas,
                "sector": sector,
                "volatility": volatility,
                "avg_daily_volume": adv,
                "spread_bps": 0.005,
            }
        
        with lock:
            completed[0] += 1
            if progress_callback:
                progress_callback(completed[0], total, ticker)
        
        return result
    
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(_enrich_single, h): i for i, h in enumerate(holdings)}
        results = [None] * len(holdings)
        import concurrent.futures as _cf
        for f in _cf.as_completed(futures, timeout=180):
            idx = futures[f]
            try:
                results[idx] = f.result(timeout=45)
            except Exception as _e:
                h = holdings[idx]
                results[idx] = _build_fallback(h)
                with lock:
                    completed[0] += 1
                    if progress_callback:
                        progress_callback(completed[0], total, f"{h.ticker} (fallback)")
        
        # Fill any remaining Nones
        for i, r in enumerate(results):
            if r is None:
                results[i] = _build_fallback(holdings[i])
    
    return [r for r in results if r is not None]


def run_stress_test(
    holdings,
    scenarios: List[str],
    progress_callback=None,
    phase_callback=None,
) -> List[Dict[str, Any]]:
    """Execute Tier 2.5 stress tests on a portfolio.
    
    Steps:
    1. Enrich holdings with current prices and betas
    2. For each scenario, compute factor shocks
    3. Apply stock impact equation: R_i = Σ β_ik * ΔF_k
    4. Compute liquidity penalty via Almgren-Chriss
    5. Compute concentration analysis (HHI, MRC)
    6. Calculate all 6 risk scores
    
    progress_callback(done: int, total: int, current_ticker: str) called per holding.
    phase_callback(checkpoint: str, pct: int, message: str) is called at real
    engine boundaries so API clients can display durable backend progress.
    """
    from services.math_engines.liquidity import square_root_impact, portfolio_liquidity_loss
    from services.math_engines.concentration import compute_concentration_analysis
    from services.math_engines.scoring import compute_all_scores, compute_stress_score
    from services.math_engines.covariance import fetch_historical_returns, compute_covariance_matrix, compute_crisis_covariance
    
    def _emit_phase(checkpoint: str, pct: int, message: str) -> None:
        if phase_callback:
            phase_callback(checkpoint, pct, message)

    # Phase 1: Enrich holdings (parallel yfinance)
    _emit_phase("enrich", 5, "Loading prices, betas, and liquidity inputs")
    enriched = enrich_holdings(holdings, progress_callback=progress_callback)
    total_value = sum(e["value"] for e in enriched)
    if total_value <= 0:
        return []
    
    weights = np.array([e["value"] / total_value for e in enriched])
    tickers = [e["ticker"] for e in enriched]
    sectors = [e["sector"] for e in enriched]
    
    # Phase 2: Fetch empirical covariance from historical returns
    _emit_phase("covariance", 55, "Building historical covariance matrix")
    n = len(enriched)
    returns_dict = fetch_historical_returns(tickers, period="2y")
    cov = compute_covariance_matrix(returns_dict, tickers)
    
    # Calculate historical skewness and kurtosis of the portfolio for Cornish-Fisher
    port_rets_list = []
    for ticker, weight in zip(tickers, weights):
        rets = returns_dict.get(ticker)
        if rets is not None and len(rets) > 0:
            port_rets_list.append(rets[-252:] * weight) # Last 1 year common approx
    
    if len(port_rets_list) > 0:
        min_len = min([len(r) for r in port_rets_list])
        port_rets = np.sum([r[-min_len:] for r in port_rets_list], axis=0)
        m2 = np.mean((port_rets - np.mean(port_rets))**2)
        if m2 > 1e-10:
            m3 = np.mean((port_rets - np.mean(port_rets))**3)
            m4 = np.mean((port_rets - np.mean(port_rets))**4)
            port_skew = float(m3 / (m2**1.5))
            port_kurt = float((m4 / (m2**2)) - 3.0)
        else:
            port_skew, port_kurt = 0.0, 0.0
    else:
        port_skew, port_kurt = 0.0, 0.0
    
    # Pre-compute crisis covariance for severe crash scenarios
    crisis_cov = compute_crisis_covariance(returns_dict, tickers, broken_arrow_corr=0.85)

    # Phase 3: Concentration analysis (base covariance, updated per-scenario)
    valid_scenarios = [
        key.lower().strip()
        for key in scenarios
        if key.lower().strip() in SCENARIOS_DEF
    ]
    _emit_phase(
        "scenarios",
        70,
        f"Running {len(valid_scenarios)} portfolio shock scenario(s)",
    )
    
    results = []
    for scenario_index, sc_key_lower in enumerate(valid_scenarios):
        
        scenario = SCENARIOS_DEF[sc_key_lower]
        shocks = scenario.get("shocks", {})
        nifty_val = scenario.get("nifty", None)
        sector_overrides = scenario.get("sector", {})
        
        # Phase 4: Per-holding impact
        holdings_results = []
        total_impact_inr = 0.0
        weighted_impact_pct = 0.0
        
        for i, e in enumerate(enriched):
            w = weights[i]
            sector = e["sector"]
            
            if sector == "Cash":
                impact_pct = 0.0
                impact_inr = 0.0
            else:
                impact_pct = 0.0
                betas = e["betas"]
                for factor_key, shock_val in shocks.items():
                    beta_val = betas.get(factor_key, 0.0)
                    if factor_key == "market" and nifty_val is not None:
                        impact_pct += beta_val * nifty_val
                    else:
                        impact_pct += beta_val * shock_val
                
                # Sector-specific override
                if sector in sector_overrides:
                    impact_pct += sector_overrides[sector]
                
                impact_inr = e["value"] * (impact_pct / 100.0)
            
            total_impact_inr += impact_inr
            weighted_impact_pct += w * impact_pct
            
            # Liquidity penalty per holding (crisis volume suppression = 0.4)
            liq = square_root_impact(
                shares_held=e["shares"],
                avg_daily_volume=e["avg_daily_volume"],
                daily_volatility=e["volatility"],
                base_spread_bps=e["spread_bps"],
                gamma=0.2,
                volume_suppression=0.4,
            )
            
            holdings_results.append({
                "ticker": e["ticker"],
                "company_name": e["company_name"],
                "sector": sector,
                "value": round(e["value"], 2),
                "weight_pct": round(float(w) * 100, 2),
                "impact_pct": round(impact_pct, 2),
                "impact_inr": round(impact_inr, 2),
                "liquidity_penalty_pct": round(liq["impact_pct"], 4),
                "liquidity_penalty_inr": round(e["value"] * liq["impact_pct"] / 100, 2),
            })
        
        # Sort: worst hit first
        holdings_results.sort(key=lambda x: x["impact_pct"])
        
        # Portfolio-level metrics
        total_impact_pct = (total_impact_inr / total_value) * 100.0 if total_value > 0 else 0.0
        worst_case_pct = total_impact_pct * 1.5  # 1.5x for tail events
        
        # Phase 5: Liquidity penalty (portfolio level)
        liq_data = []
        for e in enriched:
            if e["sector"] != "Cash":
                liq_data.append({
                    "ticker": e["ticker"], "shares": e["shares"], "price": e["price"],
                    "avg_daily_volume": e["avg_daily_volume"], "volatility": e["volatility"],
                    "spread_bps": e["spread_bps"],
                })
        portfolio_liq = portfolio_liquidity_loss(liq_data, volume_suppression=0.4, gamma=0.2)
        
        # Phase 6: Scoring
        portfolio_vol = np.sqrt(np.mean([e["volatility"]**2 for e in enriched if e["sector"] != "Cash"]))
        macro_betas = {
            k: np.mean([abs(e["betas"].get(k, 0.0)) for e in enriched if e["sector"] != "Cash"])
            for k in ["oil", "rates", "fx", "inflation"]
        }
        
        # Re-compute concentration if Broken Arrow triggered
        is_severe_crash = "CRASH" in scenario["name"] or "RECESSION" in scenario["name"]
        scenario_cov = crisis_cov if (is_severe_crash and len(crisis_cov) > 0) else cov
        scen_conc = compute_concentration_analysis(tickers, weights, sectors, scenario_cov)

        scores = compute_all_scores(
            portfolio_vol_annualized=portfolio_vol,
            worst_case_loss_pct=worst_case_pct,
            macro_betas=macro_betas,
            liquidity_impact_pct=portfolio_liq["total_liquidity_loss_pct"],
            concentration_hhi=scen_conc["hhi"],
            parametric_var_95_pct=portfolio_vol * 1.645 * np.sqrt(10) * 100.0,
            cvar_99_pct=worst_case_pct,
            liquidity_score_raw=portfolio_liq.get("total_liquidity_loss_pct", 0.0) * 10,
            skewness=port_skew,
            kurtosis=port_kurt,
        )
        scores["concentration_score"] = scen_conc["concentration_score"]
        
        results.append({
            "name": scenario["name"],
            "scenario_key": sc_key_lower,
            "impact_pct": round(total_impact_pct, 2),
            "impact_inr": round(total_impact_inr, 2),
            "worst_case_pct": round(worst_case_pct, 2),
            "total_value": round(total_value, 2),
            "scores": scores,
            "holdings": holdings_results,
            "concentration": scen_conc,
            "liquidity": {
                "total_loss_pct": portfolio_liq["total_liquidity_loss_pct"],
                "total_loss_inr": portfolio_liq["total_liquidity_loss_inr"],
            },
        })

        completed = scenario_index + 1
        scenario_pct = 70 + int((completed / max(len(valid_scenarios), 1)) * 28)
        _emit_phase(
            "scenarios",
            scenario_pct,
            f"Completed {scenario['name']} ({completed}/{len(valid_scenarios)})",
        )

    _emit_phase("scoring", 99, "Finalizing portfolio risk scores")
    
    return results
