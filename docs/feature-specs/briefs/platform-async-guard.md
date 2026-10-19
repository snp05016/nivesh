# Feature package platform-async-guard: Ruff flake8-async gate with baseline, plus AST test for project blocking calls and awaits on sync functions

Cluster: platform (Platform, operations and privacy); area: mixed
Features covered: 46 C12 Stop blocking the event loop

## Files (create or modify)
- .github/workflows/backend_ci.yml
- backend/ruff.toml
- backend/tests/test_async_hygiene.py

## Dependencies
- Feature packages (integrated before you start): platform-admin-api, platform-events-api, platform-privacy-export, platform-scheduler-ist
- Declared in the plan: platform-scheduler-ist, platform-events-api, platform-privacy-export, platform-admin-api, FIX:TEST-14, FIX:REL-01, FIX:PERF-02, FIX:REL-03, FIX:REL-07, FIX:LLM-13, FIX:REL-22, FIX:REL-11, FIX:REL-15, ENG:be-cutover, ENG:be-serve-api. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
C12 delta. It gates ruff's flake8-async rules and adds a small project-specific AST test. Build it last among the backend packages, so both baselines reflect final code. It never re-implements what ruff already checks.

1. .github/workflows/backend_ci.yml (after FIX:TEST-14): in TEST-14's gating ruff step, extend --select to E9,F63,F7,F82,ASYNC210,ASYNC220,ASYNC221,ASYNC222,ASYNC230,ASYNC251. Keep TEST-14's --extend-exclude list.
- Do not select the whole ASYNC prefix. Codes such as ASYNC109 (timeout parameter) and ASYNC110 (busy-wait) are style rules, not blocking-I/O rules.

2. backend/ruff.toml (new; there is no ruff config today). It holds only a [lint.per-file-ignores] table.
- One entry per file that currently violates one of those codes, listing only the codes it violates, for example 'services/foo.py' = ['ASYNC210']. Patterns are relative to backend/.
- Header comment: 'Baseline of pre-existing flake8-async hits, computed <date> on <commit>. Only remove entries; fix new hits or move the call into asyncio.to_thread.'
- To compute it:
  1. Run python3 -m venv <scratch>/ruffenv, then <scratch>/ruffenv/bin/pip install ruff==0.8.6. This is FIX:TEST-14's pin; ruff is a standalone linter and never imports backend code.
  2. Run ruff rule <code> for each code, and drop any reported as preview-only from both the CI flag and the baseline.
  3. Run the CI command from the repo root with --output-format concise, and group the hits by file.
  4. Re-run after writing ruff.toml: it must report 0 errors.

3. backend/tests/test_async_hygiene.py uses stdlib ast only and never imports backend modules. Scanner functions take (path, source), so unit tests can feed inline strings or a fake tree in tmp_path.
- Scan set: backend/routers/*.py, backend/core/*.py, backend/middleware/*.py, backend/services/**/*.py and backend/main.py.
- Import resolution per module:
  - map local names to dotted targets from 'import x as y' and 'from x import a as b';
  - resolve relative imports against the importing file's package;
  - a target is a backend module when it resolves to backend/<path>.py or backend/<path>/__init__.py.
- Check 1, project blocking calls. Inside every AsyncFunctionDef, walk its body without descending into nested FunctionDef, AsyncFunctionDef, Lambda or ClassDef nodes. Flag a Call whose resolved dotted name ends with get_session, deepseek_chat, claude_messages or claude_haiku, or equals yfinance.download or yfinance.Ticker.
  - Callables passed as arguments are not calls and pass: asyncio.to_thread(fn, ...), run_in_threadpool(fn, ...) and loop.run_in_executor(None, fn).
  - Generic blocking I/O (requests, httpx sync, open, subprocess, time.sleep) is ruff's job and is not checked here.
- Check 2, await on a sync function. For every Await whose value is a Call, resolve the callee. Flag it only when it resolves to a plain FunctionDef:
  (a) a bare name: a module-level def in the same file, or else a 'from <backend module> import f [as g]' alias whose target file defines f at module level;
  (b) self.m(...) inside a class body: m is defined in that same ClassDef;
  (c) mod.f(...), where mod is an import alias of a backend module whose file defines f at module level.
  - Every other attribute call is skipped, for example await request.json(), await websocket.send_text(), await client.get() and await resp.read().
  - A name defined both as def and as async def in the target scope is skipped.
- Suppression: a finding is ignored when its source line ends with a comment starting '# async-ok:' followed by a reason.
- A finding is (path relative to backend/, enclosing function name, check, callee).
- BASELINE is a frozenset literal of the findings at implementation time. Compute it with a scratch copy of the scanner run by plain python3; it only parses files. A comment records the date and commit.
- test_no_new_violations fails, listing any finding not in BASELINE.
- test_baseline_not_stale fails for baseline entries that no longer occur, so the baseline only shrinks.
- Unit cases:
  - 'async def h(): get_session()' is flagged;
  - the same call through 'await asyncio.to_thread(get_session)', or inside a nested def, is not flagged;
  - in a fake two-file tree, 'from services.x import f' (f a plain def in services/x.py) followed by 'await f()' is flagged;
  - 'await request.json()' is not flagged, even when some scanned module defines a sync def json;
  - 'await self.m()' with a sync m in the same class is flagged; with an async m it is not;
  - 'from services import llm' followed by 'await llm.f()', with a sync f, is flagged;
  - a line ending in '# async-ok: reason' is not flagged.

Not built: the ANYIO_THREAD_TOKENS knob. platform-jobruns documents it in OBSERVABILITY.md as the remedy if /health latency shows thread starvation.

## Acceptance checks
- In CI, the ruff step with the added ASYNC codes passes; backend/ruff.toml is the only baseline.
- The ruff.toml header and the BASELINE comment record the date and commit they were computed on.
- test_async_hygiene.py passes in CI, including the scanner unit cases, the no-new-violations test and the stale-baseline test.
- The scratch ruff 0.8.6 run reports 0 errors after ruff.toml is written.
- AST parse is clean on the test file.
- backend/core/lifecycle.py is not modified.

## Cluster spec
docs/feature-specs/spec_platform.md holds the reviewed spec for the whole cluster (data model, API contracts, iOS states, flags, copy, tests) and the coverage table. Read the parts for your features and files; the contract written there is binding for both the backend and the iOS package of a feature.

## Constraints (hard rules)
- Fix track and engine: the audit-fix track and the Research Engine are integrated (or integrating) on the same line. Build on their code; never re-implement what they already do. If a dependency is not in the code yet, do not stub or duplicate it: build your part against the documented interface behind the feature flag, and report it.
- Research Engine decisions win: every number is computed by validated code; DeepSeek only phrases computed facts behind the grounding validator; no buy/sell/hold, price targets or stock-level probabilities; English-only v1; legacy analysis routes are retired (410); track record and cohort display only when RESEARCH_SEBI_RA_REG_NO is set. Where a feature conflicts, the engine decision is the default and the feature sits behind a flag that is off.
- Compliance: no advice, recommendations, ratings or targets; no performance claims in marketing or share content; never claim SEBI registration; DPDP Act 2023 / Rules 2025 (consent, purpose limitation, erasure, export, breach logging); App Store rules (5.1.1 account deletion, StoreKit for digital goods, privacy manifest).
- Engineering: ORM models only in backend/models/db_models.py; schema changes only via a new Alembic revision with a RANDOM 12-hex id chained to the current single head; DB access through get_session(); thin routers, logic in services/; Lakhs/Crores; iOS colours only Theme.* tokens, stripEmoji on AI text, no GeometryReader inside ScrollView/HStack, no nested NavigationStack, ViewBuilder helpers over 5 lines become View structs; free, terms-respecting data sources only (AMFI NAV files, NSE/BSE public files, yfinance) with an honest User-Agent (contact https://github.com/snp05016/nivesh); no new third-party dependency unless the brief names one; every new surface behind a server-side feature flag (reuse the project's flag mechanism) that degrades gracefully; every feature with tests.
- Backend code cannot be executed here: static checks plus hermetic tests that are correct by construction. iOS: swiftc -parse only. ml-engine code can be executed and its tests must pass.

## Local test commands
- ml-engine: cd <your worktree>/ml-engine && PYTHONDONTWRITEBYTECODE=1 backend/venv/bin/python -m pytest -p no:cacheprovider -q <tests>
- backend: static checks only (pycheck, pyright_delta); tests hermetic and correct by construction.
- iOS: swiftc -parse only; verify every symbol you use by grepping its declaration.
