# No API Credits Policy

Normal CI must not use paid API credits. The default CI/CD environment is designed to cost ₹0 / $0 in LLM, embedding, Copilot, or paid data-provider usage.

## Default Mode

All default workflows must force mock mode:

```bash
LLM_MODE=mock
DISABLE_LIVE_LLM=1
DISABLE_PAID_APIS=1
ENABLE_SCHEDULER=false
FORCE_DISABLE_SCHEDULER=1
DISABLE_RAG_INGESTION=1
```

Any workflow step that could spend credits must fail closed unless a maintainer explicitly enables it in a separate manual-only integration workflow. The workflows in this repository do not expose paid API keys to PR jobs.

## Secrets

Paid API keys must never be available to pull request workflows. This includes:

- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `DEEPSEEK_API_KEY`
- `GOOGLE_API_KEY`
- `GEMINI_API_KEY`
- embedding-provider API keys
- Copilot or agent-chat API credentials

If any of these keys are present in a default workflow environment, the step must fail before tests run.

## Manual-Only Paid Integrations

Paid API integration tests must be manual-only, maintainer-triggered, and isolated from normal CI. They must not run on PR open, PR synchronize, push, nightly schedule, release artifact generation, or backend deployment health checks.

## Forbidden Calls

Default CI must not call:

- DeepSeek, Claude, OpenAI, Anthropic, Google AI, or embedding APIs
- Copilot chat or agent-backed recap jobs
- `/analyze`, `/analyze/batch`, advisor reformatting, RAG ingestion, or live LLM-backed endpoints
- tests that hit paid external APIs

Tests that normally touch paid APIs must be mocked, skipped, or moved behind an explicit manual-only maintainer flag.
