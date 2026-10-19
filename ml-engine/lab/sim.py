"""Time Machine: an event-driven, daily-bar simulator for NSE cash-equity delivery trades.

Design
------
* Event sourced. A session is (config, actions). `replay()` folds the actions over
  the data and is fully deterministic, so the backend only stores the action log and
  any past state can be rebuilt and audited.
* No lookahead. The player decides after the close of `clock`; orders can only fill
  on a later bar. Every read goes through `PITView(asof=clock)`.
* Honest fidelity. Daily OHLCV cannot tell us queue position or intraday paths, so
  fills use conservative rules (trade-through for limits, gap-aware stops, a
  participation cap, square-root impact). Every assumption is listed in `ASSUMPTIONS`
  and returned with the state.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import date

from .costs import Brokerage, charges
from .data import Bar, MarketData, PITView

ASSUMPTIONS = [
    "Daily bars only: an order placed after the close of day t can first fill on day t+1.",
    "Market orders fill at the open plus slippage; they never fill outside the day's high-low range.",
    "Limit orders fill only if the price trades through the limit (low < buy limit, high > sell limit) or opens through it.",
    "Stop orders trigger on the day's range; a gap through the stop fills at the open, not at the stop.",
    "At most `max_participation` of the day's traded volume can be filled per symbol per day (uses that day's realised volume, which is mildly optimistic).",
    "Slippage = half-spread (by liquidity bucket, an assumption) + impact_coef * daily volatility * sqrt(quantity / 20-day average volume).",
    "A bar with high == low is treated as circuit-locked: no fills.",
    "Delivery (CNC) only: no short selling, no leverage, no intraday product.",
    "Sale proceeds are usable for new buys immediately (as brokers allow); withdrawals are not modelled.",
    "Dividends are credited gross on the ex-date; TDS and record-date eligibility are not modelled.",
]

SPREAD_BUCKETS_BPS = [(1e9, 2.0), (1e8, 5.0), (1e7, 15.0), (0.0, 40.0)]  # ADV in INR -> half-spread bps (assumption)


class ActionError(ValueError):
    """An invalid player action. The message is safe to show."""


@dataclass
class SimConfig:
    start: date
    end: date
    universe: list[str]
    capital: float = 1_000_000.0
    max_participation: float = 0.10
    impact_coef: float = 0.7
    brokerage_flat: float = 20.0
    brokerage_pct: float = 0.0003
    hide_identity: bool = False  # "blind" mode: show tickers as A, B, C so hindsight memory can't help

    def brokerage(self) -> Brokerage:
        return Brokerage(self.brokerage_flat, self.brokerage_pct)


@dataclass
class Order:
    id: str
    symbol: str
    side: str
    qty: int
    order_type: str = "MARKET"  # MARKET | LIMIT | STOP
    limit: float | None = None
    stop: float | None = None
    tif: str = "DAY"  # DAY | GTC
    placed: date | None = None
    status: str = "OPEN"  # OPEN | PARTIAL | FILLED | CANCELLED | EXPIRED | REJECTED
    filled_qty: int = 0
    avg_price: float = 0.0
    reason: str = ""
    thesis: str = ""
    planned_stop: float | None = None
    planned_exit: float | None = None
    horizon_days: int | None = None
    conviction: float | None = None  # player's self-rated 0..1, used for calibration feedback

    @property
    def remaining(self) -> int:
        return self.qty - self.filled_qty


@dataclass
class Fill:
    order_id: str
    symbol: str
    side: str
    qty: int
    price: float
    d: date
    charges: dict
    slippage_bps: float
    ref_price: float


@dataclass
class Lot:
    qty: int
    cost: float  # per share, including buy charges
    entry: date
    order_id: str


@dataclass
class Trade:
    """A closed (or partially closed) round trip, matched FIFO."""
    symbol: str
    qty: int
    entry_date: date
    exit_date: date
    entry_cost: float  # per share incl. buy charges
    exit_net: float  # per share net of sell charges
    entry_order_id: str
    exit_order_id: str

    @property
    def pnl(self) -> float:
        return (self.exit_net - self.entry_cost) * self.qty

    @property
    def ret(self) -> float:
        return self.exit_net / self.entry_cost - 1


@dataclass
class EquityPoint:
    d: date
    equity: float
    cash: float
    benchmark: float | None


@dataclass
class Sim:
    cfg: SimConfig
    data: MarketData
    clock: date = field(init=False)
    cash: float = field(init=False)
    lots: dict[str, list[Lot]] = field(default_factory=dict)
    orders: list[Order] = field(default_factory=list)
    fills: list[Fill] = field(default_factory=list)
    trades: list[Trade] = field(default_factory=list)
    equity: list[EquityPoint] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    finished: bool = False

    def __post_init__(self) -> None:
        cal = [d for d in self.data.calendar() if self.cfg.start <= d <= self.cfg.end]
        if len(cal) < 2:
            raise ActionError("the chosen period has fewer than two trading days of data")
        bad = [s for s in self.cfg.universe if s not in self.data.bars]
        if bad:
            raise ActionError(f"no data for: {', '.join(bad)}")
        self._cal = cal
        self._i = 0
        self.clock = cal[0]
        self.cash = float(self.cfg.capital)
        self._mark()

    # ---------- reads ----------
    def view(self) -> PITView:
        return PITView(self.data, self.clock)

    def qty(self, symbol: str) -> int:
        return sum(l.qty for l in self.lots.get(symbol, []))

    def last_close(self, symbol: str, upto: date | None = None) -> float | None:
        h = self.data.history(symbol, upto or self.clock)
        return h[-1].close if h else None

    def holdings_value(self, upto: date | None = None) -> float:
        return sum(self.qty(s) * (self.last_close(s, upto) or 0.0) for s in self.lots)

    # ---------- actions ----------
    def apply(self, action: dict) -> None:
        kind = action.get("type")
        if kind == "order":
            self._place(action)
        elif kind == "cancel":
            self._cancel(str(action.get("order_id", "")))
        elif kind == "advance":
            self.advance(int(action.get("days", 1)))
        elif kind == "note":
            self._log("note", text=str(action.get("text", ""))[:2000])
        else:
            raise ActionError(f"unknown action type: {kind!r}")

    def _place(self, a: dict) -> None:
        if self.finished:
            raise ActionError("the simulation has ended")
        sym = str(a.get("symbol", ""))
        if sym not in self.cfg.universe:
            raise ActionError(f"{sym} is not in this simulation's universe")
        side = str(a.get("side", "")).upper()
        if side not in ("BUY", "SELL"):
            raise ActionError("side must be BUY or SELL")
        qty = a.get("qty")
        if not isinstance(qty, int) or isinstance(qty, bool) or qty <= 0:
            raise ActionError("quantity must be a positive whole number of shares")
        otype = str(a.get("order_type", "MARKET")).upper()
        if otype not in ("MARKET", "LIMIT", "STOP"):
            raise ActionError("order_type must be MARKET, LIMIT or STOP")
        limit, stop = a.get("limit"), a.get("stop")
        if otype == "LIMIT" and not (isinstance(limit, (int, float)) and limit > 0):
            raise ActionError("a LIMIT order needs a positive limit price")
        if otype == "STOP" and not (isinstance(stop, (int, float)) and stop > 0):
            raise ActionError("a STOP order needs a positive stop price")
        tif = str(a.get("tif", "DAY")).upper()
        if tif not in ("DAY", "GTC"):
            raise ActionError("tif must be DAY or GTC")
        if side == "SELL":
            pending = sum(o.remaining for o in self.orders if o.symbol == sym and o.side == "SELL" and o.status in ("OPEN", "PARTIAL"))
            if qty + pending > self.qty(sym):
                raise ActionError(f"you hold {self.qty(sym)} {sym} with {pending} already pending sale; short selling is not allowed in delivery")
        conf = a.get("conviction")
        o = Order(
            id=f"o{len(self.orders) + 1}", symbol=sym, side=side, qty=qty, order_type=otype,
            limit=_opt_float(limit) if otype == "LIMIT" else None, stop=_opt_float(stop) if otype == "STOP" else None,
            tif=tif, placed=self.clock, thesis=str(a.get("thesis", ""))[:2000],
            planned_stop=_opt_float(a.get("planned_stop")), planned_exit=_opt_float(a.get("planned_exit")),
            horizon_days=int(a["horizon_days"]) if isinstance(a.get("horizon_days"), int) else None,
            conviction=float(conf) if isinstance(conf, (int, float)) and 0 <= conf <= 1 else None,
        )
        self.orders.append(o)
        self._log("order_placed", order_id=o.id, symbol=sym, side=side, qty=qty, order_type=otype)

    def _cancel(self, oid: str) -> None:
        o = next((o for o in self.orders if o.id == oid), None)
        if o is None or o.status not in ("OPEN", "PARTIAL"):
            raise ActionError(f"order {oid} is not open")
        o.status, o.reason = "CANCELLED", "cancelled by you"
        self._log("order_cancelled", order_id=oid)

    def advance(self, days: int = 1) -> None:
        if days < 1 or days > 260:
            raise ActionError("advance between 1 and 260 trading days at a time")
        for _ in range(days):
            if self._i + 1 >= len(self._cal):
                self.finished = True
                self._log("finished")
                return
            self._i += 1
            self.clock = self._cal[self._i]
            self._corporate_actions(self.clock)
            self._match(self.clock)
            self._mark()

    # ---------- day processing ----------
    def _corporate_actions(self, d: date) -> None:
        for ca in self.data.actions_on(d):
            if ca.symbol not in self.cfg.universe:
                continue
            held = self.qty(ca.symbol)
            if ca.kind in ("split", "bonus") and ca.factor > 0:
                prev = self.last_close(ca.symbol, self._cal[self._i - 1]) or 0.0
                frac_cash = 0.0
                for lot in self.lots.get(ca.symbol, []):
                    new_q = lot.qty * ca.factor
                    whole = math.floor(new_q + 1e-9)
                    frac_cash += (new_q - whole) * prev / ca.factor  # cash in lieu at the post-action reference price
                    lot.cost = lot.cost * lot.qty / whole if whole else lot.cost
                    lot.qty = whole
                for o in self.orders:
                    if o.symbol == ca.symbol and o.status in ("OPEN", "PARTIAL"):
                        o.qty = o.filled_qty + math.floor(o.remaining * ca.factor)
                        o.limit = o.limit / ca.factor if o.limit else None
                        o.stop = o.stop / ca.factor if o.stop else None
                self.cash += frac_cash
                self._log("corporate_action", symbol=ca.symbol, kind=ca.kind, factor=ca.factor, held_before=held, held_after=self.qty(ca.symbol), cash_in_lieu=round(frac_cash, 2), source=ca.source)
            elif ca.kind == "dividend" and held:
                amt = held * ca.cash_per_share
                self.cash += amt
                self._log("dividend", symbol=ca.symbol, per_share=ca.cash_per_share, shares=held, amount=round(amt, 2), source=ca.source)

    def _match(self, d: date) -> None:
        used: dict[str, int] = {}
        for o in self.orders:
            if o.status not in ("OPEN", "PARTIAL") or o.placed is None or o.placed >= d:
                continue
            bar = self.data.bar(o.symbol, d)
            if bar is None:
                self._end_day(o, "no trading in this stock today")
                continue
            if bar.high == bar.low:
                self._end_day(o, "single-price day (likely circuit-locked); no fill simulated")
                continue
            px_ref = self._trigger(o, bar)
            if px_ref is None:
                self._end_day(o, "price did not reach your level")
                continue
            cap = int(self.cfg.max_participation * bar.volume) - used.get(o.symbol, 0)
            q = min(o.remaining, max(cap, 0))
            if o.side == "SELL":
                q = min(q, self.qty(o.symbol))
            if q <= 0:
                self._end_day(o, "liquidity cap reached")
                continue
            slip = self._slippage_bps(o.symbol, d, q) if o.order_type != "LIMIT" else 0.0
            sign = 1 if o.side == "BUY" else -1
            px = px_ref * (1 + sign * slip / 1e4)
            px = min(px, bar.high) if o.side == "BUY" else max(px, bar.low)
            if o.order_type == "LIMIT" and o.limit is not None:
                px = min(px, o.limit) if o.side == "BUY" else max(px, o.limit)
            if o.side == "BUY":
                q = self._affordable(q, px, d)
                if q <= 0:
                    o.status, o.reason = "REJECTED", "not enough cash"
                    self._log("order_rejected", order_id=o.id, reason=o.reason)
                    continue
            self._fill(o, q, round(px, 2), d, slip, px_ref)
            used[o.symbol] = used.get(o.symbol, 0) + q
            if o.remaining and o.order_type == "MARKET":
                o.status, o.reason = "CANCELLED", "rest cancelled: liquidity cap"
            elif o.remaining:
                self._end_day(o, "partly filled (liquidity cap)")

    def _trigger(self, o: Order, b: Bar) -> float | None:
        if o.order_type == "MARKET":
            return b.open
        if o.order_type == "LIMIT":
            lim = o.limit or 0.0
            if o.side == "BUY":
                return b.open if b.open <= lim else (lim if b.low < lim else None)
            return b.open if b.open >= lim else (lim if b.high > lim else None)
        st = o.stop or 0.0
        if o.side == "SELL":
            return b.open if b.open <= st else (st if b.low <= st else None)
        return b.open if b.open >= st else (st if b.high >= st else None)

    def _slippage_bps(self, sym: str, d: date, q: int) -> float:
        prior = [b for b in self.data.history(sym, d) if b.d < d][-21:]
        vols = [b.volume for b in prior[-20:] if b.volume > 0]
        adv = sum(vols) / len(vols) if vols else 0.0
        rets = [math.log(b2.close / b1.close) for b1, b2 in zip(prior, prior[1:]) if b1.close > 0 and b2.close > 0]
        sigma = _stdev(rets) if len(rets) >= 5 else 0.02
        adv_inr = adv * (prior[-1].close if prior else 0.0)
        half = next(bps for floor, bps in SPREAD_BUCKETS_BPS if adv_inr >= floor)
        impact = self.cfg.impact_coef * sigma * math.sqrt(q / adv) * 1e4 if adv > 0 else 100.0
        return half + impact

    def _affordable(self, q: int, px: float, d: date) -> int:
        brk = self.cfg.brokerage()
        while q > 0 and q * px + charges("BUY", q * px, d, brk)["total"] > self.cash + 1e-6:
            q = min(q - 1, int(self.cash / (px * 1.002)))
        return max(q, 0)

    def _fill(self, o: Order, q: int, px: float, d: date, slip: float, ref: float) -> None:
        ch = charges(o.side, q * px, d, self.cfg.brokerage())
        f = Fill(o.id, o.symbol, o.side, q, px, d, ch, round(slip, 2), ref)
        self.fills.append(f)
        o.avg_price = (o.avg_price * o.filled_qty + px * q) / (o.filled_qty + q)
        o.filled_qty += q
        o.status = "FILLED" if o.remaining == 0 else "PARTIAL"
        if o.side == "BUY":
            self.cash -= q * px + ch["total"]
            self.lots.setdefault(o.symbol, []).append(Lot(q, px + ch["total"] / q, d, o.id))
        else:
            self.cash += q * px - ch["total"]
            net = px - ch["total"] / q
            left = q
            lots = self.lots[o.symbol]
            while left:
                lot = lots[0]
                take = min(left, lot.qty)
                self.trades.append(Trade(o.symbol, take, lot.entry, d, lot.cost, net, lot.order_id, o.id))
                lot.qty -= take
                left -= take
                if lot.qty == 0:
                    lots.pop(0)
            if not lots:
                del self.lots[o.symbol]
        self._log("fill", order_id=o.id, symbol=o.symbol, side=o.side, qty=q, price=px, charges=ch["total"], slippage_bps=round(slip, 2))

    def _end_day(self, o: Order, why: str) -> None:
        if o.tif == "DAY":
            o.status = "EXPIRED" if o.filled_qty == 0 else "PARTIAL_EXPIRED"
            o.reason = why
            self._log("order_expired", order_id=o.id, reason=why)

    def _mark(self) -> None:
        bench = self.data.benchmark
        b = self.last_close(bench) if bench else None
        self.equity.append(EquityPoint(self.clock, round(self.cash + self.holdings_value(), 2), round(self.cash, 2), b))
        if self.cash < -0.01:
            raise AssertionError("cash went negative")  # accounting invariant; must never trigger

    def _log(self, event: str, **kw) -> None:
        self.events.append({"d": self.clock.isoformat(), "event": event, **kw})

    # ---------- output ----------
    def state(self) -> dict:
        v = self.view()
        positions = []
        for sym in sorted(self.lots):
            q = self.qty(sym)
            cost = sum(l.qty * l.cost for l in self.lots[sym])
            px = (v.last(sym) or Bar(self.clock, 0, 0, 0, 0, 0)).close
            positions.append({"symbol": sym, "qty": q, "avg_cost": round(cost / q, 2), "last": px, "value": round(q * px, 2), "unrealised": round(q * px - cost, 2)})
        return {
            "clock": self.clock.isoformat(), "finished": self.finished, "cash": round(self.cash, 2),
            "equity": self.equity[-1].equity, "positions": positions,
            "orders": [_order_dict(o) for o in self.orders],
            "fills": [_jsonable(asdict(f)) for f in self.fills],
            "trades": [{**_jsonable(asdict(t)), "pnl": round(t.pnl, 2), "ret": round(t.ret, 5)} for t in self.trades],
            "equity_curve": [_jsonable(asdict(p)) for p in self.equity],
            "events": self.events[-200:], "assumptions": ASSUMPTIONS,
            "days_total": len(self._cal), "day_index": self._i,
        }


def replay(cfg: SimConfig, data: MarketData, actions: list[dict]) -> Sim:
    """Rebuild a session from its action log. Raises ActionError at the first invalid action."""
    sim = Sim(cfg, data)
    for i, a in enumerate(actions):
        try:
            sim.apply(a)
        except ActionError as e:
            raise ActionError(f"action {i + 1}: {e}") from None
    return sim


def _opt_float(x) -> float | None:
    return float(x) if isinstance(x, (int, float)) and x > 0 else None


def _stdev(xs: list[float]) -> float:
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def _jsonable(d: dict) -> dict:
    return {k: (v.isoformat() if isinstance(v, date) else v) for k, v in d.items()}


def _order_dict(o: Order) -> dict:
    return {**_jsonable(asdict(o)), "avg_price": round(o.avg_price, 2), "remaining": o.remaining}
