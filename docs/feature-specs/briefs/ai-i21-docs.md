# Feature package ai-i21-docs: Document the deferred I21 track record and 'My analyses' preconditions (no code)

Cluster: ai (AI cost architecture and research surfaces); area: docs
Features covered: 59. I21 Visible track record

## Files (create or modify)
- docs/research/COMPLIANCE.md

## Dependencies
- Feature packages (integrated before you start): none
- Declared in the plan: ENG:docs-research. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
Roadmap I21 is Defer (smaller version 'My analyses', built once I22 lands; final recommendation Phase 3). No code is built now; see spec section 3.5. Add a short section '## 12. Deferred: visible track record and My analyses (roadmap I21)' to docs/research/COMPLIANCE.md:
- Default: the engine's gate stays (SPEC 8.6, D37). Live numbers appear only on the admin track-record endpoint, and RESEARCH_TRACK_RECORD_PUBLIC takes effect only with a valid registration (section 6). That engine flag is the only switch; there is no second one.
- Preconditions before any user-visible track record, in order:
  1. SEBI RA registration and the legal RA_DISCLAIMER_TEXT change (section 6);
  2. live gate G7 passed for the horizon shown (SPEC 8.5);
  3. the displayed metric verified under SEBI's PaRRVA framework (confirm current eligibility and which metrics it verifies with counsel at that time);
  4. a legal-approved display sentence committed in code that states n, a confidence interval and the benchmark;
  5. then RESEARCH_TRACK_RECORD_PUBLIC=true.
- Data rules: any track-record query filters on the production procedure_id and never mixes baseline and model rows; in-app only; never in marketing, share cards, push notifications or App Store copy.
- 'My analyses' is Phase 3 and is built from engine report history. A per-user view log would be new personal data (DPDP purpose, erasure and export) and needs its own review.
- No calendar dates and no agency names in this section.

## Acceptance checks
1. Section 12 exists in docs/research/COMPLIANCE.md and the earlier sections are unchanged.
2. It names procedure_id, PaRRVA, G7 and RESEARCH_TRACK_RECORD_PUBLIC.
3. It contains no calendar dates.

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
