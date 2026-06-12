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


def _value_score(f: dict) -> int | None:
    pe, pb = f.get("pe_ratio"), f.get("pb_ratio")
    parts = []
    if isinstance(pe, (int, float)) and pe > 0:
        parts.append(_clamp(100 - (pe / 40.0) * 100))   # PE 0→100, 40+→0
    if isinstance(pb, (int, float)) and pb > 0:
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


def _compute_factor_scores(ticker: str, exchange: str) -> dict | None:
    try:
        from services.nse_data_provider import get_fundamentals
        f = get_fundamentals(ticker, exchange) or {}
    except Exception:
        f = {}
    scores = {
        "value":          _value_score(f),
        "quality":        _quality_score(f),
        "momentum":       _momentum_score(ticker, exchange),
        "growth":         None,    # needs multi-year earnings; left honest until sourced
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


def _financial_trends(ticker: str, exchange: str) -> dict | None:
    """Best-effort multi-year series from yfinance financials. None if unavailable."""
    try:
        import yfinance as yf
        suffix = ".NS" if exchange == "NSE" else ".BO"
        sym = ticker if ticker.endswith((".NS", ".BO")) else f"{ticker}{suffix}"
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


def _peer_comparison(ticker: str, exchange: str) -> list:
    """Sector peer table. Requires a peer/sector source; returns [] until one is wired."""
    try:
        from services.nse_data_provider import get_sector_peers  # not yet present
        return get_sector_peers(ticker, exchange) or []
    except Exception:
        return []


def build_extreme_bundles(ticker: str, exchange: str = "NSE") -> dict:
    """Assemble all deterministic graph bundles for an extreme analysis result."""
    return {
        "factor_scores":    _compute_factor_scores(ticker, exchange),
        "piotroski":        _compute_piotroski(ticker),
        "financial_trends": _financial_trends(ticker, exchange),
        "ownership_trends": _ownership_trends(ticker),
        "peer_comparison":  _peer_comparison(ticker, exchange),
    }
