"""Trade journal routes: /trade-journal CRUD and stats.

Split out of routers/portfolio.py (ARCH-14); paths, handler names and tags are unchanged.
"""
import logging
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Header
from core.security import require_user_match, assert_same_user
from helpers import (
    get_session, User, TradeJournal, TradeJournalAddRequest,
    TradeJournalUpdateRequest, _extract_json_from_text, require_auth,
)
import os
from services.llm_utils import deepseek_chat as _deepseek_chat
from services.kyc_consent_service import AI_PROCESSING_CONSENT, has_active_consent
from services import llm_budget
from services.portfolio_service import compute_trade_journal_stats

router = APIRouter(tags=["Portfolio"])


# ---------------------------------------------------------------------------
# 18. POST /trade-journal
# ---------------------------------------------------------------------------
@router.post("/trade-journal")
def trade_journal_add_endpoint(req: TradeJournalAddRequest, token_user: int = Depends(require_auth)):
    assert_same_user(req.user_id, token_user)
    action = req.action.upper()
    if action not in ("BUY", "SELL", "HOLD", "WATCH"):
        raise HTTPException(status_code=400, detail="action must be BUY, SELL, HOLD, or WATCH")
    if req.price_at_time <= 0:
        raise HTTPException(status_code=400, detail="price_at_time must be > 0")
    ticker = req.ticker.upper().strip()
    try:
        with get_session() as session:
            entry = TradeJournal(
                user_id=req.user_id,
                ticker=ticker,
                action=action,
                price_at_time=req.price_at_time,
                reason_text=req.reason_text.strip(),
                outcome_text=req.outcome_text.strip() if req.outcome_text else None,
            )
            entry.company_name = req.company_name
            entry.mood = req.mood
            session.add(entry)
            session.commit()
            session.refresh(entry)
            entry_id = entry.id
        return {"success": True, "entry_id": entry_id, "ticker": ticker, "action": action}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 19. GET /trade-journal/{user_id}
# ---------------------------------------------------------------------------
@router.get("/trade-journal/{user_id}")
def trade_journal_get_endpoint(user_id: int, _caller: int = Depends(require_user_match)):
    try:
        with get_session() as session:
            user = session.get(User, user_id)
            if not user:
                raise HTTPException(status_code=404, detail=f"User {user_id} not found")
            entries = session.query(TradeJournal).filter_by(
                user_id=user_id
            ).order_by(TradeJournal.created_at.desc()).all()
            result = []
            for e in entries:
                row = {
                    "id": e.id,
                    "ticker": e.ticker,
                    "action": e.action,
                    "price_at_time": e.price_at_time,
                    "reason_text": e.reason_text,
                    "outcome_text": e.outcome_text,
                    "created_at": e.created_at.strftime("%Y-%m-%d %H:%M") if e.created_at else "",
                }
                # Gracefully include new columns if they exist post-migration
                try:
                    row["company_name"] = getattr(e, "company_name", None)
                except Exception as e:
                    import logging
                    logging.warning(f"Caught exception: {e}")
                    row["company_name"] = None
                try:
                    row["mood"] = getattr(e, "mood", None)
                except Exception as e:
                    import logging
                    logging.warning(f"Caught exception: {e}")
                    row["mood"] = None
                try:
                    upd = getattr(e, "updated_at", None)
                    row["updated_at"] = upd.strftime("%Y-%m-%d %H:%M") if upd else None
                except Exception as e:
                    import logging
                    logging.warning(f"Caught exception: {e}")
                    row["updated_at"] = None
                result.append(row)
        return {"user_id": user_id, "entries": result, "total": len(result)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 20. PUT /trade-journal/{entry_id}
# ---------------------------------------------------------------------------
@router.put("/trade-journal/{entry_id}")
def trade_journal_update_endpoint(entry_id: int, req: TradeJournalUpdateRequest, user_id: int, _caller: int = Depends(require_user_match)):
    """Update outcome_text and mood on a trade journal entry. user_id passed as query param."""
    try:
        with get_session() as session:
            entry = session.query(TradeJournal).filter_by(id=entry_id).first()
            if not entry:
                raise HTTPException(status_code=404, detail="Entry not found")
            if entry.user_id != user_id:
                raise HTTPException(status_code=403, detail="Not authorized to edit this entry")
            entry.outcome_text = req.outcome_text.strip()
            entry.mood = req.mood
            entry.updated_at = datetime.now(timezone.utc)
            session.commit()
            session.refresh(entry)
            result = {
                "id": entry.id,
                "ticker": entry.ticker,
                "action": entry.action,
                "price_at_time": entry.price_at_time,
                "reason_text": entry.reason_text,
                "outcome_text": entry.outcome_text,
                "created_at": entry.created_at.strftime("%Y-%m-%d %H:%M") if entry.created_at else "",
            }
            result["company_name"] = getattr(entry, "company_name", None)
            result["mood"] = getattr(entry, "mood", None)
            upd = getattr(entry, "updated_at", None)
            result["updated_at"] = upd.strftime("%Y-%m-%d %H:%M") if upd else None
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 21. DELETE /trade-journal/{entry_id}
# ---------------------------------------------------------------------------
@router.delete("/trade-journal/{entry_id}")
def trade_journal_delete_endpoint(entry_id: int, user_id: int, _caller: int = Depends(require_user_match)):
    """Delete a trade journal entry. user_id passed as query param."""
    try:
        with get_session() as session:
            entry = session.query(TradeJournal).filter_by(id=entry_id).first()
            if not entry:
                raise HTTPException(status_code=404, detail="Entry not found")
            if entry.user_id != user_id:
                raise HTTPException(status_code=403, detail="Not authorized to delete this entry")
            session.delete(entry)
            session.commit()
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# 22. GET /trade-journal/{user_id}/stats
# ---------------------------------------------------------------------------
@router.get("/trade-journal/{user_id}/stats")
def trade_journal_stats_endpoint(user_id: int, _caller: int = Depends(require_user_match)):
    """
    Compute analytics over all journal entries for a user. The bearer must be
    the path user (GH-630: 401 without a token, 403 for another user's id).

    Args:
        user_id (int): The user_id.
        _caller (int): The authenticated user_id (equal to user_id).

    Returns:
        Any: The response.
    """
    try:
        with get_session() as session:
            user = session.get(User, user_id)
            if not user:
                raise HTTPException(status_code=404, detail=f"User {user_id} not found")
            entries = session.query(TradeJournal).filter_by(user_id=user_id).all()
            entries_data = []
            for e in entries:
                entries_data.append({
                    "ticker": e.ticker,
                    "action": e.action,
                    "reason_text": e.reason_text or "",
                    "outcome_text": (e.outcome_text or "").lower(),
                })

        stats = compute_trade_journal_stats(entries_data)
        total_entries = stats["total_entries"]

        # Trade journal pattern detection → DeepSeek V4 Flash (Tier 1 bulk task)
        patterns = []
        try:
            all_reasons = " | ".join(e["reason_text"] for e in entries_data if e["reason_text"])
            if all_reasons and os.getenv("DEEPSEEK_API_KEY") and has_active_consent(user_id, AI_PROCESSING_CONSENT):
                llm_budget.guard(user_id, "trade_journal_stats")  # over budget -> no patterns
                prompt = (
                    f'Find 2 patterns in these trade journal reasons: {all_reasons[:2000]}. '
                    'Return JSON: [{"pattern": str}]'
                )
                raw_text = _deepseek_chat(
                    [{"role": "user", "content": prompt}],
                    max_tokens=150,
                    log_endpoint="trade_journal_stats",
                )
                raw = _extract_json_from_text(raw_text)
                patterns = json.loads(raw)
                if not isinstance(patterns, list):
                    patterns = []
        except Exception as _pe:
            logging.info(f"[TJ-STATS] Pattern AI call failed: {_pe}")
            patterns = []

        return {
            "user_id": user_id,
            **stats,
            "patterns": patterns,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")
