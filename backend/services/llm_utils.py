from __future__ import annotations

import logging
"""
Canonical LLM utilities for the Nivesh backend (ARCH-03 gateway).
The only place that constructs DeepSeek (OpenAI-compatible) and Anthropic
clients; every call made through deepseek_chat / claude_messages is written to
the token log. tests/test_llm_gateway.py fails if a client is built elsewhere.

Usage:
    from services.llm_utils import deepseek_chat, claude_messages, DEEPSEEK_MODEL
"""

import functools
import json
import os
import re
import time as _time
from typing import Any

import openai as _openai_lib

# Regex to strip unparsed DeepSeek thinking tags from output (fix 2.27)
_THINK_TAG_RE = re.compile(r"</?think(?:ing)?>", re.IGNORECASE)
_DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")

# ═════════════════════════════════════════════════════════════════════════════
# Model constants — canonical definitions
# ═════════════════════════════════════════════════════════════════════════════

# The only place model IDs live (tests/test_model_names.py enforces it). Override per
# deploy via env, e.g. after a frozen-input eval justifies a newer model.
HAIKU_MODEL = os.getenv("NIVESH_HAIKU_MODEL", "claude-haiku-4-5-20251001")  # Tier 2 — synthesis agents
SONNET_MODEL = os.getenv("NIVESH_SONNET_MODEL", "claude-sonnet-4-6")         # Tier 3 — final reformatter only
DEEPSEEK_MODEL = os.getenv("NIVESH_DEEPSEEK_MODEL", "deepseek-chat")         # Tier 1 — bulk agent tasks
DEEPSEEK_REASONER_MODEL = os.getenv("NIVESH_DEEPSEEK_REASONER_MODEL", "deepseek-reasoner")  # extreme scans

_CLAUDE_MAJOR_RE = re.compile(r"^claude-[a-z]+-(\d+)")


def sampling_kwargs(model: str) -> dict[str, Any]:
    """temperature=0 for Claude 4.x and older; {} for 5.x+, which reject non-default sampling (400)."""
    m = _CLAUDE_MAJOR_RE.match(model or "")
    if m and int(m.group(1)) >= 5:
        return {}
    return {"temperature": 0}


def contains_devanagari(text: object) -> bool:
    """Return True when AI text contains Hindi/Devanagari script."""
    return isinstance(text, str) and bool(_DEVANAGARI_RE.search(text))


# ═════════════════════════════════════════════════════════════════════════════
# DeepSeek client
# ═════════════════════════════════════════════════════════════════════════════

@functools.lru_cache(maxsize=1)
def get_deepseek_client() -> "_openai_lib.OpenAI":
    """Return the shared DeepSeek OpenAI-compatible client (built once, connections reused).

    The SDK's own retries (max_retries) cover 408/409/429/5xx and connection errors;
    callers never add a retry loop on top (LLM-17).
    """
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    return _openai_lib.OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com/v1",
        timeout=60.0,
        max_retries=2,
    )


# ═════════════════════════════════════════════════════════════════════════════
# DeepSeek chat — one SDK call, caller's token budget honoured
# ═════════════════════════════════════════════════════════════════════════════

def deepseek_chat(
    messages: list[dict],
    *,
    max_tokens: int = 1024,
    temperature: float = 0.3,
    log_endpoint: str | None = None,
    model: str | None = None,
) -> str:
    """Call DeepSeek via the OpenAI-compatible API and return the answer text.

    DEEPSEEK_MODEL (deepseek-chat) is a non-thinking model: the request uses the
    caller's max_tokens (clamped to 16..8192). DEEPSEEK_REASONER_MODEL spends
    output tokens on reasoning_content first, so it gets max_tokens + 8000
    headroom (capped at 16000) and no temperature.

    One SDK call; the client's max_retries handles transient errors, everything
    else (400/401/422, budget) raises straight to the caller. Returns '' when the
    model produced no content: reasoning_content is never returned as the answer.
    """
    from helpers import _log_token_usage  # local import avoids circular deps
    from services import llm_budget

    # Raises LlmBudgetExceeded before any spend once today's global cap is reached;
    # callers already treat a failed call as "AI unavailable".
    llm_budget.assert_global_budget()

    selected_model = model or DEEPSEEK_MODEL
    is_reasoner = selected_model == DEEPSEEK_REASONER_MODEL
    if is_reasoner:
        effective_max = min(max_tokens + 8000, 16000)
    else:
        effective_max = max(16, min(max_tokens, 8192))

    kwargs: dict = dict(
        model=selected_model,
        messages=messages,
        max_tokens=effective_max,
    )
    if not is_reasoner:
        kwargs["temperature"] = temperature  # deepseek-reasoner does not support temperature

    response = get_deepseek_client().chat.completions.create(**kwargs)

    # Every call is logged and metered (LLM-09, ARCH-03, LLM-02); unlabelled callers still show up in spend.
    if getattr(response, "usage", None) is not None:
        _log_token_usage(log_endpoint or llm_budget.current_feature() or "deepseek_unlabelled",
                         response.usage, selected_model)

    choice = response.choices[0]
    content = choice.message.content or ""
    if not content.strip():
        logging.info(f"[DeepSeek] empty content (finish_reason={getattr(choice, 'finish_reason', None)})")
        return ""
    # Strip unparsed <think>/</think> tags
    return _THINK_TAG_RE.sub("", content).strip()


_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*([\[{].*?[\]}])\s*```", re.DOTALL)


def extract_json_from_text(text: str) -> str:
    """Extract the primary JSON object or array from LLM output.

    Priority: a ```json fenced block, then the outermost {...} or [...] span
    (the earliest one that parses, so prose brackets before the payload are
    skipped), then the legacy ``` split. Returns the input stripped if nothing
    matches. Single implementation for orchestrator, helpers and routers.
    """
    text = text.strip()
    m = _FENCED_JSON_RE.search(text)
    if m:
        return m.group(1).strip()
    spans = []
    for opener, closer in (("{", "}"), ("[", "]")):
        start, end = text.find(opener), text.rfind(closer)
        if start != -1 and end > start:
            spans.append((start, text[start:end + 1]))
    spans.sort()
    for _, candidate in spans:
        try:
            json.loads(candidate)
            return candidate
        except ValueError:
            continue
    if spans:
        return spans[0][1]
    if "```" in text:
        parts = text.split("```")
        if len(parts) >= 2:
            return parts[1].strip().removeprefix("json").strip()
    return text


# ═════════════════════════════════════════════════════════════════════════════
# Anthropic (Claude) client + logged messages call
# ═════════════════════════════════════════════════════════════════════════════

def get_anthropic_client():
    """Return an Anthropic client. The only `anthropic.Anthropic(` call site."""
    import anthropic  # lazy: only paths that actually call Claude need the SDK

    return anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def claude_messages(*, model: str, messages: list[Any], max_tokens: int, feature: str, **kwargs):
    """client.messages.create with 3 attempts (1 s, 2 s backoff); logs usage under `feature`.

    kwargs pass straight through (system, temperature, ...). Re-raises the last error.
    """
    from helpers import _log_token_usage  # local import avoids circular deps
    from services import llm_budget

    llm_budget.assert_global_budget()  # LlmBudgetExceeded before any spend past the daily cap
    client = get_anthropic_client()
    for attempt in range(3):
        try:
            response = client.messages.create(model=model, max_tokens=max_tokens, messages=messages, **kwargs)
            break
        except Exception as exc:
            logging.info(f"[Anthropic] {feature} attempt {attempt + 1}/3 failed: {exc}")
            if attempt == 2:
                raise
            _time.sleep(1.0 * (2 ** attempt))
    _log_token_usage(feature, response.usage, model)
    return response


# ═════════════════════════════════════════════════════════════════════════════
# Backward-compatible aliases for callers that still use the private names
# ═════════════════════════════════════════════════════════════════════════════

_get_deepseek_client = get_deepseek_client
_deepseek_chat = deepseek_chat
