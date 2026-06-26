"""DB-backed cache for YouTube summaries using the YouTubeVideoSummary ORM model."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from database import get_session

logger = logging.getLogger(__name__)

# Maximum age in days before a cached summary is considered stale
_CACHE_TTL_DAYS = 7


class YouTubeSummaryCache:
    """Read/write YouTube video summaries to the DB using get_session()."""

    def get(self, video_id: str, transcript_hash: str) -> Optional[dict]:
        """Return cached summary dict if it exists and the transcript hash matches."""
        try:
            from models.db_models import YouTubeVideoSummary  # deferred import — model may not exist yet
        except ImportError:
            logger.debug("YouTubeVideoSummary model not yet available; cache miss")
            return None

        try:
            with get_session() as session:
                row = (
                    session.query(YouTubeVideoSummary)
                    .filter(YouTubeVideoSummary.video_id == video_id)
                    .first()
                )
                if row is None:
                    return None

                if str(row.transcript_hash) != transcript_hash:
                    logger.debug("Cache stale (hash mismatch) for %s", video_id)
                    return None

                age_days = (
                    datetime.now(timezone.utc) - row.updated_at.replace(tzinfo=timezone.utc)
                ).days
                if age_days >= _CACHE_TTL_DAYS:
                    logger.debug("Cache expired (%d days) for %s", age_days, video_id)
                    return None

                return json.loads(str(row.summary_json))
        except Exception as exc:
            logger.warning("YouTubeSummaryCache.get failed for %s: %s", video_id, exc)
            return None

    def set(self, video_id: str, data: dict, transcript_hash: str) -> None:
        """Upsert a summary record for video_id."""
        try:
            from models.db_models import YouTubeVideoSummary
        except ImportError:
            logger.debug("YouTubeVideoSummary model not yet available; cache write skipped")
            return

        try:
            summary_json = json.dumps(data, ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            logger.warning("Cannot serialise summary for %s: %s", video_id, exc)
            return

        try:
            with get_session() as session:
                row = (
                    session.query(YouTubeVideoSummary)
                    .filter(YouTubeVideoSummary.video_id == video_id)
                    .first()
                )
                now = datetime.now(timezone.utc)
                if row is None:
                    row = YouTubeVideoSummary(
                        video_id=video_id,
                        transcript_hash=transcript_hash,
                        summary_json=summary_json,
                        created_at=now,
                        updated_at=now,
                    )
                    session.add(row)
                else:
                    setattr(row, "transcript_hash", transcript_hash)
                    setattr(row, "summary_json", summary_json)
                    setattr(row, "updated_at", now)
                session.commit()
                logger.debug("Cached summary for video_id=%s", video_id)
        except Exception as exc:
            logger.warning("YouTubeSummaryCache.set failed for %s: %s", video_id, exc)
