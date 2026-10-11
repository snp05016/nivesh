import json
from contextlib import contextmanager

import pytest
from fastapi import HTTPException
from unittest.mock import MagicMock, patch, AsyncMock

from services.youtube_summary.summarizer import YouTubeSummaryService
from services.youtube_summary.transcript import TranscriptExtractor, _parse_video_id
from services.youtube_summary.schemas import YouTubeVideoSummaryResponse
from services.youtube_summary.providers import DeepSeekProvider, _empty_summary

def test_parse_video_id():
    assert _parse_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert _parse_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert _parse_video_id("dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert _parse_video_id("invalid") is None

@patch("services.youtube_summary.transcript.YouTubeTranscriptApi")
def test_transcript_extractor_youtube_api(mock_yt_api):
    mock_transcript_list = MagicMock()
    mock_transcript = MagicMock()
    mock_transcript.fetch.return_value = [{"start": 0.0, "text": "Hello world"}]
    mock_transcript_list.find_manually_created_transcript.return_value = mock_transcript
    mock_yt_api.list_transcripts.return_value = mock_transcript_list
    
    extractor = TranscriptExtractor()
    result = extractor.extract("dQw4w9WgXcQ")
    
    assert result is not None
    assert result["video_id"] == "dQw4w9WgXcQ"
    assert result["text"] == "Hello world"
    assert result["source"] == "youtube_api"

def test_transcript_extractor_no_fallback_without_captions(monkeypatch):
    # REG-14: no yt-dlp/description fallback; no public captions means no transcript.
    import sys
    import types
    fake = types.SimpleNamespace()
    fake.YouTubeTranscriptApi = MagicMock()
    fake.YouTubeTranscriptApi.list_transcripts.side_effect = Exception("Not available")
    fake.TranscriptsDisabled = type("TranscriptsDisabled", (Exception,), {})
    fake.NoTranscriptFound = type("NoTranscriptFound", (Exception,), {})
    monkeypatch.setitem(sys.modules, "youtube_transcript_api", fake)

    assert TranscriptExtractor().extract("dQw4w9WgXcQ") is None

@pytest.mark.asyncio
@patch("services.youtube_summary.summarizer.get_provider")
@patch("services.youtube_summary.summarizer.TranscriptExtractor")
@patch("services.youtube_summary.summarizer.YouTubeSummaryCache")
async def test_youtube_summary_service_summarize(mock_cache_cls, mock_extractor_cls, mock_get_provider):
    # Mock Extractor
    mock_extractor = MagicMock()
    mock_extractor.extract.return_value = {
        "video_id": "dQw4w9WgXcQ",
        "text": "This is a test transcript.",
        "source": "youtube_api",
        "hash": "testhash123",
        "char_count": 26,
        "segments": []
    }
    mock_extractor_cls.return_value = mock_extractor
    
    # Mock Cache (no hit)
    mock_cache = MagicMock()
    mock_cache.get.return_value = None
    mock_cache_cls.return_value = mock_cache
    
    # Mock Provider
    mock_provider = MagicMock()
    mock_provider.summarize_chunks = AsyncMock(return_value={
        "tldr": "Test TLDR",
        "key_points": ["Point 1"],
        "sentiment": "bullish",
        "confidence": 0.8
    })
    mock_get_provider.return_value = mock_provider
    
    service = YouTubeSummaryService()
    response = await service.summarize("dQw4w9WgXcQ")
    
    assert isinstance(response, YouTubeVideoSummaryResponse)
    assert response.video_id == "dQw4w9WgXcQ"
    assert response.summary.tldr == "Test TLDR"
    assert response.summary.sentiment == "bullish"
    assert response.source.cached is False
    assert mock_cache.set.called

@pytest.mark.asyncio
@patch("services.youtube_summary.summarizer.TranscriptExtractor")
@patch("services.youtube_summary.summarizer.YouTubeSummaryCache")
async def test_youtube_summary_service_cached(mock_cache_cls, mock_extractor_cls):
    mock_extractor = MagicMock()
    mock_extractor.extract.return_value = {
        "video_id": "dQw4w9WgXcQ",
        "text": "This is a test transcript.",
        "source": "youtube_api",
        "hash": "testhash123",
        "char_count": 26,
        "segments": []
    }
    mock_extractor_cls.return_value = mock_extractor
    
    mock_cache = MagicMock()
    mock_cache.get.return_value = {
        "tldr": "Cached TLDR",
        "key_points": ["Point 1"],
        "sentiment": "bearish",
        "confidence": 0.9
    }
    mock_cache_cls.return_value = mock_cache
    
    service = YouTubeSummaryService()
    response = await service.summarize("dQw4w9WgXcQ")
    
    assert response.summary.tldr == "Cached TLDR"
    assert response.source.cached is True


# ---------------------------------------------------------------------------
# GH-634: failures must raise HTTP errors, never return/cache a blank summary
# ---------------------------------------------------------------------------

_TRANSCRIPT = {
    "video_id": "dQw4w9WgXcQ",
    "text": "This is a test transcript.",
    "source": "youtube_api",
    "hash": "testhash123",
    "char_count": 26,
    "segments": [],
}


def _service(mock_cache_cls, mock_extractor_cls, transcript=_TRANSCRIPT, cached=None):
    mock_extractor = MagicMock()
    mock_extractor.extract.return_value = transcript
    mock_extractor_cls.return_value = mock_extractor
    mock_cache = MagicMock()
    mock_cache.get.return_value = cached
    mock_cache_cls.return_value = mock_cache
    return YouTubeSummaryService(), mock_cache


@pytest.mark.asyncio
@patch("services.youtube_summary.summarizer.TranscriptExtractor")
@patch("services.youtube_summary.summarizer.YouTubeSummaryCache")
async def test_transcript_unavailable_raises_404(mock_cache_cls, mock_extractor_cls):
    service, mock_cache = _service(mock_cache_cls, mock_extractor_cls, transcript=None)
    with pytest.raises(HTTPException) as exc_info:
        await service.summarize("dQw4w9WgXcQ")
    assert exc_info.value.status_code == 404
    assert not mock_cache.set.called


@pytest.mark.asyncio
@patch("services.youtube_summary.summarizer.TranscriptExtractor")
@patch("services.youtube_summary.summarizer.YouTubeSummaryCache")
async def test_unparsable_id_raises_400(mock_cache_cls, mock_extractor_cls):
    service, _ = _service(mock_cache_cls, mock_extractor_cls)
    with pytest.raises(HTTPException) as exc_info:
        await service.summarize("invalid")
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
@patch("services.youtube_summary.summarizer.get_provider")
@patch("services.youtube_summary.summarizer.TranscriptExtractor")
@patch("services.youtube_summary.summarizer.YouTubeSummaryCache")
async def test_provider_failure_raises_502_and_no_cache(mock_cache_cls, mock_extractor_cls, mock_get_provider):
    service, mock_cache = _service(mock_cache_cls, mock_extractor_cls)
    mock_provider = MagicMock()
    mock_provider.summarize_chunks = AsyncMock(side_effect=RuntimeError("secret upstream detail"))
    mock_get_provider.return_value = mock_provider

    with pytest.raises(HTTPException) as exc_info:
        await service.summarize("dQw4w9WgXcQ")
    assert exc_info.value.status_code == 502
    assert "secret upstream detail" not in str(exc_info.value.detail)
    assert not mock_cache.set.called


@pytest.mark.asyncio
@patch("services.youtube_summary.summarizer.get_provider")
@patch("services.youtube_summary.summarizer.TranscriptExtractor")
@patch("services.youtube_summary.summarizer.YouTubeSummaryCache")
async def test_empty_summary_not_cached(mock_cache_cls, mock_extractor_cls, mock_get_provider):
    service, mock_cache = _service(mock_cache_cls, mock_extractor_cls)
    mock_provider = MagicMock()
    mock_provider.summarize_chunks = AsyncMock(return_value=_empty_summary())
    mock_get_provider.return_value = mock_provider

    with pytest.raises(HTTPException) as exc_info:
        await service.summarize("dQw4w9WgXcQ")
    assert exc_info.value.status_code == 502
    assert not mock_cache.set.called


@pytest.mark.asyncio
@patch("services.youtube_summary.summarizer.get_provider")
@patch("services.youtube_summary.summarizer.TranscriptExtractor")
@patch("services.youtube_summary.summarizer.YouTubeSummaryCache")
async def test_empty_cached_row_is_regenerated(mock_cache_cls, mock_extractor_cls, mock_get_provider):
    service, mock_cache = _service(mock_cache_cls, mock_extractor_cls, cached=_empty_summary())
    mock_provider = MagicMock()
    mock_provider.summarize_chunks = AsyncMock(return_value={"tldr": "Fresh TLDR", "key_points": ["P"]})
    mock_get_provider.return_value = mock_provider

    response = await service.summarize("dQw4w9WgXcQ")
    assert response.summary.tldr == "Fresh TLDR"
    assert response.source.cached is False
    assert mock_provider.summarize_chunks.called


@pytest.mark.asyncio
async def test_deepseek_all_chunks_fail_raises():
    with patch("services.llm_utils.deepseek_chat", side_effect=RuntimeError("DeepSeek down")):
        with pytest.raises(RuntimeError):
            await DeepSeekProvider().summarize_chunks(["chunk one"])


@patch("services.youtube_summary.summarizer.TranscriptExtractor")
@patch("services.youtube_summary.summarizer.YouTubeSummaryCache")
def test_get_cached_ignores_empty_row(mock_cache_cls, mock_extractor_cls):
    service, _ = _service(mock_cache_cls, mock_extractor_cls)
    row = MagicMock()
    row.summary_json = json.dumps(_empty_summary())

    @contextmanager
    def fake_get_session():
        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = row
        yield session

    with patch("database.get_session", fake_get_session):
        assert service.get_cached("dQw4w9WgXcQ") is None
