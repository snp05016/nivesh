"""
Portfolio chart generation for Nivesh app.
Pure Python data visualization using matplotlib — no AI/LLM calls.
Generates up to 11 PNG charts with dark professional theme and Indian numbering.
"""

import os
import math
from datetime import datetime, date, timedelta
from pathlib import Path
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend — safe for server use
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

from database import get_session, Portfolio, PortfolioValuationHistory, AnalysisHistory
from helpers import _to_ns, _yf_price, _yf_fetch_info


# ---------------------------------------------------------------------------
# Dark professional theme constants
# ---------------------------------------------------------------------------
BG_COLOR = "#1a1a2e"
GRID_COLOR = "#2d2d44"
TEXT_COLOR = "#e0e0e0"
ACCENT_GREEN = "#00b894"
ACCENT_RED = "#e74c3c"
ACCENT_BLUE = "#0984e3"
ACCENT_ORANGE = "#e17055"
ACCENT_PURPLE = "#a29bfe"
ACCENT_YELLOW = "#fdcb6e"
ACCENT_TEAL = "#00cec9"

CHART_COLORS = [
    "#00b894", "#0984e3", "#e17055", "#a29bfe", "#fdcb6e",
    "#00cec9", "#e74c3c", "#6c5ce7", "#fd79a8", "#55efc4",
    "#fab1a0", "#81ecec", "#dfe6e9", "#ffeaa7", "#74b9ff",
]

# Approximate Nifty 50 sector weights for comparison chart
NIFTY_SECTOR_WEIGHTS = {
    "Banking": 33.0, "IT": 14.0, "Oil & Gas": 12.0,
    "Auto": 6.5, "FMCG": 6.0, "Pharma": 4.5,
    "Power": 4.0, "Finance": 3.5, "Metals": 3.0,
    "Cement": 2.5, "Telecom": 2.5, "Engineering": 2.0,
    "Consumer": 2.0, "Steel": 1.5, "Paints": 1.0,
    "Mining": 1.0, "Diversified": 0.5, "Other": 0.5,
}


# ---------------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------------
def _setup_dark_style():
    """Configure matplotlib for dark professional theme."""
    plt.rcParams.update({
        "figure.facecolor": BG_COLOR,
        "axes.facecolor": BG_COLOR,
        "axes.edgecolor": GRID_COLOR,
        "axes.labelcolor": TEXT_COLOR,
        "text.color": TEXT_COLOR,
        "xtick.color": TEXT_COLOR,
        "ytick.color": TEXT_COLOR,
        "grid.color": GRID_COLOR,
        "grid.alpha": 0.3,
        "figure.dpi": 150,
        "savefig.dpi": 150,
        "savefig.facecolor": BG_COLOR,
        "savefig.bbox": "tight",
        "font.size": 10,
        "axes.titlesize": 13,
        "axes.labelsize": 10,
    })


# ---------------------------------------------------------------------------
# Indian formatting
# ---------------------------------------------------------------------------
def _format_indian_short(value: float | None) -> str:
    """Format a numeric INR value in Indian notation: Cr / L / plain."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "₹0"
    abs_val = abs(value)
    sign = "-" if value < 0 else ""
    if abs_val >= 1_00_00_000:
        return f"{sign}₹{abs_val / 1_00_00_000:,.2f} Cr"
    elif abs_val >= 1_00_000:
        return f"{sign}₹{abs_val / 1_00_000:,.2f} L"
    else:
        return f"{sign}₹{abs_val:,.0f}"


def _format_indian_axis(x, _pos=None) -> str:
    """Formatter for matplotlib axis ticks in Indian notation."""
    abs_x = abs(x)
    if abs_x >= 1_00_00_000:
        return f"₹{x / 1_00_00_000:.1f}Cr"
    elif abs_x >= 1_00_000:
        return f"₹{x / 1_00_000:.1f}L"
    else:
        return f"₹{x:,.0f}"


# ---------------------------------------------------------------------------
# Chart filename helper
# ---------------------------------------------------------------------------
def _chart_filename(user_id: int, n: int) -> str:
    return f"chart_{user_id}_{n}.png"


# ---------------------------------------------------------------------------
# Sector lookup via yfinance
# ---------------------------------------------------------------------------
_sector_cache: dict[str, str] = {}


def _get_sector(ticker: str) -> str:
    """Look up sector for a ticker via yfinance info, with in-memory cache."""
    t = ticker.upper()
    if t in _sector_cache:
        return _sector_cache[t]
    try:
        ns = _to_ns(t)
        info = _yf_fetch_info(ns)
        sector = info.get("sector") or info.get("industry") or "Other"
        _sector_cache[t] = sector
        return sector
    except Exception:
        _sector_cache[t] = "Other"
        return "Other"


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------
def generate_portfolio_charts(user_id: int, output_dir: str) -> list[dict]:
    """
    Generate all portfolio charts as PNG files.

    Args:
        user_id: The user ID whose portfolio to chart.
        output_dir: Directory to save chart PNGs.

    Returns:
        List of dicts: [{filename, title, description}, ...]
        Empty list if user has no holdings.
    """
    os.makedirs(output_dir, exist_ok=True)
    _setup_dark_style()

    # ── Step 1: Fetch data from DB ──────────────────────────────────────
    with get_session() as session:
        holdings = session.query(Portfolio).filter(
            Portfolio.user_id == user_id,
            Portfolio.group_name == "holdings",
        ).all()

        valuation_history = (
            session.query(PortfolioValuationHistory)
            .filter(PortfolioValuationHistory.user_id == user_id)
            .order_by(PortfolioValuationHistory.snapshot_date.asc())
            .all()
        )

        # Latest signal per ticker
        ticker_signals: dict[str, str] = {}
        for h in holdings:
            row = (
                session.query(AnalysisHistory)
                .filter(AnalysisHistory.ticker == h.ticker)
                .order_by(AnalysisHistory.created_at.desc())
                .first()
            )
            if row:
                ticker_signals[h.ticker] = row.signal

    if not holdings:
        return []

    # ── Step 2: Enrich holdings with live prices & computed fields ──────
    enriched = []
    for h in holdings:
        ns = _to_ns(h.ticker)
        current_price, _ = _yf_price(ns)
        invested = h.shares * h.buy_price
        current_val = h.shares * current_price if current_price else 0.0
        pnl = current_val - invested
        pnl_pct = (pnl / invested * 100) if invested > 0 else 0.0
        sector = _get_sector(h.ticker)
        signal = ticker_signals.get(h.ticker, "N/A")
        purchase_date = getattr(h, "purchase_date", None)
        created_at = getattr(h, "created_at", None)
        # Holding period in days
        hold_days = None
        ref_date = purchase_date or created_at
        if ref_date:
            try:
                if isinstance(ref_date, str):
                    ref_date = datetime.strptime(ref_date[:10], "%Y-%m-%d")
                hold_days = (datetime.utcnow() - ref_date).days
            except Exception:
                pass

        enriched.append({
            "ticker": h.ticker,
            "company_name": h.company_name or h.ticker,
            "shares": h.shares,
            "buy_price": h.buy_price,
            "current_price": current_price or 0.0,
            "invested": invested,
            "current_value": current_val,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "sector": sector,
            "signal": signal,
            "hold_days": hold_days,
        })

    total_value = sum(e["current_value"] for e in enriched)
    total_invested = sum(e["invested"] for e in enriched)

    charts: list[dict] = []
    n = 0  # chart sequence number

    # ═══════════════════════════════════════════════════════════════════
    # Chart 1: Sector Allocation Pie
    # ═══════════════════════════════════════════════════════════════════
    try:
        sector_values: dict[str, float] = {}
        for e in enriched:
            sector_values[e["sector"]] = sector_values.get(e["sector"], 0.0) + e["current_value"]

        sectors = sorted(sector_values.items(), key=lambda x: x[1], reverse=True)
        labels = [s[0] for s in sectors]
        values = [s[1] for s in sectors]
        colors = CHART_COLORS[:len(labels)]

        fig, ax = plt.subplots(figsize=(8, 5))
        wedges, texts, autotexts = ax.pie(
            values, labels=None, autopct="%1.1f%%",
            colors=colors, pctdistance=0.75,
            textprops={"color": TEXT_COLOR, "fontsize": 8},
        )
        for at in autotexts:
            at.set_color(BG_COLOR)
            at.set_fontweight("bold")

        legend_labels = [
            f"{l} ({_format_indian_short(v)})"
            for l, v in zip(labels, values)
        ]
        ax.legend(
            wedges, legend_labels,
            loc="center left", bbox_to_anchor=(1, 0.5), fontsize=7,
            labelcolor=TEXT_COLOR, framealpha=0.3, facecolor=BG_COLOR,
            edgecolor=GRID_COLOR,
        )
        ax.set_title("Sector Allocation", fontweight="bold", pad=15)

        fname = _chart_filename(user_id, n)
        fig.savefig(os.path.join(output_dir, fname))
        plt.close(fig)
        charts.append({
            "filename": fname,
            "title": "Sector Allocation",
            "description": f"Portfolio distribution across {len(sectors)} sectors",
        })
        n += 1
    except Exception as exc:
        print(f"[CHART] Sector Allocation failed: {exc}")

    # ═══════════════════════════════════════════════════════════════════
    # Chart 2: Sector P&L Horizontal Bar
    # ═══════════════════════════════════════════════════════════════════
    try:
        sector_pnl: dict[str, float] = {}
        for e in enriched:
            sector_pnl[e["sector"]] = sector_pnl.get(e["sector"], 0.0) + e["pnl"]

        sp_sorted = sorted(sector_pnl.items(), key=lambda x: x[1], reverse=True)
        s_labels = [s[0] for s in sp_sorted]
        s_values = [s[1] for s in sp_sorted]
        s_colors = [ACCENT_GREEN if v >= 0 else ACCENT_RED for v in s_values]

        fig, ax = plt.subplots(figsize=(8, 5))
        bars = ax.barh(s_labels, s_values, color=s_colors, height=0.6)
        ax.axvline(0, color="white", linewidth=0.5)
        ax.set_xlabel("Profit / Loss")
        ax.set_title("Sector P&L", fontweight="bold")
        ax.xaxis.set_major_formatter(mticker.FuncFormatter(_format_indian_axis))
        ax.invert_yaxis()
        ax.grid(axis="x", alpha=0.2)

        for i, v in enumerate(s_values):
            offset = max(abs(v) * 0.02, 500)
            ax.text(v + offset, i, _format_indian_short(v),
                    va="center", fontsize=8, color=TEXT_COLOR)

        fname = _chart_filename(user_id, n)
        fig.savefig(os.path.join(output_dir, fname))
        plt.close(fig)
        charts.append({
            "filename": fname,
            "title": "Sector P&L",
            "description": "Profit/Loss aggregated by sector",
        })
        n += 1
    except Exception as exc:
        print(f"[CHART] Sector P&L failed: {exc}")

    # ═══════════════════════════════════════════════════════════════════
    # Chart 3: Top 10 Holdings by Value
    # ═══════════════════════════════════════════════════════════════════
    try:
        top10 = sorted(enriched, key=lambda x: x["current_value"], reverse=True)[:10]
        t_labels = [e["ticker"] for e in top10]
        t_values = [e["current_value"] for e in top10]
        t_colors = [ACCENT_GREEN if e["pnl"] >= 0 else ACCENT_RED for e in top10]

        fig, ax = plt.subplots(figsize=(8, 5))
        ax.barh(t_labels, t_values, color=t_colors, height=0.6)
        ax.set_xlabel("Current Value")
        ax.set_title(f"Top {len(top10)} Holdings by Value", fontweight="bold")
        ax.xaxis.set_major_formatter(mticker.FuncFormatter(_format_indian_axis))
        ax.invert_yaxis()
        ax.grid(axis="x", alpha=0.2)

        for i, (v, e) in enumerate(zip(t_values, top10)):
            label = f"{_format_indian_short(v)}  |  P&L: {e['pnl_pct']:+.1f}%"
            ax.text(v + max(v * 0.02, 500), i, label,
                    va="center", fontsize=7, color=TEXT_COLOR)

        fname = _chart_filename(user_id, n)
        fig.savefig(os.path.join(output_dir, fname))
        plt.close(fig)
        charts.append({
            "filename": fname,
            "title": "Top Holdings",
            "description": "Largest holdings by current market value",
        })
        n += 1
    except Exception as exc:
        print(f"[CHART] Top Holdings failed: {exc}")

    # ═══════════════════════════════════════════════════════════════════
    # Chart 4: Portfolio Value Over Time (Line) or Current Value (Bar)
    # ═══════════════════════════════════════════════════════════════════
    try:
        fig, ax = plt.subplots(figsize=(8, 5))

        if len(valuation_history) >= 2:
            dates = [datetime.strptime(v.snapshot_date, "%Y-%m-%d") for v in valuation_history]
            vals = [v.total_value for v in valuation_history]
            invested_vals = [v.total_invested for v in valuation_history]

            ax.fill_between(dates, vals, invested_vals, alpha=0.15, color=ACCENT_GREEN)
            ax.plot(dates, vals, color=ACCENT_GREEN, linewidth=2, label="Portfolio Value")
            ax.plot(dates, invested_vals, color=ACCENT_BLUE, linewidth=1.5,
                    linestyle="--", label="Total Invested")
            ax.set_ylabel("Value")
            ax.set_title("Portfolio Value Over Time", fontweight="bold")
            ax.yaxis.set_major_formatter(mticker.FuncFormatter(_format_indian_axis))
            ax.legend(loc="upper left", fontsize=8, facecolor=BG_COLOR,
                      edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR)
            ax.grid(alpha=0.2)
            fig.autofmt_xdate()
            desc = "Portfolio value tracked over time with cost basis"
        else:
            # Fallback: bar chart of current values
            e_sorted = sorted(enriched, key=lambda x: x["current_value"], reverse=True)
            e_labels = [e["ticker"] for e in e_sorted]
            e_values = [e["current_value"] for e in e_sorted]
            colors = [ACCENT_GREEN if e["pnl"] >= 0 else ACCENT_RED for e in e_sorted]

            ax.bar(range(len(e_labels)), e_values, color=colors)
            ax.set_xticks(range(len(e_labels)))
            ax.set_xticklabels(e_labels, rotation=45, ha="right", fontsize=7)
            ax.set_ylabel("Value")
            ax.set_title("Portfolio Value by Holding", fontweight="bold")
            ax.yaxis.set_major_formatter(mticker.FuncFormatter(_format_indian_axis))
            ax.grid(axis="y", alpha=0.2)
            desc = "Current value by holding (no history available)"

        fname = _chart_filename(user_id, n)
        fig.savefig(os.path.join(output_dir, fname))
        plt.close(fig)
        charts.append({
            "filename": fname,
            "title": "Value History",
            "description": desc,
        })
        n += 1
    except Exception as exc:
        print(f"[CHART] Value History failed: {exc}")

    # ═══════════════════════════════════════════════════════════════════
    # Chart 5: Buy vs Current Price Scatter
    # ═══════════════════════════════════════════════════════════════════
    try:
        valid = [e for e in enriched if e["current_price"] > 0]
        if valid:
            buy_prices = [e["buy_price"] for e in valid]
            cur_prices = [e["current_price"] for e in valid]
            tickers = [e["ticker"] for e in valid]
            max_p = max(max(buy_prices), max(cur_prices)) * 1.15

            fig, ax = plt.subplots(figsize=(8, 5))
            ax.plot([0, max_p], [0, max_p], "--", color=GRID_COLOR,
                    linewidth=1, label="Breakeven")

            for bp, cp, tk in zip(buy_prices, cur_prices, tickers):
                color = ACCENT_GREEN if cp >= bp else ACCENT_RED
                ax.scatter(bp, cp, color=color, s=70, alpha=0.85,
                           edgecolors="white", linewidth=0.5, zorder=5)
                ax.annotate(tk, (bp, cp), textcoords="offset points",
                            xytext=(5, 5), fontsize=6, color=TEXT_COLOR, alpha=0.85)

            ax.set_xlabel("Buy Price (₹)")
            ax.set_ylabel("Current Price (₹)")
            ax.set_title("Buy vs Current Price", fontweight="bold")
            ax.legend(loc="upper left", fontsize=8, facecolor=BG_COLOR,
                      edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR)
            ax.grid(alpha=0.2)

            fname = _chart_filename(user_id, n)
            fig.savefig(os.path.join(output_dir, fname))
            plt.close(fig)
            charts.append({
                "filename": fname,
                "title": "Buy vs Current Price",
                "description": "Price movement since purchase — above line = gain",
            })
            n += 1
    except Exception as exc:
        print(f"[CHART] Buy vs Current failed: {exc}")

    # ═══════════════════════════════════════════════════════════════════
    # Chart 6: Price Distribution (Histogram / Bar)
    # ═══════════════════════════════════════════════════════════════════
    try:
        prices = [e["current_price"] for e in enriched if e["current_price"] > 0]
        if prices:
            brackets = [
                (0, 100, "₹0-100"), (100, 500, "₹100-500"),
                (500, 1000, "₹500-1K"), (1000, 5000, "₹1K-5K"),
                (5000, 10000, "₹5K-10K"), (10000, float("inf"), "₹10K+"),
            ]
            counts = []
            b_labels = []
            for lo, hi, label in brackets:
                cnt = sum(1 for p in prices if lo <= p < hi)
                if cnt > 0:
                    counts.append(cnt)
                    b_labels.append(label)

            if counts:
                fig, ax = plt.subplots(figsize=(8, 5))
                bar_colors = CHART_COLORS[:len(b_labels)]
                ax.bar(range(len(b_labels)), counts, color=bar_colors, alpha=0.85)
                ax.set_xticks(range(len(b_labels)))
                ax.set_xticklabels(b_labels, fontsize=9)
                ax.set_ylabel("Number of Holdings")
                ax.set_title("Price Distribution", fontweight="bold")
                ax.grid(axis="y", alpha=0.2)

                for i, c in enumerate(counts):
                    ax.text(i, c + 0.15, str(c), ha="center", fontsize=10,
                            fontweight="bold", color=TEXT_COLOR)

                fname = _chart_filename(user_id, n)
                fig.savefig(os.path.join(output_dir, fname))
                plt.close(fig)
                charts.append({
                    "filename": fname,
                    "title": "Price Distribution",
                    "description": "Number of holdings in each price bracket",
                })
                n += 1
    except Exception as exc:
        print(f"[CHART] Price Distribution failed: {exc}")

    # ═══════════════════════════════════════════════════════════════════
    # Chart 7: Daily P&L Waterfall (last 7 days)
    # ═══════════════════════════════════════════════════════════════════
    try:
        recent_snapshots = valuation_history[-8:]  # need up to 8 for 7 deltas
        if len(recent_snapshots) >= 2:
            dates = [r.snapshot_date for r in recent_snapshots]
            values = [r.total_value for r in recent_snapshots]
            # Day-over-day change
            deltas = []
            delta_dates = []
            for i in range(1, len(values)):
                deltas.append(values[i] - values[i - 1])
                delta_dates.append(dates[i])

            fig, ax = plt.subplots(figsize=(8, 5))
            colors = [ACCENT_GREEN if d >= 0 else ACCENT_RED for d in deltas]
            ax.bar(range(len(deltas)), deltas, color=colors)
            ax.set_xticks(range(len(deltas)))
            ax.set_xticklabels(delta_dates, rotation=30, ha="right", fontsize=7)
            ax.axhline(0, color="white", linewidth=0.5)
            ax.set_ylabel("Daily P&L Change")
            ax.set_title("Daily P&L Waterfall (Last 7 Days)", fontweight="bold")
            ax.yaxis.set_major_formatter(mticker.FuncFormatter(_format_indian_axis))
            ax.grid(axis="y", alpha=0.2)

            for i, d in enumerate(deltas):
                va = "bottom" if d >= 0 else "top"
                ax.text(i, d, _format_indian_short(d), ha="center", va=va,
                        fontsize=7, color=TEXT_COLOR)

            fname = _chart_filename(user_id, n)
            fig.savefig(os.path.join(output_dir, fname))
            plt.close(fig)
            charts.append({
                "filename": fname,
                "title": "Daily P&L Waterfall",
                "description": "Day-over-day portfolio value change",
            })
            n += 1
    except Exception as exc:
        print(f"[CHART] Daily P&L Waterfall failed: {exc}")

    # ═══════════════════════════════════════════════════════════════════
    # Chart 8: Sector Weight vs Nifty 50
    # ═══════════════════════════════════════════════════════════════════
    try:
        if total_value > 0:
            pf_sector_pct: dict[str, float] = {}
            for e in enriched:
                sec = e["sector"]
                pf_sector_pct[sec] = pf_sector_pct.get(sec, 0.0) + e["current_value"] / total_value * 100

            # Only show sectors present in portfolio with a Nifty benchmark
            common_sectors = sorted(
                set(pf_sector_pct.keys()) & set(NIFTY_SECTOR_WEIGHTS.keys()),
                key=lambda s: pf_sector_pct.get(s, 0), reverse=True,
            )

            if common_sectors:
                fig, ax = plt.subplots(figsize=(8, 5))
                x = np.arange(len(common_sectors))
                width = 0.35

                pf_vals = [pf_sector_pct.get(s, 0) for s in common_sectors]
                nifty_vals = [NIFTY_SECTOR_WEIGHTS.get(s, 0) for s in common_sectors]

                bars1 = ax.bar(x - width / 2, pf_vals, width, label="Your Portfolio",
                               color=ACCENT_GREEN, alpha=0.85)
                bars2 = ax.bar(x + width / 2, nifty_vals, width, label="Nifty 50",
                               color=ACCENT_BLUE, alpha=0.55)

                ax.set_xticks(x)
                ax.set_xticklabels(common_sectors, rotation=30, ha="right", fontsize=8)
                ax.set_ylabel("Weight (%)")
                ax.set_title("Sector Weight vs Nifty 50", fontweight="bold")
                ax.legend(loc="upper right", fontsize=8, facecolor=BG_COLOR,
                          edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR)
                ax.grid(axis="y", alpha=0.2)

                fname = _chart_filename(user_id, n)
                fig.savefig(os.path.join(output_dir, fname))
                plt.close(fig)
                charts.append({
                    "filename": fname,
                    "title": "Sector vs Nifty",
                    "description": "Your sector allocation compared to Nifty 50 benchmark",
                })
                n += 1
    except Exception as exc:
        print(f"[CHART] Sector vs Nifty failed: {exc}")

    # ═══════════════════════════════════════════════════════════════════
    # Chart 9: Top Gainers / Losers (or Dividend Yield if available)
    # ═══════════════════════════════════════════════════════════════════
    try:
        # Check if dividend yield data is available via yfinance
        div_yield_available = False
        div_by_sector: dict[str, float] = {}
        div_counts: dict[str, int] = {}

        for e in enriched:
            try:
                ns = _to_ns(e["ticker"])
                info = _yf_fetch_info(ns)
                dy = info.get("dividendYield") or info.get("trailingAnnualDividendYield")
                if dy is not None and dy > 0:
                    sec = e["sector"]
                    div_by_sector[sec] = div_by_sector.get(sec, 0.0) + float(dy)
                    div_counts[sec] = div_counts.get(sec, 0) + 1
                    div_yield_available = True
            except Exception:
                pass

        if div_yield_available and div_by_sector:
            # Average dividend yield by sector
            avg_div = {
                sec: div_by_sector[sec] / div_counts[sec] * 100
                for sec in div_by_sector
            }
            div_sorted = sorted(avg_div.items(), key=lambda x: x[1], reverse=True)
            d_labels = [s[0] for s in div_sorted]
            d_values = [s[1] for s in div_sorted]

            fig, ax = plt.subplots(figsize=(8, 5))
            ax.barh(d_labels, d_values, color=ACCENT_TEAL, height=0.6)
            ax.set_xlabel("Dividend Yield (%)")
            ax.set_title("Avg Dividend Yield by Sector", fontweight="bold")
            ax.invert_yaxis()
            ax.grid(axis="x", alpha=0.2)

            for i, v in enumerate(d_values):
                ax.text(v + 0.05, i, f"{v:.2f}%", va="center", fontsize=8, color=TEXT_COLOR)

            fname = _chart_filename(user_id, n)
            fig.savefig(os.path.join(output_dir, fname))
            plt.close(fig)
            charts.append({
                "filename": fname,
                "title": "Dividend Yield by Sector",
                "description": "Average trailing dividend yield per sector",
            })
            n += 1
        else:
            # Fallback: Top Gainers / Losers by P&L%
            top_gainers = sorted(enriched, key=lambda x: x["pnl_pct"], reverse=True)[:5]
            top_losers = sorted(enriched, key=lambda x: x["pnl_pct"])[:5]
            combined = top_gainers + top_losers
            c_labels = [f"{e['ticker']}" for e in combined]
            c_values = [e["pnl_pct"] for e in combined]
            c_colors = [ACCENT_GREEN if v >= 0 else ACCENT_RED for v in c_values]

            fig, ax = plt.subplots(figsize=(8, 5))
            ax.barh(c_labels, c_values, color=c_colors, height=0.6)
            ax.axvline(0, color="white", linewidth=0.5)
            ax.set_xlabel("P&L %")
            ax.set_title("Top Gainers & Losers", fontweight="bold")
            ax.invert_yaxis()
            ax.grid(axis="x", alpha=0.2)

            for i, v in enumerate(c_values):
                va = "left" if v >= 0 else "right"
                offset = 0.5 if v >= 0 else -0.5
                ax.text(v + offset, i, f"{v:+.1f}%", va="center",
                        fontsize=8, color=TEXT_COLOR, ha=va)

            fname = _chart_filename(user_id, n)
            fig.savefig(os.path.join(output_dir, fname))
            plt.close(fig)
            charts.append({
                "filename": fname,
                "title": "Top Gainers & Losers",
                "description": "Best and worst performing holdings by P&L%",
            })
            n += 1
    except Exception as exc:
        print(f"[CHART] Gainers/Losers failed: {exc}")

    # ═══════════════════════════════════════════════════════════════════
    # Chart 10: Portfolio Concentration (Top 5 vs Rest)
    # ═══════════════════════════════════════════════════════════════════
    try:
        by_value = sorted(enriched, key=lambda x: x["current_value"], reverse=True)
        if len(by_value) >= 2:
            top5_value = sum(e["current_value"] for e in by_value[:5])
            rest_value = total_value - top5_value
            top5_pct = (top5_value / total_value * 100) if total_value > 0 else 0
            rest_pct = 100 - top5_pct

            fig, ax = plt.subplots(figsize=(8, 5))
            pie_values = [top5_value, rest_value]
            pie_labels_inner = [f"Top 5\n{top5_pct:.1f}%", f"Rest\n{rest_pct:.1f}%"]

            wedges, texts = ax.pie(
                pie_values, labels=None,
                colors=[ACCENT_ORANGE, GRID_COLOR],
                startangle=90, wedgeprops={"edgecolor": BG_COLOR, "linewidth": 2},
            )

            # Top 5 breakdown as text box
            top5_text = "\n".join(
                f"{i+1}. {e['ticker']}: {e['current_value']/total_value*100:.1f}%"
                for i, e in enumerate(by_value[:5])
            )
            ax.text(0, -0.85, top5_text, ha="center", va="top", fontsize=8,
                    color=TEXT_COLOR, fontfamily="monospace",
                    bbox=dict(boxstyle="round,pad=0.5", facecolor=BG_COLOR,
                              edgecolor=GRID_COLOR, alpha=0.8))

            ax.legend(
                wedges,
                [f"Top 5 Holdings ({_format_indian_short(top5_value)})",
                 f"Rest ({_format_indian_short(rest_value)})"],
                loc="upper center", bbox_to_anchor=(0.5, 0.05), fontsize=8,
                labelcolor=TEXT_COLOR, framealpha=0.3, facecolor=BG_COLOR,
            )
            ax.set_title("Portfolio Concentration", fontweight="bold", pad=20)

            fname = _chart_filename(user_id, n)
            fig.savefig(os.path.join(output_dir, fname))
            plt.close(fig)
            charts.append({
                "filename": fname,
                "title": "Portfolio Concentration",
                "description": f"Top 5 holdings make up {top5_pct:.1f}% of portfolio",
            })
            n += 1
    except Exception as exc:
        print(f"[CHART] Concentration failed: {exc}")

    # ═══════════════════════════════════════════════════════════════════
    # Chart 11: Risk/Reward Scatter (P&L% vs Holding Period)
    # ═══════════════════════════════════════════════════════════════════
    try:
        valid_rr = [e for e in enriched if e["hold_days"] is not None and e["hold_days"] > 0]
        if valid_rr:
            hold_days = [e["hold_days"] for e in valid_rr]
            pnl_pcts = [e["pnl_pct"] for e in valid_rr]
            tickers_rr = [e["ticker"] for e in valid_rr]
            sizes = [max(e["current_value"] / total_value * 500, 20) if total_value > 0 else 50
                     for e in valid_rr]

            fig, ax = plt.subplots(figsize=(8, 5))
            ax.axhline(0, color="white", linewidth=0.5, alpha=0.5)

            for hd, pp, tk, sz in zip(hold_days, pnl_pcts, tickers_rr, sizes):
                color = ACCENT_GREEN if pp >= 0 else ACCENT_RED
                ax.scatter(hd, pp, s=sz, color=color, alpha=0.75,
                           edgecolors="white", linewidth=0.5, zorder=5)
                ax.annotate(tk, (hd, pp), textcoords="offset points",
                            xytext=(5, 5), fontsize=6, color=TEXT_COLOR, alpha=0.8)

            ax.set_xlabel("Holding Period (Days)")
            ax.set_ylabel("P&L %")
            ax.set_title("Risk / Reward: P&L% vs Holding Period", fontweight="bold")
            ax.grid(alpha=0.2)

            fname = _chart_filename(user_id, n)
            fig.savefig(os.path.join(output_dir, fname))
            plt.close(fig)
            charts.append({
                "filename": fname,
                "title": "Risk/Reward Scatter",
                "description": "P&L% vs holding period — bubble size = portfolio weight",
            })
            n += 1
    except Exception as exc:
        print(f"[CHART] Risk/Reward failed: {exc}")

    return charts
