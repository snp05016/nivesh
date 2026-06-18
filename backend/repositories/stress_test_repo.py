"""Repository queries used by the portfolio stress-test engine."""

from models.db_models import Portfolio


def list_portfolio_holdings(user_id: int, group_name: str) -> list[dict]:
    from database import get_session

    with get_session() as session:
        rows = (
            session.query(Portfolio)
            .filter(
                Portfolio.user_id == user_id,
                Portfolio.group_name == group_name,
            )
            .all()
        )
        return [
            {
                "ticker": row.ticker,
                "company_name": row.company_name,
                "shares": float(row.shares),
                "buy_price": float(row.buy_price),
                "group_name": row.group_name,
            }
            for row in rows
        ]
