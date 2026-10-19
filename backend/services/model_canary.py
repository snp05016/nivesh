"""Daily model-id canary (I08): a one-token request to every configured model.

A retired or renamed model id otherwise only shows up as degraded user features. A failure
raises CanaryFailure, which job_runs.tracked records and alerts on. Switched off with env
CANARY_ENABLED=0 (an ops job, not a server flag) when all LLM spend must be zero. Never logs
prompts or keys.
"""
import logging
import os

from services import llm_utils

try:
    from services.llm_budget import LlmBudgetExceeded
except ImportError:  # pragma: no cover - the budget module is optional here
    class LlmBudgetExceeded(RuntimeError):
        pass

logger = logging.getLogger(__name__)

_OFF = {"0", "false", "off", "no"}
_MESSAGES = [{"role": "user", "content": "ping"}]


class CanaryFailure(RuntimeError):
    """At least one model id failed its canary request."""


def _models() -> list[str]:
    models = [llm_utils.DEEPSEEK_MODEL, llm_utils.HAIKU_MODEL, llm_utils.SONNET_MODEL]
    models += [m.strip() for m in os.getenv("CANARY_EXTRA_MODELS", "").split(",") if m.strip()]
    return list(dict.fromkeys(models))


def _ping(model: str) -> str:
    if model.startswith("deepseek"):
        if not os.getenv("DEEPSEEK_API_KEY"):
            return "skipped_no_key"
        llm_utils.deepseek_chat(
            _MESSAGES, max_tokens=1, temperature=0, model=model, log_endpoint="model_canary",
        )
    elif model.startswith("claude"):
        if not os.getenv("ANTHROPIC_API_KEY"):
            return "skipped_no_key"
        llm_utils.claude_messages(model=model, messages=_MESSAGES, max_tokens=1, feature="model_canary")
    else:
        return "skipped_unknown_provider"
    return "ok"


def run_model_canary() -> dict:
    if os.getenv("CANARY_ENABLED", "1").strip().lower() in _OFF:
        return {"skipped": "disabled"}
    results: dict[str, str] = {}
    for model in _models():
        try:
            results[model] = _ping(model)
        except LlmBudgetExceeded:
            results[model] = "skipped_budget"
        except Exception as exc:
            results[model] = f"error: {type(exc).__name__}"
            logger.warning("model canary: %s failed (%s)", model, type(exc).__name__)
    failing = [m for m, r in results.items() if r.startswith("error")]
    if failing:
        raise CanaryFailure("models failing: " + ", ".join(failing))
    return {"models": results}
