"""REG-14: no cookie-authenticated YouTube access, audio download, page scraping
or publisher-column scraping in backend services."""

import asyncio
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_BACKEND = Path(__file__).resolve().parents[1]
_BANNED = (
    "cookiefile", "cookies.txt", "bestaudio", "ytsearch",
    "yt_dlp", "yt-dlp", "faster_whisper", "faster-whisper",
)


def test_services_and_requirements_have_no_youtube_scraping():
    files = sorted((_BACKEND / "services").rglob("*.py")) + [_BACKEND / "requirements.txt"]
    hits = [
        f"{p.relative_to(_BACKEND)}: {term}"
        for p in files
        for term in _BANNED
        if term in p.read_text(encoding="utf-8", errors="replace")
    ]
    assert hits == []


def test_expert_harvester_scrapes_no_publisher_columns():
    text = (_BACKEND / "services" / "harvester_expert.py").read_text(encoding="utf-8")
    assert "moneycontrol.com" not in text
    assert "cnbctv18.com" not in text
    assert "scraperapi" not in text.lower()


def test_get_transcript_raises_without_public_captions(monkeypatch):
    from services import transcript_engine

    monkeypatch.setattr(transcript_engine, "_fetch_youtube_api", lambda *_a, **_k: None)
    with pytest.raises(transcript_engine.TranscriptError):
        asyncio.run(transcript_engine.get_transcript("abcdefghijk", 600.0))


def test_transcript_api_called_without_cookie_session(monkeypatch):
    from services import transcript_engine

    api_cls = MagicMock()
    api_cls.return_value.fetch.return_value = [{"text": "word " * 100, "start": 0.0, "duration": 30.0}]
    fake = types.SimpleNamespace()
    fake.YouTubeTranscriptApi = api_cls
    fake.TranscriptsDisabled = type("TranscriptsDisabled", (Exception,), {})
    fake.NoTranscriptFound = type("NoTranscriptFound", (Exception,), {})
    monkeypatch.setitem(sys.modules, "youtube_transcript_api", fake)

    result = transcript_engine._fetch_youtube_api("abcdefghijk", 0.0)

    assert result is not None and result["source"] == "youtube_api"
    api_cls.assert_called_once_with()
