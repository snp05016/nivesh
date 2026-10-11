"""
Harvester endpoints — ported from nivesh-harvester/main.py into the main backend.

All data endpoints, /sources included, require auth.
Admin endpoints (trigger/stats) require admin auth.
"""

from __future__ import annotations
from fastapi import APIRouter, Query, Header
from helpers import require_auth, require_admin
from services.harvester_service import (
    fetch_feed,
    fetch_governance,
    fetch_sources,
    search_cards,
    trigger_manual_scrape,
    fetch_stats,
    reformat_pending
)

router = APIRouter(prefix="/harvester", tags=["harvester"])


@router.get("/feed")
def get_feed(
    ticker: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    authorization: str = Header(None),
):
    require_auth(authorization)
    return fetch_feed(ticker, limit)


@router.get("/governance/{ticker}")
def get_governance(ticker: str, limit: int = Query(default=20, ge=1, le=100), authorization: str = Header(None)):
    require_auth(authorization)
    return fetch_governance(ticker, limit)


@router.get("/sources")
def get_sources(authorization: str = Header(None)):
    require_auth(authorization)
    return fetch_sources()


@router.get("/search")
def search(q: str = Query(..., min_length=1), limit: int = Query(default=30, ge=1, le=100), authorization: str = Header(None)):
    require_auth(authorization)
    return search_cards(q, limit)


@router.post("/trigger/scrape")
def trigger_scrape(
    source: str = Query(..., pattern="^(sebi|expert|youtube)$"),
    limit: int = Query(default=20, ge=1, le=100),
    authorization: str = Header(None),
):
    require_admin(authorization)
    return trigger_manual_scrape(source, limit)


@router.get("/stats")
def stats(authorization: str = Header(None)):
    require_admin(authorization)
    return fetch_stats()
