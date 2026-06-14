"""
services/nightly_jobs.py — Nightly batch jobs for pre-computing indicators.

Run via cron or directly:
    python3 -m services.nightly_jobs

Tasks:
    rank_01 — Pre-compute SMA/close indicators for Nifty 500 and cache to disk.
    rank_05 — Batch compute RRG quadrants for major sector ETFs.
"""

import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

# Top Nifty 500 symbols — subset used when DB query returns nothing
NIFTY_500_SYMBOLS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "HINDUNILVR.NS",
    "ICICIBANK.NS", "SBIN.NS", "BAJFINANCE.NS", "LT.NS", "AXISBANK.NS",
    "WIPRO.NS", "SUNPHARMA.NS", "TITAN.NS", "MARUTI.NS", "KOTAKBANK.NS",
    "POWERGRID.NS", "ITC.NS", "BHARTIARTL.NS", "ASIANPAINT.NS", "HCLTECH.NS",
    "ADANIENT.NS", "TATAMOTORS.NS", "ONGC.NS", "NTPC.NS", "COALINDIA.NS",
    "TATASTEEL.NS", "JSWSTEEL.NS", "TECHM.NS", "DRREDDY.NS", "CIPLA.NS",
    "ULTRACEMCO.NS", "NESTLEIND.NS", "DIVISLAB.NS", "EICHERMOT.NS", "BAJAJFINSV.NS",
    "HEROMOTOCO.NS", "BPCL.NS", "GRASIM.NS", "INDUSINDBK.NS", "SBILIFE.NS",
    "APOLLOHOSP.NS", "HDFCLIFE.NS", "TATACONSUM.NS", "PIDILITIND.NS", "DABUR.NS",
    "GODREJCP.NS", "BERGEPAINT.NS", "HAVELLS.NS", "CHOLAFIN.NS", "MUTHOOTFIN.NS",
]


def _get_nifty500_from_db() -> list[str]:
    """Fetch up to 500 distinct tickers from the PKScreener signals table."""
    try:
        from database import get_session, PKScreenerSignal
        with get_session() as session:
            rows = (
                session.query(PKScreenerSignal.ticker)
                .distinct()
                .limit(500)
                .all()
            )
            tickers = [r.ticker for r in rows if r.ticker]
            if tickers:
                # Ensure .NS suffix for yfinance
                return [
                    t if "." in t else f"{t}.NS"
                    for t in tickers
                ]
    except Exception as e:
        print(f"[nightly] DB ticker fetch failed: {e}")
    return []


def compute_and_cache_indicators(ticker: str) -> bool:
    """Pre-compute SMA-20, SMA-50, and last close for a ticker.

    Result is stored as JSON in cache/indicators/<ticker>.json so the
    analyze() hot path can load it without a yfinance round-trip.
    Returns True on success, False on failure.
    """
    try:
        import yfinance as yf

        cache_dir = Path("cache/indicators")
        cache_dir.mkdir(parents=True, exist_ok=True)
        safe_name = ticker.replace(".", "_").replace("/", "_")
        cache_file = cache_dir / f"{safe_name}.json"

        hist = yf.download(ticker, period="1y", auto_adjust=True, progress=False)
        if hist.empty:
            print(f"[nightly] Empty history for {ticker} — skipping")
            return False

        closes = [float(x) for x in hist["Close"].dropna().tolist()]
        if not closes:
            return False

        sma_20 = round(sum(closes[-20:]) / 20, 4) if len(closes) >= 20 else None
        sma_50 = round(sum(closes[-50:]) / 50, 4) if len(closes) >= 50 else None
        sma_200 = round(sum(closes[-200:]) / 200, 4) if len(closes) >= 200 else None

        cache_data = {
            "ticker": ticker,
            "computed_at": datetime.now(timezone.utc).isoformat(),
            "sma_20": sma_20,
            "sma_50": sma_50,
            "sma_200": sma_200,
            "last_close": round(closes[-1], 4) if closes else None,
            "data_points": len(closes),
        }
        with open(cache_file, "w") as f:
            json.dump(cache_data, f)
        return True

    except Exception as e:
        print(f"[nightly] Failed {ticker}: {e}")
        return False


def run_nightly_precompute(max_workers: int = 10) -> dict:
    """Main entry point for nightly cron job (rank_01).

    Fetches Nifty 500 tickers from DB (falls back to hardcoded list),
    then pre-computes and caches indicators in parallel.
    Returns a summary dict.
    """
    tickers = _get_nifty500_from_db() or NIFTY_500_SYMBOLS
    print(f"[nightly] Pre-computing indicators for {len(tickers)} stocks...")

    start = time.monotonic()
    with ThreadPoolExecutor(max_workers=max_workers) as exe:
        results = list(exe.map(compute_and_cache_indicators, tickers))

    elapsed = round(time.monotonic() - start, 1)
    success = sum(results)
    failed = len(results) - success
    print(f"[nightly] Done in {elapsed}s — {success}/{len(tickers)} succeeded, {failed} failed")
    return {
        "total": len(tickers),
        "success": success,
        "failed": failed,
        "elapsed_s": elapsed,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Task rank_05 — Batch RRG quadrant calculation for sector ETFs
# ---------------------------------------------------------------------------

# Representative NSE tickers for each major sector
SECTOR_ETFS = {
    "IT":        "INFY.NS",
    "Banking":   "HDFCBANK.NS",
    "Energy":    "RELIANCE.NS",
    "FMCG":      "HINDUNILVR.NS",
    "Pharma":    "SUNPHARMA.NS",
    "Auto":      "TATAMOTORS.NS",
    "Metals":    "TATASTEEL.NS",
    "Telecom":   "BHARTIARTL.NS",
    "Realty":    "DLF.NS",
    "Infra":     "LT.NS",
}


def _compute_rrg_for_sector(sector: str, ticker: str, benchmark_closes: list[float]) -> dict:
    """Compute a simplified RRG RS-Ratio and RS-Momentum for one sector ticker."""
    try:
        import yfinance as yf
        import math

        hist = yf.download(ticker, period="6mo", auto_adjust=True, progress=False)
        if hist.empty or len(hist) < 14:
            return {"sector": sector, "ticker": ticker, "error": "insufficient data"}

        closes = [float(x) for x in hist["Close"].dropna().tolist()]
        bench = benchmark_closes

        # Align lengths
        min_len = min(len(closes), len(bench))
        if min_len < 14:
            return {"sector": sector, "ticker": ticker, "error": "alignment too short"}

        closes = closes[-min_len:]
        bench = bench[-min_len:]

        # RS Line = sector / benchmark (relative strength)
        rs_line = [c / b for c, b in zip(closes, bench) if b != 0]
        if len(rs_line) < 14:
            return {"sector": sector, "ticker": ticker, "error": "rs_line too short"}

        rs_ratio = round(sum(rs_line[-10:]) / 10, 6) if len(rs_line) >= 10 else None
        rs_momentum = None
        if rs_ratio is not None and len(rs_line) >= 14:
            rs_prev = sum(rs_line[-14:-4]) / 10
            rs_momentum = round(rs_ratio - rs_prev, 6) if rs_prev else None

        # Quadrant classification
        quadrant = "Unknown"
        if rs_ratio is not None and rs_momentum is not None:
            median_rs = sum(rs_line) / len(rs_line)
            if rs_ratio >= median_rs and rs_momentum >= 0:
                quadrant = "Leading"
            elif rs_ratio >= median_rs and rs_momentum < 0:
                quadrant = "Weakening"
            elif rs_ratio < median_rs and rs_momentum >= 0:
                quadrant = "Improving"
            else:
                quadrant = "Lagging"

        return {
            "sector": sector,
            "ticker": ticker,
            "rrg_quadrant": quadrant,
            "rs_ratio": rs_ratio,
            "rs_momentum": rs_momentum,
            "computed_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        return {"sector": sector, "ticker": ticker, "error": str(e)}


def compute_rrg_batch(benchmark: str = "^NSEI") -> dict:
    """Batch compute RRG quadrants for all sectors (rank_05).

    Downloads the benchmark once, then fans out sector computations in parallel.
    Result is cached to cache/rrg_batch.json.
    Returns a dict of {sector: rrg_result}.
    """
    import yfinance as yf

    print(f"[nightly] Computing RRG batch for {len(SECTOR_ETFS)} sectors vs {benchmark}...")

    # Fetch benchmark once — used by all sector workers
    try:
        bench_hist = yf.download(benchmark, period="6mo", auto_adjust=True, progress=False)
        if bench_hist.empty:
            print(f"[nightly] Benchmark {benchmark} returned empty — aborting RRG batch")
            return {}
        bench_closes = [float(x) for x in bench_hist["Close"].dropna().tolist()]
    except Exception as e:
        print(f"[nightly] Benchmark fetch failed: {e}")
        return {}

    results: dict = {}
    with ThreadPoolExecutor(max_workers=6) as exe:
        futures = {
            exe.submit(_compute_rrg_for_sector, sector, ticker, bench_closes): sector
            for sector, ticker in SECTOR_ETFS.items()
        }
        from concurrent.futures import as_completed
        for fut in as_completed(futures):
            sector = futures[fut]
            try:
                results[sector] = fut.result()
            except Exception as e:
                results[sector] = {"sector": sector, "error": str(e)}

    # Cache result to disk
    try:
        cache_dir = Path("cache")
        cache_dir.mkdir(parents=True, exist_ok=True)
        with open(cache_dir / "rrg_batch.json", "w") as f:
            json.dump({
                "computed_at": datetime.now(timezone.utc).isoformat(),
                "benchmark": benchmark,
                "sectors": results,
            }, f, indent=2)
        print(f"[nightly] RRG batch cached — {len(results)} sectors computed")
    except Exception as e:
        print(f"[nightly] RRG batch cache write failed: {e}")

    return results


if __name__ == "__main__":
    print("=== Nightly Pre-compute Run ===")
    summary = run_nightly_precompute(max_workers=10)
    print(f"Indicators: {summary}")

    print("\n=== Nightly RRG Batch ===")
    rrg = compute_rrg_batch()
    for sector, data in rrg.items():
        quadrant = data.get("rrg_quadrant", data.get("error", "?"))
        print(f"  {sector:12s}: {quadrant}")
