# Feature package data-flags: Register data flags in the project flag module plus a cohort-aware wrapper

Cluster: data (Data foundation); area: backend
Features covered: I14, I15, I16, I18, I25

## Files (create or modify)
- backend/services/feature_flags.py
- backend/services/data_flags.py
- backend/tests/test_data_flags.py
- backend/.env.example

## Dependencies
- Feature packages (integrated before you start): none
- Declared in the plan: platform-flags. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
Do not create a flag mechanism. The project module is backend/services/feature_flags.py from platform-flags; habit-flags writes the same path, and the integration lead merges them. If it does not exist when this package starts, stop and report.

1) backend/services/feature_flags.py: add six keys to FLAG_DEFAULTS, in that module's value format (for platform-flags: {'default', 'client': False, 'description'}). Make no other edit.
- data_instruments: True. Weekly NSE EQUITY_L refresh and new-listing search.
- data_eod_prices: True. EOD mirror from ml-engine; requests a marketdata gap-fill while research mode is off.
- data_eod_display: False. Return NSE EQ and Nifty closes to user-facing callers. Turn on only after legal clears NSE and NSE Indices data rights.
- data_mf_universe: True. AMFI harvest and NAV history.
- data_corp_actions_confirm: False. Corporate-action proposals and API (Defer).
- data_results_digest: False. Results digest (Defer).

2) New backend/services/data_flags.py (stdlib, fastapi, services.feature_flags):
- enabled(key) -> bool: feature_flags.is_enabled(key).
- _allowlist(key) -> frozenset[int]:
  - read env 'FEATURE_' + key.upper() + '_USERS' on every call;
  - comma-separated, stripped; keep only positive ints;
  - log one WARNING per (key, bad entry) via a module-level set; never raise.
- enabled_for(key, user_id) -> bool: enabled(key) or (user_id is not None and user_id in _allowlist(key)).
- any_enabled(key) -> bool: enabled(key) or bool(_allowlist(key)). Jobs use this so a cohort gets data while the flag is off.
- require(key, user_id=None) -> None: raise HTTPException(404, detail={'code':'FEATURE_DISABLED','feature':key}) unless enabled_for(key, user_id).
- Add a '# ponytail: env allowlist; move into feature_flags if it gains per-user targeting' comment.

3) backend/.env.example: a commented 'Data feeds' block with:
- the six keys, their defaults and the override syntax the flag module uses;
- FEATURE_DATA_CORP_ACTIONS_CONFIRM_USERS= and FEATURE_DATA_RESULTS_DIGEST_USERS= (test-cohort user ids);
- a note that the Defer flags and data_eod_display stay off until the conditions in docs/data/DATA_FEEDS.md are met.

## Acceptance checks
PYPARSE and PYRIGHT clean. No other module named feature_flags is added.

backend/tests/test_data_flags.py (hermetic; monkeypatch feature_flags.is_enabled and env) covers:
- the defaults are True, True, False, True, False, False
- an allowlisted id is enabled while the flag is off; another id is not
- ' 12, abc ,7' parses to {12, 7} and warns once across two calls
- any_enabled is true with only an allowlist
- require raises 404 with detail {'code':'FEATURE_DISABLED','feature':key}, and returns None for an allowlisted user

The flag module's own tests stay green.

## Cluster spec
docs/feature-specs/spec_data.md holds the reviewed spec for the whole cluster (data model, API contracts, iOS states, flags, copy, tests) and the coverage table. Read the parts for your features and files; the contract written there is binding for both the backend and the iOS package of a feature.

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
