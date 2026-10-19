"""REG-16: the IPO Hub exposes no unsourced grey-market premium and makes no
'apply' call-to-action (bids go only through SEBI-registered intermediaries)."""
import re
from pathlib import Path
from uuid import uuid4

import pytest

from database import get_session
from models.db_models import IPOListing  # pyright: ignore[reportMissingImports]  (checker resolves `models` to ml-engine/models)
from services import feature_flags
from services.ipo_service import _MOCK_IPOS

IPO_HUB_VIEW = (Path(__file__).resolve().parents[2] / "ios" / "StockApp" / "stockme" / "stockme"
                / "Views" / "IPOHubView.swift")


@pytest.fixture(autouse=True)
def _focus_flags_on(monkeypatch):
    """I04: the forum and IPO hub are off by default; these tests exercise them."""
    monkeypatch.setenv("NIVESH_FLAG_FORUM", "true")
    monkeypatch.setenv("NIVESH_FLAG_IPO_HUB", "true")
    feature_flags._reset_cache()
    yield
    feature_flags._reset_cache()


@pytest.fixture()
def ipo_with_legacy_gmp():
    """A row whose DB column still carries a GMP value (rows seeded before REG-16)."""
    with get_session() as session:
        row = IPOListing(company_name=f"GMP Probe {uuid4().hex[:8]}", symbol=f"GMP{uuid4().hex[:6]}".upper(),
                         open_date="2026-01-05", close_date="2026-01-07", listing_date="2026-01-12",
                         gmp=95.0)
        session.add(row)
        session.commit()
        row_id = row.id
    yield row_id
    with get_session() as session:
        session.query(IPOListing).filter(IPOListing.id == row_id).delete()
        session.commit()


@pytest.mark.parametrize("path", ["/api/ipo", "/api/ipo/calendar"])
def test_ipo_lists_have_no_gmp(client, ipo_with_legacy_gmp, path):
    resp = client.get(path)
    assert resp.status_code == 200, resp.text
    items = resp.json()
    assert any(item["id"] == ipo_with_legacy_gmp for item in items)
    assert all("gmp" not in item for item in items)


def test_ipo_detail_has_no_gmp(client, ipo_with_legacy_gmp):
    resp = client.get(f"/api/ipo/{ipo_with_legacy_gmp}")
    assert resp.status_code == 200, resp.text
    assert "gmp" not in resp.json()


def test_mock_seed_has_no_gmp():
    assert all("gmp" not in row for row in _MOCK_IPOS)


def test_ipo_hub_view_has_no_apply_cta():
    if not IPO_HUB_VIEW.is_file():  # backend-only checkout (the server) has no iOS tree
        pytest.skip("iOS sources not present")
    source = IPO_HUB_VIEW.read_text(encoding="utf-8")
    assert "Apply Now" not in source
    assert not re.search(r"apply for", source, re.IGNORECASE)
