"""LLM-25: model IDs live only in services/llm_utils.py, and 5.x Claude requests carry no
non-default sampling parameters."""
import ast
import re
from pathlib import Path
from unittest.mock import MagicMock

# Import from llm_utils (the canonical definition; orchestrator re-exports these
# but pulls in the heavy tradingagents graph, which isn't importable everywhere).
from services.llm_utils import HAIKU_MODEL, SONNET_MODEL, DEEPSEEK_MODEL, sampling_kwargs

BACKEND = Path(__file__).resolve().parents[1]
_MODEL_ID_RE = re.compile(r"^(claude-(haiku|sonnet|opus)|deepseek-(chat|reasoner|v\d))")
_SKIP_DIRS = {"venv", ".venv", "tradingagents-core", "tests", "tests_suite"}
# Pricing-table keys are substring matchers for cost estimates, not request IDs.
_ALLOWED = {"services/llm_utils.py", "core/dashboard_state.py"}


def test_model_ids_centralised():
    offenders = []
    for path in BACKEND.rglob("*.py"):
        rel = path.relative_to(BACKEND)
        if rel.parts[0] in _SKIP_DIRS or "site-packages" in rel.parts or rel.as_posix() in _ALLOWED:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                    and _MODEL_ID_RE.match(node.value):
                offenders.append(f"{rel.as_posix()}:{node.lineno} {node.value!r}")
    assert not offenders, "import model IDs from services.llm_utils: " + ", ".join(offenders)


def test_model_constants_valid():
    assert HAIKU_MODEL and SONNET_MODEL and DEEPSEEK_MODEL
    # The old "claude-3-5-sonnet-latest" alias 404s on the Anthropic API.
    assert "3-5-sonnet-latest" not in SONNET_MODEL


def test_sampling_kwargs_by_generation():
    assert sampling_kwargs("claude-sonnet-4-6") == {"temperature": 0}
    assert sampling_kwargs("claude-haiku-4-5-20251001") == {"temperature": 0}
    assert sampling_kwargs("claude-sonnet-5-5") == {}
    assert sampling_kwargs("claude-haiku-5-5") == {}


def test_reformat_request_caches_system_prompt_and_drops_temperature_on_5x(monkeypatch):
    from services import orchestrator

    client = MagicMock()
    msg = MagicMock()
    msg.content = [MagicMock(text='{"signal": "HOLD"}')]
    client.messages.create.return_value = msg
    monkeypatch.setattr(orchestrator, "get_anthropic_client", lambda: client)
    monkeypatch.setattr(orchestrator, "SONNET_MODEL", "claude-sonnet-5-5")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test_key")
    monkeypatch.setattr("time.sleep", lambda _s: None)

    try:
        orchestrator.reformat_with_claude("raw analysis text", "TCS.NS", "NSE")
    except Exception:
        pass  # only the outgoing request matters here

    kwargs = client.messages.create.call_args_list[0].kwargs
    assert kwargs["model"] == "claude-sonnet-5-5"
    assert "temperature" not in kwargs
    assert kwargs["system"][0]["cache_control"] == {"type": "ephemeral"}
