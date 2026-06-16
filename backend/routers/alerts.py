from fastapi import APIRouter, HTTPException, Header
from helpers import (
    get_session, verify_access_token, PriceTarget,
    AlertAddRequest, AlertRemoveRequest, _to_ns, _yf_price
)

router = APIRouter(tags=["Price Alerts"])


@router.post("/alerts/add")
def alerts_add_endpoint(req: AlertAddRequest, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user != req.user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if req.direction not in ("above", "below"):
        raise HTTPException(status_code=400, detail="direction must be 'above' or 'below'")
    if req.target_price <= 0:
        raise HTTPException(status_code=400, detail="target_price must be greater than 0")
    ticker = req.ticker.upper()
    try:
        with get_session() as session:
            new_alert = PriceTarget(
                user_id=req.user_id,
                ticker=ticker,
                target_price=req.target_price,
                direction=req.direction,
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
            "target_price": req.target_price,
            "direction": req.direction,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/alerts/remove")
def alerts_remove_endpoint(req: AlertRemoveRequest, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user != req.user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        with get_session() as session:
            alert = session.query(PriceTarget).filter_by(
                id=req.alert_id, user_id=req.user_id
            ).first()
            if not alert:
                raise HTTPException(status_code=404, detail="Alert not found")
            session.delete(alert)
            session.commit()
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


import asyncio
import httpx
import logging
from helpers import _yf_price, _to_ns, get_session, PriceTarget

logger = logging.getLogger(__name__)

async def _price_alert_poller():
    """Background task that polls every 5 minutes and sends APNs push notifications."""
    while True:
        try:
            with get_session() as session:
                pending = session.query(PriceTarget).filter_by(triggered=False).all()
                if not pending:
                    await asyncio.sleep(300)
                    continue
                
                # Fetch distinct prices — offload blocking yfinance I/O to threadpool
                # so the asyncio event loop is not frozen during network calls.
                unique_tickers = {a.ticker for a in pending}
                prices = {}
                for t in unique_tickers:
                    ns_ticker = _to_ns(t)
                    price, _ = await asyncio.to_thread(_yf_price, ns_ticker)
                    if price is not None:
                        prices[t] = price
                
                # Check for triggered alerts
                for alert in pending:
                    current_price = prices.get(alert.ticker)
                    if current_price is None:
                        continue
                        
                    triggered = False
                    if alert.direction == "above" and current_price >= alert.target_price:
                        triggered = True
                    elif alert.direction == "below" and current_price <= alert.target_price:
                        triggered = True
                        
                    if triggered:
                        alert.triggered = True
                        session.commit()
                        
                        # Fire APNs Push Notification
                        await _send_apns_push(
                            user_id=alert.user_id,
                            ticker=alert.ticker,
                            target_price=alert.target_price,
                            current_price=current_price,
                            direction=alert.direction
                        )
        except Exception as e:
            logger.error(f"Error in price alert poller: {e}")
            
        await asyncio.sleep(300)


async def _send_apns_push(user_id: int, ticker: str, target_price: float, current_price: float, direction: str):
    """Sends an Apple Push Notification using HTTP/2 to the user's device."""
    # Placeholder for APNs config
    apns_topic = "com.nivesh.app"
    apns_auth_key_path = "/path/to/AuthKey_XYZ123.p8"
    apns_key_id = "XYZ123"
    apns_team_id = "TEAM123"
    
    # In production, we would fetch the user's APNs device token from the DB.
    # We mock it here since Nivesh is currently mocking device tokens.
    mock_device_token = f"mock_device_token_for_user_{user_id}"
    apns_url = f"https://api.development.push.apple.com/3/device/{mock_device_token}"
    
    payload = {
        "aps": {
            "alert": {
                "title": f"🚨 {ticker} Alert Triggered!",
                "body": f"{ticker} is now {'above' if direction == 'above' else 'below'} ₹{target_price} (Current: ₹{current_price}).",
            },
            "sound": "default",
            "badge": 1
        },
        "ticker": ticker,
        "type": "price_alert"
    }
    
    headers = {
        "apns-topic": apns_topic,
        "apns-push-type": "alert",
        "apns-priority": "10",
        # We would generate a JWT token here using the AuthKey.p8
        "authorization": "bearer MOCKED_JWT_TOKEN"
    }
    
    try:
        # APNs requires HTTP/2, httpx supports it with http2=True
        async with httpx.AsyncClient(http2=True) as client:
            # We don't await the actual call to avoid breaking if the URL is unreachable in dev
            # response = await client.post(apns_url, json=payload, headers=headers)
            logger.info(f"Mocked APNs Push sent to {mock_device_token} for {ticker}")
    except Exception as e:
        logger.error(f"Failed to send APNs push: {e}")


@router.get("/alerts/{user_id}")
def alerts_get_endpoint(user_id: int, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user != user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
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

        return {"alerts": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
