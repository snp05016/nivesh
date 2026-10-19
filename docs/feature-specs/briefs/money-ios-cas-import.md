# Feature package money-ios-cas-import: CAS import flow and import history on iOS

Cluster: money (Portfolio and money features); area: ios
Features covered: 21 I28 CAS import + X-ray

## Files (create or modify)
- ios/StockApp/stockme/stockme/Models/CASImportModels.swift
- ios/StockApp/stockme/stockme/NetworkManager+Imports.swift
- ios/StockApp/stockme/stockme/ViewModels/CASImportViewModel.swift
- ios/StockApp/stockme/stockme/Views/Money/CASImportView.swift
- ios/StockApp/stockme/stockme/Views/Money/CASImportSections.swift
- ios/StockApp/stockme/stockme/Views/Money/ImportHistoryView.swift
- ios/StockApp/stockme/stockme/Views/Money/PortfolioMoneySection.swift
- ios/StockApp/stockme/stockmeTests/CASImportModelsTests.swift

## Dependencies
- Feature packages (integrated before you start): money-cas-api, money-ios-mf-aware
- Declared in the plan: money-ios-mf-aware, money-cas-api, FIX:FINSEC-06, platform-ios-flags-events. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
Shown only when moneyCasImport is on; spec 3.5 copy and notice text are exact. (1) CASImportModels.swift: CASPreviewRequest (Encodable pdf_base64, password, consent_notice_version, attest_own_statement), CASPreview, CASPreviewScheme (isin, name, amc, units, valuation {date, nav, valueInr, costInr?}, mode, reason?, flags?), CASPreviewTotals (schemes, balance, skipped, valueInr), CASCommitResult, CASUndoResult, ImportBatchSummary; enum CASImportErrorCode with userMessage for WRONG_PASSWORD, UNSUPPORTED_STATEMENT, DEMAT_CAS_NOT_SUPPORTED, ALREADY_IMPORTED, QUOTA_EXCEEDED, FILE_TOO_LARGE, PARSE_TIMEOUT, PARSE_BUSY (spec copy) and 'Something went wrong. Please try again.' for NOT_A_PDF, INVALID_REQUEST, CONSENT_REQUIRED, PREVIEW_EXPIRED, LEDGER_CONFLICT, UNDO_WOULD_OVERSELL, ALREADY_COMMITTED, FEATURE_DISABLED. (2) NetworkManager+Imports.swift: previewCAS(pdf:password:) authRequest POST '/api/v1/me/imports/cas/preview', JSON with base64 PDF, 90 s timeout, non-2xx -> typed error from detail.code; commitImport, cancelImport, undoImport (DELETE), listImports. The password lives only in view-model memory, cleared after the request, never logged or persisted. (3) CASImportViewModel: @MainActor states idle(consent) -> fileChosen -> uploading -> preview -> committing -> done | failed(code, message); rejects files over 10 MB before upload; logs EventLogger.shared.log(.importStart, ['kind': 'cas']) on upload and .importDone with ['kind': 'cas', 'outcome': 'ok'|'failed'] after commit or failure (no tickers or amounts). (4) CASImportView: title 'Import mutual funds'; intro 'Upload your Consolidated Account Statement (CAS) from CAMS or KFintech.'; help 'Request a Detailed CAS for the period Since inception from the CAMS or KFintech website. It arrives by email as a password-protected PDF.'; notice cas-v1 verbatim with the two required toggles enabling 'Choose PDF'; .fileImporter([.pdf]) with security-scoped read; SecureField 'Statement password' .privacySensitive(); preview rows with badges 'Added as a balance' / 'Skipped' and reasons: balance 'Imported as a balance on <date>. Returns for this fund aren't calculated yet.', cost_unknown 'Cost not in statement: gains are measured from the statement date.', isin_missing 'No ISIN in the statement', manual_entries_exist 'You've added this fund by hand', zero_balance 'No units left', older_statement 'A newer statement is already imported'; buttons 'Add to portfolio' and 'Cancel' (cancelImport); done 'Added 5 funds.'. (5) CASImportSections: CASConsentCard, CASPreviewList, CASPreviewRow, CASImportResultView (View structs). (6) ImportHistoryView: listImports rows with 'Undo' behind confirmationDialog 'Undo this import? Its funds will be removed from your portfolio.'. (7) PortfolioMoneySection: when flags.isOn(.moneyCasImport), rows 'Import mutual funds (CAS)' -> CASImportView and 'Your imports' -> ImportHistoryView; .onAppear: if the flag is on and UserDefaults 'nivesh_openCASImport' is true, set it false and open CASImportView once via navigationDestination(isPresented:).

## Acceptance checks
swiftc -parse clean. CASImportModelsTests: request encodes snake_case keys and base64; preview fixture decodes with nulls; every code maps to its copy; an 11 MB file is refused; the password is empty after a completed request; with the flag off PortfolioMoneySection shows no import rows and ignores nivesh_openCASImport.

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
