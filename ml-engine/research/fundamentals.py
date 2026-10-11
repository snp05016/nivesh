"""Display-only fundamentals from yfinance (spec 4.7). Values only, never model inputs.

Two layers:

* :func:`fetch_fundamentals` is the only network code: one yfinance call per
  symbol, cached as JSON under ``$RESEARCH_DATA_DIR/raw/yfinance/fundamentals``
  for 7 days, with a per-night refresh cap (:class:`FetchBudget`) and a minimum
  spacing between requests. On any failure it returns the last cached payload
  (or None).
* Everything else is pure: statement frames in, ratios and a
  ``contract.Fundamentals`` block out (:func:`fundamentals_block`).

Rules: ``point_in_time`` is always false; statements whose fiscal period ended
more than 15 months before as-of make the block ``stale``; financials (banks,
NBFCs, insurers) get Altman and Beneish ``applicable: false``. Piotroski is
"f of max_possible available checks" with no grade. Altman Z''-EM and Beneish M
are emitted as values only: their zone and flag thresholds live in the admin
methodology document and are never part of the output.
"""

from __future__ import annotations

import calendar
import json
import logging
import math
import os
import re
import tempfile
import threading
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import config
from .config import FUNDAMENTALS
from .contract import (
    Fact,
    Fundamentals,
    Piotroski,
    PiotroskiCheck,
    Quality,
    ReasonCode,
    ScoreValue,
    Source,
    Valuation,
)
from .formatting import make_fact

log = logging.getLogger(__name__)

CACHE_SUBDIR = Path("raw") / "yfinance" / "fundamentals"
THROTTLE_SECONDS = 1.0  # minimum spacing between yfinance requests in this process
STATEMENTS = ("income", "balance", "cashflow")
INFO_KEYS = (
    "sector", "industry", "trailingPE", "priceToBook", "enterpriseToEbitda",
    "trailingAnnualDividendYield", "marketCap", "currency", "financialCurrency",
)
_SYMBOL_RE = re.compile(r"^[A-Z0-9&-]{1,20}$")
_PERIOD_MATCH_DAYS = 45  # statement columns within this many days are the same fiscal period

# yfinance line items (first present alias wins).
REVENUE = ("Total Revenue", "Operating Revenue")
COGS = ("Cost Of Revenue", "Reconciled Cost Of Revenue")
GROSS_PROFIT = ("Gross Profit",)
OPERATING_INCOME = ("Operating Income", "Total Operating Income As Reported")
EBIT = ("EBIT",)
NET_INCOME = ("Net Income", "Net Income Common Stockholders",
              "Net Income From Continuing Operation Net Minority Interest")
SGA = ("Selling General And Administration",)
DEPRECIATION = ("Reconciled Depreciation", "Depreciation And Amortization",
                "Depreciation Amortization Depletion")
TOTAL_ASSETS = ("Total Assets",)
CURRENT_ASSETS = ("Current Assets",)
CURRENT_LIABILITIES = ("Current Liabilities",)
LONG_TERM_DEBT = ("Long Term Debt", "Long Term Debt And Capital Lease Obligation")
TOTAL_DEBT = ("Total Debt",)
EQUITY = ("Stockholders Equity", "Common Stock Equity")
TOTAL_LIABILITIES = ("Total Liabilities Net Minority Interest",)
RETAINED_EARNINGS = ("Retained Earnings",)
WORKING_CAPITAL = ("Working Capital",)
NET_PPE = ("Net PPE",)
RECEIVABLES = ("Accounts Receivable", "Receivables")
SHARES = ("Ordinary Shares Number", "Share Issued")
CFO = ("Operating Cash Flow", "Cash Flow From Continuing Operating Activities")

PIOTROSKI_IDS = ("roa_positive", "cfo_positive", "roa_improving", "accruals", "leverage_down",
                 "liquidity_up", "no_dilution", "gross_margin_up", "asset_turnover_up")
_FINANCIAL_SECTORS = {"financial services", "financials", "financial"}
_FINANCIAL_INDUSTRY_WORDS = ("bank", "insurance", "credit services", "capital markets",
                             "asset management", "mortgage", "financial")


# ── Fetch and cache ─────────────────────────────────────────────────────────


@dataclass
class FetchBudget:
    """Network refreshes allowed in one nightly run (stale cache entries beyond it are reused)."""

    remaining: int = FUNDAMENTALS["max_refreshes_per_night"]

    def take(self) -> bool:
        if self.remaining <= 0:
            return False
        self.remaining -= 1
        return True


@dataclass
class _Throttle:
    interval_s: float
    _last: float = float("-inf")
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def wait(self) -> None:
        with self._lock:
            delay = self._last + self.interval_s - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            self._last = time.monotonic()


_THROTTLE = _Throttle(THROTTLE_SECONDS)


def cache_path(symbol: str, data_dir: Path | None = None) -> Path:
    if not _SYMBOL_RE.fullmatch(symbol):
        raise ValueError(f"invalid NSE symbol {symbol!r}")
    return Path(data_dir or config.DATA_DIR) / CACHE_SUBDIR / f"{symbol}.json"


def _read_cache(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        datetime.fromisoformat(payload["fetched_at"])
        return payload
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _write_cache(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.stem}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, sort_keys=True, separators=(",", ":"))
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def frame_to_json(df: Any) -> dict[str, dict[str, float]]:
    """yfinance statement (rows = line items, columns = period ends) -> {iso date: {item: value}}."""
    out: dict[str, dict[str, float]] = {}
    if not isinstance(df, pd.DataFrame) or df.empty:
        return out
    for col in df.columns:
        items = {str(k): v for k, v in zip(df.index, (_finite(x) for x in df[col].tolist())) if v is not None}
        if items:
            out[pd.Timestamp(col).date().isoformat()] = items
    return out


def frame_from_json(data: dict[str, dict[str, float]] | None) -> pd.DataFrame:
    """Inverse of :func:`frame_to_json`; columns are period ends, newest first."""
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame({pd.Timestamp(k): v for k, v in data.items()})
    return df.reindex(columns=sorted(df.columns, reverse=True))


def _finite(x: Any) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _clean_info(info: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if not isinstance(info, dict):
        return out
    for key in INFO_KEYS:
        value = info.get(key)
        if isinstance(value, str) and value:
            out[key] = value
        elif isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
            out[key] = float(value)
    return out


def _default_ticker(yahoo_symbol: str) -> Any:
    import yfinance  # deferred: heavy import, and tests never reach the network

    return yfinance.Ticker(yahoo_symbol)


def fetch_fundamentals(
    symbol: str,
    *,
    data_dir: Path | None = None,
    budget: FetchBudget | None = None,
    now: datetime | None = None,
    ticker_factory: Callable[[str], Any] = _default_ticker,
) -> dict[str, Any] | None:
    """Cached yfinance ``.info`` subset and annual statements for an NSE symbol.

    A cache entry younger than 7 days is returned without a request. Otherwise
    one refresh is attempted if ``budget`` allows (None means no cap: a single
    on-demand symbol); failures and an exhausted budget fall back to the cached
    payload, which may be older than the TTL, or None.
    """
    path = cache_path(symbol, data_dir)
    now = now or datetime.now(timezone.utc)
    cached = _read_cache(path)
    if cached is not None:
        age = now - datetime.fromisoformat(cached["fetched_at"])
        if age < timedelta(days=FUNDAMENTALS["cache_ttl_days"]):
            return cached
    if budget is not None and not budget.take():
        return cached
    try:
        _THROTTLE.wait()
        ticker = ticker_factory(f"{symbol}.NS")
        payload: dict[str, Any] = {
            "symbol": symbol,
            "fetched_at": now.isoformat(),
            "info": _clean_info(ticker.info),
            "income": frame_to_json(ticker.income_stmt),
            "balance": frame_to_json(ticker.balance_sheet),
            "cashflow": frame_to_json(ticker.cashflow),
        }
        if not payload["info"] and not any(payload[s] for s in STATEMENTS):
            raise ValueError("empty yfinance response")
        _write_cache(path, payload)
        return payload
    except Exception as exc:  # network, parsing or rate limit: keep the last good copy
        log.warning("fundamentals fetch failed for %s: %s", symbol, exc)
        return cached


# ── Pure helpers on statement frames ────────────────────────────────────────


@dataclass(frozen=True)
class Statements:
    """Annual statement frames (rows = yfinance line items, columns = period ends, newest first)."""

    income: pd.DataFrame
    balance: pd.DataFrame
    cashflow: pd.DataFrame

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> Statements:
        return cls(*(frame_from_json(payload.get(name)) for name in STATEMENTS))

    def periods(self) -> list[pd.Timestamp]:
        """Fiscal period ends, newest first (income statement, else balance sheet)."""
        base = self.income if not self.income.empty else self.balance
        return list(base.columns)

    def value(self, aliases: Iterable[str], period: pd.Timestamp) -> float | None:
        """First alias present in any statement for the column within 45 days of ``period``."""
        for frame in (self.income, self.balance, self.cashflow):
            if frame.empty:
                continue
            cols = [c for c in frame.columns if abs((c - period).days) <= _PERIOD_MATCH_DAYS]
            if not cols:
                continue
            for alias in aliases:
                if alias in frame.index:
                    v = frame.at[alias, cols[0]]
                    if pd.notna(v) and math.isfinite(float(v)):
                        return float(v)
        return None


def _div(num: float | None, den: float | None, *, positive_den: bool = True) -> float | None:
    if num is None or den is None or den == 0 or (positive_den and den < 0):
        return None
    return num / den


def _gross_profit(st: Statements, p: pd.Timestamp) -> float | None:
    gp = st.value(GROSS_PROFIT, p)
    if gp is not None:
        return gp
    rev, cogs = st.value(REVENUE, p), st.value(COGS, p)
    return None if rev is None or cogs is None else rev - cogs


def _gt(a: float | None, b: float | None) -> int | None:
    return None if a is None or b is None else int(a > b)


def piotroski_signals(st: Statements) -> dict[str, int | None]:
    """The 9 Piotroski checks on the latest two fiscal years; None where inputs are missing.

    ROA uses year-end total assets; no_dilution is strict (shares not higher).
    """
    out: dict[str, int | None] = dict.fromkeys(PIOTROSKI_IDS)
    periods = st.periods()
    if not periods:
        return out
    t = periods[0]
    p = periods[1] if len(periods) > 1 else None

    def v(aliases: tuple[str, ...], period: pd.Timestamp | None) -> float | None:
        return None if period is None else st.value(aliases, period)

    ni_t, ta_t, cfo_t = v(NET_INCOME, t), v(TOTAL_ASSETS, t), v(CFO, t)
    roa_t = _div(ni_t, ta_t)
    roa_p = _div(v(NET_INCOME, p), v(TOTAL_ASSETS, p))
    out["roa_positive"] = _gt(roa_t, 0.0)
    out["cfo_positive"] = _gt(cfo_t, 0.0)
    out["roa_improving"] = _gt(roa_t, roa_p)
    out["accruals"] = _gt(cfo_t, ni_t) if ta_t is not None and ta_t > 0 else None
    lev_t = _div(v(LONG_TERM_DEBT, t), ta_t)
    lev_p = _div(v(LONG_TERM_DEBT, p), v(TOTAL_ASSETS, p))
    out["leverage_down"] = _gt(lev_p, lev_t)
    cr_t = _div(v(CURRENT_ASSETS, t), v(CURRENT_LIABILITIES, t))
    cr_p = _div(v(CURRENT_ASSETS, p), v(CURRENT_LIABILITIES, p))
    out["liquidity_up"] = _gt(cr_t, cr_p)
    sh_t, sh_p = v(SHARES, t), v(SHARES, p)
    out["no_dilution"] = None if sh_t is None or sh_p is None else int(sh_t <= sh_p)
    rev_t, rev_p = v(REVENUE, t), v(REVENUE, p)
    gm_t = _div(_gross_profit(st, t), rev_t)
    gm_p = None if p is None else _div(_gross_profit(st, p), rev_p)
    out["gross_margin_up"] = _gt(gm_t, gm_p)
    out["asset_turnover_up"] = _gt(_div(rev_t, ta_t), _div(rev_p, v(TOTAL_ASSETS, p)))
    return out


def altman_z_em(st: Statements) -> float | None:
    """Altman Z''-EM value 6.56 X1 + 3.26 X2 + 6.72 X3 + 1.05 X4 (latest year); value only."""
    periods = st.periods()
    if not periods:
        return None
    t = periods[0]
    ta = st.value(TOTAL_ASSETS, t)
    wc = st.value(WORKING_CAPITAL, t)
    if wc is None:
        ca, cl = st.value(CURRENT_ASSETS, t), st.value(CURRENT_LIABILITIES, t)
        wc = None if ca is None or cl is None else ca - cl
    ebit = st.value(EBIT, t)
    if ebit is None:
        ebit = st.value(OPERATING_INCOME, t)
    x = (_div(wc, ta), _div(st.value(RETAINED_EARNINGS, t), ta), _div(ebit, ta),
         _div(st.value(EQUITY, t), st.value(TOTAL_LIABILITIES, t)))
    x1, x2, x3, x4 = x
    if x1 is None or x2 is None or x3 is None or x4 is None:
        return None
    return 6.56 * x1 + 3.26 * x2 + 6.72 * x3 + 1.05 * x4


def beneish_m(st: Statements) -> float | None:
    """Beneish (1999) 8-variable M-score on the latest two fiscal years; value only."""
    periods = st.periods()
    if len(periods) < 2:
        return None
    t, p = periods[0], periods[1]
    items = {"sales": REVENUE, "ta": TOTAL_ASSETS, "ppe": NET_PPE, "dep": DEPRECIATION,
             "ca": CURRENT_ASSETS, "cl": CURRENT_LIABILITIES, "ltd": LONG_TERM_DEBT,
             "rec": RECEIVABLES, "sga": SGA}
    raw_t = {k: st.value(a, t) for k, a in items.items()}
    raw_p = {k: st.value(a, p) for k, a in items.items()}
    extra = (_gross_profit(st, t), _gross_profit(st, p), st.value(NET_INCOME, t), st.value(CFO, t))
    if any(v is None for v in (*raw_t.values(), *raw_p.values(), *extra)):
        return None
    c = {k: float(v) for k, v in raw_t.items() if v is not None}
    q = {k: float(v) for k, v in raw_p.items() if v is not None}
    gp_t, gp_p, ni, cfo = (float(v) for v in extra if v is not None)
    try:
        dsri = (c["rec"] / c["sales"]) / (q["rec"] / q["sales"])
        gmi = (gp_p / q["sales"]) / (gp_t / c["sales"])
        aqi = (1.0 - (c["ca"] + c["ppe"]) / c["ta"]) / (1.0 - (q["ca"] + q["ppe"]) / q["ta"])
        sgi = c["sales"] / q["sales"]
        depi = (q["dep"] / (q["dep"] + q["ppe"])) / (c["dep"] / (c["dep"] + c["ppe"]))
        sgai = (c["sga"] / c["sales"]) / (q["sga"] / q["sales"])
        tata = (ni - cfo) / c["ta"]
        lvgi = ((c["cl"] + c["ltd"]) / c["ta"]) / ((q["cl"] + q["ltd"]) / q["ta"])
    except ZeroDivisionError:
        return None
    m = (-4.84 + 0.920 * dsri + 0.528 * gmi + 0.404 * aqi + 0.892 * sgi + 0.115 * depi
         - 0.172 * sgai + 4.679 * tata - 0.327 * lvgi)
    return m if math.isfinite(m) else None


def quality_ratios(st: Statements) -> dict[str, float | None]:
    """ROE %, operating margin %, debt/equity and CFO/PAT on the latest fiscal year."""
    periods = st.periods()
    if not periods:
        return dict.fromkeys(("roe_pct", "operating_margin_pct", "debt_to_equity", "cfo_to_pat"))
    t = periods[0]
    ni, eq = st.value(NET_INCOME, t), st.value(EQUITY, t)
    roe = _div(ni, eq)
    margin = _div(st.value(OPERATING_INCOME, t), st.value(REVENUE, t))
    return {
        "roe_pct": None if roe is None else roe * 100.0,
        "operating_margin_pct": None if margin is None else margin * 100.0,
        "debt_to_equity": _div(st.value(TOTAL_DEBT, t), eq),
        "cfo_to_pat": _div(st.value(CFO, t), ni),  # only for positive profit
    }


def is_financial(sector: str | None, industry: str | None) -> bool | None:
    """Banks, NBFCs, insurers and other financials, from yfinance sector or industry."""
    if not sector and not industry:
        return None
    if sector and sector.strip().lower() in _FINANCIAL_SECTORS:
        return True
    ind = (industry or "").lower()
    return any(word in ind for word in _FINANCIAL_INDUSTRY_WORDS)


def _positive(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and math.isfinite(value) and value > 0 else None


def pe_ttm(payload: dict[str, Any] | None) -> float | None:
    """Trailing P/E when positive (for building sector peer lists)."""
    return None if payload is None else _positive(payload.get("info", {}).get("trailingPE"))


def sector(payload: dict[str, Any] | None) -> str | None:
    return None if payload is None else payload.get("info", {}).get("sector") or None


def market_cap_cr(payload: dict[str, Any] | None) -> float | None:
    """Market capitalisation in INR crore (1 crore = 1e7), for the report snapshot."""
    cap = None if payload is None else _positive(payload.get("info", {}).get("marketCap"))
    return None if cap is None else cap / 1e7


def pe_sector_pctl(pe: float | None, peer_pes: Sequence[float] | None) -> float | None:
    """Mid-rank percentile of ``pe`` among itself plus its positive-P/E sector peers.

    ``peer_pes`` excludes the stock itself; fewer than 5 peers gives None.
    """
    if pe is None or peer_pes is None:
        return None
    peers = np.asarray([x for x in peer_pes if x is not None], dtype=float)
    peers = peers[np.isfinite(peers) & (peers > 0)]
    if peers.size < FUNDAMENTALS["min_sector_peers"]:
        return None
    less, equal = float(np.sum(peers < pe)), float(np.sum(peers == pe))
    return 100.0 * (less + 0.5 * equal + 0.5) / (peers.size + 1)


def is_stale(fiscal_period_end: date | None, as_of: date) -> bool:
    if fiscal_period_end is None:
        return False
    months = as_of.year * 12 + as_of.month - 1 - FUNDAMENTALS["stale_after_months"]
    year, month = divmod(months, 12)
    cutoff = date(year, month + 1, min(as_of.day, calendar.monthrange(year, month + 1)[1]))
    return fiscal_period_end < cutoff


# ── Contract block ──────────────────────────────────────────────────────────


def unavailable_fundamentals(reason: ReasonCode = "source_unavailable") -> Fundamentals:
    """Every fact unavailable with ``reason`` (fetch failed, symbol unknown, skipped)."""

    def na(fid: str, source: Source = "yfinance") -> Fact:
        return make_fact(fid, None, source=source, as_of=None, reason=reason)

    return Fundamentals(
        status="unavailable", reason=reason, source="yfinance", fetched_at=None, fiscal_period_end=None,
        point_in_time=False, statement_basis="unknown", is_financial=None,
        valuation=Valuation(pe_ttm=na("fund.pe_ttm"), pb=na("fund.pb"), ev_ebitda=na("fund.ev_ebitda"),
                            dividend_yield_pct=na("fund.dividend_yield_pct"),
                            pe_sector_pctl=na("fund.pe_sector_pctl", "computed")),
        quality=Quality(roe_pct=na("fund.roe_pct"), operating_margin_pct=na("fund.operating_margin_pct"),
                        debt_to_equity=na("fund.debt_to_equity"), cfo_to_pat=na("fund.cfo_to_pat")),
        piotroski=Piotroski(f_score=na("fund.piotroski.f_score", "computed"),
                            max_possible=na("fund.piotroski.max_possible", "computed"),
                            signals=[PiotroskiCheck(id=sid, value=None) for sid in PIOTROSKI_IDS]),
        altman_z_em=ScoreValue(applicable=False, value=na("fund.altman_z_em", "computed")),
        beneish_m=ScoreValue(applicable=False, value=na("fund.beneish_m", "computed")),
    )


def fundamentals_block(
    payload: dict[str, Any] | None,
    *,
    as_of: date,
    peer_pes: Sequence[float] | None = None,
) -> Fundamentals:
    """``contract.Fundamentals`` from a :func:`fetch_fundamentals` payload.

    ``peer_pes`` are the positive trailing P/Es of the stock's sector peers in
    the universe (itself excluded). None or a malformed payload gives an
    unavailable block (source_unavailable).
    """
    if payload is None:
        return unavailable_fundamentals()
    try:
        return _build(payload, as_of=as_of, peer_pes=peer_pes)
    except Exception as exc:  # malformed cache or unexpected yfinance shape: never break a report
        log.warning("fundamentals block failed for %s: %s", payload.get("symbol"), exc)
        return unavailable_fundamentals()


def _build(payload: dict[str, Any], *, as_of: date, peer_pes: Sequence[float] | None) -> Fundamentals:
    info: dict[str, Any] = payload.get("info") or {}
    fetched_at = datetime.fromisoformat(payload["fetched_at"])
    fetched = fetched_at.date()
    st = Statements.from_payload(payload)
    periods = st.periods()
    fiscal_end = periods[0].date() if periods else None
    stale = is_stale(fiscal_end, as_of)
    financial = is_financial(info.get("sector"), info.get("industry"))
    na_fin: ReasonCode = "not_applicable_financials"

    def fact(fid: str, value: float | None, source: Source = "yfinance", *,
             reason: ReasonCode = "source_unavailable", statement: bool = True) -> Fact:
        """Statement-derived facts turn stale with the block; info (price) ratios do not."""
        if value is None or not math.isfinite(value):
            return make_fact(fid, None, source=source, as_of=fetched, reason=reason)
        return make_fact(fid, value, source=source, as_of=fetched,
                         status="stale" if stale and statement else None)

    pe = _positive(info.get("trailingPE"))
    dy = info.get("trailingAnnualDividendYield")
    dividend_yield = float(dy) * 100.0 if isinstance(dy, float) and dy >= 0 else None
    q = quality_ratios(st)
    signals = piotroski_signals(st)
    known = [v for v in signals.values() if v is not None]
    altman = None if financial else altman_z_em(st)
    beneish = None if financial else beneish_m(st)

    block_facts = [pe, _positive(info.get("priceToBook")), dividend_yield, *q.values(), *known]
    if all(v is None for v in block_facts):
        return unavailable_fundamentals()

    return Fundamentals(
        status="stale" if stale else "ok",
        reason="stale_source" if stale else None,
        source="yfinance",
        fetched_at=fetched_at,
        fiscal_period_end=fiscal_end,
        point_in_time=False,
        statement_basis="unknown",  # Yahoo does not say whether statements are consolidated
        is_financial=financial,
        valuation=Valuation(
            pe_ttm=fact("fund.pe_ttm", pe, statement=False),
            pb=fact("fund.pb", _positive(info.get("priceToBook")), statement=False),
            ev_ebitda=fact("fund.ev_ebitda", None if financial else _positive(info.get("enterpriseToEbitda")),
                           reason=na_fin if financial else "source_unavailable", statement=False),
            dividend_yield_pct=fact("fund.dividend_yield_pct", dividend_yield, statement=False),
            pe_sector_pctl=fact("fund.pe_sector_pctl", pe_sector_pctl(pe, peer_pes), "computed",
                                statement=False),
        ),
        quality=Quality(
            roe_pct=fact("fund.roe_pct", q["roe_pct"]),
            operating_margin_pct=fact("fund.operating_margin_pct", q["operating_margin_pct"]),
            debt_to_equity=fact("fund.debt_to_equity", None if financial else q["debt_to_equity"],
                                reason=na_fin if financial else "source_unavailable"),
            cfo_to_pat=fact("fund.cfo_to_pat", q["cfo_to_pat"]),
        ),
        piotroski=Piotroski(
            f_score=fact("fund.piotroski.f_score", float(sum(known)) if known else None, "computed"),
            max_possible=fact("fund.piotroski.max_possible", float(len(known)), "computed"),
            signals=[PiotroskiCheck(id=sid, value=signals[sid]) for sid in PIOTROSKI_IDS],  # type: ignore[arg-type]
        ),
        altman_z_em=ScoreValue(
            applicable=financial is not True,
            value=fact("fund.altman_z_em", altman, "computed",
                       reason=na_fin if financial else "source_unavailable"),
        ),
        beneish_m=ScoreValue(
            applicable=financial is not True,
            value=fact("fund.beneish_m", beneish, "computed",
                       reason=na_fin if financial else "source_unavailable"),
        ),
    )
