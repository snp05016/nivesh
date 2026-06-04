from fastapi import APIRouter, HTTPException, Header
from helpers import (
    get_session, verify_access_token, PriceTarget,
    AlertAddRequest, AlertRemoveRequest, _to_ns, _yf_price
)

router = APIRouter(tags=["Price Alerts"])


@router.post("/alerts/add")
def alerts_add_endpoint(req: AlertAddRequest, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user is None or token_user != req.user_id:
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
    if token_user is None or token_user != req.user_id:
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


@router.get("/alerts/check/{user_id}")
def alerts_check_endpoint(user_id: int, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user is None or token_user != user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        with get_session() as session:
            pending = (
                session.query(PriceTarget)
                .filter_by(user_id=user_id, triggered=False)
                .all()
            )
            pending_data = [
                {
                    "id": a.id,
                    "ticker": a.ticker,
                    "target_price": a.target_price,
                    "direction": a.direction,
                }
                for a in pending
            ]

        newly_triggered = []
        for row in pending_data:
            ns_ticker = _to_ns(row["ticker"])
            current_price, _ = _yf_price(ns_ticker)
            if current_price is None:
                continue
            triggered = False
            if row["direction"] == "above" and current_price >= row["target_price"]:
                triggered = True
            elif row["direction"] == "below" and current_price <= row["target_price"]:
                triggered = True

            if triggered:
                with get_session() as session:
                    alert = session.query(PriceTarget).filter_by(id=row["id"]).first()
                    if alert:
                        alert.triggered = True
                        session.commit()
                newly_triggered.append({
                    "id": row["id"],
                    "ticker": row["ticker"],
                    "target_price": row["target_price"],
                    "direction": row["direction"],
                    "current_price": current_price,
                })

        return {"newly_triggered": newly_triggered}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts/{user_id}")
def alerts_get_endpoint(user_id: int, authorization: str = Header(None)):
    token_user = verify_access_token(authorization.split(" ", 1)[1] if authorization and authorization.startswith("Bearer ") else "")
    if token_user is None or token_user != user_id:
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
