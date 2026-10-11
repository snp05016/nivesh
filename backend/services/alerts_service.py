import asyncio
import httpx
import logging
import os
import jwt as pyjwt
import time
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

    result = []
    for row in alerts_data:
        ns_ticker = _to_ns(row["ticker"])
        current_price, _ = _yf_price(ns_ticker)
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

async def _send_apns_push(user_id: int, ticker: str, target_price: float, current_price: float, direction: str):
    """Sends an Apple Push Notification via APNs HTTP/2 to the user's registered device(s)."""
    apns_topic = os.getenv("APNS_TOPIC", "com.nivesh.app")
    apns_key_path = os.getenv("APNS_AUTH_KEY_PATH", "")
    apns_key_id = os.getenv("APNS_KEY_ID", "")
    apns_team_id = os.getenv("APNS_TEAM_ID", "")
    apns_env = os.getenv("APNS_ENVIRONMENT", "development")

    apns_host = (
        "https://api.push.apple.com" if apns_env == "production"
        else "https://api.sandbox.push.apple.com"
    )

    with get_session() as session:
        tokens = (
            session.query(DeviceToken.device_token)
            .filter_by(user_id=user_id, platform="ios")
            .all()
        )

    if not tokens:
        logger.info(f"No device tokens registered for user {user_id}, skipping APNs push for {ticker}")
        return True

    payload = {
        "aps": {
            "alert": {
                "title": f"{ticker} Alert Triggered",
                "body": f"{ticker} is now {'above' if direction == 'above' else 'below'} {target_price} (Current: {current_price})",
            },
            "sound": "default",
            "badge": 1,
        },
        "ticker": ticker,
        "type": "price_alert",
    }

    if not apns_key_path or not apns_key_id or not apns_team_id:
        logger.warning(f"APNs credentials not configured — logged push for {ticker} to user {user_id} with {len(tokens)} device(s)")
        return True

    try:
        with open(apns_key_path, "r") as f:
            auth_key = f.read()

        token_payload = {"iss": apns_team_id, "iat": int(time.time())}
        apns_token = pyjwt.encode(token_payload, auth_key, algorithm="ES256", headers={"kid": apns_key_id})

        headers = {
            "apns-topic": apns_topic,
            "apns-push-type": "alert",
            "apns-priority": "10",
            "authorization": f"bearer {apns_token}",
        }
    except FileNotFoundError:
        logger.error("APNs auth key not found at configured path")
        return False
    except Exception as e:
        logger.error("APNs JWT signing failed (%s)", type(e).__name__)
        return False

    any_success = False
    dead_tokens = []
    for (device_token,) in tokens:
        url = f"{apns_host}/3/device/{_url_quote(device_token)}"
        try:
            async with httpx.AsyncClient(http2=True) as client:
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code == 200:
                    logger.info("APNs push sent to user %d for %s", user_id, ticker)
                    any_success = True
                elif _is_dead_token(response):
                    dead_tokens.append(device_token)
                else:
                    logger.warning("APNs push rejected %d for user %d: %s",
                                   response.status_code, user_id, response.text[:200])
        except httpx.HTTPError:
            logger.warning("APNs HTTP transport error for user %d", user_id)
        except Exception as e:
            logger.warning("APNs dispatch error for user %d (%s)", user_id, type(e).__name__)
    if dead_tokens:
        with get_session() as session:
            session.query(DeviceToken).filter(
                DeviceToken.user_id == user_id,
                DeviceToken.device_token.in_(dead_tokens),
            ).delete(synchronize_session=False)
            session.commit()
        logger.info("Pruned %d unregistered APNs token(s) for user %d", len(dead_tokens), user_id)
    return any_success or not tokens


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

    prices = {}
    for t in {row[2] for row in pending}:
        price, _ = await asyncio.to_thread(_yf_price, _to_ns(t))
        if price is not None:
            prices[t] = price

    for alert_id, user_id, ticker, target_price, direction in pending:
        current_price = prices.get(ticker)
        if current_price is None:
            continue
        crossed = (
            (direction == "above" and current_price >= target_price)
            or (direction == "below" and current_price <= target_price)
        )
        if not crossed:
            continue
        if not _claim_alert(alert_id, user_id, ticker, direction, target_price, current_price):
            continue

        if not push_allowed(user_id):
            continue
        push_ok = await _send_apns_push(
            user_id=user_id,
            ticker=ticker,
            target_price=target_price,
            current_price=current_price,
            direction=direction
        )
        if not push_ok:
            logger.warning("APNs push failed for alert %d (inbox row written)", alert_id)


async def price_alert_poller():
    """Background task that polls every 5 minutes; inbox row always, APNs push best-effort."""
    while True:
        try:
            await _poll_once()
        except Exception as e:
            logger.error(f"Error in price alert poller: {e}")

        await asyncio.sleep(300)
