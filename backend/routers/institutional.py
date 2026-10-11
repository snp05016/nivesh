"""Institutional-money routes: FII/DII flow, block deals, institutional flow and leaderboard.

Split out of routers/market.py (ARCH-14); paths, handler names and tags are unchanged.
"""
from helpers import get_session, DataHarvestingError
import logging
import asyncio
from datetime import timezone
from fastapi import APIRouter, HTTPException, Query
from services.scraper import fetch_institutional_flow
from pydantic import BaseModel as _BaseModel
from typing import List as _List, Optional as _Optional
from datetime import datetime as _dt

router = APIRouter(tags=["Market Data"])


@router.get("/block-deals/{ticker}")
def block_deals_endpoint(
    ticker: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    from database import BlockDeal
    try:
        with get_session() as db:
            deals = db.query(BlockDeal).filter(BlockDeal.ticker == ticker.upper()).order_by(BlockDeal.date.desc()).offset(offset).limit(limit).all()
            return {
                "ticker": ticker,
                "deals": [
                    {
                        "date": d.date,
                        "client_name": d.client_name,
                        "deal_type": d.deal_type,
                        "quantity": d.quantity,
                        "price": d.price
                    } for d in deals
                ]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/fii-dii-flow")
def fii_dii_flow_endpoint(
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    from database import FIIDIIFlow
    try:
        with get_session() as db:
            flows = db.query(FIIDIIFlow).order_by(FIIDIIFlow.date.desc()).offset(offset).limit(limit).all()
            # Try to parse dates properly if needed or just return them
            return {
                "flows": [
                    {
                        "date": f.date,
                        "fii_buy": f.fii_buy,
                        "fii_sell": f.fii_sell,
                        "fii_net": f.fii_net,
                        "dii_buy": f.dii_buy,
                        "dii_sell": f.dii_sell,
                        "dii_net": f.dii_net
                    } for f in flows
                ]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/v1/market/institutional-flow")
def market_institutional_flow_endpoint():
    """
    Top 10 mutual funds by 1-year return (leaderboard).

    Args:

    Returns:
        Any: The response.
    """
    try:
        return fetch_institutional_flow()
    except Exception as e:
        logging.warning("Institutional flow unavailable: %s", e)
        raise HTTPException(status_code=502, detail="Institutional flow temporarily unavailable")


class MutualFundEntry(_BaseModel):
    fund_name: str
    amc: _Optional[str]
    return_1y_pct: _Optional[float]
    return_3y_pct: _Optional[float]
    aum_crores: _Optional[float]
    category: _Optional[str]


class InstitutionalLeaderboardResponseLocal(_BaseModel):
    top_funds: _List[MutualFundEntry]
    fetched_at: str


# ── /api/v1/market/institutional-leaderboard ─────────────────────────────────

@router.get("/api/v1/market/institutional-leaderboard", response_model=InstitutionalLeaderboardResponseLocal)
async def institutional_leaderboard_endpoint():
    """
    Top-performing mutual funds sorted by 1-year return.
Proxies DII floor support intelligence. 15-min TTL cache.
Raises 503 on DataHarvestingError.

    Args:

    Returns:
        Any: The response.
    """
    try:
        raw = await asyncio.get_event_loop().run_in_executor(None, fetch_institutional_flow)
    except DataHarvestingError:
        raise
    except Exception as exc:
        raise DataHarvestingError(str(exc)) from exc

    raw_funds = raw.get("top_funds", []) if isinstance(raw, dict) else []
    funds = [
        MutualFundEntry(
            fund_name=f.get("fund_name", f.get("name", "")),
            amc=f.get("amc"),
            return_1y_pct=f.get("return_1y_pct", f.get("1y_return")),
            return_3y_pct=f.get("return_3y_pct", f.get("3y_return")),
            aum_crores=f.get("aum_crores"),
            category=f.get("category"),
        )
        for f in raw_funds
    ]
    # Sort by 1-year return descending (highest alpha first)
    funds.sort(key=lambda f: f.return_1y_pct or 0.0, reverse=True)

    return InstitutionalLeaderboardResponseLocal(
        top_funds=funds,
        fetched_at=_dt.now(timezone.utc).isoformat(),
    )
