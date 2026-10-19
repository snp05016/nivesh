"""Admin dashboard payloads (moved out of main.py, REL-15).

The routes in routers/admin_dashboard.py check admin auth and call these.
State is read through the core.dashboard_state module so it is always live.
"""
import json
import logging
import os
import time
from collections import Counter
from datetime import datetime, timezone

from sqlalchemy.orm import undefer

import core.dashboard_state as _ds
from database import get_session
from helpers import _quick_info_cache
from models.db_models import (
    AnalysisHistory, DeviceToken, NetWorthLedger, NewsArticle, Portfolio,
    PortfolioValuationHistory, PriceTarget, SignalEvent, TradeJournal, User, YouTubeVideo,
)
from services.ai_engine_monitor import build_ai_engine_monitor


def build_dashboard_data() -> dict:
    """System uptime, active jobs, token stats, cache health and DB entity counts."""
    uptime = (datetime.now(timezone.utc) - _ds.SERVER_START).total_seconds()
    
    # Fetch historical analyses and stats from DB
    history = []
    db_stats = {}
    try:
        with get_session() as session:
            # Summary rows only; raw_output/full_json come from /dashboard-data/analysis/{id} (GH-689).
            rows = session.query(AnalysisHistory).order_by(AnalysisHistory.created_at.desc()).limit(50).all()
            for r in rows:
                history.append({
                    "id": r.id,
                    "ts": r.created_at.isoformat(),
                    "ticker": r.ticker,
                    "analysis_date": r.analysis_date,
                    "signal": r.signal,
                    "confidence": r.confidence_pct,
                    "was_correct": r.was_correct,
                    "user_id": r.user_id,
                })
            db_stats = {
                "users": session.query(User).count(),
                "holdings": session.query(Portfolio).count(),
                "analyses": session.query(AnalysisHistory).count(),
                "signal_events": session.query(SignalEvent).count(),
                "trade_journals": session.query(TradeJournal).count(),
                "news_articles": session.query(NewsArticle).count(),
                "youtube_videos": session.query(YouTubeVideo).count(),
            }
            # Fetch latest news and videos
            latest_news = []
            for n in session.query(NewsArticle).order_by(NewsArticle.published_at.desc()).limit(10).all():
                latest_news.append({
                    "headline": n.headline,
                    "ticker": n.ticker,
                    "ts": n.published_at.isoformat(),
                    "sentiment": n.sentiment,
                    "red_flag": n.is_red_flag
                })
            latest_videos = []
            for v in session.query(YouTubeVideo).order_by(YouTubeVideo.published_at.desc()).limit(10).all():
                latest_videos.append({
                    "title": v.title,
                    "channel": v.channel_name,
                    "ts": v.published_at.isoformat(),
                    "ticker": v.matched_ticker
                })
    except Exception as e:
        logging.info(f"Error fetching history for dashboard: {e}")

    try:
        import services.scraper as scr
        scraper_cache = {}
        raw_items = None
        try:
            # TTLLRUCache or similar has no items() — convert to dict first
            raw_items = list(scr._CACHE.items())
        except (AttributeError, TypeError):
            # fallback: try dict access
            try:
                raw_items = list(dict(scr._CACHE).items())
            except Exception as _e:
                raw_items = {}
        if raw_items:
            for k, v in raw_items:
                try:
                    # v may be a (value, timestamp) tuple or a {"ts": ...} dict
                    if isinstance(v, dict):
                        ts = v.get("ts", 0)
                    elif isinstance(v, (tuple, list)) and len(v) >= 2:
                        ts = v[1]
                    else:
                        ts = 0
                    scraper_cache[str(k)] = {"age_s": round(time.time() - float(ts))}
                except Exception as _e:
                    continue
    except Exception as _e:
        scraper_cache = {}

    cache_stats = {
        "quick_info": len(_quick_info_cache),  # helpers' live L1 cache the routers fill
        "scraper": scraper_cache
    }

    with _ds._dash_lock:
        active = list(_ds._active_analyses.values())
        completed = list(_ds._completed_analyses)
        reqs = list(_ds._request_log)
        tok = {
            "total_input":       _ds._token_stats["total_input"],
            "total_output":      _ds._token_stats["total_output"],
            "total_cache_read":  _ds._token_stats["total_cache_read"],
            "total_cache_write": _ds._token_stats["total_cache_write"],
            "total_calls":       _ds._token_stats["total_calls"],
            "recent":            list(_ds._token_stats["recent"]),
        }

    # Separate Claude vs DeepSeek stats from token_log.jsonl
    ai_health = {
        "anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
        "deepseek": bool(os.getenv("DEEPSEEK_API_KEY")),
        "google": bool(os.getenv("GOOGLE_API_KEY")),
    }
    # Per-vendor spend from token_log.jsonl (one reader: core.dashboard_state, LLM-09).
    # Lines with no known model are counted under "unknown" and never priced.
    stats_by_vendor = _ds.token_usage_summary()["by_vendor"]
    claude_stats = stats_by_vendor["claude"]
    deepseek_stats = stats_by_vendor["deepseek"]
    unknown_stats = stats_by_vendor["unknown"]

    # Per-feature error extraction from request log
    feature_routes = {
        "News Feed":            ["/api/v1/home-feed"],
        "Tech Momentum":        ["/api/v1/market/dashboard-pulse"],
        "Screener":             ["/screener"],
        "Alerts":               ["/alerts/add", "/alerts/"],
        "Portfolio Calendar":   ["/api/v1/portfolio/valuation-history"],
        "Earnings Dashboard":   ["/earnings-calendar", "/api/v1/earnings/"],
        "Analysis Engine":      ["/analyze"],
        "YouTube Harvester":    ["/api/v1/admin/harvest-youtube"],
        "Advisor Harvester":    ["/api/v1/admin/harvest-advisors"],
        "Macro Impact":         ["/api/v1/macro-impact"],
        "Sector Performance":   ["/sector-performance"],
    }
    feature_errors = {}
    persisted_harvests = _ds.persisted_harvest_status()  # scheduler runs from any worker (SILENT-13)
    with _ds._dash_lock:
        all_reqs = list(_ds._request_log)
        current_harvests = {k: v.copy() for k, v in _ds._harvest_status.items()}
        h_logs = list(_ds._dash_logs)
    current_harvests.update(persisted_harvests)

    for feature, prefixes in feature_routes.items():
        errs = []
        for r in all_reqs:
            path = r.get("path", "")
            if any(path.startswith(p) or path == p for p in prefixes):
                if r.get("status", 200) >= 400:
                    errs.append({
                        "ts": r.get("ts"),
                        "path": path,
                        "status": r.get("status"),
                        "duration_ms": r.get("duration_ms"),
                    })
        feature_errors[feature] = errs[:5]

    # ── v2 engine: merge DB-backed active jobs ───────────────────────────
    db_active_jobs = {}
    try:
        import database
        for j in database.list_active_jobs():
            db_active_jobs[j["job_id"]] = {
                "job_id": j["job_id"], "user_id": j.get("user_id"),
                "ticker": j["ticker"], "scan_type": j.get("scan_type"),
                "status": j["status"], "stage": j.get("stage"),
                "progress_pct": j.get("progress_pct", 0),
                "checkpoints": (j.get("checkpoints") or [])[-5:],
                "tokens_used": j.get("tokens_used"),
                "error": j.get("error"),
            }
    except Exception as e:
        logging.info(f"[dashboard] DB active jobs read failed: {e}")

    merged_active = list({**db_active_jobs, **{a.get("job_id", ""): a for a in active}}.values())

    return {
        "server_start":    _ds.SERVER_START.isoformat(),
        "uptime_s":        round(uptime),
        "active_analyses": merged_active,
        "recent_analyses": completed,
        "historical_analyses": history,
        "request_log":     reqs,
        "token_stats":     tok,
        "db_stats":        db_stats,
        "cache_stats":     cache_stats,
        "claude_stats":    claude_stats,
        "deepseek_stats":  deepseek_stats,
        "unknown_stats":   unknown_stats,
        "feature_errors":  feature_errors,
        "harvest_status":  current_harvests,
        "harvest_logs":    h_logs,
        "latest_news":     latest_news if 'latest_news' in locals() else [],
        "latest_videos":   latest_videos if 'latest_videos' in locals() else [],
        "ai_health":       ai_health,
        "ai_engine":       build_ai_engine_monitor(mode="running"),
    }


def get_analysis_detail(analysis_id: int) -> dict | None:
    """raw_output/full_json for one archive row, or None when it does not exist."""
    with get_session() as session:
        row = session.query(AnalysisHistory).filter(AnalysisHistory.id == analysis_id).first()
        if row is None:
            return None
        return {"id": row.id, "raw_output": row.raw_output, "full_json": row.full_json}


def build_user_data(user_id: int) -> dict:
    """User details, holdings, alerts, journal, valuation history and recent analyses.

    Raises LookupError when the user does not exist.
    """
    result: dict = {"user_id": user_id}
    with get_session() as session:
        # ── User info ──
        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            raise LookupError("User not found")
        result["user"] = {
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        }

        # ── Portfolio ──
        holdings = session.query(Portfolio).filter(Portfolio.user_id == user_id).all()
        portfolio_rows = []
        total_invested = 0.0
        holdings_count = 0
        for h in holdings:
            invested = h.shares * h.buy_price
            # Watchlist rows are exported with their label but are not holdings (DB-19).
            if str(h.group_name or "watchlist") != "watchlist":
                total_invested += invested
                holdings_count += 1
            portfolio_rows.append({
                "id": h.id,
                "ticker": h.ticker,
                "company_name": h.company_name,
                "shares": h.shares,
                "buy_price": h.buy_price,
                "group_name": h.group_name or "watchlist",
                "notes": h.notes or "",
                "invested": round(invested, 2),
                "created_at": h.created_at.isoformat() if h.created_at else None,
            })
        result["portfolio"] = portfolio_rows
        result["portfolio_summary"] = {"total_invested": round(total_invested, 2), "holdings_count": holdings_count}

        # ── Analysis History ──
        # raw_output is deferred (PERF-08); this export ships it, so load it in the same query.
        analyses = session.query(AnalysisHistory).options(undefer(AnalysisHistory.raw_output)).filter(
            AnalysisHistory.user_id == user_id
        ).order_by(AnalysisHistory.created_at.desc()).limit(50).all()
        analysis_rows = []
        for a in analyses:
            parsed_json = {}
            try:
                parsed_json = json.loads(a.full_json) if a.full_json else {}
            except Exception as _e:
                pass
            analysis_rows.append({
                "id": a.id,
                "ticker": a.ticker,
                "analysis_date": a.analysis_date,
                "signal": a.signal,
                "confidence_pct": a.confidence_pct,
                "target_short": a.target_short,
                "target_medium": a.target_medium,
                "target_long": a.target_long,
                "promoter_pledged_pct": a.promoter_pledged_pct,
                "outcome_delta_pct": a.outcome_delta_pct,
                "was_correct": a.was_correct,
                "created_at": a.created_at.isoformat() if a.created_at else None,
                # Key fields from full_json
                "company_name": parsed_json.get("company_name", ""),
                "bull_case": parsed_json.get("bull_case", []),
                "bear_case": parsed_json.get("bear_case", []),
                "key_risks": parsed_json.get("key_risks", []),
                "key_factors": parsed_json.get("key_factors", {}),
                "current_price_inr": parsed_json.get("current_price_inr"),
                "upside_downside_pct": parsed_json.get("upside_downside_pct", {}),
                "management_quality": parsed_json.get("management_quality", ""),
                "technical_trend": parsed_json.get("technical_trend", ""),
                "fundamental_score": parsed_json.get("fundamental_score", ""),
                "disclaimer": parsed_json.get("disclaimer", ""),
                "raw_output": a.raw_output or "",
            })
        result["analyses"] = analysis_rows

        # Signal distribution
        sig_counts = Counter(a["signal"] for a in analysis_rows)
        result["signal_distribution"] = dict(sig_counts)

        # ── Watchlist / Price Alerts ──
        alerts = session.query(PriceTarget).filter(PriceTarget.user_id == user_id).order_by(PriceTarget.created_at.desc()).all()
        result["alerts"] = [{
            "id": a.id,
            "ticker": a.ticker,
            "target_price": a.target_price,
            "direction": a.direction,
            "triggered": a.triggered,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        } for a in alerts]

        # ── Trade Journal ──
        journal = session.query(TradeJournal).filter(TradeJournal.user_id == user_id).order_by(TradeJournal.created_at.desc()).all()
        result["trade_journal"] = [{
            "id": j.id,
            "ticker": j.ticker,
            "company_name": j.company_name or "",
            "action": j.action,
            "price_at_time": j.price_at_time,
            "reason_text": j.reason_text,
            "outcome_text": j.outcome_text or "",
            "mood": j.mood or "",
            "created_at": j.created_at.isoformat() if j.created_at else None,
            "updated_at": j.updated_at.isoformat() if j.updated_at else None,
        } for j in journal]

        # ── Portfolio Valuation History ──
        val_hist = session.query(PortfolioValuationHistory).filter(
            PortfolioValuationHistory.user_id == user_id
        ).order_by(PortfolioValuationHistory.snapshot_date.asc()).all()
        result["valuation_history"] = [{
            "snapshot_date": v.snapshot_date,
            "total_value": v.total_value,
            "total_invested": v.total_invested,
            "total_pnl": v.total_pnl,
            "pnl_percent": v.pnl_percent,
            "nifty_close": v.nifty_close,
        } for v in val_hist]

        # ── Net Worth Ledger ──
        nw_rows = session.query(NetWorthLedger).filter(
            NetWorthLedger.user_id == user_id
        ).order_by(NetWorthLedger.snapshot_date.asc()).all()
        result["net_worth_ledger"] = [{
            "snapshot_date": n.snapshot_date,
            "total_value_inr": n.total_value_inr,
            "daily_delta_inr": n.daily_delta_inr,
            "daily_delta_pct": n.daily_delta_pct,
            "peak_value_inr": n.peak_value_inr,
            "top_gainer_ticker": n.top_gainer_ticker,
            "top_gainer_pct": n.top_gainer_pct,
            "top_loser_ticker": n.top_loser_ticker,
            "top_loser_pct": n.top_loser_pct,
        } for n in nw_rows]

        # ── Device Tokens ──
        tokens = session.query(DeviceToken).filter(DeviceToken.user_id == user_id).all()
        result["device_tokens"] = [{
            "platform": t.platform,
            "token_preview": t.device_token[:20] + "..." if t.device_token else "",
            "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        } for t in tokens]

        # ── Analysis accuracy stats ──
        correct = sum(1 for a in analysis_rows if a["was_correct"] is True)
        incorrect = sum(1 for a in analysis_rows if a["was_correct"] is False)
        checked = correct + incorrect
        result["accuracy"] = {
            "correct": correct,
            "incorrect": incorrect,
            "checked": checked,
            "accuracy_pct": round(correct / checked * 100, 1) if checked > 0 else None,
        }


    return result
