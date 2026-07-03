"""
Webhook listeners for real-time corporate announcements from BSE and NSE.
"""
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from datetime import datetime, timezone

from backend.database import get_session
from backend.models.db_models import NewsArticle

logger = logging.getLogger(__name__)

class WebhookResponse(BaseModel):
    status: str
    message: str

def handle_bse_corporate_announcement(payload: Dict[str, Any]) -> WebhookResponse:
    """
    Listener function to handle BSE corporate announcement webhooks.

    Args:
        payload (Dict[str, Any]): The webhook payload from BSE.

    Returns:
        WebhookResponse: A response indicating the status of the processing.
    """
    logger.info("Received BSE corporate announcement webhook payload.")
    try:
        announcement_id = payload.get("id", "unknown_bse_id")
        company_name = payload.get("company_name", "Unknown Company")

        logger.info(f"Processing BSE announcement {announcement_id} for {company_name}")

        subject = payload.get("subject", f"BSE Corporate Announcement: {company_name}")
        url = payload.get("url", f"https://www.bseindia.com/xml-data/corpfiling/AttachLive/{announcement_id}")

        with get_session() as session:
            existing = session.query(NewsArticle).filter_by(article_url=url).first()
            if not existing:
                article = NewsArticle(
                    source="bse",
                    ticker=payload.get("symbol"),
                    headline=subject,
                    body_text=payload.get("details", subject),
                    article_url=url,
                    published_at=datetime.now(timezone.utc)
                )
                session.add(article)
                session.commit()

        return WebhookResponse(status="success", message="BSE announcement processed successfully")
    except Exception as e:
        logger.error(f"Error processing BSE webhook: {e}")
        return WebhookResponse(status="error", message=str(e))


def handle_nse_corporate_announcement(payload: Dict[str, Any]) -> WebhookResponse:
    """
    Listener function to handle NSE corporate announcement webhooks.

    Args:
        payload (Dict[str, Any]): The webhook payload from NSE.

    Returns:
        WebhookResponse: A response indicating the status of the processing.
    """
    logger.info("Received NSE corporate announcement webhook payload.")
    try:
        announcement_id = payload.get("id", "unknown_nse_id")
        symbol = payload.get("symbol", "Unknown Symbol")

        logger.info(f"Processing NSE announcement {announcement_id} for {symbol}")

        subject = payload.get("subject", f"NSE Corporate Announcement: {symbol}")
        url = payload.get("url", f"https://www.nseindia.com/corporate/{announcement_id}")

        with get_session() as session:
            existing = session.query(NewsArticle).filter_by(article_url=url).first()
            if not existing:
                article = NewsArticle(
                    source="nse",
                    ticker=symbol,
                    headline=subject,
                    body_text=payload.get("details", subject),
                    article_url=url,
                    published_at=datetime.now(timezone.utc)
                )
                session.add(article)
                session.commit()

        return WebhookResponse(status="success", message="NSE announcement processed successfully")
    except Exception as e:
        logger.error(f"Error processing NSE webhook: {e}")
        return WebhookResponse(status="error", message=str(e))
