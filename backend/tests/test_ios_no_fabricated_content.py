"""Static guards: iOS sources must not ship fabricated user data.

FAKE-13 (closed #522): the home-screen widget timeline used hardcoded demo
portfolio, P&L and NIFTY literals shown to every user as their own data.
"""
from pathlib import Path

import pytest

IOS_ROOT = Path(__file__).resolve().parents[2] / "ios" / "StockApp" / "stockme"

if not IOS_ROOT.is_dir():  # backend-only checkout (e.g. the server) has no iOS tree
    pytest.skip("iOS sources not present", allow_module_level=True)


def test_widget_has_no_hardcoded_portfolio():
    src = (IOS_ROOT / "NiveshWidget" / "NiveshWidget.swift").read_text(encoding="utf-8")
    for literal in ("1250400", "22450", "45000"):
        assert literal not in src, f"widget ships fabricated literal {literal}"
    # The widget must read the App Group snapshot the app writes.
    assert 'UserDefaults(suiteName: Self.suite)' in src
    assert "Open Nivesh to sync" in src


def test_widget_and_app_share_app_group():
    group = "group.saumypatel.stockme"
    for rel in ("stockme.entitlements", "NiveshWidget/NiveshWidget.entitlements"):
        assert group in (IOS_ROOT / rel).read_text(encoding="utf-8"), rel
    store = (IOS_ROOT / "stockme" / "Utilities" / "WidgetSnapshotStore.swift").read_text(encoding="utf-8")
    assert f'"{group}"' in store
