"""GET /portfolio/export/pdf/{user_id}: real PDF, no LLM call, non-2xx on failure (CMON-11)."""

from __future__ import annotations

import importlib.util
import sys
from unittest.mock import MagicMock

import pytest

FPDF_INSTALLED = importlib.util.find_spec("fpdf") is not None
_TICKER = "PDFTESTCO"
_UNPRICED = "PDFNOPRICE"


@pytest.fixture
def pdf_holding(test_user_id, monkeypatch):
    from database import get_session, Portfolio  # pyright: ignore[reportAttributeAccessIssue]  (checker resolves `models` to ml-engine/models)

    with get_session() as session:
        session.add(Portfolio(
            user_id=test_user_id, ticker=_TICKER, company_name="PDF Test Co",
            shares=10, buy_price=100.0, group_name="holdings",
        ))
        session.commit()
    monkeypatch.setattr("routers.portfolio_exports._yf_price", lambda _sym: (110.0, 100.0))
    yield test_user_id
    with get_session() as session:
        session.query(Portfolio).filter_by(user_id=test_user_id, ticker=_TICKER).delete()
        session.commit()


def test_fpdf2_probe_matches_installed_package():
    import routers.portfolio_exports as exports_router

    assert exports_router.FPDF2_AVAILABLE is FPDF_INSTALLED


@pytest.mark.skipif(not FPDF_INSTALLED, reason="fpdf2 not installed")
def test_export_returns_pdf(client, auth_headers, pdf_holding):
    resp = client.get(f"/portfolio/export/pdf/{pdf_holding}", headers=auth_headers)

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/pdf")
    assert ".pdf" in resp.headers["content-disposition"]
    assert resp.content.startswith(b"%PDF")


@pytest.mark.skipif(not FPDF_INSTALLED, reason="fpdf2 not installed")
def test_export_makes_no_llm_call(client, auth_headers, pdf_holding, monkeypatch):
    anthropic_cls = MagicMock()
    monkeypatch.setattr(sys.modules["anthropic"], "Anthropic", anthropic_cls)

    resp = client.get(f"/portfolio/export/pdf/{pdf_holding}", headers=auth_headers)

    assert resp.status_code == 200
    anthropic_cls.assert_not_called()


def test_export_unavailable_returns_503(client, auth_headers, test_user_id, monkeypatch):
    monkeypatch.setattr("routers.portfolio_exports.FPDF2_AVAILABLE", False)

    resp = client.get(f"/portfolio/export/pdf/{test_user_id}", headers=auth_headers)

    assert resp.status_code == 503
    assert not resp.headers["content-type"].startswith("text/plain")


@pytest.mark.skipif(not FPDF_INSTALLED, reason="fpdf2 not installed")
def test_export_with_unpriced_holding_still_returns_pdf(client, auth_headers, pdf_holding, monkeypatch):
    from database import get_session, Portfolio  # pyright: ignore[reportAttributeAccessIssue]  (checker resolves `models` to ml-engine/models)

    with get_session() as session:
        session.add(Portfolio(
            user_id=pdf_holding, ticker=_UNPRICED, company_name="No Price Co",
            shares=10, buy_price=100.0, group_name="holdings",
        ))
        session.commit()
    monkeypatch.setattr(
        "routers.portfolio_exports._yf_price",
        lambda sym: (None, None) if sym.startswith(_UNPRICED) else (110.0, 100.0),
    )
    try:
        resp = client.get(f"/portfolio/export/pdf/{pdf_holding}", headers=auth_headers)
    finally:
        with get_session() as session:
            session.query(Portfolio).filter_by(user_id=pdf_holding, ticker=_UNPRICED).delete()
            session.commit()

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/pdf")
    assert resp.content.startswith(b"%PDF")
