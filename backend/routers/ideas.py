"""Ideas routes: /api/v1/ideas/advisors and /api/v1/ideas/feed.

Split out of routers/market.py (ARCH-14); paths, handler names and tags are unchanged.
"""
from helpers import get_session, AdvisorBiography, TextAdvisoryInsight, log_ideas_error
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from services.sebi_registry import REGISTERED_CHANNELS, registry_is_fresh

router = APIRouter(tags=["Market Data"])


# ═══════════════════════════════════════════════════════════════════════════════
# Ideas Workspace — Registered Channel Directory & Advisory Feed
# ═══════════════════════════════════════════════════════════════════════════════

# ── GET /api/v1/ideas/advisors ─────────────────────────────────────────────

@router.get("/api/v1/ideas/advisors")
def ideas_advisors_endpoint():
    """
    Returns the YouTube channels in services/sebi_registry.py with their SEBI
registration numbers. Built from that registry only, never from the database,
so no unverified registration claim can be served. The list is empty while the
registry is not fresh (re-verified within 90 days), so stale badges fail closed.
Response: { "advisors": [...], "count": N, "fetched_at": "..." }
    """
    channels = REGISTERED_CHANNELS if registry_is_fresh() else []
    advisors = [
        {
            "id": i + 1,
            "advisor_name": c["name"],
            "sebi_reg_number": c["sebi_reg"],
            "experience_years": 0,
            "analytical_framework": ", ".join(t.replace("_", " ").title() for t in c["tags"]),
            "full_biography_text": (
                f"Registered entity: {c['entity']}. SEBI registration {c['sebi_reg']} "
                "(verify at sebi.gov.in). Publishes market commentary on YouTube."
            ),
            "created_at": None,
        }
        for i, c in enumerate(channels)
    ]
    return {
        "advisors": advisors,
        "count": len(advisors),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


# ── GET /api/v1/ideas/feed ─────────────────────────────────────────────────

@router.get("/api/v1/ideas/feed")
def ideas_feed_endpoint(limit: int = 20, sentiment: str = "all"):
    """
    Returns recent TextAdvisoryInsight rows joined with advisor names.
Filter by sentiment: ?sentiment=all (default), bullish, or bearish.
Falls back gracefully if no insights exist.
Response: { "insights": [{id, advisor_name, timestamp, content_text,
                          target_ticker, extracted_sentiment}], "count": N }

    Args:
        limit (int): The limit.
        sentiment (str): The sentiment.

    Returns:
        Any: The response.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    sentiment = sentiment.lower()
    try:
        with get_session() as session:
            q = session.query(TextAdvisoryInsight, AdvisorBiography.advisor_name).join(
                AdvisorBiography,
                TextAdvisoryInsight.advisor_id == AdvisorBiography.id,
                isouter=True,
            )
            if sentiment == "bullish":
                q = q.filter(TextAdvisoryInsight.extracted_sentiment == "BULLISH")
            elif sentiment == "bearish":
                q = q.filter(TextAdvisoryInsight.extracted_sentiment == "BEARISH")

            rows = q.order_by(TextAdvisoryInsight.timestamp.desc()).limit(
                min(limit, 100)
            ).all()

            insights = []
            for insight, advisor_name in rows:
                insights.append({
                    "id": insight.id,
                    "advisor_name": advisor_name or "Unknown Advisor",
                    "timestamp": insight.timestamp.isoformat() if insight.timestamp else None,
                    "content_text": insight.content_text,
                    "target_ticker": insight.target_ticker,
                    "extracted_sentiment": insight.extracted_sentiment,
                })

            return {
                "insights": insights,
                "count": len(insights),
                "sentiment_filter": sentiment,
                "fetched_at": now_iso,
            }
    except Exception as e:
        log_ideas_error("ideas_feed", str(e))
        raise HTTPException(status_code=500, detail=f"Failed to fetch ideas feed: {e}")
