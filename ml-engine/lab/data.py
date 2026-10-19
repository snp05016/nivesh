"""Market data contract for the Lab, plus the point-in-time gate.

Prices are UNADJUSTED exchange prices. Splits, bonuses and dividends arrive as
explicit `CorporateAction` events so share counts in a simulation stay real.
"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class Bar:
    d: date
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class CorporateAction:
    symbol: str
    ex_date: date
    kind: str  # "split" | "bonus" | "dividend"
    factor: float = 1.0  # share multiplier for split/bonus (1:5 split -> 5.0; 1:1 bonus -> 2.0)
    cash_per_share: float = 0.0  # dividend in INR per pre-action share
    source: str = ""


@dataclass(frozen=True)
class NewsItem:
    """Anything textual (headline, filing, result) with the time it became public."""
    symbol: str | None
    published: date
    title: str
    source: str
    url: str = ""


@dataclass
class MarketData:
    """In-memory, unadjusted daily data for a fixed universe. Loaders build one of these."""
    bars: dict[str, list[Bar]]
    actions: dict[str, list[CorporateAction]] = field(default_factory=dict)
    news: list[NewsItem] = field(default_factory=list)
    benchmark: str | None = None  # symbol inside `bars` used as the benchmark, e.g. "^NSEI"
    provenance: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        for sym, rows in self.bars.items():
            rows.sort(key=lambda b: b.d)
            dates = [b.d for b in rows]
            if len(set(dates)) != len(dates):
                raise ValueError(f"duplicate bars for {sym}")
        self._dates = {s: [b.d for b in rows] for s, rows in self.bars.items()}
        self._by_date = {s: {b.d: b for b in rows} for s, rows in self.bars.items()}
        self.news.sort(key=lambda n: n.published)

    @property
    def symbols(self) -> list[str]:
        return sorted(s for s in self.bars if s != self.benchmark)

    def calendar(self) -> list[date]:
        """Trading days = union of days on which any instrument printed a bar."""
        return sorted({d for ds in self._dates.values() for d in ds})

    def bar(self, symbol: str, d: date) -> Bar | None:
        return self._by_date.get(symbol, {}).get(d)

    def history(self, symbol: str, upto: date) -> list[Bar]:
        """Bars with date <= upto (inclusive)."""
        ds = self._dates.get(symbol, [])
        return self.bars.get(symbol, [])[: bisect_right(ds, upto)]

    def actions_on(self, d: date) -> list[CorporateAction]:
        return [a for acts in self.actions.values() for a in acts if a.ex_date == d]


class LookaheadError(RuntimeError):
    """Raised when code asks for information that did not exist yet at the simulated time."""


@dataclass(frozen=True)
class PITView:
    """The only door through which a player, mentor or model may read market data.

    Everything visible is dated <= `asof`. Asking for later data raises instead of
    silently truncating, so leaks show up in tests rather than in results.
    """
    data: MarketData
    asof: date

    def history(self, symbol: str, upto: date | None = None) -> list[Bar]:
        upto = upto or self.asof
        if upto > self.asof:
            raise LookaheadError(f"{symbol}: asked for {upto}, clock is {self.asof}")
        return self.data.history(symbol, upto)

    def last(self, symbol: str) -> Bar | None:
        h = self.data.history(symbol, self.asof)
        return h[-1] if h else None

    def news(self, symbol: str | None = None, limit: int = 50) -> list[NewsItem]:
        items = [n for n in self.data.news if n.published <= self.asof and (symbol is None or n.symbol in (symbol, None))]
        return items[-limit:]

    def actions(self, symbol: str) -> list[CorporateAction]:
        return [a for a in self.data.actions.get(symbol, []) if a.ex_date <= self.asof]
