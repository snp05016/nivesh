# Vendored TradingAgents (`backend/tradingagents-core`)

## Provenance

- Upstream: TauricResearch/TradingAgents (PyPI/package name `tradingagents`), version 0.2.5.
- Upstream commit or tag: **unknown**. It was copied in without a recorded base, so a
  diff against upstream must be done by hand against the 0.2.5 release.
- The directory is git-ignored (`backend/.gitignore`: `tradingagents-core/`). Only the
  Python sources were force-added (about 104 files). `pyproject.toml`, `uv.lock`, the
  upstream Dockerfile and docker-compose are not tracked, so a clean clone cannot
  `pip install -e` it.

## How it is loaded

There is exactly one mechanism: `backend/services/orchestrator.py` inserts
`backend/tradingagents-core` at the front of `sys.path` right before its
`from tradingagents...` imports. Every user of the pipeline (the `job_worker`
subprocess, `routers/analysis.py`) imports the orchestrator first.
Do not add another `sys.path` insert or a `pip install -e` step;
`backend/tests/test_vendored_tradingagents_path.py` enforces this.

If a `tradingagents` package is also pip-installed in the venv, it is shadowed. Remove
it anyway (`pip uninstall tradingagents`) so only one copy exists.

Because the directory sits at the front of `sys.path`, its top-level `cli/`,
`tests/` and `test.py` can shadow backend modules with the same names. Do not add
backend modules with those names.

## Dependency floors

The fork's runtime floors are kept in `backend/requirements.txt`, not in the fork's
untracked pyproject: `langchain-core>=0.3.81`, `langgraph>=0.4.8`,
`langchain-anthropic>=0.3.15`, `langchain-openai` and `langgraph-checkpoint-sqlite`.
The fork's optional extras (backtrader, langchain-google-genai, typer, questionary,
rich) are not installed. The Google client is imported lazily, only when
`llm_provider` is `google`; the orchestrator sets `deepseek`.

## Local modifications (not upstream)

`git log --oneline -- backend/tradingagents-core` lists 19 local commits, from
2026-06-12 to 2026-06-30:

| Commit | Date | Change |
|---|---|---|
| 136e961 | 2026-06-12 | Add Governance Analyst to the multi-agent pipeline |
| f03f916 | 2026-06-12 | NaN serialization fixes, debate rounds 1 to 3 |
| f615ffe | 2026-06-12 | `_log_state` governance_report safe access |
| e6015cc | 2026-06-12 | Bear Researcher KeyError: `latest_speaker` field |
| c2237d4 | 2026-06-12 | 20-stage checkpoint progress events |
| 1a53816 | 2026-06-12 | Dynamic checkpoint progress, config-based models |
| 3d92954 | 2026-06-12 | Extreme analysis: deepseek-v4-pro thinking mode |
| 93f93fd | 2026-06-13 | AI cost reduction v2: governance fast-track |
| bc1ef8e | 2026-06-14 | `search_filings` on governance and news ToolNodes |
| 08713ef | 2026-06-14 | Track `llm_clients/` |
| 1488adf | 2026-06-14 | Force-add missing fork modules |
| 4b3448a | 2026-06-16 | Dashboard AI Engine live monitor |
| c882c06 | 2026-06-18 | Production-readiness fixes |
| 644b449 | 2026-06-25 | Alert ordering, hardcoded password, pyc cleanup |
| 54e954c | 2026-06-26 | Bulk commit of pending backend/tradingagents changes |
| acf6739 | 2026-06-26 | Daemon threads, TTLCache, timezone fixes |
| 353cea1 | 2026-06-30 | gh-602: unprotected global state |
| 6258ac6 | 2026-06-30 | gh-596: raw excepts and silent fallthroughs |
| 05a51a7 | 2026-06-30 | gh-596 follow-up |

The fork also imports backend code (`graph/trading_graph.py` lazily imports
`services.orchestrator.search_filings`, `services.factor_engine` and
`services.feedback_injector`), so it cannot run outside this backend.

## Policy

- Put new product logic (agents, prompts, progress hooks) in `backend/services` and
  plug it in by composition: the orchestrator already subclasses `GraphSetup` and
  `TradingAgentsGraph`. Do not edit files in the vendored fork.
- If a vendor edit is unavoidable, keep it minimal and add a row to the table above.
- The new research engine should not depend on this graph. Once it replaces the old
  analysis pipeline, delete `backend/tradingagents-core` and the orchestrator
  subclasses instead of maintaining the fork.
