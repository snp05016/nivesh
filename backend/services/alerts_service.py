import asyncio
import httpx
import logging
import os
import threading
import jwt as pyjwt
import time
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from typing import Optional
from urllib.parse import quote as _url_quote

from helpers import _yf_price, _to_ns, get_session, PriceTarget
from models.db_models import DeviceToken
from services.notifications_inbox import create_notification
from services.preferences import push_allowed
from services import entitlement_service

logger = logging.getLogger(__name__)

def add_price_alert(user_id: int, ticker: str, target_price: float, direction: str):
    if direction not in ("above", "below"):
        raise ValueError("direction must be 'above' or 'below'")
    if target_price <= 0:
        raise ValueError("target_price must be greater than 0")
        
    ticker = ticker.upper()
    with get_session() as session:
        active = session.query(PriceTarget).filter_by(user_id=user_id, triggered=False).count()
    entitlement_service.enforce_quota(user_id, "price_alerts", active)
    with get_session() as session:
        new_alert = PriceTarget(
            user_id=user_id,
            ticker=ticker,
            target_price=target_price,
            direction=direction,
            triggered=False,
        )
        session.add(new_alert)
        session.commit()
        session.refresh(new_alert)
        alert_id = new_alert.id
        
    return {
        "success": True,
        "alert_id": alert_id,
        "ticker": ticker,
        "target_price": target_price,
        "direction": direction,
    }

def remove_price_alert(user_id: int, alert_id: int):
    with get_session() as session:
        alert = session.query(PriceTarget).filter_by(
            id=alert_id, user_id=user_id
        ).first()
        if not alert:
            raise LookupError("Alert not found")
        session.delete(alert)
        session.commit()
    return {"success": True}

def _current_prices(tickers) -> dict:
    """{ticker: current price or None}, one lookup per unique ticker, fetched
    concurrently (PERF-17). Blocking: call from a thread, not the event loop.

    ponytail: per-call pool; swap for the shared quote gateway when it exists.
    """
    unique = sorted(set(tickers))
    if not unique:
        return {}

    def _one(t):
        try:
            return _yf_price(_to_ns(t))[0]
        except Exception as e:
            logger.warning("Price lookup failed for %s: %s", t, e)
            return None

    with ThreadPoolExecutor(max_workers=min(8, len(unique))) as ex:
        return dict(zip(unique, ex.map(_one, unique)))


def get_alerts_data(user_id: int):
    with get_session() as session:
        alerts = (
            session.query(PriceTarget)
            .filter_by(user_id=user_id)
            .order_by(PriceTarget.created_at.desc())
            .all()
        )
        alerts_data = [
            {
                "id": a.id,
                "ticker": a.ticker,
                "target_price": a.target_price,
                "direction": a.direction,
                "triggered": a.triggered,
                "created_at": a.created_at.strftime("%Y-%m-%d") if a.created_at else "",
            }
            for a in alerts
        ]

    prices = _current_prices(row["ticker"] for row in alerts_data)
    result = []
    for row in alerts_data:
        current_price = prices.get(row["ticker"])
        distance_pct = None
        if current_price and row["target_price"]:
            distance_pct = round(abs(current_price - row["target_price"]) / row["target_price"] * 100, 2)
        result.append({
            "id": row["id"],
            "ticker": row["ticker"],
            "company_name": row["ticker"],
            "target_price": row["target_price"],
            "direction": row["direction"],
            "current_price": current_price,
            "distance_pct": distance_pct,
            "triggered": row["triggered"],
            "created_at": row["created_at"],
        })
    return result

class PushResult(str, Enum):
    """Outcome of one push attempt. Only SENT means a device accepted it."""
    SENT = "sent"
    NO_TOKENS = "no_tokens"
    NOT_CONFIGURED = "not_configured"
    DISABLED = "disabled"  # user turned alerts off (IOSCORE-23)
    FAILED = "failed"


# Apple rejects provider tokens refreshed more often than every 20 min and expires
# them after 60 min (TooManyProviderTokenUpdates / ExpiredProviderToken).
_PROVIDER_TOKEN_TTL = 50 * 60
_provider_tokens: dict = {}
_provider_lock = threading.Lock()
_unconfigured_warned = False


def _provider_token(team_id: str, key_id: str, key_path: str) -> str:
    """ES256 provider JWT, re-minted only every 50 minutes."""
    key = (team_id, key_id, key_path)
    with _provider_lock:
        cached = _provider_tokens.get(key)
        if cached and time.time() - cached[1] < _PROVIDER_TOKEN_TTL:
            return cached[0]
        with open(key_path, "r") as f:
            auth_key = f.read()
        now = int(time.time())
        token = pyjwt.encode({"iss": team_id, "iat": now}, auth_key, algorithm="ES256",
                             headers={"kid": key_id})
        _provider_tokens[key] = (token, now)
        return token


async def send_apns(user_id: int, title: str, body: str, data: Optional[dict] = None) -> PushResult:
    """Push one alert to every iOS device of `user_id` via APNs HTTP/2."""
    global _unconfigured_warned
    with get_session() as session:
        tokens = [
            t for (t,) in session.query(DeviceToken.device_token)
            .filter_by(user_id=user_id, platform="ios").all()
        ]
    if not tokens:
        logger.info("No device tokens registered for user %d, APNs push skipped", user_id)
        return PushResult.NO_TOKENS

    apns_key_path = os.getenv("APNS_AUTH_KEY_PATH", "")
    apns_key_id = os.getenv("APNS_KEY_ID", "")
    apns_team_id = os.getenv("APNS_TEAM_ID", "")
    if not apns_key_path or not apns_key_id or not apns_team_id:
        if not _unconfigured_warned:
            logger.warning("APNs credentials not configured: pushes are not delivered")
            _unconfigured_warned = True
        return PushResult.NOT_CONFIGURED

    try:
        apns_token = _provider_token(apns_team_id, apns_key_id, apns_key_path)
    except FileNotFoundError:
        logger.error("APNs auth key not found at configured path")
        return PushResult.NOT_CONFIGURED
    except Exception as e:
        logger.error("APNs JWT signing failed (%s)", type(e).__name__)
        return PushResult.FAILED

    apns_host = (
        "https://api.push.apple.com" if os.getenv("APNS_ENVIRONMENT", "development") == "production"
        else "https://api.sandbox.push.apple.com"
    )
    headers = {
        "apns-topic": os.getenv("APNS_TOPIC", "com.nivesh.app"),
        "apns-push-type": "alert",
        "apns-priority": "10",
        "authorization": f"bearer {apns_token}",
    }
    payload = {"aps": {"alert": {"title": title, "body": body}, "sound": "default", "badge": 1},
               **(data or {})}

    any_success = False
    dead_tokens = []
    try:
        # ponytail: one client per push (shared across its devices); a process-wide
        # client would need one per event loop (poller loop vs asyncio.run callers).
        async with httpx.AsyncClient(http2=True, timeout=10) as client:
            for device_token in tokens:
                url = f"{apns_host}/3/device/{_url_quote(device_token)}"
                try:
                    response = await client.post(url, json=payload, headers=headers)
                except httpx.HTTPError:
                    logger.warning("APNs HTTP transport error for user %d", user_id)
                    continue
                if response.status_code == 200:
                    any_success = True
                elif _is_dead_token(response):
                    dead_tokens.append(device_token)
                else:
                    logger.warning("APNs push rejected %d for user %d: %s",
                                   response.status_code, user_id, response.text[:200])
    except Exception as e:  # e.g. ImportError when h2 is missing
        logger.error("APNs dispatch error for user %d (%s)", user_id, type(e).__name__)
    if dead_tokens:
        with get_session() as session:
            session.query(DeviceToken).filter(
                DeviceToken.user_id == user_id,
                DeviceToken.device_token.in_(dead_tokens),
            ).delete(synchronize_session=False)
            session.commit()
        logger.info("Pruned %d unregistered APNs token(s) for user %d", len(dead_tokens), user_id)
    if any_success:
        logger.info("APNs push sent to user %d", user_id)
        return PushResult.SENT
    return PushResult.NO_TOKENS if len(dead_tokens) == len(tokens) else PushResult.FAILED


async def _send_apns_push(user_id: int, ticker: str, target_price: float, current_price: float,
                          direction: str) -> PushResult:
    """Price-alert push for `ticker`."""
    return await send_apns(
        user_id,
        f"{ticker} Alert Triggered",
        f"{ticker} is now {direction} ₹{target_price:,.2f} (current ₹{current_price:,.2f})",
        {"ticker": ticker, "type": "price_alert"},
    )


def _is_dead_token(response) -> bool:
    """APNs says the device token will never work again (410, or 400 bad token)."""
    if response.status_code == 410:
        return True
    if response.status_code != 400:
        return False
    try:
        reason = response.json().get("reason")
    except Exception:
        return False
    return reason in ("BadDeviceToken", "Unregistered")


def _claim_alert(alert_id: int, user_id: int, ticker: str, direction: str,
                 target_price: float, current_price: float) -> bool:
    """Atomically flip triggered False->True and write the inbox row in one
    transaction. False if another poller (uvicorn worker) claimed it first."""
    with get_session() as session:
        claimed = (
            session.query(PriceTarget)
            .filter(PriceTarget.id == alert_id, PriceTarget.triggered.is_(False))
            .update({"triggered": True}, synchronize_session=False)
        )
        if not claimed:
            session.rollback()
            return False
        # The inbox row is the durable delivery; APNs is best-effort on top.
        create_notification(
            user_id,
            "price_alert",
            f"{ticker} alert triggered",
            f"{ticker} is now {direction} ₹{target_price:,.2f} "
            f"(current ₹{current_price:,.2f})",
            action_url=f"nivesh://analyze/{ticker}",
            session=session,
        )
        session.commit()
        return True


def _crossed(direction: str, current_price: float, target_price: float) -> bool:
    return ((direction == "above" and current_price >= target_price)
            or (direction == "below" and current_price <= target_price))


def check_alerts(user_id: int) -> list:
    """Claim this user's untriggered alerts whose price has crossed the target (GH-656).

    Same atomic claim and inbox row as the poller, minus the push (the user is
    in-app). Only alerts this call claimed are returned, each with a price, so a
    second call returns []; unknown prices are skipped and stay untriggered.
    """
    with get_session() as session:
        pending = (
            session.query(PriceTarget.id, PriceTarget.ticker,
                          PriceTarget.target_price, PriceTarget.direction)
            .filter_by(user_id=user_id, triggered=False).all()
        )
    prices = _current_prices(row[1] for row in pending)
    newly = []
    for alert_id, ticker, target_price, direction in pending:
        current_price = prices.get(ticker)
        if current_price is None or not _crossed(direction, current_price, target_price):
            continue
        if _claim_alert(alert_id, user_id, ticker, direction, target_price, current_price):
            newly.append({"id": alert_id, "ticker": ticker, "target_price": target_price,
                          "direction": direction, "current_price": current_price})
    return newly


async def _poll_once() -> None:
    """One poller pass: trigger crossed alerts, write the inbox row, push best-effort.

    No session is held across network awaits: read, fetch prices, then claim
    each crossed alert in its own short transaction before pushing.
    """
    with get_session() as session:
        pending = (
            session.query(PriceTarget.id, PriceTarget.user_id, PriceTarget.ticker,
                          PriceTarget.target_price, PriceTarget.direction)
            .filter_by(triggered=False).all()
        )
    if not pending:
        return

    # Ticker resolution and price fetches both run off the event loop.
    prices = await asyncio.to_thread(_current_prices, [row[2] for row in pending])

    for alert_id, user_id, ticker, target_price, direction in pending:
        current_price = prices.get(ticker)
        if current_price is None:
            continue
        if not _crossed(direction, current_price, target_price):
            continue
        if not _claim_alert(alert_id, user_id, ticker, direction, target_price, current_price):
            continue

        if not push_allowed(user_id):
            continue
        result = await _send_apns_push(
            user_id=user_id,
            ticker=ticker,
            target_price=target_price,
            current_price=current_price,
            direction=direction
        )
        if result != PushResult.SENT:
            logger.warning("APNs push not delivered for alert %d: %s (inbox row written)",
                           alert_id, getattr(result, "value", result))


async def price_alert_poller():
    """Background task that polls every 5 minutes; inbox row always, APNs push best-effort."""
    while True:
        try:
            await _poll_once()
        except Exception as e:
            logger.error(f"Error in price alert poller: {e}")

        await asyncio.sleep(300)
