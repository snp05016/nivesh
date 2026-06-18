from fastapi import APIRouter, HTTPException, Header, Depends
from datetime import datetime, timezone
import time
from pydantic import BaseModel
from typing import Optional

from helpers import (
    get_session, verify_access_token, User, Portfolio, AnalysisHistory,
    DeviceToken, AdvisorInsight, _to_ns, _yf_price, _yf_fetch_info,
    _check_rate_limit, WatchlistAddRequest, WatchlistRemoveRequest,
    _get_asm_gsm_lists, upsert_device_token,
)

router = APIRouter(tags=["User"])

# Watchlist cache
_watchlist_price_cache: dict = {}
_WATCHLIST_CACHE_TTL = 120


class DeviceTokenRegisterRequest(BaseModel):
    user_id: int
    device_token: str
    platform: str = "ios"


class TestNotificationRequest(BaseModel):
    user_id: int
    ticker: str
    exchange: str = "NSE"


class MorningSummaryPushRequest(BaseModel):
    user_id: int


def _deliver_apns(user_id: int, payload: dict) -> bool:
    try:
        with get_session() as session:
            tokens = session.query(DeviceToken).filter_by(user_id=user_id).all()
            if not tokens:
                return False
            for dt in tokens:
                print(f"[APNs] Would deliver to {dt.platform} token {dt.device_token[:12]}... : {payload.get('title', '')}")
        return True
    except Exception as e:
        print(f"[APNs] Delivery failed for user {user_id}: {e}")
        return False


@router.get("/users")
def list_users(authorization: str = Header(None)):
    from core.security import require_admin
    require_admin(authorization)
    with get_session() as session:
        users = session.query(User).order_by(User.id).all()
        return [
            {
                "id": u.id,
                "username": u.username,
                "display_name": u.display_name,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in users
        ]


@router.post("/watchlist/add")
def watchlist_add_endpoint(req: WatchlistAddRequest, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user != req.user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        ticker = req.ticker.upper()
        with get_session() as session:
            existing = session.query(Portfolio).filter_by(
                user_id=req.user_id, ticker=ticker, group_name="watchlist"
            ).first()
            if existing:
                return {"already_exists": True, "message": "Already in watchlist"}
            new_item = Portfolio(
                user_id=req.user_id,
                ticker=ticker,
                company_name=req.company_name,
                shares=0,
                buy_price=0,
                group_name="watchlist",
            )
            session.add(new_item)
            session.commit()
        _watchlist_price_cache.pop(req.user_id, None)
        return {"success": True, "ticker": ticker}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/watchlist/remove")
def watchlist_remove_endpoint(req: WatchlistRemoveRequest, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user != req.user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        ticker = req.ticker.upper()
        with get_session() as session:
            item = session.query(Portfolio).filter_by(
                user_id=req.user_id, ticker=ticker, group_name="watchlist"
            ).first()
            if not item:
                return {"success": False, "message": "Not in watchlist"}
            session.delete(item)
            session.commit()
        _watchlist_price_cache.pop(req.user_id, None)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/watchlist/{user_id}")
def watchlist_get_endpoint(user_id: int, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user != user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        now = time.time()
        cached = _watchlist_price_cache.get(user_id)
        if cached and (now - cached["ts"]) < _WATCHLIST_CACHE_TTL:
            return {"watchlist": cached["data"]}

        with get_session() as session:
            user = session.get(User, user_id)
            if not user:
                raise HTTPException(status_code=404, detail=f"User {user_id} not found")
            items = session.query(Portfolio).filter_by(
                user_id=user_id, group_name="watchlist"
            ).all()
            items_data = [(h.ticker, h.company_name) for h in items]

        try:
            asm_gsm_data = _get_asm_gsm_lists()
        except Exception:
            asm_gsm_data = {"ASM": set(), "GSM": set()}

        result = []
        for ticker, company_name in items_data:
            ns = _to_ns(ticker)
            current_price, prev_close = _yf_price(ns)
            day_change_pct = 0.0
            if current_price and prev_close and prev_close > 0:
                day_change_pct = round((current_price - prev_close) / prev_close * 100, 2)

            last_signal = None
            last_signal_date = None
            try:
                with get_session() as _sess:
                    sig_row = _sess.query(AnalysisHistory).filter(
                        AnalysisHistory.ticker == ticker
                    ).order_by(AnalysisHistory.created_at.desc()).first()
                    if sig_row:
                        last_signal = sig_row.signal
                        last_signal_date = sig_row.analysis_date
            except Exception:
                pass

            asm_gsm_status = "UNKNOWN"
            try:
                t_base = ticker.upper().split(".")[0]
                if t_base in asm_gsm_data.get("GSM", set()):
                    asm_gsm_status = "GSM"
                elif t_base in asm_gsm_data.get("ASM", set()):
                    asm_gsm_status = "ASM"
                elif asm_gsm_data.get("ASM") or asm_gsm_data.get("GSM"):
                    asm_gsm_status = "CLEAN"
            except Exception:
                asm_gsm_status = "UNKNOWN"

            result.append({
                "ticker": ticker,
                "company_name": company_name,
                "exchange": "NSE",
                "current_price": current_price or 0.0,
                "day_change_pct": day_change_pct,
                "last_signal": last_signal,
                "last_signal_date": last_signal_date,
                "asm_gsm_status": asm_gsm_status,
            })

        _watchlist_price_cache[user_id] = {"data": result, "ts": now}
        return {"watchlist": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/notifications/register-device")
def notifications_register_device(req: DeviceTokenRegisterRequest):
    """Register or update a device token. Delegates to shared upsert helper."""
    try:
        return upsert_device_token(req.user_id, req.device_token, req.platform or "ios")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/notifications/test")
def notifications_test(req: TestNotificationRequest):
    try:
        ns_ticker = _to_ns(req.ticker)
        info = _yf_fetch_info(ns_ticker)
        price = info.get("currentPrice") or info.get("regularMarketPrice") or 0.0

        signal_str = "UNKNOWN"
        confidence = None
        with get_session() as session:
            row = session.query(AnalysisHistory).filter(
                AnalysisHistory.ticker == req.ticker.upper()
            ).order_by(AnalysisHistory.created_at.desc()).first()
            if row:
                signal_str = row.signal
                confidence = row.confidence_pct

        conf_str = f" | Confidence: {int(confidence)}%" if confidence else ""
        price_str = f"₹{price:,.2f}" if price else "Price unavailable"

        payload = {
            "title": f"{req.ticker.upper()} — {signal_str}",
            "body": f"{price_str}{conf_str}",
            "data": {"ticker": req.ticker.upper(), "exchange": req.exchange},
        }

        _deliver_apns(req.user_id, payload)

        return payload
    except Exception as e:
        return {
            "title": f"{req.ticker.upper()} — Analysis",
            "body": "Tap to view latest analysis",
            "data": {"ticker": req.ticker.upper(), "exchange": req.exchange},
        }


@router.post("/notifications/morning-summary-push")
def notifications_morning_summary_push(req: MorningSummaryPushRequest):
    try:
        with get_session() as session:
            user = session.get(User, req.user_id)
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            display_name = user.display_name

        try:
            from routers.analysis import morning_summary_endpoint
            summary_data = morning_summary_endpoint(req.user_id)
        except Exception:
            summary_data = {"summary": "Check your portfolio today.", "mood": "cautious", "priority_items": []}

        mood = summary_data.get("mood", "cautious")
        mood_emoji = "📈" if mood == "positive" else "📉" if mood == "negative" else "📊"

        priority_items = summary_data.get("priority_items", []) or []
        first_action = ""
        if priority_items:
            item = priority_items[0]
            first_action = f"\n• {item.get('ticker', '')}: {item.get('action', '')}"

        body = f"Good morning, {display_name}! {mood_emoji} {summary_data.get('summary', '')[:80]}{first_action}"

        payload = {
            "title": f"☀️ Daily Market Brief — {mood.upper()}",
            "body": body,
            "data": {"type": "morning_summary"},
        }

        _deliver_apns(req.user_id, payload)
        return {"success": True, "payload": payload}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/v1/experts")
def get_experts():
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        with get_session() as session:
            rows = session.query(AdvisorInsight).order_by(
                AdvisorInsight.published_at.desc()
            ).limit(500).all()

        advisor_map: dict = {}
        for r in rows:
            name = r.advisor_name
            if name not in advisor_map:
                advisor_map[name] = {"channel_id": r.channel_id, "post_count": 0,
                                     "tickers": set(), "stances": [], "latest_at": r.published_at}
            d = advisor_map[name]
            d["post_count"] += 1
            d["tickers"].add(r.ticker)
            d["stances"].append(r.stance)
            if r.published_at > d["latest_at"]:
                d["latest_at"] = r.published_at

        experts = []
        for name, d in advisor_map.items():
            sc = {s: d["stances"].count(s) for s in set(d["stances"])}
            dominant = max(sc, key=sc.get) if sc else "Neutral"
            focus = list(d["tickers"])[:4]
            experts.append({
                "id": d["channel_id"] or name.replace(" ", "_"),
                "name": name,
                "sebi_reg_id": None,
                "years_experience": 0,
                "strategy": f"{dominant.title()} Analyst",
                "focus_tags": focus,
                "post_count": d["post_count"],
                "is_verified": True,
                "bio": f"Financial analyst covering {', '.join(focus[:3])}. "
                       f"{d['post_count']} tracked calls in Nivesh.",
            })
        experts.sort(key=lambda e: e["post_count"], reverse=True)
        return {"experts": experts[:20], "fetched_at": now_iso}
    except Exception as e:
        print(f"[EXPERTS] {e}")
        return {"experts": [], "fetched_at": now_iso}


@router.get("/api/v1/expert-posts")
def get_expert_posts(limit: int = 30):
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        with get_session() as session:
            rows = session.query(AdvisorInsight).order_by(
                AdvisorInsight.published_at.desc()
            ).limit(limit).all()

        posts = []
        for r in rows:
            content = f"{r.ticker}: [{r.stance.upper()}] {r.catalyst_summary}" if r.ticker else f"[{r.stance.upper()}] {r.catalyst_summary}"
            posts.append({
                "id": f"{r.video_id}_{r.ticker}",
                "expert_id": r.channel_id or r.advisor_name.replace(" ", "_"),
                "expert_name": r.advisor_name,
                "content": content,
                "ticker": r.ticker or None,
                "chart_image_url": None,
                "published_at": r.published_at.isoformat() + "Z",
                "like_count": r.view_count or 0,
                "is_premium": False,
                "video_url": r.video_url,
                "video_title": r.video_title,
                "confidence": r.confidence,
                "stance": r.stance,
            })
        return {"posts": posts, "fetched_at": now_iso}
    except Exception as e:
        print(f"[EXPERT-POSTS] {e}")
        return {"posts": [], "fetched_at": now_iso}

@router.get("/api/v1/admin/error-telemetry")
def get_error_telemetry(current_user: User = Depends(verify_access_token)):
    """Admin endpoint to get recent error logs."""
    from database import get_session, MarketErrorLog, is_admin
    import json
    from fastapi import HTTPException

    
    with get_session() as db:
        if not is_admin(db, current_user.id):
            raise HTTPException(status_code=403, detail="Admin access required")
            
        logs = db.query(MarketErrorLog).order_by(MarketErrorLog.timestamp.desc()).limit(100).all()
        results = []
        for log in logs:
            try:
                # payload_json might contain the full JSON telemetry
                payload = json.loads(log.error_message)
                results.append({
                    "error_type": payload.get("classification", log.component),
                    "endpoint": payload.get("telemetry", {}).get("request_route", ""),
                    "timestamp": log.timestamp.isoformat() if log.timestamp else payload.get("timestamp"),
                    "message": payload.get("exception", {}).get("message", "Unknown"),
                    "stack_summary": payload.get("exception", {}).get("cleaned_traceback", [])
                })
            except Exception:
                # fallback for plain string errors
                results.append({
                    "error_type": log.component,
                    "endpoint": "",
                    "timestamp": log.timestamp.isoformat() if log.timestamp else "",
                    "message": log.error_message,
                    "stack_summary": []
                })
        return {"errors": results}
