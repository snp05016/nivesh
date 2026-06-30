import logging
"""
services/sector_rotation.py — Sector rotation logic based on Relative Rotation Graphs (RRG).

Computes momentum and relative strength for sectors and tracks institutional fund flows
to determine sector positioning.
"""
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

SECTOR_NAME_TO_TICKER = {name: ticker for ticker, name in SECTOR_TICKERS}

SECTOR_KEYWORD_MAP = {
    "bank": "PSU Bank",
    "fmcg": "FMCG",
    "consumer": "FMCG",
    "technology": "IT",
    "software": "IT",
    "it ": "IT",
    "pharma": "Pharma",
    "healthcare": "Pharma",
    "auto": "Auto",
    "realty": "Realty",
    "real estate": "Realty",
    "energy": "Energy",
    "oil": "Energy",
    "gas": "Energy",
    "metal": "Metal",
    "mining": "Metal",
}

RRG_LEADING_THRESHOLD = 100.0
RRG_IMPROVING_THRESHOLD = 100.0
RRG_WEAKENING_THRESHOLD = 100.0
RRG_LAGGING_THRESHOLD = 100.0

RRG_CONFIDENCE_LEADING = 0.05
RRG_CONFIDENCE_IMPROVING = 0.02
RRG_CONFIDENCE_WEAKENING = -0.03
RRG_CONFIDENCE_LAGGING = -0.08

RRG_RS_RATIO_PERIODS = 14
RRG_MOMENTUM_PERIODS = 10


def get_sector_rotation_data(period: str):
    """
    Fetch sector rotation data including momentum, returns, and institutional conviction.

    Args:
        period (str): The time period for analysis (e.g., '1m', '3m', '6m', '1y').

    Returns:
        dict: A dictionary containing the period and a list of sector performance metrics.
    """
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
            logging.info(f"Error processing sector {name}: {e}")

    return {"period": period, "sectors": sectors}


def _resolve_sector(ticker: str) -> str:
    """
    Resolve the sector for a given ticker by fetching info from yfinance.

    Args:
        ticker (str): The stock ticker symbol.

    Returns:
        str: The identified sector name, or "Unknown" if not found.
    """
    info = yf.Ticker(ticker).info
    sector = info.get("sector") or info.get("industry", "")
    if not sector:
        return "Unknown"
    sector_lower = sector.lower()
    for keyword, mapped_name in SECTOR_KEYWORD_MAP.items():
        if keyword in sector_lower:
            return mapped_name
    return "Unknown"


def _get_sector_etf(sector_name: str) -> str:
    """
    Get the benchmark ETF or index ticker for a given sector name.

    Args:
        sector_name (str): The sector name.

    Returns:
        str: The ETF or index ticker, defaulting to '^NSEI'.
    """
    return SECTOR_NAME_TO_TICKER.get(sector_name, "^NSEI")


def _compute_rs_ratio_and_momentum(
    sector_prices: list[float],
    benchmark_prices: list[float],
) -> tuple[float, float]:
    """
    Compute Relative Strength (RS) Ratio and Momentum for RRG analysis.

    Args:
        sector_prices (list[float]): Historical prices for the sector.
        benchmark_prices (list[float]): Historical prices for the benchmark.

    Returns:
        tuple[float, float]: A tuple containing RS Ratio and RS Momentum.
    """
    if len(sector_prices) < RRG_RS_RATIO_PERIODS + 1 or len(benchmark_prices) < RRG_RS_RATIO_PERIODS + 1:
        return 100.0, 100.0

    min_len = min(len(sector_prices), len(benchmark_prices))
    ratios: list[float] = []
    for i in range(min_len):
        denom = benchmark_prices[i]
        if denom == 0:
            return 100.0, 100.0
        ratios.append((sector_prices[i] / denom) * 100.0)

    latest_ratio = ratios[-1]
    past_ratio = ratios[-RRG_RS_RATIO_PERIODS]
    rs_ratio = 100.0 + (latest_ratio - past_ratio)

    if len(ratios) < RRG_MOMENTUM_PERIODS + 1:
        return round(rs_ratio, 2), 100.0

    roc_window = RRG_MOMENTUM_PERIODS
    rocs: list[float] = []
    for i in range(len(ratios) - roc_window, len(ratios)):
        prev = ratios[i - 1] if i > 0 else ratios[i]
        if prev == 0:
            return round(rs_ratio, 2), 100.0
        rocs.append(((ratios[i] - prev) / prev) * 100.0)

    avg_momentum = sum(rocs) / len(rocs)
    rs_momentum = 100.0 + avg_momentum

    return round(rs_ratio, 2), round(rs_momentum, 2)


def _compute_rrg_quadrant(rs_ratio: float, rs_momentum: float) -> str:
    """
    Determine the RRG quadrant based on RS Ratio and RS Momentum.

    Args:
        rs_ratio (float): The Relative Strength Ratio.
        rs_momentum (float): The Relative Strength Momentum.

    Returns:
        str: The RRG quadrant name ('Leading', 'Weakening', 'Improving', 'Lagging').
    """
    if rs_ratio >= RRG_LEADING_THRESHOLD and rs_momentum >= RRG_LEADING_THRESHOLD:
        return "Leading"
    if rs_ratio >= RRG_IMPROVING_THRESHOLD and rs_momentum < RRG_IMPROVING_THRESHOLD:
        return "Weakening"
    if rs_ratio < RRG_WEAKENING_THRESHOLD and rs_momentum >= RRG_WEAKENING_THRESHOLD:
        return "Improving"
    return "Lagging"


def _compute_confidence_modifier(quadrant: str) -> float:
    """
    Get the confidence modifier associated with an RRG quadrant.

    Args:
        quadrant (str): The RRG quadrant.

    Returns:
        float: The confidence modifier for the quadrant.
    """
    modifiers = {
        "Leading": RRG_CONFIDENCE_LEADING,
        "Improving": RRG_CONFIDENCE_IMPROVING,
        "Weakening": RRG_CONFIDENCE_WEAKENING,
        "Lagging": RRG_CONFIDENCE_LAGGING,
    }
    return modifiers.get(quadrant, 0.0)


def _compute_rrg_summary(quadrant: str) -> str:
    """
    Generate a human-readable summary for the current RRG quadrant.

    Args:
        quadrant (str): The RRG quadrant.

    Returns:
        str: A summary text explaining the current quadrant status.
    """
    summaries = {
        "Leading": (
            f"Stock is in a Leading quadrant (+{RRG_CONFIDENCE_LEADING*100:.0f}% confidence boost). "
            f"Strong relative performance vs benchmark."
        ),
        "Improving": (
            f"Stock is in an Improving quadrant (+{RRG_CONFIDENCE_IMPROVING*100:.0f}% confidence boost). "
            f"Momentum building, but relative strength below benchmark."
        ),
        "Weakening": (
            f"Stock is in a Weakening quadrant ({RRG_CONFIDENCE_WEAKENING*100:.0f}% confidence penalty). "
            f"Relative strength above benchmark but momentum fading."
        ),
        "Lagging": (
            f"Stock is in a Lagging quadrant ({RRG_CONFIDENCE_LAGGING*100:.0f}% confidence penalty). "
            f"Both relative strength and momentum below benchmark."
        ),
    }
    return summaries.get(quadrant, "RRG data unavailable.")


def compute_rrg_quadrant(ticker: str, benchmark: str = "^NSEI") -> dict:
    """
    Compute full RRG quadrant statistics for a given ticker.

    Args:
        ticker (str): The stock ticker symbol.
        benchmark (str): The benchmark index ticker. Defaults to '^NSEI'.

    Returns:
        dict: A dictionary containing RRG quadrant details, RS Ratio, RS Momentum,
        confidence modifier, and summary text.
    """
    try:
        sector = _resolve_sector(ticker)
        sector_etf = _get_sector_etf(sector)
        benchmark_etf = benchmark if sector_etf == "^NSEI" else "^NSEI"

        sector_hist = yf.Ticker(sector_etf).history(period="3mo")
        bench_hist = yf.Ticker(benchmark_etf).history(period="3mo")

        if sector_hist.empty or bench_hist.empty:
            return {
                "sector": sector if sector != "Unknown" else "Unknown",
                "rrg_quadrant": "Unknown",
                "rs_ratio": 0.0,
                "rs_momentum": 0.0,
                "confidence_modifier": 0.0,
                "rrg_summary": "Insufficient price data to compute RRG."
            }

        sector_prices = sector_hist["Close"].tolist()
        bench_prices = bench_hist["Close"].tolist()

        rs_ratio, rs_momentum = _compute_rs_ratio_and_momentum(sector_prices, bench_prices)
        quadrant = _compute_rrg_quadrant(rs_ratio, rs_momentum)
        modifier = _compute_confidence_modifier(quadrant)
        summary = _compute_rrg_summary(quadrant)

        return {
            "sector": sector,
            "rrg_quadrant": quadrant,
            "rs_ratio": rs_ratio,
            "rs_momentum": rs_momentum,
            "confidence_modifier": modifier,
            "rrg_summary": summary,
        }

    except Exception as _e:
        return {
            "sector": "Unknown",
            "rrg_quadrant": "Unknown",
            "rs_ratio": 0.0,
            "rs_momentum": 0.0,
            "confidence_modifier": 0.0,
            "rrg_summary": "Unable to compute RRG data for this ticker.",
        }
