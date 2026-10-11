"""Advisor consensus route: GET /api/v1/portfolio/advisor-consensus.

Split out of routers/portfolio.py (ARCH-14); path, handler name and tags are unchanged.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from collections import Counter, defaultdict
from fastapi import APIRouter, Depends, HTTPException, Query
from helpers import get_session, AdvisorInsight, require_auth
from services import stock_universe

router = APIRouter(tags=["Portfolio"])


@router.get("/api/v1/portfolio/advisor-consensus")
def portfolio_advisor_consensus(
    _caller: int = Depends(require_auth),
    user_id: Optional[int] = None,
    days: int = Query(7, ge=1, le=30),
):
    """
    Aggregate AdvisorInsight rows into sector signals and trending tickers.

    The result is market-wide, not per-user: user_id is accepted only for older iOS
    builds and ignored (AUTH-26).

    Args:
        days (int): Look-back window, 1-30.

    Returns:
        Any: The response.
    """

    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        with get_session() as session:
            # ── Fetch all insights in the window ────────────────────────────
            rows = (
                session.query(
                    AdvisorInsight.ticker, AdvisorInsight.video_id, AdvisorInsight.view_count,
                    AdvisorInsight.stance, AdvisorInsight.advisor_name,
                )
                .filter(AdvisorInsight.published_at >= cutoff)
                .all()
            )

            # ── last_harvest_at: most recent created_at across entire table ─
            last_row = (
                session.query(AdvisorInsight.created_at)
                .order_by(AdvisorInsight.created_at.desc())
                .first()
            )
            last_harvest_at = (
                last_row.created_at.isoformat() + "Z"
                if last_row and last_row.created_at
                else None
            )

        # ── total_videos_processed ──────────────────────────────────────────
        total_videos_processed = len({r.video_id for r in rows})

        # ── trending_tickers ─────────────────────────────────────────────────
        ticker_data: dict[str, dict] = {}
        for r in rows:
            tk = r.ticker.upper().strip()
            if tk not in ticker_data:
                ticker_data[tk] = {
                    "mention_count": 0,
                    "view_count_sum": 0,
                    "stances": [],
                    "advisors": set(),
                }
            ticker_data[tk]["mention_count"] += 1
            ticker_data[tk]["view_count_sum"] += r.view_count or 0
            ticker_data[tk]["stances"].append((r.stance or "").upper())
            ticker_data[tk]["advisors"].add(r.advisor_name)

        def _dominant_stance(stances: list[str]) -> str:
            counts = Counter(s for s in stances if s in ("BULLISH", "NEUTRAL", "BEARISH"))
            if not counts:
                return "NEUTRAL"
            return counts.most_common(1)[0][0]

        sorted_tickers = sorted(
            ticker_data.items(),
            key=lambda kv: kv[1]["mention_count"],
            reverse=True,
        )[:5]

        trending_tickers = []
        for tk, td in sorted_tickers:
            company_name = (stock_universe.by_ticker(tk) or {}).get("company_name") or tk
            trending_tickers.append({
                "ticker": tk,
                "company_name": company_name,
                "mention_count": td["mention_count"],
                "dominant_stance": _dominant_stance(td["stances"]),
                "total_view_count": td["view_count_sum"],
                "advisors": sorted(td["advisors"]),
            })

        # ── sector_signals ───────────────────────────────────────────────────
        sector_data: dict[str, dict] = defaultdict(lambda: {
            "bullish_count": 0,
            "bearish_count": 0,
            "neutral_count": 0,
            "advisors": set(),
            "mention_count": 0,
        })
        for r in rows:
            tk = r.ticker.upper().strip()
            sector = stock_universe.sector_for(tk)
            stance = (r.stance or "").upper()
            sector_data[sector]["mention_count"] += 1
            if stance == "BULLISH":
                sector_data[sector]["bullish_count"] += 1
            elif stance == "BEARISH":
                sector_data[sector]["bearish_count"] += 1
            else:
                sector_data[sector]["neutral_count"] += 1
            sector_data[sector]["advisors"].add(r.advisor_name)

        sector_signals = []
        for theme, sd in sector_data.items():
            if sd["mention_count"] < 2:
                continue
            sector_signals.append({
                "theme": theme,
                "bullish_count": sd["bullish_count"],
                "bearish_count": sd["bearish_count"],
                "neutral_count": sd["neutral_count"],
                "top_advisors": sorted(sd["advisors"]),
            })

        sector_signals.sort(key=lambda x: x["bullish_count"], reverse=True)
        sector_signals = sector_signals[:3]

        return {
            "generated_at": datetime.now(timezone.utc).isoformat() + "Z",
            "window_days": days,
            "sector_signals": sector_signals,
            "trending_tickers": trending_tickers,
            "total_videos_processed": total_videos_processed,
            "last_harvest_at": last_harvest_at,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")
