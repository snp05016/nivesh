"""GET /api/v1/me/portfolio/crisis-replay: how today's stocks moved in the COVID-2020 window (I35). Flag money_crisis_replay."""
from fastapi import APIRouter, Depends, HTTPException

from core.feature_flags import require_flag
from core.security import require_auth
from services import money_crisis_replay

router = APIRouter(prefix="/api/v1/me/portfolio", tags=["Money"])


@router.get("/crisis-replay", dependencies=[Depends(require_flag("money_crisis_replay"))])
def crisis_replay(scenario: str = "covid_2020", user_id: int = Depends(require_auth)):
    try:
        return money_crisis_replay.replay(user_id, scenario)
    except ValueError:
        raise HTTPException(
            status_code=422, detail={"code": "UNKNOWN_SCENARIO", "message": "That scenario isn't available."}
        ) from None
    except money_crisis_replay.ReplayUnavailable:
        raise HTTPException(
            status_code=503,
            detail={"code": "REPLAY_UNAVAILABLE", "message": "The replay is not available right now."},
            headers={"Retry-After": "300"},
        ) from None
