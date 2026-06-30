import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from services.youtube_summary.summarizer import YouTubeSummaryService
from services.youtube_summary.transcript import TranscriptExtractor, _parse_video_id
from services.youtube_summary.schemas import YouTubeVideoSummaryResponse

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

@patch("services.youtube_summary.transcript.yt_dlp")
@patch("services.youtube_summary.transcript.YouTubeTranscriptApi")
def test_transcript_extractor_yt_dlp_fallback(mock_yt_api, mock_yt_dlp):
    # Make youtube-transcript-api fail
    mock_yt_api.list_transcripts.side_effect = Exception("Not available")
    
    # Mock yt-dlp
    mock_ydl_instance = MagicMock()
    mock_ydl_instance.extract_info.return_value = {
        "description": "This is a fallback description " * 10 # make it > 200 chars
    }
    mock_yt_dlp.YoutubeDL.return_value.__enter__.return_value = mock_ydl_instance
    
    extractor = TranscriptExtractor()
    result = extractor.extract("dQw4w9WgXcQ")
    
    assert result is not None
    assert result["source"] == "yt_dlp"
    assert result["char_count"] > 200

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
