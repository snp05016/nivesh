import pytest
from services.orchestrator import HAIKU_MODEL, SONNET_MODEL, DEEPSEEK_MODEL

def test_model_names_are_valid():
    assert "4-5" not in HAIKU_MODEL
    assert "4-6" not in SONNET_MODEL
    assert "v4-flash" not in DEEPSEEK_MODEL
    
    assert HAIKU_MODEL == "claude-3-5-haiku-20241022"
    assert SONNET_MODEL == "claude-3-5-sonnet-latest"
    assert DEEPSEEK_MODEL == "deepseek-chat"
