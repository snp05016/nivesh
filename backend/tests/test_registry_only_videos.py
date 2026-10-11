"""REG-03: only videos from SEBI-registered registry channels are stored, served on the
home feed, tagged to holdings or summarised, and the summary prompt makes no
registration claim and asks for no action items."""
import asyncio
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from fastapi import HTTPException

import database
from models.db_models import Portfolio, YouTubeVideo
from services import youtube_harvester
from services.youtube_harvester import _upsert_video


def _video(video_id: str, sebi_reg, title: str = "Market wrap", view_count: int = 0, **extra) -> dict:
    return {
        "video_id": video_id, "title": title, "channel_name": "Some Channel",
        "video_url": f"https://www.youtube.com/watch?v={video_id}",
        "published_at": datetime.now(timezone.utc).isoformat(),
        "view_count": view_count, "source": "api_search", "sebi_reg": sebi_reg, **extra,
    }


def _row(video_id: str) -> Any:
    with database.get_session() as session:
        return session.query(YouTubeVideo).filter(YouTubeVideo.video_id == video_id).first()


def _insert(*videos: dict) -> None:
    with database.get_session() as session:
        for v in videos:
            session.add(YouTubeVideo(
                video_id=v["video_id"], title=v["title"], channel_name=v["channel_name"],
                video_url=v["video_url"], published_at=datetime.now(timezone.utc).replace(tzinfo=None),
                view_count=v["view_count"], source=v["source"], sebi_reg=v["sebi_reg"],
                matched_ticker=v.get("matched_ticker"),
            ))
        session.commit()


def test_upsert_rejects_unregistered():
    with database.get_session() as session:
        assert _upsert_video(session, _video("REG03unreg1", None)) is False
        assert _upsert_video(session, _video("REG03reg001", "INH-TEST")) is True
        session.commit()

    assert _row("REG03unreg1") is None
    assert _row("REG03reg001") is not None


def test_home_feed_excludes_unregistered(client):
    _insert(
        _video("REG03feedUn", None, title="Unregistered tip", view_count=2_000_000_000),
        _video("REG03feedOk", "INH-TEST", title="Registry video", view_count=1_900_000_000),
    )

    resp = client.get("/api/v1/home-feed?user_id=0")

    assert resp.status_code == 200, resp.text
    ids = {v["video_id"] for v in resp.json()["youtube_videos"]}
    assert "REG03feedOk" in ids
    assert "REG03feedUn" not in ids
    assert all(v["sebi_reg"] for v in resp.json()["youtube_videos"])


def test_summary_403_for_non_registry(client, auth_headers, monkeypatch):
    from routers import youtube_summary as yt_router
    get_service = MagicMock()
    monkeypatch.setattr(yt_router, "_get_service", get_service)
    _insert(_video("REG03sumUn1", None))

    for vid in ("REG03notInD", "REG03sumUn1"):
        resp = client.post("/api/v1/youtube/summary", headers=auth_headers,
                           json={"url": f"https://www.youtube.com/watch?v={vid}"})
        assert resp.status_code == 403, resp.text
        assert client.get(f"/api/v1/youtube/summary/{vid}", headers=auth_headers).status_code == 404

    get_service.return_value.summarize.assert_not_called()
    get_service.return_value.get_cached.assert_not_called()


def test_summary_checks_and_summarises_the_same_id(client, auth_headers, monkeypatch):
    """A URL smuggling a registered ID past the check must not summarise another ID."""
    from routers import youtube_summary as yt_router
    get_service = MagicMock()
    summarize = get_service.return_value.summarize = AsyncMock(
        side_effect=HTTPException(status_code=418, detail="reached summarize"))
    monkeypatch.setattr(yt_router, "_get_service", get_service)
    _insert(_video("REG03sumReg", "INH-TEST"))

    resp = client.post("/api/v1/youtube/summary", headers=auth_headers,
                       json={"url": "https://www.youtube.com/xembed/REG03sumReg?v=REG03sumUn2"})
    assert resp.status_code == 403, resp.text
    summarize.assert_not_called()

    resp = client.post("/api/v1/youtube/summary", headers=auth_headers,
                       json={"url": "https://www.youtube.com/watch?v=REG03sumReg"})
    assert resp.status_code == 418, resp.text
    summarize.assert_awaited_once_with(url_or_id="REG03sumReg", force_refresh=False)


def test_is_registry_video():
    from services.youtube_summary.summarizer import is_registry_video
    _insert(_video("REG03isReg1", "INH-TEST"), _video("REG03isUnr1", None))

    assert is_registry_video("REG03isReg1") is True
    assert is_registry_video("REG03isUnr1") is False
    assert is_registry_video("REG03absent") is False


def test_prompt_has_no_registration_claim():
    from services.youtube_summary import providers
    assert "SEBI-registered" not in providers._SYSTEM_PROMPT
    assert "action_items" not in providers._SYSTEM_PROMPT


def test_built_response_never_carries_action_items():
    from services.youtube_summary.summarizer import YouTubeSummaryService
    service = YouTubeSummaryService.__new__(YouTubeSummaryService)  # no extractor/cache needed
    resp = service._build_response(
        video_id="REG03build1", video_url="https://www.youtube.com/watch?v=REG03build1",
        summary_dict={"tldr": "x", "key_points": ["y"], "action_items": ["Buy below 50"]},
        transcript_source="cached", transcript_chars=0, from_cache=True,
        provider_name="cached", chunks_processed=0,
    )
    assert resp.summary.action_items == []


def test_portfolio_harvest_tags_registry_videos_without_searching(monkeypatch):
    def _no_network(*_a, **_k):
        raise AssertionError("portfolio harvest must not search YouTube")

    monkeypatch.setattr(youtube_harvester.requests, "get", _no_network)
    monkeypatch.setattr(youtube_harvester.yt_dlp, "YoutubeDL", _no_network)
    monkeypatch.setattr(youtube_harvester, "get_company_name",
                        lambda t: "Regtag Industries" if t == "REGTAGX" else t)
    with database.get_session() as session:
        session.add(Portfolio(user_id=990001, ticker="REGTAGX", company_name="Regtag Industries",
                              shares=1, buy_price=1, group_name="holdings"))
        session.commit()
    _insert(
        _video("REG03tagReg", "INH-TEST", title="Regtag Industries Q2 results review"),
        _video("REG03tagUnr", None, title="Regtag Industries multibagger tip"),
        _video("REG03tagOth", "INH-TEST", title="REGTAGXYZ is a different word"),
    )

    result = asyncio.run(youtube_harvester.harvest_portfolio_videos())

    assert "error" not in result, result
    assert result["by_ticker"]["REGTAGX"] == 1
    assert _row("REG03tagReg").matched_ticker == "REGTAGX"
    assert _row("REG03tagUnr").matched_ticker is None
    assert _row("REG03tagOth").matched_ticker is None
