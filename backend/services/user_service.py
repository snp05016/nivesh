import time
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import logging
import json

from helpers import (
    get_session, User, Portfolio, AnalysisHistory, DeviceToken, AdvisorInsight,
    _to_ns, _yf_price, _yf_fetch_info, _get_asm_gsm_lists
)
from database import MarketErrorLog
from services.harvester_reformatter import strip_emoji
from services.notifications_inbox import create_notification
from services.preferences import push_allowed
from services.sebi_registry import registration_for_channel
from services import entitlement_service

_watchlist_price_cache: dict = {}
_WATCHLIST_CACHE_TTL = 120

def get_all_users() -> list:
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

def add_to_watchlist(user_id: int, ticker: str, company_name: str) -> dict:
    ticker = ticker.upper()
    with get_session() as session:
        existing = session.query(Portfolio).filter_by(
            user_id=user_id, ticker=ticker, group_name="watchlist"
        ).first()
        if existing:
            return {"already_exists": True, "message": "Already in watchlist"}
        count = session.query(Portfolio).filter_by(user_id=user_id, group_name="watchlist").count()
    # Outside the session: get_effective_tier may create the subscription row.
    entitlement_service.enforce_quota(user_id, "watchlist_size", count)
    with get_session() as session:
        new_item = Portfolio(
            user_id=user_id,
            ticker=ticker,
            company_name=company_name,
            shares=0,
            buy_price=0,
            group_name="watchlist",
        )
        session.add(new_item)
        session.commit()
    _watchlist_price_cache.pop(user_id, None)
    return {"success": True, "ticker": ticker}

def remove_from_watchlist(user_id: int, ticker: str) -> dict:
    ticker = ticker.upper()
    with get_session() as session:
        item = session.query(Portfolio).filter_by(
            user_id=user_id, ticker=ticker, group_name="watchlist"
        ).first()
        if not item:
            return {"success": False, "message": "Not in watchlist"}
        session.delete(item)
        session.commit()
    _watchlist_price_cache.pop(user_id, None)
    return {"success": True}

def get_watchlist(user_id: int) -> Optional[dict]:
    now = time.time()
    cached = _watchlist_price_cache.get(user_id)
    if cached and (now - cached["ts"]) < _WATCHLIST_CACHE_TTL:
        return {"watchlist": cached["data"]}

    with get_session() as session:
        user = session.get(User, user_id)
        if not user:
            return None
        items = session.query(Portfolio).filter_by(
            user_id=user_id, group_name="watchlist"
        ).all()
        items_data = [(h.ticker, h.company_name) for h in items]

    try:
        asm_gsm_data = _get_asm_gsm_lists()
    except Exception as e:
        logging.warning(f"Caught exception: {e}")
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
        except Exception as e:
            logging.error(f"Error occurred: {e}", exc_info=True)
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
        except Exception as e:
            logging.warning(f"Caught exception: {e}")
            asm_gsm_status = "UNKNOWN"

        result.append({
            "ticker": ticker,
            "company_name": company_name,
            "exchange": "NSE",
            "current_price": current_price or 0.0,  # numeric for shipped apps; check price_status
            "price_status": "live" if current_price else "unavailable",
            "day_change_pct": day_change_pct,
            "last_signal": last_signal,
            "last_signal_date": last_signal_date,
            "asm_gsm_status": asm_gsm_status,
        })

    _watchlist_price_cache[user_id] = {"data": result, "ts": now}
    return {"watchlist": result}


def _deliver_apns(user_id: int, payload: dict) -> bool:
    if not push_allowed(user_id):
        return False
    try:
        with get_session() as session:
            tokens = session.query(DeviceToken).filter_by(user_id=user_id).all()
            if not tokens:
                return False
            for dt in tokens:
                logging.info(f"[APNs] Would deliver to {dt.platform} token {dt.device_token[:12]}... : {payload.get('title', '')}")
        return True
    except Exception as e:
        logging.info(f"[APNs] Delivery failed for user {user_id}: {e}")
        return False

def test_notification(user_id: int, ticker: str, exchange: str) -> dict:
    ns_ticker = _to_ns(ticker)
    info = _yf_fetch_info(ns_ticker)
    price = info.get("currentPrice") or info.get("regularMarketPrice") or 0.0

    signal_str = "UNKNOWN"
    confidence = None
    with get_session() as session:
        row = session.query(AnalysisHistory).filter(
            AnalysisHistory.ticker == ticker.upper()
        ).order_by(AnalysisHistory.created_at.desc()).first()
        if row:
            signal_str = row.signal
            confidence = row.confidence_pct

    conf_str = f" | Confidence: {int(confidence)}%" if confidence else ""
    price_str = f"₹{price:,.2f}" if price else "Price unavailable"

    payload = {
        "title": f"{ticker.upper()} — {signal_str}",
        "body": f"{price_str}{conf_str}",
        "data": {"ticker": ticker.upper(), "exchange": exchange},
    }

    _deliver_apns(user_id, payload)
    return payload

def push_morning_summary(user_id: int) -> Optional[dict]:
    with get_session() as session:
        user = session.get(User, user_id)
        if not user:
            return None
        display_name = user.display_name

    try:
        from routers.analysis import morning_summary_endpoint
        summary_data = morning_summary_endpoint(user_id)
    except Exception as e:
        logging.warning(f"Caught exception: {e}")
        summary_data = {"summary": "Check your portfolio today.", "mood": "cautious", "priority_items": []}

    mood = summary_data.get("mood", "cautious")
    mood_label = "UP" if mood == "positive" else "DOWN" if mood == "negative" else "NEUTRAL"

    priority_items = summary_data.get("priority_items", []) or []
    first_action = ""
    if priority_items:
        item = priority_items[0]
        first_action = f"\n- {strip_emoji(item.get('ticker', ''))}: {strip_emoji(item.get('action', ''))}"

    body = f"Good morning, {display_name}! [{mood_label}] {strip_emoji(summary_data.get('summary', '')[:80])}{first_action}"

    payload = {
        "title": f"Daily Market Brief — {mood.upper()}",
        "body": body,
        "data": {"type": "morning_summary"},
    }

    create_notification(user_id, "morning_brief", payload["title"], body)
    _deliver_apns(user_id, payload)
    return {"success": True, "payload": payload}


def get_experts_service() -> dict:
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
            # Registration only from the SEBI registry, never assumed.
            reg = registration_for_channel(d["channel_id"], name)
            experts.append({
                "id": d["channel_id"] or name.replace(" ", "_"),
                "name": name,
                "sebi_reg_id": reg,
                "years_experience": 0,
                "strategy": f"{dominant.title()} Analyst",
                "focus_tags": focus,
                "post_count": d["post_count"],
                "is_verified": reg is not None,
                "bio": f"YouTube channel covering {', '.join(focus[:3])}. "
                       f"{d['post_count']} tracked calls in Nivesh.",
            })
        experts.sort(key=lambda e: e["post_count"], reverse=True)
        return {"experts": experts[:20], "fetched_at": now_iso}
    except Exception as e:
        logging.info(f"[EXPERTS] {e}")
        return {"experts": [], "fetched_at": now_iso}


def get_expert_posts_service(limit: int = 30) -> dict:
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
        logging.info(f"[EXPERT-POSTS] {e}")
        return {"posts": [], "fetched_at": now_iso}


def fetch_error_telemetry() -> dict:
    with get_session() as db:
        logs = db.query(MarketErrorLog).order_by(MarketErrorLog.timestamp.desc()).limit(100).all()
        results = []
        for log in logs:
            try:
                payload = json.loads(log.error_message)
                results.append({
                    "error_type": payload.get("classification", log.component),
                    "endpoint": payload.get("telemetry", {}).get("request_route", ""),
                    "timestamp": log.timestamp.isoformat() if log.timestamp else payload.get("timestamp"),
                    "message": payload.get("exception", {}).get("message", "Unknown"),
                    "stack_summary": payload.get("exception", {}).get("cleaned_traceback", [])
                })
            except Exception as e:
                logging.warning(f"Caught exception: {e}")
                results.append({
                    "error_type": log.component,
                    "endpoint": "",
                    "timestamp": log.timestamp.isoformat() if log.timestamp else "",
                    "message": log.error_message,
                    "stack_summary": []
                })
        return {"errors": results}
