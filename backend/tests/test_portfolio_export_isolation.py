"""AUTH-27: portfolio exports never mix in other users' data or leak exception text.

The Excel 'Analysis History' sheet listed the 100 most recent analyses ANY user ran;
it now lists only the caller's own. The PDF export's top-level failure returns a
non-200 JSON error with a generic message, never str(exception).

Run from backend/:
    ../venv/bin/pytest tests/test_portfolio_export_isolation.py -v
"""

from unittest.mock import MagicMock
from uuid import uuid4


def _make_user(ticker: str, analysed: str):
    """User with one holding and one analysis row of `analysed`; returns (user_id, headers)."""
    import database
    from models.db_models import AnalysisHistory, Portfolio, User

    with database.get_session() as session:
        user = User(username=f"export_{uuid4().hex[:12]}", password_hash="test", display_name="Export Test")
        session.add(user)
        session.flush()
        user_id = int(user.id)  # type: ignore[arg-type]
        session.add(Portfolio(
            user_id=user_id, ticker=ticker, company_name=f"{ticker} Ltd",
            shares=1, buy_price=100.0, group_name="holdings",
        ))
        session.add(AnalysisHistory(
            user_id=user_id, ticker=analysed, analysis_date="2026-10-01",
            signal="HOLD", full_json="{}",
        ))
        session.commit()
    return user_id, {"Authorization": f"Bearer {database.create_access_token(user_id)}"}


def test_excel_history_sheet_contains_only_callers_analyses(client, monkeypatch):
    import routers.portfolio as portfolio_router

    a_tag, b_tag = f"AAA{uuid4().hex[:6]}".upper(), f"BBB{uuid4().hex[:6]}".upper()
    uid_a, headers_a = _make_user("INFY", a_tag)
    _make_user("TCS", b_tag)

    history_sheet = MagicMock()
    workbook = MagicMock()
    workbook.create_sheet.return_value = history_sheet
    fake_openpyxl = MagicMock()
    fake_openpyxl.Workbook.return_value = workbook
    monkeypatch.setattr(portfolio_router, "openpyxl", fake_openpyxl)
    monkeypatch.setattr(portfolio_router, "OPENPYXL_AVAILABLE", True)
    for style in ("PatternFill", "XLFont", "Alignment"):
        monkeypatch.setattr(portfolio_router, style, MagicMock(), raising=False)
    monkeypatch.setattr(portfolio_router, "_yf_price", lambda ns: (110.0, None))

    r = client.get(f"/portfolio/export/excel/{uid_a}", headers=headers_a)

    assert r.status_code == 200, r.text
    workbook.create_sheet.assert_called_once_with("Analysis History")
    tickers = {
        c.kwargs["value"] for c in history_sheet.cell.call_args_list
        if c.kwargs.get("column") == 2 and c.kwargs.get("row", 1) > 1
    }
    assert tickers == {a_tag}


def test_pdf_export_failure_is_generic_non_200(client, monkeypatch):
    import routers.portfolio as portfolio_router

    uid, headers = _make_user("INFY", "INFY")
    secret = "db-password=hunter2 at 10.0.0.5"

    def _boom():
        raise RuntimeError(secret)

    monkeypatch.setattr(portfolio_router, "FPDF2_AVAILABLE", True)
    monkeypatch.setattr(portfolio_router, "get_session", _boom)

    r = client.get(f"/portfolio/export/pdf/{uid}", headers=headers)

    assert r.status_code >= 500
    assert secret not in r.text
    assert "hunter2" not in r.text
    assert r.json()["detail"].startswith("Portfolio review unavailable")
