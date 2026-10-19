from config.settings import get_user_agent
import logging
"""
Portfolio-related endpoints extracted from main.py.
"""
import random
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Query, Request

from services.disk_cache import invalidate as _cache_invalidate
from services.ledger_service import record_transaction, get_or_create_default_group, adjust_position, close_position, LedgerError, parse_trade_date
from services.yfinance_client import _yf_price_with_status

from helpers import (
    get_session, EXCHANGE_SUFFIX, _to_ns, _yf_price, _quick_info_cache,
    _QUICK_INFO_TTL, DataHarvestingError, User, Portfolio,
    PortfolioValuationHistory, PKScreenerSignal, MacroEvent, PortfolioAddRequest,
    PortfolioRemoveRequest, PortfolioUpdateRequest, PortfolioNoteRequest, _check_rate_limit,
    _get_analyze_semaphore, _acquire_analysis_slot, _release_analysis_slot, _dash_start_job,
    _dash_end_job, _dash_update_harvest, require_auth,
)
from core.security import require_user_match, assert_same_user


from decimal import Decimal

from services.staleness import compute_staleness
from repositories.analysis_repo import latest_signals_by_ticker


# Splits/bonuses reach holdings as ledger SPLIT rows (ledger_service.sync_corporate_actions_all_users).

from services.portfolio_service import (
    _nse_session,
    compute_holding_pnl,
    _INDICES_TICKERS,
)


from pydantic import BaseModel as _BaseModel, Field as _Field
from typing import Optional as _Optional


# _INDICES_TICKERS, _get_indices_data imported from services.portfolio_service


router = APIRouter(tags=["Portfolio"])

# ---------------------------------------------------------------------------
# 1. GET /portfolio/{user_id}
# ---------------------------------------------------------------------------
@router.get("/portfolio/{user_id}")
def portfolio_endpoint(
    user_id: int, request: Request, _caller: int = Depends(require_user_match), is_virtual: bool = False,
):
    # Fund rows (ISIN tickers) go only to builds that declare they understand them; shipped
    # builds would show an ISIN as a stock (money-mf-valuation).
    mf_ok = "asset_class" in [t.strip() for t in request.headers.get("X-Client-Features", "").split(",")]
    try:
        with get_session() as session:
            user = session.get(User, user_id)
            if not user:
                raise HTTPException(status_code=404, detail=f"User {user_id} not found")

            holding_query = session.query(Portfolio)
            if mf_ok:
                holding_query = holding_query.execution_options(include_mf=True)
            holdings = holding_query.filter(
                Portfolio.user_id == user_id,
                Portfolio.group_name != "watchlist",
                Portfolio.is_virtual == is_virtual,
            ).all()
            if not holdings:
                return {"user": user.display_name, "holdings": [], "total_invested": 0, "total_current": 0, "total_pnl": 0}

            tickers = [h.ticker for h in holdings]
            fund_tickers = [h.ticker for h in holdings if h.asset_class == "MF"]
            latest = latest_signals_by_ticker(session, [t for t in tickers if t not in fund_tickers], user_id=user_id)
            last_analyses = {t: rows[0]["created_at"] for t, rows in latest.items()}
            last_signals = {t: rows[0]["signal"] or "HOLD" for t, rows in latest.items()}

        # Fetch all prices in parallel — 10x faster than sequential yfinance calls.
        # Sync handler (threadpool), so the _to_ns probe stays off the event loop too.
        from concurrent.futures import ThreadPoolExecutor

        def _safe_price(ticker):
            try:
                return _yf_price_with_status(_to_ns(ticker))
            except Exception:
                return (None, None, "unavailable", None)

        stock_tickers = [t for t in tickers if t not in fund_tickers]
        with ThreadPoolExecutor(max_workers=max(1, min(len(stock_tickers), 10))) as pool:
            price_results = list(pool.map(_safe_price, stock_tickers))
        prices = dict(zip(stock_tickers, price_results))
        if fund_tickers:
            from services import money_pricing

            for isin, quote in money_pricing.price_quotes([(t, "MF") for t in fund_tickers]).items():
                prices[isin] = (quote.price, quote.prev_close, quote.status, quote.as_of)

        rows = []
        unpriced: list[str] = []
        total_invested = Decimal("0")
        total_current = Decimal("0")

        for h in holdings:
            current_price, prev_close, price_status, price_as_of = prices.get(
                h.ticker, (None, None, "unavailable", None)
            )
            shares = float(h.shares or 0)  # type: ignore[arg-type]
            buy_price = float(h.buy_price or 0)  # type: ignore[arg-type]
            # An unpriced holding is valued at cost (P&L 0), never at a fake ₹0 price.
            pnl_data = compute_holding_pnl(shares, buy_price, current_price, prev_close, price_status)
            if pnl_data["price_status"] == "unavailable":
                unpriced.append(str(h.ticker))

            total_invested += Decimal(str(pnl_data["invested_inr"]))
            total_current += Decimal(str(pnl_data["current_value_inr"]))

            rows.append({
                "ticker": h.ticker,
                "company_name": h.company_name,
                "group": h.group_name,
                "asset_class": h.asset_class or "EQ",
                # The read model stores full precision; round only for display.
                "shares": round(shares, 6),
                "buy_price": round(buy_price, 2),
                "purchase_date": getattr(h, "purchase_date", "N/A"),
                "notes": getattr(h, "notes", ""),
                "target_price": float(getattr(h, "target_price", 0.0) or 0.0),
                "current_price": current_price or buy_price,
                "price_status": pnl_data["price_status"],
                "price_as_of": price_as_of,
                "day_change_pct": pnl_data["day_change_pct"],
                "invested_inr": pnl_data["invested_inr"],
                "current_value_inr": pnl_data["current_value_inr"],
                "pnl_inr": pnl_data["pnl_inr"],
                "pnl_pct": pnl_data["pnl_pct"],
                "notes": h.notes or "",
                "staleness": compute_staleness(
                    last_analyses.get(h.ticker),
                    pnl_data["day_change_pct"],
                    last_signals.get(h.ticker, "HOLD"),
                ),
            })

        total_pnl = total_current - total_invested

        return {
            "user": user.display_name,
            "user_id": user_id,
            "as_of": datetime.now(timezone.utc).strftime("%d-%b-%Y %H:%M UTC"),
            "total_invested_inr": round(float(total_invested), 2),
            "total_current_inr": round(float(total_current), 2),
            "total_pnl_inr": round(float(total_pnl), 2),
            "total_pnl_pct": round(float(total_pnl / total_invested * Decimal("100")), 2) if total_invested > 0 else 0,
            "unpriced_tickers": unpriced,
            "holdings": sorted(rows, key=lambda x: (x["pnl_pct"] or 0), reverse=True),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 2. GET /portfolio/history/{user_id}
# ---------------------------------------------------------------------------
@router.get("/portfolio/history/{user_id}")
def portfolio_history_endpoint(user_id: int, days: int = Query(30, ge=1, le=3650), _caller: int = Depends(require_user_match)):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    with get_session() as session:
        rows = session.query(PortfolioValuationHistory).filter(
            PortfolioValuationHistory.user_id == user_id,
            PortfolioValuationHistory.snapshot_date >= cutoff,
        ).order_by(PortfolioValuationHistory.snapshot_date.asc()).all()
        return {
            "user_id": user_id,
            "days": days,
            "snapshots": [
                {
                    "date": r.snapshot_date,
                    "total_value": r.total_value,
                    "total_invested": r.total_invested,
                    "total_pnl": r.total_pnl,
                    "pnl_pct": r.pnl_percent,
                    "nifty_close": r.nifty_close,
                }
                for r in rows
            ],
        }


# ---------------------------------------------------------------------------
# 5. POST /portfolio & 6. POST /portfolio/add
# ---------------------------------------------------------------------------
def _parse_trade_date(s: Optional[str]) -> Optional[datetime]:
    """purchase_date -> aware UTC midnight (ledger_service.parse_trade_date); 400 when
    unparseable or in the future. None/blank -> None (the ledger dates the trade now)."""
    try:
        return parse_trade_date(s)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/portfolio")
@router.post("/portfolio/add")
def portfolio_add_endpoint(
    req: PortfolioAddRequest,
    token_user: int = Depends(require_auth),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key", max_length=64),
):
    assert_same_user(req.user_id, token_user)
    if not req.ticker or not req.ticker.strip():
        raise HTTPException(status_code=400, detail="Ticker cannot be empty.")
    if req.shares <= 0:
        raise HTTPException(status_code=400, detail="Shares must be greater than 0.")
    if req.buy_price <= 0:
        raise HTTPException(status_code=400, detail="Buy price must be greater than 0.")
    # Paper trades would merge into the real holding (one read-model row per
    # user+ticker, no is_virtual on Transaction), so reject them until built.
    if req.is_virtual:
        raise HTTPException(status_code=400, detail="Paper trades are not supported yet.")

    ticker = req.ticker.upper().strip()
    trade_date = _parse_trade_date(req.purchase_date)
    try:
        record_transaction(
            user_id=req.user_id,
            ticker=ticker,
            transaction_type=req.transaction_type.upper(),
            quantity=req.shares,
            price=req.buy_price,
            fees=0.0,
            date=trade_date,
            notes=req.notes,
            company_name=req.company_name,
            target_price=req.target_price,
            purchase_date=trade_date.strftime("%Y-%m-%d") if trade_date else None,
            client_request_id=idempotency_key,
        )
        _cache_invalidate("morning_brief", str(req.user_id))

        ns = _to_ns(ticker)
        current_price, prev_close = _yf_price(ns)
        pnl_data = compute_holding_pnl(req.shares, req.buy_price, current_price, prev_close)

        return {
            "success": True,
            "ticker": ticker,
            "company_name": req.company_name,
            "group": "holdings",
            "shares": req.shares,
            "buy_price": req.buy_price,
            "current_price": current_price or req.buy_price,
            **pnl_data,
        }
    except HTTPException:
        raise
    except LedgerError as e:  # e.g. oversell / backdated SELL: a client error, not a 500
        raise HTTPException(status_code=422, detail=str(e))
    except ValueError as e:
        # Other rule violations raised on the add path.
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logging.exception("[portfolio/add] failed for user %s %s", req.user_id, ticker)
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 7. DELETE /portfolio/remove
# ---------------------------------------------------------------------------
@router.delete("/portfolio/remove")
def portfolio_remove_endpoint(req: PortfolioRemoveRequest, token_user: int = Depends(require_auth)):
    assert_same_user(req.user_id, token_user)
    ticker = req.ticker.upper().strip()
    try:
        # Through the ledger, so a later BUY cannot resurrect the removed lots.
        if not close_position(req.user_id, ticker):
            raise HTTPException(status_code=404, detail="Holding not found.")
        _cache_invalidate("morning_brief", str(req.user_id))
        return {"success": True, "ticker": ticker}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 8. PUT /portfolio/update
# ---------------------------------------------------------------------------
@router.put("/portfolio/update")
def portfolio_update_endpoint(req: PortfolioUpdateRequest, token_user: int = Depends(require_auth)):
    assert_same_user(req.user_id, token_user)
    if req.shares <= 0:
        raise HTTPException(status_code=400, detail="Shares must be greater than 0.")
    if req.buy_price <= 0:
        raise HTTPException(status_code=400, detail="Buy price must be greater than 0.")

    ticker = req.ticker.upper().strip()
    try:
        # Through the ledger (ADJUST entry), so the next BUY/SELL keeps this edit.
        company_name = adjust_position(
            req.user_id, ticker, req.shares, req.buy_price,
            target_price=req.target_price, purchase_date=req.purchase_date,
        )
        if company_name is None:
            raise HTTPException(status_code=404, detail="Holding not found.")
        _cache_invalidate("morning_brief", str(req.user_id))

        ns = _to_ns(ticker)
        current_price, prev_close = _yf_price(ns)
        pnl_data = compute_holding_pnl(req.shares, req.buy_price, current_price, prev_close)

        return {
            "success": True,
            "ticker": ticker,
            "company_name": company_name,
            "group": "holdings",
            "shares": req.shares,
            "buy_price": req.buy_price,
            "current_price": current_price or req.buy_price,
            **pnl_data,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 9. GET /portfolio/transactions/{ticker}
# ---------------------------------------------------------------------------
@router.get("/portfolio/transactions/{ticker}")
def portfolio_transactions_endpoint(ticker: str, user_id: int, _caller: int = Depends(require_user_match)):
    ticker = ticker.upper().strip()
    try:
        from services.ledger_service import get_transactions_for_ticker
        return get_transactions_for_ticker(user_id=user_id, ticker=ticker)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 10. PUT /portfolio/note
# ---------------------------------------------------------------------------
@router.put("/portfolio/note")
def portfolio_note_endpoint(req: PortfolioNoteRequest, token_user: int = Depends(require_auth)):
    assert_same_user(req.user_id, token_user)
    ticker = req.ticker.upper().strip()
    try:
        with get_session() as session:
            holding = session.query(Portfolio).filter_by(
                user_id=req.user_id, ticker=ticker
            ).first()
            if not holding:
                raise HTTPException(status_code=404, detail="Stock not found in portfolio or watchlist")
            holding.notes = req.note.strip()
            session.commit()
            _cache_invalidate("morning_brief", str(req.user_id))
        return {"success": True, "ticker": ticker, "note": req.note.strip()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


from database import PortfolioTransaction


@router.post("/portfolio/multi-asset/transaction", status_code=410)
def multi_asset_transaction_entry(_token_user: int = Depends(require_auth)):
    """Retired (money C4): portfolio_transactions is the only ledger, so stock and
    fund trades go through POST /portfolio/add. The body is ignored and nothing is
    read or written (require_auth only verifies the token)."""
    raise HTTPException(
        status_code=410,
        detail={"code": "ENDPOINT_RETIRED", "message": "Use POST /portfolio/add."},
    )


@router.get("/portfolio/multi-asset/transactions/{user_id}")
def multi_asset_transactions_history(user_id: int, asset_type: _Optional[str] = None, _caller: int = Depends(require_user_match)):
        
    try:
        with get_session() as session:
            query = session.query(PortfolioTransaction).filter(PortfolioTransaction.user_id == user_id)
            if asset_type:
                query = query.filter(PortfolioTransaction.asset_type == asset_type.upper())
            
            transactions = query.order_by(PortfolioTransaction.date.desc()).all()
            
            return [
                {
                    "id": tx.id,
                    "asset_type": tx.asset_type,
                    "symbol": tx.symbol,
                    "transaction_type": tx.transaction_type,
                    "quantity": tx.quantity,
                    "price": tx.price,
                    "fees": tx.fees,
                    "date": tx.date.isoformat() if tx.date else None,
                    "notes": tx.notes
                }
                for tx in transactions
            ]
    except Exception as e:
        logging.error(f"Error fetching multi-asset transactions: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
