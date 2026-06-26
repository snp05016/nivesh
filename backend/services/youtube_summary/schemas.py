"""Pydantic v2 request/response schemas for the YouTube summary service."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TimestampEntry(BaseModel):
    start_seconds: int = 0
    label: str = ""
    summary: str = ""


class SummaryContent(BaseModel):
    tldr: str = ""
    key_points: list[str] = Field(default_factory=list)
    finance_insights: list[str] = Field(default_factory=list)
    tickers_mentioned: list[str] = Field(default_factory=list)
    risks_or_red_flags: list[str] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)
    sentiment: str = "neutral"  # bullish|bearish|neutral|mixed
    confidence: float = 0.0


class SourceMetadata(BaseModel):
    transcript_source: str = ""
    summary_provider: str = ""
    cached: bool = False
    transcript_hash: str = ""
    estimated_input_tokens: int = 0
    estimated_output_tokens: int = 0


class YouTubeVideoSummaryResponse(BaseModel):
    video_id: str
    url: str
    title: str = ""
    channel: str = ""
    duration_seconds: int = 0
    summary: SummaryContent = Field(default_factory=SummaryContent)
    timestamps: list[TimestampEntry] = Field(default_factory=list)
    source: SourceMetadata = Field(default_factory=SourceMetadata)
