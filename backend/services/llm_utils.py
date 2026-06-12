"""
Canonical LLM utilities for the Nivesh backend.
Single source of truth for DeepSeek client construction, chat completion,
and model constants.  Previously triplicated across orchestrator.py,
analysis.py, portfolio.py, and advisor_harvester.py.

Usage:
    from services.llm_utils import deepseek_chat, get_deepseek_client, DEEPSEEK_MODEL
"""

from __future__ import annotations

import os
import re
import time as _time

import openai as _openai_lib

# Regex to strip unparsed DeepSeek thinking tags from output (fix 2.27)
_THINK_TAG_RE = re.compile(r"</?think(?:ing)?>", re.IGNORECASE)

# ═════════════════════════════════════════════════════════════════════════════
# Model constants — canonical definitions
# ═════════════════════════════════════════════════════════════════════════════

HAIKU_MODEL = "claude-haiku-4-5-20251001"  # Tier 2 — synthesis agents
SONNET_MODEL = "claude-3-5-sonnet-latest"   # Tier 3 — final reformatter only
DEEPSEEK_MODEL = "deepseek-chat"            # Tier 1 — bulk agent tasks


# ═════════════════════════════════════════════════════════════════════════════
# DeepSeek client
# ═════════════════════════════════════════════════════════════════════════════

def get_deepseek_client() -> "_openai_lib.OpenAI":
    """Return a lazily-constructed DeepSeek OpenAI-compatible client."""
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    return _openai_lib.OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com/v1",
        timeout=60.0,
    )


# ═════════════════════════════════════════════════════════════════════════════
# DeepSeek chat — with reasoning_content fallback & exponential backoff
# ═════════════════════════════════════════════════════════════════════════════

def deepseek_chat(
    messages: list[dict],
    *,
    max_tokens: int = 512,
    temperature: float = 0.3,
    log_endpoint: str | None = None,
    model: str | None = None,
) -> str:
    """Call DeepSeek V4 Flash/Pro via OpenAI-compatible API.

    V4 Flash/Pro are thinking models — reasoning_content consumes max_tokens
    before content is generated.  We inflate the requested max_tokens to
    leave room for internal reasoning, then return content (or
    reasoning_content as fallback).

    When model is 'deepseek-v4-pro', enables thinking mode with max reasoning effort.
    Retries up to 3 times with exponential backoff (2 s, 4 s, 8 s).
    """
    from helpers import _log_token_usage  # local import avoids circular deps

    selected_model = model or DEEPSEEK_MODEL
    is_pro = selected_model == "deepseek-reasoner"
    client = get_deepseek_client()
    last_exc: Exception | None = None
    # Reasoner (is_pro) needs headroom for reasoning_content, but the old `max_tokens * 8`
    # inflated extreme calls to 64K-128K tokens — a primary cause of 15-20 min runaways.
    # Cap the reasoner headroom; leave the non-pro `* 5` path UNCHANGED (5 external callers
    # depend on it: portfolio red-flags/macro/trade-journal, advisor harvester, morning briefs).
    if is_pro:
        effective_max = min(max_tokens + 8000, 16000)
    else:
        effective_max = max(max_tokens * 5, 512)

    for attempt in range(3):
        try:
            kwargs: dict = dict(
                model=selected_model,
                messages=messages,
                max_tokens=effective_max,
                temperature=temperature,
            )
            if is_pro:
                kwargs.pop("temperature", None) # deepseek-reasoner does not support temperature

            response = client.chat.completions.create(**kwargs)

            if log_endpoint and hasattr(response, "usage"):
                _log_token_usage(log_endpoint, response.usage)

            choice = response.choices[0]
            content = choice.message.content or ""

            # If content empty (all tokens consumed by reasoning), fall back
            if not content.strip():
                reasoning = getattr(choice.message, "reasoning_content", None) or ""
                if reasoning.strip():
                    content = reasoning
            # Strip unparsed <think>/</think> tags (DeepSeek V4 Flash artifact)
            content = _THINK_TAG_RE.sub("", content).strip()
            return content

        except Exception as exc:
            last_exc = exc
            print(f"[DeepSeek] Attempt {attempt + 1}/3 failed: {exc}")
            if attempt < 2:
                _time.sleep(2.0 * (2 ** attempt))

    raise RuntimeError(
        f"DeepSeek call failed after 3 retries: {last_exc}"
    ) from last_exc


# ═════════════════════════════════════════════════════════════════════════════
# Backward-compatible aliases for callers that still use the private names
# ═════════════════════════════════════════════════════════════════════════════

_get_deepseek_client = get_deepseek_client
_deepseek_chat = deepseek_chat
