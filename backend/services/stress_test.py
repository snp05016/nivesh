"""Indian Equity Stress Test Engine — Tier 2.5 Hybrid Architecture.

Implements: §5-12 of Indian_Equity_Stress_Test_Engine.md.
Core workflow: Beta Estimation → Shock Propagation → Portfolio Aggregation → 
Liquidity Penalty → Concentration Analysis → Scoring.
"""
from __future__ import annotations
import logging
import numpy as np
import threading
from typing import List, Dict, Any, Optional
from helpers import _yf_fetch_info, _yf_price, _to_ns

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

# Size-segment shocks apply to holdings in that market-cap bucket; others take the Nifty leg.
_SIZE_LEGS = {"midcap": "mid", "smallcap": "small"}

# ponytail: AMFI half-yearly cut-offs (approx.), refresh when the list changes
LARGE_CAP_MIN_INR = 1.0e12  # ₹1,00,000 Cr
MID_CAP_MIN_INR = 3.3e11    # ₹33,000 Cr

# ponytail: static PSU list for the POLICY_SHOCK override; derive from index constituents if it drifts
PSU_TICKERS = frozenset({
    "SBIN", "BANKBARODA", "PNB", "CANBK", "UNIONBANK", "INDIANB", "BANKINDIA", "IOB",
    "UCOBANK", "CENTRALBK", "MAHABANK", "ONGC", "IOC", "BPCL", "HINDPETRO", "GAIL", "OIL",
    "COALINDIA", "NTPC", "POWERGRID", "NHPC", "SJVN", "NLCINDIA", "BEL", "HAL", "BDL",
    "MAZDOCK", "COCHINSHIP", "BEML", "BHEL", "SAIL", "NMDC", "NATIONALUM", "HINDCOPPER",
    "MOIL", "RECLTD", "PFC", "IRFC", "IREDA", "HUDCO", "LICI", "GICRE", "NIACL", "IRCTC",
    "CONCOR", "RVNL", "IRCON", "NBCC",
})

SPREAD_HALF = 0.0005  # ponytail: flat 5 bps half-spread; tier by ADV if needed
DEFAULT_ADV = 1_000_000
FALLBACK_ANNUAL_VOL = 0.30
MIN_RETURNS = 20              # daily returns needed before a measured sigma/covariance is trusted
MIN_PRICED_COVERAGE_PCT = 50.0  # below this the job fails instead of reporting numbers
DEGRADED_COVERAGE_PCT = 90.0
MACRO_ASSUMPTION = (
    "Macro and flow factor sensitivities are not estimated; "
    "only the market leg and sector overrides are applied."
)

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
    """Call fn with timeout. Returns default (and logs why) on timeout or error."""
    import queue
    result_queue = queue.Queue()
    def _worker():
        try:
            result_queue.put(("ok", fn(*args)))
        except Exception as e:
            result_queue.put(("err", str(e)))
    name = getattr(fn, "__name__", repr(fn))
    arg0 = args[0] if args else ""
    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    t.join(timeout=timeout)
    if t.is_alive():
        logging.warning("[StressTest] %s(%s) timed out after %ss", name, arg0, timeout)
        return default
    try:
        status, value = result_queue.get_nowait()
    except queue.Empty:
        return default
    if status == "ok":
        return value
    logging.warning("[StressTest] %s(%s) failed: %s", name, arg0, value)
    return default

from services.math_engines.vasicek import get_adjusted_macro_betas

def _estimate_betas(ticker: str, sector: str = "Other") -> dict[str, Any]:
    """Fetch beta estimates using Vasicek Bayesian Shrinkage (plain dict for JSON/aggregation)."""
    return get_adjusted_macro_betas(ticker, sector).model_dump()


def _size_bucket(market_cap: float) -> str:
    """AMFI-style size bucket; unknown market cap is treated as large cap."""
    if market_cap >= LARGE_CAP_MIN_INR or market_cap <= 0:
        return "large"
    return "mid" if market_cap >= MID_CAP_MIN_INR else "small"


def _build_fallback(h, exc: Optional[BaseException] = None) -> dict:
    """Build a fallback enriched holding when enrichment fails: cost basis and default inputs, flagged."""
    ticker = h.ticker.upper() if hasattr(h, 'ticker') else str(h)
    name = h.company_name if hasattr(h, 'company_name') else ticker
    shares = float(h.shares) if hasattr(h, 'shares') else 0
    buy_price = float(h.buy_price) if hasattr(h, 'buy_price') else 0
    logging.warning("[StressTest] enrichment failed for %s, using cost basis and defaults: %s", ticker, exc)
    return {
        "ticker": ticker, "yf_symbol": ticker if "." in ticker else f"{ticker}.NS",
        "company_name": name or ticker,
        "shares": shares, "price": buy_price, "value": shares * buy_price,
        "betas": {"market": 1.0, "market_beta_source": "default"},
        "sector": get_sector(name or ""), "size_bucket": "large",
        "fallback_daily_vol": FALLBACK_ANNUAL_VOL / np.sqrt(252),
        "avg_daily_volume": DEFAULT_ADV, "spread_bps": SPREAD_HALF,
        "price_source": "cost_basis", "adv_source": "default",
    }

def enrich_holdings(holdings, progress_callback=None) -> List[Dict[str, Any]]:
    """Enrich portfolio holdings with current price, beta factors, and liquidity params.
    
    Uses ThreadPoolExecutor (max 8 workers) to fetch yfinance data in parallel.
    progress_callback(done: int, total: int, current_ticker: str) called per holding.
    Every row records where its inputs came from (price_source, adv_source,
    betas.market_beta_source) so run_stress_test can report data quality.
    """
    total = len(holdings)
    completed = [0]
    lock = threading.Lock()
    
    def _enrich_single(h):
        ticker = h.ticker.upper()
        
        if ticker in ("CASH", "INR"):
            price = float(h.buy_price) if h.buy_price and float(h.buy_price) > 0 else 1.0
            result = {
                "ticker": ticker, "yf_symbol": ticker, "company_name": h.company_name or "Cash",
                "shares": float(h.shares), "price": price, "value": float(h.shares) * price,
                "betas": {}, "sector": "Cash", "size_bucket": "large", "fallback_daily_vol": 0.0,
                "avg_daily_volume": 0, "spread_bps": 0.0,
                "price_source": "cash", "adv_source": "cash",
            }
        else:
            sym = _to_ns(ticker)  # bare NSE tickers (HAL, INFY) also resolve to US listings
            live_price = None
            try:
                price_info = _yf_price(sym)
                if price_info and price_info[0] and float(price_info[0]) > 0:
                    live_price = float(price_info[0])
            except Exception as exc:
                logging.warning("[StressTest] price fetch failed for %s: %s", sym, exc)
            price = live_price if live_price is not None else float(h.buy_price)

            info = _call_with_timeout(_yf_fetch_info, sym, default={}, timeout=30)
            if not isinstance(info, dict):
                info = {}
            beta_hint = float(info.get("beta") or 1.0)
            adv = float(info.get("averageVolume") or info.get("averageDailyVolume10Day") or 0.0)
            sector = get_sector(h.company_name or "")
            
            result = {
                "ticker": ticker,
                "yf_symbol": sym,
                "company_name": h.company_name or ticker,
                "shares": float(h.shares),
                "price": price,
                "value": float(h.shares) * price,
                "betas": _estimate_betas(sym, sector),
                "sector": sector,
                "size_bucket": _size_bucket(float(info.get("marketCap") or 0.0)),
                # Used only when fewer than MIN_RETURNS daily returns are available.
                "fallback_daily_vol": (0.20 * beta_hint + 0.05) / np.sqrt(252),
                "avg_daily_volume": adv if adv > 0 else DEFAULT_ADV,
                "spread_bps": SPREAD_HALF,
                "price_source": "live" if live_price is not None else "cost_basis",
                "adv_source": "info" if adv > 0 else "default",
            }
        
        with lock:
            completed[0] += 1
            if progress_callback:
                progress_callback(completed[0], total, ticker)
        
        return result
    
    from concurrent.futures import ThreadPoolExecutor
    import concurrent.futures as _cf
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(_enrich_single, h): i for i, h in enumerate(holdings)}
        results = [None] * len(holdings)
        for f in _cf.as_completed(futures, timeout=180):
            idx = futures[f]
            try:
                results[idx] = f.result(timeout=45)
            except Exception as exc:
                h = holdings[idx]
                results[idx] = _build_fallback(h, exc)
                with lock:
                    completed[0] += 1
                    if progress_callback:
                        progress_callback(completed[0], total, f"{h.ticker} (fallback)")
        
        # Fill any remaining Nones
        for i, r in enumerate(results):
            if r is None:
                results[i] = _build_fallback(holdings[i])
    
    return [r for r in results if r is not None]


def _holding_impact_pct(e: dict, scenario: dict) -> float:
    """Scenario return of one enriched holding in percent.

    R_i = β_market × market_leg + Σ β_k × ΔF_k + sector/PSU overrides, where the
    market leg is the scenario's market shock, else its size-segment shock for
    holdings in that bucket, else its Nifty move.
    """
    if e["sector"] == "Cash":
        return 0.0
    shocks = scenario.get("shocks", {})
    betas = e["betas"]
    market_leg = shocks.get("market")
    if market_leg is None:
        market_leg = scenario.get("nifty", 0.0)
        for size_key, bucket in _SIZE_LEGS.items():
            if size_key in shocks and e.get("size_bucket") == bucket:
                market_leg = shocks[size_key]
    impact = betas.get("market", 1.0) * market_leg
    impact += sum(
        betas.get(k, 0.0) * v
        for k, v in shocks.items()
        if k != "market" and k not in _SIZE_LEGS
    )
    overrides = scenario.get("sector", {})
    impact += overrides.get(e["sector"], 0.0)
    if e["ticker"].split(".")[0] in PSU_TICKERS:
        impact += overrides.get("PSU", 0.0)
    return float(impact)


def _data_quality(enriched: list[dict], cov_source: str) -> dict[str, Any]:
    """Job-level provenance: which inputs were measured and which were defaults."""
    stocks = [e for e in enriched if e["sector"] != "Cash"]
    stock_value = sum(e["value"] for e in stocks)
    live_value = sum(e["value"] for e in stocks if e["price_source"] == "live")
    coverage_pct = round(100.0 * live_value / stock_value, 1) if stock_value > 0 else 100.0
    return {
        "holdings_total": len(stocks),
        "live_priced": sum(1 for e in stocks if e["price_source"] == "live"),
        "cost_basis_tickers": [e["ticker"] for e in stocks if e["price_source"] != "live"],
        "default_volatility_tickers": [e["ticker"] for e in stocks if e["vol_source"] != "historical"],
        "default_adv_tickers": [e["ticker"] for e in stocks if e["adv_source"] != "info"],
        "default_beta_tickers": [
            e["ticker"] for e in stocks if e["betas"].get("market_beta_source") != "estimated"
        ],
        "covariance": cov_source,
        "macro_betas": "not_estimated",
        "coverage_pct": coverage_pct,
        "degraded": coverage_pct < DEGRADED_COVERAGE_PCT or cov_source != "historical",
    }


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

    Raises RuntimeError when less than MIN_PRICED_COVERAGE_PCT of the stock value
    could be priced live (the job is then marked FAILED instead of reporting
    numbers built on cost basis).
    """
    from services.math_engines.liquidity import square_root_impact, portfolio_liquidity_loss, liquidity_score
    from services.math_engines.concentration import compute_concentration_analysis
    from services.math_engines.scoring import compute_all_scores
    from services.math_engines.covariance import fetch_historical_returns, compute_covariance_matrix, crisis_covariance_from
    
    def _emit_phase(checkpoint: str, pct: int, message: str) -> None:
        if phase_callback:
            phase_callback(checkpoint, pct, message)

    valid_scenarios = [
        key.lower().strip()
        for key in scenarios
        if key.lower().strip() in SCENARIOS_DEF
    ]
    if not valid_scenarios:
        return []

    # Phase 1: Enrich holdings (parallel yfinance)
    _emit_phase("enrich", 5, "Loading prices, betas, and liquidity inputs")
    enriched = enrich_holdings(holdings, progress_callback=progress_callback)
    total_value = sum(e["value"] for e in enriched)
    if total_value <= 0:
        return []
    
    weights = np.array([e["value"] / total_value for e in enriched])
    tickers = [e["ticker"] for e in enriched]
    symbols = [e.get("yf_symbol", e["ticker"]) for e in enriched]
    sectors = [e["sector"] for e in enriched]
    stock_symbols = [s for s, e in zip(symbols, enriched) if e["sector"] != "Cash"]
    
    # Phase 2: Fetch empirical covariance from historical returns
    _emit_phase("covariance", 55, "Building historical covariance matrix")
    returns_dict = fetch_historical_returns(stock_symbols, period="2y") if stock_symbols else {}
    usable_returns = {
        s: np.asarray(r, dtype=float)
        for s, r in returns_dict.items()
        if r is not None and len(r) >= MIN_RETURNS
    }

    # Daily sigma per holding: measured from returns, else a beta-based fallback.
    for e, sym in zip(enriched, symbols):
        if e["sector"] == "Cash":
            e["daily_vol"], e["vol_source"] = 0.0, "cash"
        elif sym in usable_returns:
            e["daily_vol"] = float(np.std(usable_returns[sym][-252:], ddof=1))
            e["vol_source"] = "historical"
        else:
            e["daily_vol"], e["vol_source"] = float(e["fallback_daily_vol"]), "default"

    measured = sum(1 for s in stock_symbols if s in usable_returns)
    if stock_symbols and measured == len(stock_symbols):
        cov_source = "historical"
    elif measured > 0:
        cov_source = "partial"
    else:
        cov_source = "identity_fallback" if stock_symbols else "historical"

    data_quality = _data_quality(enriched, cov_source)
    if stock_symbols and data_quality["coverage_pct"] < MIN_PRICED_COVERAGE_PCT:
        raise RuntimeError(
            f"Insufficient market data: only {data_quality['coverage_pct']}% "
            "of portfolio value could be priced"
        )

    cov = compute_covariance_matrix(usable_returns, symbols)
    # Cash has no variance; unmeasured stocks keep their fallback variance and no correlation.
    for i, e in enumerate(enriched):
        if e["vol_source"] != "historical":
            cov[i, :] = 0.0
            cov[:, i] = 0.0
            cov[i, i] = e["daily_vol"] ** 2
    
    # Calculate historical skewness and kurtosis of the portfolio for Cornish-Fisher
    port_rets_list = []
    for sym, weight in zip(symbols, weights):
        rets = usable_returns.get(sym)
        if rets is not None:
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
    crisis_cov = crisis_covariance_from(cov, broken_arrow_corr=0.85)

    # Phase 3: Concentration analysis (base covariance, updated per-scenario)
    _emit_phase(
        "scenarios",
        70,
        f"Running {len(valid_scenarios)} portfolio shock scenario(s)",
    )

    # Liquidity inputs do not depend on the scenario.
    liq_data = [
        {
            "ticker": e["ticker"], "shares": e["shares"], "price": e["price"],
            "avg_daily_volume": e["avg_daily_volume"], "volatility": e["daily_vol"],
            "spread_bps": e["spread_bps"],
        }
        for e in enriched if e["sector"] != "Cash"
    ]
    portfolio_liq = portfolio_liquidity_loss(liq_data, volume_suppression=0.4, gamma=0.2)
    
    results = []
    for scenario_index, sc_key_lower in enumerate(valid_scenarios):
        
        scenario = SCENARIOS_DEF[sc_key_lower]
        
        # Phase 4: Per-holding impact
        holdings_results = []
        total_impact_inr = 0.0
        
        for i, e in enumerate(enriched):
            w = weights[i]
            impact_pct = _holding_impact_pct(e, scenario)
            impact_inr = e["value"] * (impact_pct / 100.0)
            total_impact_inr += impact_inr
            
            # Liquidity penalty per holding (crisis volume suppression = 0.4)
            liq = square_root_impact(
                shares_held=e["shares"],
                avg_daily_volume=e["avg_daily_volume"],
                daily_volatility=e["daily_vol"],
                base_spread_bps=e["spread_bps"],
                gamma=0.2,
                volume_suppression=0.4,
            )
            
            holdings_results.append({
                "ticker": e["ticker"],
                "company_name": e["company_name"],
                "sector": e["sector"],
                "value": round(e["value"], 2),
                "weight_pct": round(float(w) * 100, 2),
                "impact_pct": round(impact_pct, 2),
                "impact_inr": round(impact_inr, 2),
                "liquidity_penalty_pct": round(liq.impact_pct, 4),
                "liquidity_penalty_inr": round(e["value"] * liq.impact_pct / 100, 2),
                "is_estimated": e["sector"] != "Cash" and (
                    e["price_source"] != "live"
                    or e["vol_source"] != "historical"
                    or e["adv_source"] != "info"
                    or e["betas"].get("market_beta_source") != "estimated"
                ),
            })
        
        # Sort: worst hit first
        holdings_results.sort(key=lambda x: x["impact_pct"])
        
        # Portfolio-level metrics. "Worst case" = scenario loss plus forced-liquidation cost.
        total_impact_pct = (total_impact_inr / total_value) * 100.0
        worst_case_pct = (
            (total_impact_inr - portfolio_liq.total_liquidity_loss_inr) / total_value
        ) * 100.0
        
        # Phase 6: Scoring (crisis correlations for crash scenarios)
        is_severe_crash = "CRASH" in scenario["name"] or "RECESSION" in scenario["name"]
        scenario_cov = crisis_cov if is_severe_crash else cov
        scen_conc = compute_concentration_analysis(tickers, weights, sectors, scenario_cov).model_dump()

        port_daily_vol = float(np.sqrt(max(float(weights @ scenario_cov @ weights), 0.0)))
        scores = compute_all_scores(
            portfolio_vol_annualized=port_daily_vol * np.sqrt(252),
            worst_case_loss_pct=worst_case_pct,
            macro_betas={},  # not estimated -> neutral "unknown" fragility
            liquidity_impact_pct=portfolio_liq.total_liquidity_loss_pct,
            concentration_hhi=scen_conc["hhi"],
            parametric_var_95_pct=1.645 * port_daily_vol * np.sqrt(10) * 100.0,  # 10-day 95% VaR
            cvar_99_pct=abs(worst_case_pct),
            liquidity_score_raw=liquidity_score(portfolio_liq.total_liquidity_loss_pct),
            skewness=port_skew,
            kurtosis=port_kurt,
        ).model_dump()
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
                "total_loss_pct": portfolio_liq.total_liquidity_loss_pct,
                "total_loss_inr": portfolio_liq.total_liquidity_loss_inr,
            },
            "data_quality": data_quality,
            "assumptions": [MACRO_ASSUMPTION],
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
