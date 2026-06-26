"""LLM client implementations and factory for the trading agents framework.

This package provides a unified interface for interacting with various LLM
providers (OpenAI, Anthropic, Google, etc.) using LangChain under the hood.
"""

from .base_client import BaseLLMClient
from .factory import create_llm_client

__all__ = ["BaseLLMClient", "create_llm_client"]
