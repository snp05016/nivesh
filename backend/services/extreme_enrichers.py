"""Deterministic, code-computed graph bundles for *extreme* analysis.

Philosophy: the numbers a chart renders must be REAL and computed in Python — the
LLM only adds narrative. Every bundle is best-effort and degrades gracefully
(returns ``None`` / ``[]`` on missing data) so a flaky data source never breaks a run.

Bundles
-------
- factor_scores     : value/quality/momentum/growth/low_volatility (0-100), derived
                      from fundamentals + price history.
- piotroski         : full F-score breakdown (services.piotroski).
- financial_trends  : multi-year revenue/profit/margin series (best-effort, yfinance).
- ownership_trends  : promoter-pledging trend from stored AnalysisHistory rows.
- peer_comparison   : sector peer table (requires a peer source; [] until wired).
"""
from __future__ import annotations


# ── primitive scorers (each returns 0-100 or None) ──────────────────────────

def _clamp(x: float) -> int:
    return int(max(0, min(100, round(x))))


def _value_score(f: dict, peers_info: list[dict]) -> int | None:
    import statistics
    pe, pb = f.get("pe_ratio"), f.get("pb_ratio")
    
    pe_list = [p.get("trailingPE") for p in peers_info if isinstance(p.get("trailingPE"), (int, float))]
    pb_list = [p.get("priceToBook") for p in peers_info if isinstance(p.get("priceToBook"), (int, float))]
    
    if isinstance(pe, (int, float)): pe_list.append(pe)
    if isinstance(pb, (int, float)): pb_list.append(pb)
    
    parts = []
    if isinstance(pe, (int, float)) and pe > 0:
        if len(pe_list) > 1:
            median_pe = statistics.median(pe_list)
            stdev_pe = statistics.pstdev(pe_list) if len(pe_list) > 1 else 0
            if stdev_pe == 0:
                parts.append(_clamp(100 - (pe / 40.0) * 100))
            else:
                z_score = (median_pe - pe) / stdev_pe
                parts.append(_clamp(50 + z_score * 20))
        else:
            parts.append(_clamp(100 - (pe / 40.0) * 100))   # PE 0→100, 40+→0

    if isinstance(pb, (int, float)) and pb > 0:
        if len(pb_list) > 1:
            median_pb = statistics.median(pb_list)
            stdev_pb = statistics.pstdev(pb_list) if len(pb_list) > 1 else 0
            if stdev_pb == 0:
                parts.append(_clamp(100 - (pb / 8.0) * 100))
            else:
                z_score = (median_pb - pb) / stdev_pb
                parts.append(_clamp(50 + z_score * 20))
        else:
            parts.append(_clamp(100 - (pb / 8.0) * 100))     # PB 0→100, 8+→0

    return _clamp(sum(parts) / len(parts)) if parts else None


def _quality_score(f: dict) -> int | None:
    roe, dte = f.get("roe"), f.get("debt_to_equity")
    parts = []
    if isinstance(roe, (int, float)):
        roe_pct = roe * 100 if abs(roe) <= 1 else roe   # yfinance gives fraction
        parts.append(_clamp((roe_pct / 30.0) * 100))     # 30% ROE → 100
    if isinstance(dte, (int, float)) and dte >= 0:
        dte_ratio = dte / 100.0 if dte > 5 else dte      # yfinance often gives %
        parts.append(_clamp(100 - (dte_ratio / 2.0) * 100))  # D/E 0→100, 2+→0
    return _clamp(sum(parts) / len(parts)) if parts else None


def _momentum_score(ticker: str, exchange: str) -> int | None:
    try:
        from services.nse_data_provider import get_price_history
        hist = get_price_history(ticker, exchange, period="6mo")
        prices = [p["close"] for p in (hist or {}).get("prices", []) if p.get("close")]
        if len(prices) < 20:
            return None
        ret = (prices[-1] - prices[0]) / prices[0] * 100
        return _clamp(50 + ret)                          # +50% → 100, -50% → 0
    except Exception:
        return None


def _low_volatility_score(ticker: str, exchange: str) -> int | None:
    try:
        import statistics
        from services.nse_data_provider import get_price_history
        hist = get_price_history(ticker, exchange, period="6mo")
        prices = [p["close"] for p in (hist or {}).get("prices", []) if p.get("close")]
        if len(prices) < 20:
            return None
        rets = [(prices[i] - prices[i - 1]) / prices[i - 1] for i in range(1, len(prices))]
        vol = statistics.pstdev(rets) * 100               # daily % stdev
        return _clamp(100 - vol * 20)                     # 0% → 100, 5%+ → 0
    except Exception:
        return None


def _growth_score(fin_trends: dict | None) -> int | None:
    if not fin_trends or not fin_trends.get("revenue_cr") or not fin_trends.get("net_profit_cr"):
        return None
        
    rev = fin_trends["revenue_cr"]
    np = fin_trends["net_profit_cr"]
    
    if len(rev) < 2 or len(np) < 2:
        return None
        
    rev_start, rev_end = rev[0], rev[-1]
    np_start, np_end = np[0], np[-1]
    
    parts = []
    if rev_start and rev_end and rev_start > 0:
        rev_growth = (rev_end - rev_start) / rev_start * 100
        parts.append(_clamp(50 + (rev_growth / 20.0) * 50))
    
    if np_start and np_end and np_start > 0:
        np_growth = (np_end - np_start) / np_start * 100
        parts.append(_clamp(50 + (np_growth / 20.0) * 50))
        
    return _clamp(sum(parts) / len(parts)) if parts else None


def _compute_factor_scores(
    ticker: str,
    exchange: str,
    peers_info: list[dict] | None = None,
    fin_trends: dict | None = None,
) -> dict | None:
    try:
        from services.nse_data_provider import get_fundamentals
        f = get_fundamentals(ticker, exchange) or {}
    except Exception:
        f = {}
    scores = {
        "value":          _value_score(f, peers_info or []),
        "quality":        _quality_score(f),
        "momentum":       _momentum_score(ticker, exchange),
        "growth":         _growth_score(fin_trends),
        "low_volatility": _low_volatility_score(ticker, exchange),
    }
    return scores if any(v is not None for v in scores.values()) else None


def _compute_piotroski(ticker: str) -> dict | None:
    try:
        from services.piotroski import compute_piotroski
        out = compute_piotroski(ticker)
        return out or None
    except Exception:
        return None


def _financial_trends(ticker: str, exchange: str, prefetch_data: dict | None = None) -> dict | None:
    """Best-effort multi-year series from yfinance financials. None if unavailable."""
    try:
        import yfinance as yf
        suffix = ".NS" if exchange == "NSE" else ".BO"
        sym = ticker if ticker.endswith((".NS", ".BO")) else f"{ticker}{suffix}"
        
        if prefetch_data and "financials" in prefetch_data and prefetch_data["financials"] is not None:
            fin = prefetch_data["financials"]
        else:
            fin = yf.Ticker(sym).financials
            
        if fin is None or fin.empty:
            return None
        years = [str(c.year) for c in fin.columns][::-1]

        def _row(label):
            if label not in fin.index:
                return None
            vals = [fin.loc[label, c] for c in fin.columns][::-1]
            # convert to Crore (yfinance reports absolute INR)
            return [round(float(v) / 1e7, 2) if v == v else None for v in vals]

        revenue = _row("Total Revenue")
        net_profit = _row("Net Income")
        margin = None
        if revenue and net_profit:
            margin = [round(np / rv * 100, 2) if rv else None
                      for np, rv in zip(net_profit, revenue)]
        if not (revenue or net_profit):
            return None
        return {"years": years, "revenue_cr": revenue,
                "net_profit_cr": net_profit, "net_margin_pct": margin}
    except Exception:
        return None


def _ownership_trends(ticker: str) -> dict | None:
    """Promoter-pledging trend reconstructed from stored AnalysisHistory rows."""
    try:
        import database
        with database.get_session() as s:
            rows = (s.query(database.AnalysisHistory)
                      .filter(database.AnalysisHistory.ticker == ticker.upper(),
                              database.AnalysisHistory.promoter_pledged_pct.isnot(None))
                      .order_by(database.AnalysisHistory.created_at.asc()).all())
            points = [(r.analysis_date, r.promoter_pledged_pct) for r in rows]
        if len(points) < 2:
            return None
        return {"dates": [d for d, _ in points],
                "promoter_pledged_pct": [round(float(p), 2) for _, p in points]}
    except Exception:
        return None


def _get_peers_info(ticker: str, exchange: str, prefetch_data: dict | None = None) -> list[dict]:
    try:
        import yfinance as yf
        suffix = ".NS" if exchange == "NSE" else ".BO"
        sym = ticker if ticker.endswith((".NS", ".BO")) else f"{ticker}{suffix}"
        
        if prefetch_data and "info" in prefetch_data and prefetch_data["info"] is not None:
            info = prefetch_data["info"]
        else:
            info = yf.Ticker(sym).info
            
        industry_key = info.get("industryKey")
        if not industry_key:
            return []
            
        ind = yf.Industry(industry_key)
        df = ind.top_companies
        if df is None or df.empty:
            return []
            
        peers_info = []
        peer_syms = [p_sym for p_sym, _ in df.head(5).iterrows() if p_sym != sym]
        
        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_sym = {executor.submit(lambda s: yf.Ticker(s).info, p): p for p in peer_syms}
            for future in as_completed(future_to_sym):
                try:
                    p_info = future.result()
                    if p_info:
                        peers_info.append(p_info)
                except Exception:
                    pass
        return peers_info
    except Exception:
        return []


def _peer_comparison(peers_info: list[dict]) -> list:
    """Sector peer table."""
    peers = []
    for p in peers_info:
        sym = p.get("symbol", "")
        peers.append({
            "ticker": sym,
            "name": p.get("longName", p.get("shortName", sym))
        })
    return peers


def build_extreme_bundles(ticker: str, exchange: str = "NSE", prefetch_data: dict | None = None) -> dict:
    """Assemble all deterministic graph bundles for an extreme analysis result."""
    peers_info = _get_peers_info(ticker, exchange, prefetch_data)
    fin_trends = _financial_trends(ticker, exchange, prefetch_data)
    
    return {
        "factor_scores":    _compute_factor_scores(ticker, exchange, peers_info, fin_trends),
        "piotroski":        _compute_piotroski(ticker),
        "financial_trends": fin_trends,
        "ownership_trends": _ownership_trends(ticker),
        "peer_comparison":  _peer_comparison(peers_info),
    }
