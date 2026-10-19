#!/usr/bin/env python3
"""Backfill daily_prices from the ml-engine EOD export for a date range.

    python -m scripts.backfill_daily_prices --start 2018-01-29 --end 2018-02-02

Ignores the data_eod_prices flag and never asks the engine to gap-fill: older
ranges come from the engine's own `python -m research.marketdata.store backfill`.
Exits 1 without ML_ENGINE_API_KEY.
"""
import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

MAX_DAYS = 4000


def _iso(raw: str) -> date:
    return date.fromisoformat(raw)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--start", type=_iso, required=True)
    parser.add_argument("--end", type=_iso, required=True)
    args = parser.parse_args(argv)
    if args.end < args.start:
        print("--end must not be before --start", file=sys.stderr)
        return 2
    if (args.end - args.start).days + 1 > MAX_DAYS:
        print(f"range is limited to {MAX_DAYS} days", file=sys.stderr)
        return 2

    from services import eod_prices
    from services.research import config as research_config
    from services.research.client import MLEngineClient

    if not research_config.CONFIG.ml_engine_api_key:
        print("ML_ENGINE_API_KEY is not set", file=sys.stderr)
        return 1
    client = MLEngineClient()
    total = 0
    d = args.start
    while d <= args.end:
        n = eod_prices.mirror_date(d, client=client)
        if n:
            print(f"{d}: {n} rows")
        total += n
        d += timedelta(days=1)
    print(f"total: {total} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
