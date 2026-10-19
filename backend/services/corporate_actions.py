"""Corporate-action records and the user-facing proposal list (data foundation, I18).

Events come from yfinance (MATH-07's fetch_split_events); each becomes one
corporate_actions row (SPLIT_OR_BONUS). The ledger writes (apply, dismiss, undo and
the guarded auto-apply) live in ledger_service, the only ledger writer.
"""
import logging
from datetime import date, datetime, timedelta
from typing import Optional

from core.timeutil import utcnow
from repositories.research_repo import normalize_symbol

logger = logging.getLogger(__name__)

ACTION_TYPE = "SPLIT_OR_BONUS"
ACTION_LABEL = "Share split or bonus"
SOURCE_LABEL = "Yahoo Finance corporate actions"
UNDO_WINDOW_DAYS = 30
_CONFIRM_TOLERANCE = 0.02
_PREV_CLOSE_LOOKBACK_DAYS = 10


def ratio_text(ratio: float) -> str:
    """2.0 -> '1 share became 2'; 1.5 -> '2 shares became 3'; otherwise '1 share became {ratio:.4g}'."""
    for b in range(1, 11):
        n = ratio * b
        if abs(n - round(n)) <= 1e-6 and round(n) >= 1:
            return f"{b} share{'' if b == 1 else 's'} became {int(round(n))}"
    return "1 share became " + format(ratio, ".4g")


def _nse_confirmed(session, ticker: str, ex_on: date, ratio: float) -> Optional[bool]:
    """Does the mirrored NSE bhavcopy show the adjustment? None when the rows are not mirrored.

    Internal read: the data_eod_display gate protects user-facing prices, not this check.
    """
    from models.db_models import DailyPrice
    from services import instruments

    inst = instruments.resolve(symbol=ticker)
    if inst is None:
        return None
    row = (
        session.query(DailyPrice)
        .filter(DailyPrice.instrument_id == inst.id, DailyPrice.trade_date == ex_on,
                DailyPrice.source == "nse_bhavcopy")
        .first()
    )
    prev = (
        session.query(DailyPrice)
        .filter(DailyPrice.instrument_id == inst.id, DailyPrice.source == "nse_bhavcopy",
                DailyPrice.trade_date >= ex_on - timedelta(days=_PREV_CLOSE_LOOKBACK_DAYS),
                DailyPrice.trade_date < ex_on)
        .order_by(DailyPrice.trade_date.desc())
        .first()
    )
    if row is None or prev is None or row.prev_close is None or not prev.close:
        return None
    adjusted = float(row.prev_close) / float(prev.close) * ratio
    return row.event in ("split", "override") and abs(adjusted - 1.0) <= _CONFIRM_TOLERANCE


def record_events(ticker: str, events: list[tuple[date, float]]) -> dict[date, int]:
    """Upsert one corporate_actions row per (ticker, ex-date); returns {ex_on: id}."""
    from database import get_session
    from models.db_models import CorporateAction

    symbol = normalize_symbol(ticker)
    ids: dict[date, int] = {}
    if not events or not symbol:
        return ids
    with get_session() as session:
        for ex_on, ratio in events:
            confirmed = _nse_confirmed(session, symbol, ex_on, ratio)
            row = (
                session.query(CorporateAction)
                .filter_by(ticker=symbol, action_type=ACTION_TYPE, ex_on=ex_on)
                .first()
            )
            if row is None:
                row = CorporateAction(
                    ticker=symbol, action_type=ACTION_TYPE, ex_on=ex_on, ex_date=ex_on.isoformat(),
                    purpose="Share split or bonus: " + ratio_text(ratio), ratio=ratio, source="yfinance",
                    nse_confirmed=confirmed,
                )
                session.add(row)
            else:
                row.ratio, row.nse_confirmed = ratio, confirmed
                row.purpose = "Share split or bonus: " + ratio_text(ratio)
                row.updated_at = utcnow().replace(tzinfo=None)
            session.flush()
            ids[ex_on] = int(row.id)
        session.commit()
    return ids


def application_item(app, action, group_name: Optional[str]) -> dict:
    """The API item for one application (see the cluster spec)."""
    ratio = float(action.ratio) if action.ratio is not None else None
    before = float(app.shares_before) if app.shares_before is not None else None
    decided = app.decided_at
    undo_until = (decided + timedelta(days=UNDO_WINDOW_DAYS)) if decided is not None else None
    return {
        "id": app.id,
        "ticker": action.ticker,
        "group_id": app.group_id,
        "group_name": group_name,
        "action_label": ACTION_LABEL,
        "ratio": ratio,
        "ratio_text": ratio_text(ratio) if ratio is not None else None,
        "ex_date": action.ex_on.isoformat() if action.ex_on else action.ex_date,
        "status": app.status,
        "shares_before": before,
        "shares_after": round(before * ratio, 6) if before is not None and ratio is not None else None,
        "nse_confirmed": action.nse_confirmed,
        "source": SOURCE_LABEL,
        "decided_at": decided.isoformat() if decided is not None else None,
        "undo_until": undo_until.isoformat() if undo_until is not None else None,
    }


def list_for_user(user_id: int) -> list[dict]:
    """Pending items plus applied or dismissed items decided in the last 30 days, newest ex-date first."""
    from database import get_session
    from models.db_models import CorporateAction, CorporateActionApplication, PortfolioGroup

    cutoff = utcnow().replace(tzinfo=None) - timedelta(days=UNDO_WINDOW_DAYS)
    with get_session() as session:
        rows = (
            session.query(CorporateActionApplication, CorporateAction, PortfolioGroup.name)
            .join(CorporateAction, CorporateAction.id == CorporateActionApplication.corporate_action_id)
            .outerjoin(PortfolioGroup, PortfolioGroup.id == CorporateActionApplication.group_id)
            .filter(CorporateActionApplication.user_id == user_id)
            .all()
        )
        items = [
            (action.ex_on or date.min, app.id, application_item(app, action, group_name))
            for app, action, group_name in rows
            if app.status == "pending" or (app.decided_at is not None and app.decided_at >= cutoff)
        ]
    items.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return [item for _, _, item in items]


def item_for(user_id: int, app_id: int) -> Optional[dict]:
    from database import get_session
    from models.db_models import CorporateAction, CorporateActionApplication, PortfolioGroup

    with get_session() as session:
        row = (
            session.query(CorporateActionApplication, CorporateAction, PortfolioGroup.name)
            .join(CorporateAction, CorporateAction.id == CorporateActionApplication.corporate_action_id)
            .outerjoin(PortfolioGroup, PortfolioGroup.id == CorporateActionApplication.group_id)
            .filter(CorporateActionApplication.id == app_id, CorporateActionApplication.user_id == user_id)
            .first()
        )
        return application_item(*row) if row else None
