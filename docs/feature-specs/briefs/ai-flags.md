# Feature package ai-flags: Register the cluster's server-side flags (create the flag module only if none exists)

Cluster: ai (AI cost architecture and research surfaces); area: backend
Features covered: 10. I01 Paid-AI guard, 40. I33 Risk flags card

## Files (create or modify)
- backend/core/feature_flags.py
- backend/tests/test_feature_flags.py
- backend/.env.example

## Dependencies
- Feature packages (integrated before you start): none
- Declared in the plan: FIX:OPS-13. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
Step 0: find the project's flag module before writing anything. Five clusters each planned one (data and money: core/feature_flags.py; platform, which claims ownership, and habit: services/feature_flags.py; ios: config/feature_flags.py). Check those three paths and run grep -rln "FEATURE_DISABLED" backend --include='*.py'.

If a module exists:
- add the three keys below to its defaults registry, in its own format and with these defaults;
- if it has no function named require_feature, add one there: require_feature(key) returns a sync FastAPI dependency that raises HTTPException(404, detail={'code': 'FEATURE_DISABLED', 'feature': key}) when the module's own is_enabled(key) is false (a 4-line wrapper);
- add the tests below to that module's test file;
- do not create core/feature_flags.py.
The later ai packages import is_enabled and require_feature from whichever module this step used (find it with grep -rn "def require_feature" backend).

If no module exists, create backend/core/feature_flags.py (stdlib + fastapi only):
- DEFAULTS: dict[str, bool] = {'ai_allowance': True, 'risk_flags_concentration': True, 'risk_flags_surveillance': False}. Other clusters add their keys here.
- is_enabled(key: str) -> bool:
  - key not in DEFAULTS: log WARNING once per key (module-level set) and return False (fail closed);
  - read os.getenv(f'FEATURE_{key.upper()}') on every call, with no caching, so tests can monkeypatch it;
  - stripped lower-case value in {'1','true','yes','on'} returns True; in {'0','false','no','off'} returns False; unset returns DEFAULTS[key]; anything else logs CRITICAL once and returns DEFAULTS[key].
- require_feature(key: str) returns a sync dependency `def _dep() -> None` that raises the 404 above when not is_enabled(key).
- Module docstring: flags are env-backed and read per call; if a DB-backed store lands (platform cluster), only is_enabled changes; never put secrets or per-user targeting here; iOS learns a flag from the flagged endpoint's 404.

backend/.env.example: append one commented block, each line with a one-line comment:
- FEATURE_AI_ALLOWANCE=true (kill switch for the Copilot allowance line)
- FEATURE_RISK_FLAGS_CONCENTRATION=true (holding and sector concentration lines on a held stock)
- FEATURE_RISK_FLAGS_SURVEILLANCE=false (ASM/GSM; enable only after the REG_IND spike, legal sign-off and FIX:REG-10)
- SURVEILLANCE_REG_IND_URL=https://nsearchives.nseindia.com/content/equities/REG_IND{ddmmyy}.csv (confirm during the spike)

Tests (backend/tests/test_feature_flags.py, or the existing module's test file):
- defaults for the three keys;
- 'true', 'false', 'ON' and '0' override the default (monkeypatch.setenv/delenv);
- 'maybe' falls back to the default;
- an unknown key returns False;
- a fresh FastAPI() app with one route using Depends(require_feature('risk_flags_surveillance')) returns 404 JSON {'detail': {'code': 'FEATURE_DISABLED', 'feature': 'risk_flags_surveillance'}} by default, and 200 with FEATURE_RISK_FLAGS_SURVEILLANCE=true.

## Acceptance checks
1. PYPARSE and PYRIGHT report no errors on the changed Python files (missing-import categories excepted).
2. The flag tests pass in CI.
3. grep -rnE "(getenv\(|environ\.get\(|environ\[)f?['\"]FEATURE_" backend --include='*.py' | grep -v '/tests/' returns matches only in the flag module. (The grep suggested in review misses f-string and environ.get reads; this one was checked on samples.)
4. backend/.env.example documents the four variables.
5. Exactly one flag module defines the three keys; no second flag module is created.

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
