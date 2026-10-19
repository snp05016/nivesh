"""Corporate-action proposals on Holdings (I18): list, apply, dismiss, undo.

Flag data_corp_actions_confirm, with an env cohort allowlist (services/data_flags).
Errors use the cluster envelope HTTPException(detail={'code': ...}).
"""
from fastapi import APIRouter, Depends, HTTPException

from core.security import require_auth
from services import corporate_actions, data_flags, ledger_service

router = APIRouter(prefix="/api/v1/portfolio/corporate-actions", tags=["Corporate Actions"])

_FLAG = "data_corp_actions_confirm"


def _run(action, user_id: int, app_id: int) -> dict:
    data_flags.require(_FLAG, user_id)
    try:
        return action(user_id, app_id)
    except LookupError:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND"})
    except ledger_service.LedgerError:
        raise HTTPException(status_code=409, detail={"code": "LEDGER_CONFLICT"})
    except ValueError as exc:
        if str(exc) != "INVALID_STATE":
            raise
        item = corporate_actions.item_for(user_id, app_id)
        raise HTTPException(status_code=409, detail={"code": "INVALID_STATE", "status": item["status"] if item else None})


@router.get("")
def list_corporate_actions(user_id: int = Depends(require_auth)):
    data_flags.require(_FLAG, user_id)
    return {"items": corporate_actions.list_for_user(user_id)}


@router.post("/{app_id}/apply")
def apply_corporate_action(app_id: int, user_id: int = Depends(require_auth)):
    return _run(ledger_service.apply_corporate_action, user_id, app_id)


@router.post("/{app_id}/dismiss")
def dismiss_corporate_action(app_id: int, user_id: int = Depends(require_auth)):
    return _run(ledger_service.dismiss_corporate_action, user_id, app_id)


@router.post("/{app_id}/undo")
def undo_corporate_action(app_id: int, user_id: int = Depends(require_auth)):
    return _run(ledger_service.undo_corporate_action, user_id, app_id)
