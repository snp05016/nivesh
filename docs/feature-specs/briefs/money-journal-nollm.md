# Feature package money-journal-nollm: Remove the paid LLM call from trade-journal stats

Cluster: money (Portfolio and money features); area: backend
Features covered: 58 C16 decision journal

## Files (create or modify)
- backend/routers/trade_journal.py
- backend/tests/test_trade_journal_nollm.py

## Dependencies
- Feature packages (integrated before you start): none
- Declared in the plan: FIX:GH-630, FIX:LLM-19, FIX:ARCH-14. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
C16 smaller version; ships first, no flag (a removal, not a surface). In trade_journal_stats_endpoint (routers/trade_journal.py after FIX ARCH-14; routers/portfolio.py otherwise), after GH-630's identity check: delete the DeepSeek 'patterns' block and LLM-19's cache code for it; 'patterns' is always []; keep every other compute_trade_journal_stats key; remove _deepseek_chat/_extract_json_from_text imports if now unused. Change nothing else.

## Acceptance checks
test_trade_journal_nollm.py: a monkeypatched _deepseek_chat (if importable) is never called; the response keeps total_entries, top_keywords and action_breakdown with patterns == []; a path user_id different from the token user is rejected as GH-630 defines. PYPARSE clean.

## Cluster spec
docs/feature-specs/spec_money.md holds the reviewed spec for the whole cluster (data model, API contracts, iOS states, flags, copy, tests) and the coverage table. Read the parts for your features and files; the contract written there is binding for both the backend and the iOS package of a feature.

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
