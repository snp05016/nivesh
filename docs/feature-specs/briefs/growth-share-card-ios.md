# Feature package growth-share-card-ios: Delete the legacy 'Share as Image' export of AI analyses

Cluster: growth (Monetization, growth and bold bets); area: ios
Features covered: 63 I45 Share card, public web pages, referrals

## Files (create or modify)
- ios/StockApp/stockme/stockme/Views/AnalysisScreen.swift
- scripts/ios_static_checks.sh

## Dependencies
- Feature packages (integrated before you start): none
- Declared in the plan: ENG:ios-report-ui, FIX:IOSUI-30, FIX:IOSUI-31. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
Feature 63 is Reject. No share card is built; the re-entry spec is docs/proposals/share-card-reentry.md, written in growth-docs.
The one change that matters for compliance is removing the existing export. shareAsImage() renders the full legacy AnalysisCoreSections and AnalysisExtremeSections of a saved LLM analysis into an image for UIActivityViewController. It does so without the engine's archived-report banner (ENG §10.4), so legacy BUY/SELL-era content can be spread as images.

1. Views/AnalysisScreen.swift, or wherever IOSUI-30's split moved the code. Find it with grep -rn shareAsImage ios/.
- Delete the toolbar Button that calls shareAsImage(). Its label is Image(systemName: square.and.arrow.up) and it has .accessibilityLabel('Share as Image'). Today it is at lines 361-369.
- Delete the whole '// MARK: - Share as Image' section with private func shareAsImage(). Today it is at lines 505-540.
- Remove any state that only this code used.
- Change nothing else.

2. scripts/ios_static_checks.sh: next to the other checks, add a comment line and `fail_if_any swift_grep 'shareAsImage|Share as Image'`. CI then fails if the export comes back.

## Acceptance checks
1. swiftc -parse passes on the changed Swift file.
2. grep -rnE 'shareAsImage|Share as Image' ios/StockApp/stockme returns nothing.
3. bash scripts/ios_static_checks.sh prints 'ios_static_checks: OK'.

## Cluster spec
docs/feature-specs/spec_growth.md holds the reviewed spec for the whole cluster (data model, API contracts, iOS states, flags, copy, tests) and the coverage table. Read the parts for your features and files; the contract written there is binding for both the backend and the iOS package of a feature.

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
