"""Synthetic market data for Lab tests."""
from datetime import date, timedelta

from lab.data import Bar, MarketData


def weekdays(start: date, n: int) -> list[date]:
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def make_data(n: int = 40, start: date = date(2021, 1, 4), **overrides) -> MarketData:
    """Two stocks + an index. AAA drifts up 0.5%/day, BBB is flat at 100 with a wide range."""
    days = weekdays(start, n)
    aaa = [Bar(d, 100 * 1.005**i, 100 * 1.005**i * 1.01, 100 * 1.005**i * 0.99, 100 * 1.005**i * 1.004, 1_000_000) for i, d in enumerate(days)]
    bbb = [Bar(d, 100, 103, 97, 100, 500_000) for d in days]
    idx = [Bar(d, 1000 + i, 1001 + i, 999 + i, 1000 + i, 0) for i, d in enumerate(days)]
    bars = {"AAA": aaa, "BBB": bbb, "^NSEI": idx}
    bars.update(overrides)
    return MarketData(bars=bars, benchmark="^NSEI")
