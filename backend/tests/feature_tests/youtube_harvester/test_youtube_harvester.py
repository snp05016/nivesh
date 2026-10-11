import asyncio

from services import youtube_harvester


def test_portfolio_harvest_runs_without_searching_youtube(monkeypatch):
    # REG-03: the portfolio harvest only tags registry rows already in the DB.
    def _no_network(*_a, **_k):
        raise AssertionError("portfolio harvest must not search YouTube")

    monkeypatch.setattr(youtube_harvester.requests, "get", _no_network)
    monkeypatch.setattr(youtube_harvester.yt_dlp, "YoutubeDL", _no_network)
    monkeypatch.setattr(youtube_harvester, "get_company_name", lambda t: t)

    result = asyncio.run(youtube_harvester.harvest_portfolio_videos())

    assert "error" not in result, result
    assert {"tickers_processed", "videos_added"} <= result.keys()
