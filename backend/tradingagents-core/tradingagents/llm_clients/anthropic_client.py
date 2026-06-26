"""Anthropic Claude client implementation.

This module provides the Anthropic-specific implementation of the LLM client,
handling Claude's specific capabilities such as the extended thinking parameter.
"""

import re
from typing import Any, Optional

from langchain_anthropic import ChatAnthropic

from .base_client import BaseLLMClient, normalize_content
from .validators import validate_model

_PASSTHROUGH_KWARGS = (
    "timeout", "max_retries", "api_key", "max_tokens", "temperature",
    "callbacks", "http_client", "http_async_client", "effort",
)

# Anthropic's extended-thinking ``effort`` parameter is accepted by Opus 4.5+
# and Sonnet 4.5+ only. Haiku (any version shipped to date) 400s with
# ``"This model does not support the effort parameter"`` (#831). Future
# ``claude-{opus,sonnet}-X-Y`` releases inherit effort support via the
# forward-compat pattern below; future Haiku stays excluded by default.
_EFFORT_EXACT = {
    "claude-mythos-preview",  # non-standard preview name; effort-capable
}
_EFFORT_PATTERN = re.compile(r"^claude-(opus|sonnet)-\d+-\d+$")


def _supports_effort(model: str) -> bool:
    """Whether Anthropic accepts the ``effort`` parameter for this model.

    Args:
        model: The model identifier to check.

    Returns:
        True if the model accepts the effort parameter, False otherwise.
    """
    model_lc = model.lower()
    return model_lc in _EFFORT_EXACT or bool(_EFFORT_PATTERN.match(model_lc))


class NormalizedChatAnthropic(ChatAnthropic):
    """ChatAnthropic with normalized content output.

    Claude models with extended thinking or tool use return content as a
    list of typed blocks. This normalizes to string for consistent
    downstream handling.
    """

    def invoke(self, input, config=None, **kwargs):
        """Invoke the Anthropic Claude chat model and normalize the output.

        Args:
            input: The input messages or prompt to process.
            config: Optional configuration dictionary.
            **kwargs: Additional keyword arguments for the invocation.

        Returns:
            The normalized response from the LLM.
        """
        return normalize_content(super().invoke(input, config, **kwargs))


class AnthropicClient(BaseLLMClient):
    """Client for Anthropic Claude models."""

    def __init__(self, model: str, base_url: Optional[str] = None, **kwargs):
        """Initialize the Anthropic Claude client.

        Args:
            model: The name of the model to use.
            base_url: Optional base URL for the API endpoint.
            **kwargs: Additional client-specific configuration.
        """
        super().__init__(model, base_url, **kwargs)

    def get_llm(self) -> Any:
        """Return configured ChatAnthropic instance.

        Returns:
            A NormalizedChatAnthropic instance configured with the provided settings.
        """
        self.warn_if_unknown_model()
        llm_kwargs = {"model": self.model}

        if self.base_url:
            llm_kwargs["base_url"] = self.base_url

        for key in _PASSTHROUGH_KWARGS:
            if key not in self.kwargs:
                continue
            if key == "effort" and not _supports_effort(self.model):
                continue
            llm_kwargs[key] = self.kwargs[key]
        model_kwargs = self.kwargs.get("model_kwargs", {})
        if "extra_body" not in model_kwargs:
            model_kwargs["extra_body"] = {}
        # Enable Anthropic automatic prompt caching
        if "cache_control" not in model_kwargs["extra_body"]:
            model_kwargs["extra_body"]["cache_control"] = {"type": "ephemeral"}
        
        llm_kwargs["model_kwargs"] = model_kwargs

        return NormalizedChatAnthropic(**llm_kwargs)

    def validate_model(self) -> bool:
        """Validate model for Anthropic.

        Returns:
            True if the model is a valid Anthropic model, False otherwise.
        """
        return validate_model("anthropic", self.model)
