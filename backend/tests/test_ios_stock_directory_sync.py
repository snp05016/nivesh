"""IOSCORE-32: the iOS stock directory and the backend share one pruned universe.

Hermetic: reads files only, imports no backend modules.
"""
import json
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_BACKEND_JSON = _REPO / "backend" / "data" / "nse_bse_symbols.json"
_IOS_DIR = _REPO / "ios" / "StockApp" / "stockme" / "stockme"
_IOS_JSON = _IOS_DIR / "Resources" / "nse_bse_symbols.json"

_RETIRED = {"ZOMATO": "ETERNAL", "TATAMOTORS": "TMPV"}  # retired -> successor


def _entries(path: Path) -> dict:
    return {e["ticker"]: e for e in json.loads(path.read_text(encoding="utf-8"))}


def _ios_or_skip() -> dict:
    if not _IOS_JSON.is_file():
        pytest.skip("iOS project not present in this checkout")
    return _entries(_IOS_JSON)


def test_ios_directory_matches_backend_symbols():
    assert set(_ios_or_skip()) == set(_entries(_BACKEND_JSON))


def test_ios_directory_is_not_an_inline_literal():
    # StockDatabase decodes the bundled JSON; a hardcoded array would drift again.
    src = (_IOS_DIR / "StockDatabase.swift").read_text(encoding="utf-8")
    assert "StockEntry(ticker: \"" not in src


@pytest.mark.parametrize("path", [_BACKEND_JSON, _IOS_JSON], ids=["backend", "ios"])
def test_retired_tickers_absent_successors_present(path):
    if not path.is_file():
        pytest.skip("iOS project not present in this checkout")
    entries = _entries(path)
    for retired, successor in _RETIRED.items():
        assert retired not in entries
        assert successor in entries
    assert entries["AWL"]["name"] == "AWL Agri Business Ltd"
