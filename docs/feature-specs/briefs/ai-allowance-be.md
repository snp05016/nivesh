# Feature package ai-allowance-be: AI allowance endpoint plus Retry-After and AI_PAUSED codes

Cluster: ai (AI cost architecture and research surfaces); area: backend
Features covered: 10. I01 Paid-AI guard

## Files (create or modify)
- backend/services/llm_budget.py
- backend/routers/copilot.py
- backend/tests/test_ai_allowance.py

## Dependencies
- Feature packages (integrated before you start): ai-flags
- Declared in the plan: ai-flags, FIX:LLM-02, FIX:LLM-09, FIX:LLM-13, FIX:ARCH-03, FIX:TEST-13. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
This is a delta on top of FIX:LLM-02 and FIX:LLM-09.
- FIX:LLM-02 provides services/llm_budget.py: the LlmUsage ledger, _today_start_utc(), the memoised assert_global_budget(), check_user_budget(), guard(), require_llm_budget() and _reset_cache().
- FIX:LLM-09 adds usage_summary().

1. Changes to services/llm_budget.py

a. Extract two helpers from check_user_budget, without changing behaviour:
- _user_cap_usd(user_id: int) -> float: tier from entitlement_service.get_effective_tier(user_id); env LLM_USER_DAILY_BUDGET_USD_{FREE,PRO,SUPER_PRO}, with LLM-02's defaults.
- _user_spent_today_usd(user_id: int) -> float: SUM(LlmUsage.cost_usd) for user_id with created_at >= _today_start_utc(); 0.0 when there are no rows.
check_user_budget keeps its 429 detail {'error_code': 'AI_QUOTA_EXCEEDED', 'error_title', 'error_detail'} and adds headers={'Retry-After': str(seconds_to_ist_midnight())}.

b. global_paused() -> bool uses the same memoised global SUM compared with LLM_GLOBAL_DAILY_BUDGET_USD, but returns a bool. assert_global_budget becomes: if global_paused(), raise LlmBudgetExceeded.

c. guard() maps the breaker to HTTPException(503, detail={'error_code': 'AI_PAUSED', 'error_title': 'AI paused', 'error_detail': 'AI features are paused for today. Everything else in Nivesh works.'}, headers={'Retry-After': str(seconds_to_ist_midnight())}).

d. seconds_to_ist_midnight(now: datetime | None = None) -> int: take now in UTC (default datetime.now(timezone.utc)) and convert it to zoneinfo.ZoneInfo('Asia/Kolkata'). Return the whole seconds until the next IST midnight, never below 1.

e. allowance(user_id: int) -> dict:
- cap = _user_cap_usd(user_id); spent = _user_spent_today_usd(user_id).
- used_pct = 100 if cap <= 0, else min(100, int(spent / cap * 100)).
- state, in order of precedence: 'paused' if global_paused(); else 'exhausted' if spent >= cap; else 'low' if used_pct >= 80; else 'ok'.
- Return exactly {'used_pct': used_pct, 'state': state}. Never return money, caps or tier.

2. Changes to routers/copilot.py
Add:
`@router.get('/api/v1/ai/allowance') def ai_allowance(user_id: int = Depends(require_auth), _flag: None = Depends(require_feature('ai_allowance'))) -> dict: return llm_budget.allowance(user_id)`
- Sync def; import require_auth from core.security and require_feature from the project flag module (see ai-flags).
- The flag is a kill switch (default on), kept because every new surface sits behind a server-side flag.
- Contract:
  - 200 {'used_pct': int 0-100, 'state': 'ok'|'low'|'exhausted'|'paused'};
  - 401 without a token;
  - 404 {'detail': {'code': 'FEATURE_DISABLED', 'feature': 'ai_allowance'}} when the flag is off.

Edge cases:
- no rows gives 0 / 'ok';
- usage before the current IST midnight is ignored;
- a cap of 0 gives 100 / 'exhausted';
- a DB error propagates as 500, and iOS hides the line.

Tests, backend/tests/test_ai_allowance.py:
Setup: conftest client, auth_headers and test_user_id; insert LlmUsage rows via get_session; a fixture calls llm_budget._reset_cache(); monkeypatch LLM_USER_DAILY_BUDGET_USD_FREE=1.0 and entitlement_service.get_effective_tier to return 'free'.
(a) no token gives 401.
(b) FEATURE_AI_ALLOWANCE=false gives 404 FEATURE_DISABLED.
(c) no usage gives {'used_pct': 0, 'state': 'ok'}.
(d) cost 0.85 today gives 85 / 'low'.
(e) cost 1.2 gives 100 / 'exhausted'.
(f) LLM_GLOBAL_DAILY_BUDGET_USD=0.01 with a user_id NULL row of cost 1 gives 'paused'.
(g) a row created 1 h before _today_start_utc() is not counted.
(h) POST /brainstorm (mock services.brainstorming._deepseek_chat) over the cap gives 429 with an integer Retry-After between 1 and 86400, and the mock is not called.
(i) the breaker gives 503 with detail.error_code 'AI_PAUSED' and a Retry-After header.
(j) the allowance JSON keys are exactly {'used_pct', 'state'}.
(k) seconds_to_ist_midnight(datetime(2026, 10, 11, 18, 29, tzinfo=timezone.utc)) == 60.

## Acceptance checks
1. PYPARSE and PYRIGHT are clean on the three files.
2. test_ai_allowance.py passes in CI, and the existing LLM-02 tests (test_llm_budget.py) stay green.
3. The allowance response never contains a key with 'usd', 'cost', 'cap' or 'tier'.
4. No new table and no migration.

## Cluster spec
docs/feature-specs/spec_ai.md holds the reviewed spec for the whole cluster (data model, API contracts, iOS states, flags, copy, tests) and the coverage table. Read the parts for your features and files; the contract written there is binding for both the backend and the iOS package of a feature.

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
