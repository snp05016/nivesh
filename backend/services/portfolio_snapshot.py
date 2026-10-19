"""
Nivesh Portfolio Snapshot
Takes a daily valuation snapshot for all users.
Uses the same yfinance price logic as the /portfolio endpoint.
Run nightly at 4:30 PM IST (market close + 30 min settlement).

Also provides pregen_morning_briefs_all_users() — pre-generates morning briefs
for all users at 6:30 AM IST so the /morning-summary endpoint is instant.
"""
import yfinance as yf
import asyncio
import logging
from datetime import datetime, date, timedelta, timezone
import sys
import os
import json
from types import SimpleNamespace
from typing import cast

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_session, Portfolio, PortfolioValuationHistory, User, AnalysisHistory, NetWorthLedger, latest_per_ticker
from schemas.db_json_schemas import PortfolioPositionSchema, PortfolioSnapshotSchema, safe_validate_portfolio_json
from services.llm_utils import contains_devanagari
from services.yfinance_client import _yf_price, _to_ns
from services.kyc_consent_service import AI_PROCESSING_CONSENT, has_active_consent

logger = logging.getLogger(__name__)

# Disk-cache namespace for pre-generated morning briefs
from config.settings import MORNING_BRIEF_TTL
_MORNING_BRIEF_NS = "morning_brief"

# A missing price skips the user's snapshot (an honest gap) for at most this many
# days; after that, today's row is written over the priced holdings only, so one
# delisted / mistyped ticker cannot freeze PortfolioValuationHistory forever.
_SNAPSHOT_MAX_GAP_DAYS = 3


def get_current_price(ticker: str) -> float | None:
    """Latest price via the shared helper (retry, BSE→NSE fallback, WARNING on miss).

    _to_ns keeps already-suffixed tickers ("TCS.NS") and applies
    NSE_TICKER_OVERRIDES, so this prices exactly what GET /portfolio prices.
    Blocking (time.sleep in the retry): call it via asyncio.to_thread.

    Args:
        ticker (str): The stored ticker symbol, with or without exchange suffix.

    Returns:
        float | None: The latest closing price, or None if unavailable.
    """
    try:
        return _yf_price(_to_ns(ticker))[0]
    except Exception as e:
        logger.warning(f"[Snapshot] price lookup failed for {ticker}: {e}")
        return None


def _net_worth_ledger_row(db, user_id, today_str, priced, total_value, total_invested, pnl, pnl_pct, nifty_close):
    """Build today's NetWorthLedger row for one user.

    Daily delta, running peak and per-ticker moves are measured against the
    user's previous ledger row (the last snapshot), so no extra price calls are
    made and non-trading days show no phantom moves.

    Args:
        priced: (holding, price) pairs for the holdings valued today; a holding
            has ticker, company_name, shares and buy_price.
    """
    prev = db.query(NetWorthLedger).filter(
        NetWorthLedger.user_id == user_id,
        NetWorthLedger.snapshot_date < today_str,
    ).order_by(NetWorthLedger.snapshot_date.desc()).first()
    try:
        old = safe_validate_portfolio_json(json.loads(prev.portfolio_json)) if prev is not None and prev.portfolio_json else None
    except ValueError:
        old = None
    prev_prices = {p.ticker: p.current_price for p in old.positions} if old else {}

    positions, moves = [], {}
    for holding, price in priced:
        ticker = str(holding.ticker)
        value = float(holding.shares) * price  # type: ignore[arg-type]
        old_price = prev_prices.get(ticker)
        if old_price:
            moves[ticker] = round((price - old_price) / old_price * 100, 2)
        positions.append(PortfolioPositionSchema(
            ticker=ticker,
            company_name=str(holding.company_name or ""),
            shares=float(holding.shares),  # type: ignore[arg-type]
            buy_price=float(holding.buy_price),  # type: ignore[arg-type]
            current_price=price,
            day_change_pct=moves.get(ticker, 0.0),
            total_value=round(value, 2),
            weight_pct=round(value / total_value * 100, 2) if total_value > 0 else 0.0,
        ))
    gainer = max(moves, key=lambda t: moves[t]) if moves else None
    loser = min(moves, key=lambda t: moves[t]) if moves else None
    if gainer is not None and moves[gainer] <= 0:
        gainer = None
    if loser is not None and moves[loser] >= 0:
        loser = None

    prev_total = float(prev.total_value_inr) if prev is not None else None
    delta = total_value - prev_total if prev_total is not None else None
    peak = max(total_value, float(prev.peak_value_inr or prev.total_value_inr)) if prev is not None else total_value

    summary = PortfolioSnapshotSchema(
        date=today_str,
        total_value_inr=round(total_value, 2),
        total_invested_inr=round(total_invested, 2),
        total_pnl_inr=round(pnl, 2),
        pnl_pct=round(pnl_pct, 2),
        positions=positions,
        nifty_close=nifty_close,
        top_gainer_ticker=gainer,
        top_gainer_pct=moves.get(gainer) if gainer else None,
        top_loser_ticker=loser,
        top_loser_pct=moves.get(loser) if loser else None,
    )
    return NetWorthLedger(
        user_id=user_id,
        snapshot_date=today_str,
        total_value_inr=round(total_value, 2),
        daily_delta_inr=round(delta, 2) if delta is not None else None,
        daily_delta_pct=round(delta / prev_total * 100, 2) if delta is not None and prev_total else None,
        peak_value_inr=round(peak, 2),
        top_gainer_ticker=summary.top_gainer_ticker,
        top_gainer_pct=summary.top_gainer_pct,
        top_loser_ticker=summary.top_loser_ticker,
        top_loser_pct=summary.top_loser_pct,
        portfolio_json=summary.model_dump_json(),
    )


async def snapshot_all_users() -> dict:
    """Take the daily valuation snapshot and net-worth ledger row for all users.

    Three phases so no DB session is held open across yfinance calls (DB-22):
    a short read session, then pricing with no session, then one short write
    session per user. A re-run the same day only fills the rows still missing,
    so the 12:00 UTC retry job repairs users skipped for a missing price (DB-21).

    Returns:
        dict: Counts of users 'written', 'skipped_partial' and 'already' done today.
    """
    today_str = date.today().isoformat()
    stats = {"written": 0, "skipped_partial": 0, "already": 0}

    # Fetch NIFTY close for benchmark outside the per-user loop
    try:
        nifty = yf.Ticker("^NSEI")
        nifty_hist = nifty.history(period="2d")
        nifty_close = float(nifty_hist["Close"].iloc[-1]) if not nifty_hist.empty else None
    except Exception as _e:
        nifty_close = None

    # Phase 1: who still needs today's rows, with holdings copied to plain values.
    pending = []
    with get_session() as db:
        for (user_id,) in db.query(User.id).all():
            try:
                # Skip if both of today's rows exist; checked separately so a
                # re-run backfills whichever one is missing.
                valuation_done = db.query(PortfolioValuationHistory.id).filter(
                    PortfolioValuationHistory.user_id == user_id,
                    PortfolioValuationHistory.snapshot_date == today_str
                ).first() is not None
                ledger_done = db.query(NetWorthLedger.id).filter(
                    NetWorthLedger.user_id == user_id,
                    NetWorthLedger.snapshot_date == today_str
                ).first() is not None
                if valuation_done and ledger_done:
                    stats["already"] += 1
                    continue

                holdings = [
                    SimpleNamespace(
                        ticker=str(h.ticker),
                        company_name=str(h.company_name or ""),
                        shares=float(h.shares),  # type: ignore[arg-type]
                        buy_price=float(h.buy_price),  # type: ignore[arg-type]
                    )
                    for h in db.query(Portfolio).filter(
                        Portfolio.user_id == user_id,
                        Portfolio.group_name == "holdings"
                    ).all()
                ]
                if holdings:
                    pending.append((user_id, valuation_done, ledger_done, holdings))
            except Exception as e:
                logger.error(f"Snapshot read error for user {user_id}: {e}")
                db.rollback()

    # Phase 2: price each ticker once, with no session open.
    prices = {}
    for ticker in sorted({h.ticker for _, _, _, holdings in pending for h in holdings}):
        prices[ticker] = await asyncio.to_thread(get_current_price, ticker)

    # Phase 3: one short write session per user.
    for user_id, valuation_done, ledger_done, holdings in pending:
        priced = [(h, prices[h.ticker]) for h in holdings if prices.get(h.ticker)]
        missing = [h.ticker for h in holdings if not prices.get(h.ticker)]
        total_value = sum(h.shares * price for h, price in priced)
        total_invested = sum(h.shares * h.buy_price for h, _ in priced)

        with get_session() as db:
            try:
                if missing:
                    latest = db.query(PortfolioValuationHistory.snapshot_date).filter(
                        PortfolioValuationHistory.user_id == user_id
                    ).order_by(PortfolioValuationHistory.snapshot_date.desc()).first()
                    gap_ok = latest is not None and date.fromisoformat(latest[0]) >= (
                        date.today() - timedelta(days=_SNAPSHOT_MAX_GAP_DAYS)
                    )
                    if gap_ok or len(missing) == len(holdings):
                        # Never persist a cost-basis valuation as the day's real value.
                        # The retry run later today fills this gap if prices return.
                        logger.warning(f"Snapshot skipped: user={user_id} no price for {missing}")
                        stats["skipped_partial"] += 1
                        continue
                    # Unpriced holdings are left out of BOTH sides (same policy as
                    # /portfolio/benchmark), so value and P&L stay consistent.
                    logger.warning(
                        f"Snapshot partial: user={user_id} excluded unpriced {missing} "
                        f"(no snapshot in {_SNAPSHOT_MAX_GAP_DAYS}+ days)"
                    )

                pnl = total_value - total_invested
                pnl_pct = (pnl / total_invested * 100) if total_invested > 0 else 0.0

                if not valuation_done:
                    db.add(PortfolioValuationHistory(
                        user_id=user_id,
                        snapshot_date=today_str,
                        total_value=round(total_value, 2),
                        total_invested=round(total_invested, 2),
                        total_pnl=round(pnl, 2),
                        pnl_percent=round(pnl_pct, 2),
                        nifty_close=nifty_close,
                    ))
                if not ledger_done:
                    db.add(_net_worth_ledger_row(
                        db, user_id, today_str, priced, total_value, total_invested, pnl, pnl_pct, nifty_close,
                    ))
                db.commit()
                stats["written"] += 1
                logger.info(f"Snapshot saved: user={user_id} value=₹{total_value:,.0f}")

            except Exception as e:
                logger.error(f"Snapshot error for user {user_id}: {e}")
                db.rollback()

    return stats


async def pregen_morning_briefs_all_users() -> dict:
    """Pre-generate morning briefs for every user who has holdings and an active
    'ai_processing' consent (FINSEC-04: no consent, no data to the LLM processor).

    Called at 6:30 AM IST so the endpoint returns instantly when the user opens the app.
    Stores results in disk_cache under 'morning_brief' namespace keyed by user_id.

    Returns:
        dict: Summary containing generated, skipped, and errors counts.
    """
    from services.disk_cache import set as cache_set
    from services.llm_utils import deepseek_chat as _deepseek_chat

    generated = 0
    skipped = 0
    errors = 0

    # Phase 1: collect all DB data in a single scoped session, then release the connection
    # before any network I/O (yfinance / LLM) starts to avoid pool starvation.
    all_user_data: list[tuple] = []
    with get_session() as db:
        users = db.query(User).all()
        for user in users:
            if not has_active_consent(cast(int, user.id), AI_PROCESSING_CONSENT):
                skipped += 1
                continue
            holdings = db.query(Portfolio).filter_by(
                user_id=user.id, group_name="holdings"
            ).all()
            if not holdings:
                skipped += 1
                continue
            tickers = [h.ticker.upper() for h in holdings]
            last_signals: dict[str, str] = {
                t: rows[0].signal
                for t, rows in latest_per_ticker(db, tickers, user_id=cast(int, user.id)).items()
            }
            # Detach holdings from session by capturing plain values
            holding_snapshots = [
                (h.ticker, str(h.company_name or h.ticker), float(h.shares), float(h.buy_price))
                for h in holdings
            ]
            all_user_data.append((user.id, holding_snapshots, last_signals))

    # Phase 2: I/O per user — no DB session held open
    for user_id_val, holding_snapshots, last_signals in all_user_data:
        try:
            holding_lines = []
            mover_tickers = []
            significant_movers_lines = []

            for ticker, company, shares, buy_price in holding_snapshots:
                ns_sym = f"{ticker}.NS" if not ticker.endswith((".NS", ".BO")) else ticker
                try:
                    t = yf.Ticker(ns_sym)
                    hist = t.history(period="2d")
                    if not hist.empty and len(hist) >= 2:
                        current_price = float(hist["Close"].iloc[-1])
                        prev_close = float(hist["Close"].iloc[-2])
                    elif not hist.empty:
                        current_price = float(hist["Close"].iloc[-1])
                        prev_close = current_price
                    else:
                        current_price = prev_close = None
                except Exception as _e:
                    current_price = prev_close = None

                day_pct = None
                if current_price and prev_close and prev_close > 0:
                    day_pct = round((current_price - prev_close) / prev_close * 100, 2)

                invested = shares * buy_price
                current_value = shares * current_price if current_price else None
                pnl_pct = ((current_value - invested) / invested * 100) if current_value and invested > 0 else None

                # Data minimisation for the LLM processor: % moves only, never
                # share counts, prices or rupee P&L.
                day_str = (f"+{day_pct:.1f}%" if day_pct and day_pct >= 0 else f"{day_pct:.1f}%") if day_pct is not None else "N/A"
                pnl_str = f", overall P&L: {'+' if pnl_pct >= 0 else ''}{pnl_pct:.1f}%" if pnl_pct is not None else ""

                holding_lines.append(
                    f"{ticker} ({company}): day: {day_str}{pnl_str}"
                )

                if day_pct is not None and abs(day_pct) >= 2.0:
                    mover_tickers.append(ticker)
                    significant_movers_lines.append(
                        f"{ticker}: {day_str} ({'UP' if day_pct > 0 else 'DOWN'})"
                    )

            signal_lines = [
                f"{ticker}: {last_signals.get(ticker, 'No analysis yet')}"
                for ticker, _, _, _ in holding_snapshots
            ]

            portfolio_text = "\n".join(holding_lines) or "No holdings."
            movers_text = "\n".join(significant_movers_lines) or "None today"
            signals_text = "\n".join(signal_lines) or "No analysis available."

            prompt = (
                "You are a friendly Indian stock market advisor. Write a short morning brief "
                "(4-6 bullet points) for an investor. Write ONLY in English — never use Hindi. Be specific. "
                "Mention big movers. Flag anything concerning. End with one sentence on market mood. "
                "Use Indian number format (lakhs/crores). Be warm.\n\n"
                f"Portfolio:\n{portfolio_text}\n\n"
                f"Significant movers (±2%+):\n{movers_text}\n\n"
                f"Last AI signals:\n{signals_text}\n\n"
                'Return ONLY JSON: {"summary": "• Point 1\\n• Point 2", '
                '"movers": ["TICKER1"], "mood": "positive"}\n'
                'mood must be: "positive", "cautious", or "negative"'
            )

            # deepseek_chat is sync and takes a messages list (ARCH-03: the old
            # `await _deepseek_chat(prompt)` raised, so no brief was ever pre-generated).
            raw = await asyncio.to_thread(
                _deepseek_chat, [{"role": "user", "content": prompt}],
                max_tokens=1200, log_endpoint="morning_brief_pregen",
            )

            brief = None
            try:
                clean = raw.strip()
                if "```" in clean:
                    clean = clean.split("```")[1]
                    if clean.startswith("json"):
                        clean = clean[4:]
                start = clean.find("{")
                end = clean.rfind("}") + 1
                if start != -1 and end > start:
                    brief = json.loads(clean[start:end])
            except Exception as _e:
                logger.warning("[morning_brief] Unparseable pre-generated brief for user_id=%s: %s", user_id_val, _e)

            # FAKE-22: never cache canned text with an uncomputed mood for the full
            # TTL; leaving the cache empty lets the route build a real brief on demand.
            # SILENT-14: never cache a placeholder or count it as generated; the
            # on-demand endpoint builds the brief when the user opens the app.
            if not isinstance(brief, dict) or not brief.get("summary"):
                errors += 1
                logger.warning("[morning_brief] No usable pre-generated brief for user_id=%s", user_id_val)
                continue
            if contains_devanagari(brief.get("summary", "")):
                errors += 1
                logger.warning("[morning_brief] Rejected Hindi pre-generated brief for user_id=%s", user_id_val)
                continue
            brief.setdefault("movers", mover_tickers)

            brief["generated_at"] = datetime.now(timezone.utc).strftime("%H:%M")
            brief["pregen"] = True

            cache_set(_MORNING_BRIEF_NS, str(user_id_val), brief, ttl=MORNING_BRIEF_TTL)
            generated += 1
            logger.info(f"[morning_brief] Pre-generated for user_id={user_id_val}")

        except Exception as e:
            errors += 1
            logger.error(f"[morning_brief] Error for user_id={user_id_val}: {e}")
            continue

    logger.info(
        f"[morning_brief] Pre-gen complete: generated={generated} skipped={skipped} errors={errors}"
    )
    return {"generated": generated, "skipped": skipped, "errors": errors}
