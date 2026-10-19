"""Build `MarketData` for the Lab from the research engine's market-data store.

Sources, best first:
1. ``store`` — curated NSE bhavcopy panel: raw exchange OHLCV plus corporate-action
   events derived from the exchange's adjusted previous close. Share counts are real.
2. ``local_csv`` — the dev Nifty-50 CSV. Prices are already adjusted and the universe is
   today's constituents (survivorship bias). Usable for development and demos only,
   and every response built from it says so.
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from research.marketdata import store

import json
from pathlib import Path

from .data import Bar, CorporateAction, MarketData, NewsItem

SCENARIOS = Path(__file__).with_name("scenarios.json")

SPLIT_LIKE = 0.8  # factor below this is treated as a share-count change rather than a cash payout

DEV_WARNINGS = [
    "Development dataset: prices are pre-adjusted for corporate actions, so share counts and per-share prices differ from what traded on the exchange.",
    "Development dataset: the universe is today's Nifty 50 members, which hides companies that fell out of the index (survivorship bias).",
]


def panel_to_market(panel: pd.DataFrame, symbols: list[str] | None, index: pd.Series | None, source: str) -> MarketData:
    """Convert a research panel (one row per date x entity) into Lab `MarketData`.

    Instruments are keyed by the symbol they carried on their LAST row in the window, so a
    renamed company stays one instrument. Corporate actions come from rows whose `event`
    is set: factor f = prev_close_t / close_(t-1); f < SPLIT_LIKE is a share multiplier 1/f,
    otherwise a cash amount close_(t-1) - prev_close_t.
    """
    if panel.empty:
        raise ValueError("no market data in the requested window")
    p = panel.sort_values(["entity_id", "date"], kind="stable")
    last_symbol = p.groupby("entity_id")["symbol"].last()
    want = set(symbols) if symbols else None
    bars: dict[str, list[Bar]] = {}
    actions: dict[str, list[CorporateAction]] = {}
    for eid, g in p.groupby("entity_id", sort=False):
        sym = str(last_symbol[eid])
        if want is not None and sym not in want:
            continue
        g = g.loc[g["volume"].fillna(0) > 0]
        bars[sym] = [Bar(d.date(), float(o), float(h), float(l), float(c), float(v))
                     for d, o, h, l, c, v in zip(g["date"], g["open"], g["high"], g["low"], g["close"], g["volume"])]
        acts = []
        prev_close = g["close"].shift()
        for d, ev, pc, cp in zip(g["date"], g["event"], g["prev_close"], prev_close):
            if not ev or pd.isna(pc) or pd.isna(cp) or cp <= 0:
                continue
            f = float(pc) / float(cp)
            if f < SPLIT_LIKE:
                acts.append(CorporateAction(sym, d.date(), "split" if ev == "split" else "bonus", factor=round(1 / f, 6), source=f"{source}:{ev}"))
            elif f < 1:
                acts.append(CorporateAction(sym, d.date(), "dividend", cash_per_share=round(float(cp) - float(pc), 4), source=f"{source}:{ev}"))
        if acts:
            actions[sym] = acts
    bench = None
    if index is not None and len(index):
        bench = "^NSEI"
        bars[bench] = [Bar(d.date(), float(c), float(c), float(c), float(c), 0.0) for d, c in index.items()]
    return MarketData(bars=bars, actions=actions, benchmark=bench)


def load_market(start: date, end: date, symbols: list[str] | None = None, source: str = "auto", lookback_days: int = 400) -> MarketData:
    """Market data for a simulation window plus `lookback_days` of history before it.

    `source="auto"` uses the curated store when it has rows for the window, else the dev CSV.
    """
    lo = pd.Timestamp(start) - pd.Timedelta(days=lookback_days)
    used = source
    panel = pd.DataFrame()
    if source in ("auto", "store"):
        panel = store.load_panel(lo.date(), end, source="store")
        used = "store"
    if panel.empty and source in ("auto", "local_csv"):
        panel = store.load_panel(lo.date(), end, source="local_csv")
        used = "local_csv"
    index = store.load_index("NIFTY50", lo.date(), end)
    md = panel_to_market(panel, symbols, index, used)
    if used == "local_csv":
        md.actions = {}  # prices are already adjusted; applying events again would double count
    md.news = scenario_news(lo.date(), end, set(md.bars))
    md.provenance = {
        "source": used,
        "warnings": list(DEV_WARNINGS) if used == "local_csv" else [],
        "benchmark": "NIFTY 50 price index (yfinance cache)" if md.benchmark else None,
        "rows": int(len(panel)),
        "window": [lo.date().isoformat(), end.isoformat()],
    }
    if md.benchmark is None:
        md.provenance["warnings"].append("No NIFTY 50 index cache found: benchmark comparisons are unavailable.")
    return md


def liquid_universe(md: MarketData, asof: date, n: int = 30, lookback: int = 60) -> list[str]:
    """Top-n symbols by median traded value over the `lookback` sessions before `asof`.

    Uses only data dated on or before `asof`, so the universe is the one a trader could have
    picked then (no survivorship from today's index lists).
    """
    scores = []
    for s in md.symbols:
        h = md.history(s, asof)[-lookback:]
        if len(h) >= lookback // 2 and h[-1].d == asof:
            vals = sorted(b.close * b.volume for b in h)
            scores.append((vals[len(vals) // 2], s))
    return [s for _, s in sorted(scores, reverse=True)[:n]]


def scenario_news(start: date, end: date, symbols: set[str]) -> list[NewsItem]:
    """Dated, sourced events from the curated scenarios, as news items. Market-wide when not tied to a symbol."""
    if not SCENARIOS.exists():
        return []
    out = []
    for sc in json.loads(SCENARIOS.read_text()).get("scenarios", []):
        hint = [s for s in sc.get("universe_hint", []) if s in symbols]
        for ev in sc.get("timeline", []):
            d = date.fromisoformat(ev["date"])
            if start <= d <= end:
                sym = hint[0] if len(hint) == 1 and hint[0] in ev.get("event", "") else None
                out.append(NewsItem(sym, d, ev.get("event", ""), "curated timeline", ev.get("source_url", "")))
    return out
