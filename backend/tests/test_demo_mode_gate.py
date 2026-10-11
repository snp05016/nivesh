"""FAKE-23: demo money/KYC-mock routes are unreachable unless DEMO_MODE=true.

Loans (hash-based mock credit score), demo bank links, the demo finance
tracker, demo FD schemes/bookings and the mock KYC fraud-signal summary answer
404 in production (DEMO_MODE unset). KYC consents stay reachable.
"""
import pytest

import config.settings

_GATED = (
    ("get", "/api/finance/loan-offers"),
    ("post", "/api/finance/loan-applications"),
    ("get", "/api/fixed-deposits/schemes"),
    ("post", "/api/fixed-deposits/bookings"),
    ("get", "/api/kyc/fraud-signals"),
)


@pytest.mark.parametrize("method, path", _GATED)
def test_demo_routes_404_without_demo_mode(client, auth_headers, monkeypatch, method, path):
    monkeypatch.setattr(config.settings, "DEMO_MODE", False)
    kwargs = {"headers": auth_headers}
    if method == "post":
        kwargs["json"] = {}
    resp = getattr(client, method)(path, **kwargs)
    assert resp.status_code == 404, (path, resp.text)


def test_kyc_consents_not_gated(client, auth_headers, monkeypatch):
    monkeypatch.setattr(config.settings, "DEMO_MODE", False)
    assert client.get("/api/kyc/consents", headers=auth_headers).status_code != 404


def test_demo_routes_open_with_demo_mode(client, monkeypatch):
    monkeypatch.setattr(config.settings, "DEMO_MODE", True)
    assert client.get("/api/fixed-deposits/schemes").status_code == 200
