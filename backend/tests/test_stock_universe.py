"""ARCH-10 regression: one stock universe (backend/data/nse_bse_symbols.json).

Advisor-consensus resolves sectors from the full JSON via services.stock_universe,
the inline copies are gone, and the iOS bundled copy is byte-identical to the
backend file.
"""
import filecmp
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from services import stock_universe

_BACKEND = Path(__file__).resolve().parent.parent
_JSON = _BACKEND / "data" / "nse_bse_symbols.json"
_IOS_JSON = _BACKEND.parent / "ios" / "StockApp" / "stockme" / "stockme" / "Resources" / "nse_bse_symbols.json"


def _raw():
    return json.loads(_JSON.read_text(encoding="utf-8"))


def test_by_ticker_uses_json_sector():
    expected = next(e for e in _raw() if e["ticker"] == "ALKYLAMINE")
    entry = stock_universe.by_ticker("ALKYLAMINE")
    assert entry is not None
    assert entry["sector"] == expected["sector"]
    assert entry["company_name"] == expected["name"]
    assert stock_universe.sector_for("alkylamine ") == expected["sector"]
    assert stock_universe.sector_for("NOT_A_TICKER_XYZ") == "Unknown"
    assert stock_universe.sector_for("NOT_A_TICKER_XYZ", "Diversified") == "Diversified"


def test_entries_cover_whole_json():
    assert len(stock_universe.entries()) == len({e["ticker"] for e in _raw()})


def test_inline_directories_removed():
    import main
    import routers.portfolio as portfolio
    import routers.market as market

    assert not hasattr(main, "_NSE_DIRECTORY")
    assert not hasattr(main, "_NSE_DIR_INDEX")
    assert not hasattr(portfolio, "_NSE_DIRECTORY")
    # /search keeps its index, now built from the shared loader
    assert len(market._NSE_DIR_INDEX) == len(stock_universe.entries())


def test_ios_copy_in_sync():
    if not _IOS_JSON.parent.is_dir():
        pytest.skip("iOS project not present in this checkout")
    assert filecmp.cmp(_JSON, _IOS_JSON, shallow=False), (
        "iOS Resources/nse_bse_symbols.json differs from backend/data; "
        "run backend/scripts/refresh_nse_symbols.py or copy the file"
    )


def test_advisor_consensus_maps_json_only_ticker(client, auth_headers, test_user_id):
    from database import get_session
    from models.db_models import AdvisorInsight

    expected = next(e for e in _raw() if e["ticker"] == "ALKYLAMINE")
    tag = uuid.uuid4().hex[:8]
    video_ids = [f"arch10-{tag}-{i}" for i in range(2)]  # sector signals need >= 2 mentions
    now = datetime.now(timezone.utc)
    with get_session() as s:
        for vid in video_ids:
            s.add(AdvisorInsight(
                ticker="ALKYLAMINE", advisor_name=f"ARCH10 Advisor {tag}",
                channel_id="arch10", video_id=vid, video_title="t",
                video_url=f"https://example.invalid/{vid}", published_at=now,
                transcript_source="test", stance="BULLISH", confidence="HIGH",
                catalyst_summary="test", view_count=1,
            ))
        s.commit()
    try:
        resp = client.get(
            f"/api/v1/portfolio/advisor-consensus?user_id={test_user_id}&days=1",
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()

        tickers = {t["ticker"]: t for t in body["trending_tickers"]}
        assert "ALKYLAMINE" in tickers
        assert tickers["ALKYLAMINE"]["company_name"] == expected["name"]

        ours = [s for s in body["sector_signals"] if f"ARCH10 Advisor {tag}" in s["top_advisors"]]
        assert ours, body["sector_signals"]
        assert ours[0]["theme"] == expected["sector"]
        assert ours[0]["theme"] != "Unknown"
    finally:
        with get_session() as s:
            s.query(AdvisorInsight).filter(AdvisorInsight.video_id.in_(video_ids)).delete(
                synchronize_session=False
            )
            s.commit()
