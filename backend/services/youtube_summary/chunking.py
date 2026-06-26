"""Transcript chunking — splits long text into LLM-safe segments."""

from __future__ import annotations

import re
from typing import List


# Sentence-boundary split: end of sentence followed by whitespace
_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+")


class TranscriptChunker:
    """Splits transcript text into overlapping sentence-boundary-aware chunks."""

    def chunk(self, text: str, max_chars: int = 8000) -> List[str]:
        """Split text into chunks of at most max_chars, respecting sentence boundaries.

        Returns [full_text] unchanged when text fits in a single chunk.
        """
        text = text.strip()
        if not text:
            return []

        if len(text) <= max_chars:
            return [text]

        sentences = _SENTENCE_BOUNDARY_RE.split(text)
        chunks: List[str] = []
        current_parts: List[str] = []
        current_len = 0

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # If a single sentence exceeds max_chars, hard-split it
            if len(sentence) > max_chars:
                # Flush current buffer first
                if current_parts:
                    chunks.append(" ".join(current_parts))
                    current_parts = []
                    current_len = 0
                for i in range(0, len(sentence), max_chars):
                    chunks.append(sentence[i : i + max_chars])
                continue

            if current_len + len(sentence) + 1 > max_chars:
                if current_parts:
                    chunks.append(" ".join(current_parts))
                current_parts = [sentence]
                current_len = len(sentence)
            else:
                current_parts.append(sentence)
                current_len += len(sentence) + 1

        if current_parts:
            chunks.append(" ".join(current_parts))

        return chunks
