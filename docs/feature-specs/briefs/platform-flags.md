# Feature package platform-flags: Server-side feature flags: table, resolver and cache-safe public client endpoint

Cluster: platform (Platform, operations and privacy); area: backend
Features covered: 60 I46 Admin console v2, 36 I47 First-party product analytics

## Files (create or modify)
- backend/models/db_models.py
- backend/migrations/versions/ba5740a03b6b_add_feature_flags.py
- backend/services/feature_flags.py
- backend/routers/flags.py
- backend/main.py
- backend/.env.example
- backend/tests/test_feature_flags.py

## Dependencies
- Feature packages (integrated before you start): none
- Declared in the plan: FIX:DB-07, FIX:OPS-03, FIX:REL-15, FIX:AUTH-01, FIX:OPS-13. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
This package owns the project-wide server-side flag mechanism. None exists today; config/settings.py holds env constants only. Research flags stay env-only per engine decisions D27 and D36 and are not moved here.
Five other cluster plans define their own flag modules:
- data-flags and ai-flags: core/feature_flags.py;
- the money plan: core/feature_flags.py with require_flag;
- habit-flags: services/feature_flags.py with GET /api/v1/features;
- ios-flags-be: config/feature_flags.py with GET /api/v1/app-config.
Human step 2 merges them into this package as FLAG_DEFAULTS entries. That is why this module uses their FEATURE_<KEY> env prefix and their is_enabled and client_flags names. If the integration lead has already folded another cluster's keys into FLAG_DEFAULTS, keep them.

1. models/db_models.py: append class FeatureFlag(Base) after the research section, reusing that section's local imports (Mapped, mapped_column, Optional, _utcnow).
   - __tablename__ 'feature_flags'.
   - key: String(64), primary key.
   - enabled: Boolean NOT NULL, default False, server_default '0'.
   - updated_by: Integer NULL, the acting admin's users.id. It deliberately has no FK, so no erasure-policy entry is needed.
   - updated_at: DateTime NOT NULL, default _utcnow.
   - There is no value column. Add one in the package that first needs a non-boolean setting.
2. migrations/versions/ba5740a03b6b_add_feature_flags.py:
   - revision 'ba5740a03b6b'.
   - down_revision = the single head at implementation time. Find it by static-parsing migrations/versions; it is t4u5v6w7x8y9 (the engine's research tables) or later.
   - Create the table only if it is missing, using the inspector pattern from t4u5v6w7x8y9_add_research_engine_tables.py. Downgrade drops it only if present.
3. services/feature_flags.py:
   - FLAG_DEFAULTS = {'analytics': {'default': False, 'client': True, 'description': 'Product analytics (I47): store consented usage events; iOS logs them and shows the one-time ask. Turn on only after the privacy policy names analytics.'}}. This is the only key. The Your Data screen and export are rights surfaces and are never flagged. The model canary uses env CANARY_ENABLED.
   - Resolution per key:
     1. A DB row, if present (source 'db').
     2. Env FEATURE_<KEY upper-cased>, parsed case-insensitively: true/1/on/yes or false/0/off/no. Any other value is ignored (source 'env').
     3. The FLAG_DEFAULTS default (source 'default').
     4. A key in neither the DB nor FLAG_DEFAULTS resolves to False (fail closed) and logs one warning per key per process.
   - Load all rows with one query and cache them for 30 s under a threading.Lock. On any DB error, cache {} for 30 s and log a warning; never raise.
   - Public functions:
     - is_enabled(key) -> bool.
     - client_flags() -> dict[str, bool], client=True keys only.
     - list_flags() -> list[dict] with key, enabled, default, source, client_visible, description, updated_by and updated_at (ISO-8601 with Z, or None). Also include DB rows whose keys are unregistered, with description 'unregistered'.
     - set_flag(key, enabled, actor_id) -> dict. Raise KeyError for unregistered keys. Upsert via session.get(FeatureFlag, key), commit, invalidate the cache, and return the list_flags entry.
     - _reset_cache(), for tests.
4. routers/flags.py: APIRouter(prefix='/api/v1/flags', tags=['Flags']) with GET '' as a plain def.
   - It returns JSONResponse({'flags': feature_flags.client_flags()}, headers={'Cache-Control': 'no-store, private', 'Vary': 'Authorization'}). platform-events-api makes the body depend on the caller's token, so no proxy or URLCache may share it.
   - The route is public (no auth). If an auth-by-default middleware lands, add '/api/v1/flags' to its public allowlist.
   - Contract consumed by platform-ios-flags-events: 200 {'flags': {'analytics': false}}. platform-events-api later adds flags['analytics_consented'] and the top-level 'analytics_retention_days'.
5. main.py: import flags and include flags.router alongside the other includes.
6. .env.example: document the FEATURE_<KEY> overrides, for example FEATURE_ANALYTICS=false.

## Acceptance checks
- Every touched .py file passes an AST parse and pyright; missing-import categories are excepted.
- A static parse of migrations/versions shows exactly one head after this migration.
- In CI, alembic upgrade head, then downgrade -1, then upgrade head on SQLite succeeds.
- tests/test_feature_flags.py passes in CI and covers:
  - the default with no row and no env;
  - a FEATURE_ANALYTICS env override;
  - a DB row beating env;
  - an unregistered key resolving to False;
  - set_flag on an unregistered key raising KeyError;
  - set_flag being visible immediately;
  - a monkeypatched get_session that raises, giving defaults with no exception;
  - GET /api/v1/flags without a token returning 200 with flags.analytics, a Cache-Control header containing no-store and private, and Vary: Authorization.
- grep finds no get_value, privacy_center or ops_model_canary in services/feature_flags.py.
- The existing migration and app-startup tests still pass.

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
