# Import from llm_utils (the canonical definition; orchestrator re-exports these
# but pulls in the heavy tradingagents graph, which isn't importable everywhere).
from services.llm_utils import HAIKU_MODEL, SONNET_MODEL, DEEPSEEK_MODEL


def test_model_names_are_current_and_valid():
    # Tier 2 synthesis — Haiku 4.5.
    assert HAIKU_MODEL == "claude-haiku-4-5-20251001"
    # Tier 3 reformatter — Sonnet 4.6. The old "claude-3-5-sonnet-latest" alias
    # 404s on the Anthropic API, so it must not reappear.
    assert SONNET_MODEL == "claude-sonnet-4-6"
    assert "3-5-sonnet-latest" not in SONNET_MODEL
    # Tier 1 bulk agents — DeepSeek.
    assert DEEPSEEK_MODEL == "deepseek-chat"
