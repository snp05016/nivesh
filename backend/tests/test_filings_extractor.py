"""GH-623: NSE filings scraper must use the shared NSE session (correct Referer)."""
import inspect

import services.filings_extractor as fe
import services.nse_client as nse_client


class _FakeResp:
    def raise_for_status(self):
        pass

    def json(self):
        return [{
            "symbol": "TCS",
            "sm_name": "Tata Consultancy",
            "desc": "Financial Results",
            "an_dt": "10-Oct-2026 10:00:00",
            "attchmntText": "Q2",
        }]


class _FakeSession:
    def __init__(self):
        self.urls = []

    def get(self, url, timeout=None):
        self.urls.append(url)
        return _FakeResp()


def test_nse_scrape_uses_shared_session(monkeypatch):
    session = _FakeSession()
    monkeypatch.setattr(nse_client, "_nse_session", lambda: session)

    result = fe._scrape_nse_filings()

    assert result[0] == {
        "ticker": "TCS",
        "company": "Tata Consultancy",
        "filing_type": "Financial Results",
        "filed_date": "10-Oct-2026 10:00:00",
        "description": "Q2",
    }
    assert session.urls and session.urls[0].startswith("https://www.nseindia.com/api/")


def test_no_misspelled_domain():
    assert "niseindia" not in inspect.getsource(fe)
