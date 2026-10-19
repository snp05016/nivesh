"""Task 2 — engine is bounded; reasoner token headroom capped; deepseek-chat gets the caller's budget (LLM-17)."""


def test_extreme_config_is_bounded(monkeypatch):
    # conftest mocks tradingagents → DEFAULT_CONFIG is a MagicMock; use a real dict.
    monkeypatch.setattr("services.orchestrator.DEFAULT_CONFIG", {}, raising=False)
    from services.orchestrator import build_ta_config
    c = build_ta_config("extreme")
    assert c["max_debate_rounds"] == 1
    assert c["max_risk_discuss_rounds"] == 1
    assert c["max_tokens"] == 4000
    assert c["quick_think_llm"] == "deepseek-reasoner"
    assert c.get("recursion_limit") and c["recursion_limit"] <= 150
    assert c.get("analyst_tool_loop_cap") == 3


def test_standard_config_unchanged(monkeypatch):
    monkeypatch.setattr("services.orchestrator.DEFAULT_CONFIG", {}, raising=False)
    from services.orchestrator import build_ta_config
    c = build_ta_config("standard")
    assert c["max_debate_rounds"] == 1
    assert c["max_risk_discuss_rounds"] == 1
    assert c["max_tokens"] == 2000  # LLM-18: sent straight to the chat model, 1000 truncated reports


class _Msg:
    content = "ok"
    reasoning_content = ""


class _Choice:
    message = _Msg()


class _Resp:
    choices = [_Choice()]
    usage = None


def _fake_client(captured):
    class _Client:
        class chat:
            class completions:
                @staticmethod
                def create(**kw):
                    captured.update(kw)
                    return _Resp()
    return _Client()


def test_reasoner_effective_max_capped(monkeypatch):
    import services.llm_utils as lu
    captured = {}
    monkeypatch.setattr(lu, "get_deepseek_client", lambda: _fake_client(captured))
    lu.deepseek_chat([{"role": "user", "content": "hi"}],
                     max_tokens=8000, model="deepseek-reasoner")
    # old behaviour was 8000*8 = 64000; must now be capped at 16000
    assert captured["max_tokens"] == 16000


def test_non_pro_path_uses_caller_budget(monkeypatch):
    """LLM-17: deepseek-chat is not a thinking model, so max_tokens is passed through (no 5x)."""
    import services.llm_utils as lu
    captured = {}
    monkeypatch.setattr(lu, "get_deepseek_client", lambda: _fake_client(captured))
    lu.deepseek_chat([{"role": "user", "content": "hi"}],
                     max_tokens=512, model="deepseek-chat")
    assert captured["max_tokens"] == 512
