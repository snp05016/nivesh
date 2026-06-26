"""Azure OpenAI client implementation.

This module provides the Azure-specific implementation of the LLM client,
handling Azure's specific deployment naming and configuration requirements.
"""

import os
from typing import Any, Optional

from langchain_openai import AzureChatOpenAI

from .base_client import BaseLLMClient, normalize_content
from .validators import validate_model

_PASSTHROUGH_KWARGS = (
    "timeout", "max_retries", "api_key", "reasoning_effort", "temperature",
    "callbacks", "http_client", "http_async_client",
)


class NormalizedAzureChatOpenAI(AzureChatOpenAI):
    """AzureChatOpenAI with normalized content output."""

    def invoke(self, input, config=None, **kwargs):
        """Invoke the Azure OpenAI chat model and normalize the output.

        Args:
            input: The input messages or prompt to process.
            config: Optional configuration dictionary.
            **kwargs: Additional keyword arguments for the invocation.

        Returns:
            The normalized response from the LLM.
        """
        return normalize_content(super().invoke(input, config, **kwargs))


class AzureOpenAIClient(BaseLLMClient):
    """Client for Azure OpenAI deployments.

    Requires environment variables:
        AZURE_OPENAI_API_KEY: API key
        AZURE_OPENAI_ENDPOINT: Endpoint URL (e.g. https://<resource>.openai.azure.com/)
        AZURE_OPENAI_DEPLOYMENT_NAME: Deployment name
        OPENAI_API_VERSION: API version (e.g. 2025-03-01-preview)
    """

    def __init__(self, model: str, base_url: Optional[str] = None, **kwargs):
        """Initialize the Azure OpenAI client.

        Args:
            model: The name of the model to use.
            base_url: Optional base URL for the API endpoint.
            **kwargs: Additional client-specific configuration.
        """
        super().__init__(model, base_url, **kwargs)

    def get_llm(self) -> Any:
        """Return configured AzureChatOpenAI instance.

        Returns:
            A NormalizedAzureChatOpenAI instance configured with the provided settings.
        """
        self.warn_if_unknown_model()

        llm_kwargs = {
            "model": self.model,
            "azure_deployment": os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", self.model),
        }

        for key in _PASSTHROUGH_KWARGS:
            if key in self.kwargs:
                llm_kwargs[key] = self.kwargs[key]

        return NormalizedAzureChatOpenAI(**llm_kwargs)

    def validate_model(self) -> bool:
        """Azure accepts any deployed model name.

        Returns:
            Always returns True since validation depends on remote Azure deployments.
        """
        return True
