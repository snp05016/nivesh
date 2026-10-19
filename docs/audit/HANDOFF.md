# Audit fixes, research engine and Holding Detail: handoff

Branch: `audit/integration` (on GitHub), built on base `0925ba8`. It is not merged into `main` or `feature/money-control-features`. Merging is your call after the checks below.

## What landed

- **Audit fixes:** 207 of 208 fix packages are integrated. The remaining one, p2-19 (session expiry), was already fixed by another package, so it needed no commit. That covers 494 audit items:
  - 399 fixed
  - 43 partial
  - 33 already fixed
  - 19 prepared for a human step
- **Research Engine:** all 19 packages are in, under `/api/v1/research`. Every number is computed by validated code, and DeepSeek only phrases computed facts behind a grounding validator. Legacy analysis routes are gated, and iOS shows a new report screen.
- **Holding Detail with honest XIRR vs Nifty (roadmap C11 + I30):** 5 packages are in.
  - server-side feature flags plus a `GET /api/v1/features` endpoint
  - the ledger schema delta
  - the holding-detail endpoint with dated cash flows and a Nifty benchmark
  - the iOS flag store
  - the iOS "My position" screen and portfolio return card

  Flags `money_holding_detail` and `money_xirr_card` default to on. The other money flags default to off.

## What was checked here, and what was not

- **Checked:**
  - All 640 changed Python files parse.
  - All 286 changed Swift files pass `swiftc -parse`.
  - The Alembic chain has a single head (58 revisions).
  - The ml-engine suite passes: 382 tests.
  - Every package went through a strict review before it was integrated.
- **Not checked:**
  - **Backend tests were never run.** Backend code is never executed locally.
  - **The iOS app was never compiled or type-checked.** No xcodebuild was run.

## Do these first

1. **Backend tests on the server.** Run the full backend suite on the server (or in CI) against this branch. Many routers, services and import paths moved, for example `main.py` going from 935 to 225 lines and the admin dashboard and lifecycle moving into modules.
2. **Xcode build and iOS tests.** Build the app in Xcode and run the `stockmeTests` target. The many new Swift files are covered only by parse checks.
3. **Database migrations on a staging copy.** Run `alembic upgrade head` on a staging copy of the production database, then `downgrade -1` and `upgrade head` again. The migrations are written to be idempotent.
4. **Research data backfill from the server.** NSE throttles requests from this Mac, and the runbook says never to change the User-Agent or use proxies. The bhavcopy backfill therefore has to run on the server (see `docs/research/RUNBOOK.md`). Retrain after it.
5. **Engine results on the development data.** These came from a local CSV with survivorship bias, so treat them as development-only. Both horizons came out as `no_reliable_edge`:

   | | 21-day horizon | 63-day horizon |
   |---|---|---|
   | Rank IC | 0.058 (HAC t 2.27, needed 1.97) | 0.096 (t 3.52, needed 2.17) |
   | vs 12-1 momentum | no better | no better |
   | Probability of backtest overfitting | 0.66 | 0.39 |

   In the null calibration, 0 of 20 replicates reached even the weak tier. Until real data shows an edge, the app must keep showing descriptive research only.
6. **Production settings.**
   - Set `GRIEVANCE_OFFICER_NAME`/`EMAIL`.
   - Keep `RESEARCH_SEBI_RA_REG_NO` unset unless you are actually registered. While it is unset, the track record and cohort display stay hidden.
   - Set a fixed `JWT_SECRET`.
   - Review `.env.example` for the new keys.
7. **First manual deploy of the ML engine.** Run `scripts/deploy_ml_engine.sh` by hand the first time. It now builds `ml-engine:<sha>`, checks it as a candidate on 127.0.0.1:8011 and keeps the old container until the new one passes.
8. **App Store and legal.**
   - Mirror the privacy manifest's data types in App Store Connect.
   - Confirm that account deletion really erases data.
   - Assign a forum moderator (IT Rules 2021 deadlines).
9. **Regenerate `backend/openapi.json`** on a machine that is allowed to import the app.

## Notes

- **iCloud duplicates.** The repo sat on an iCloud-synced Desktop, and iCloud kept creating `name 2.py` duplicates. The duplicates were moved out of the worktrees, and the repo was then moved to `~/nivesh`.
- **Unfinished work.** The remaining 123 expansion-roadmap feature packages were planned but not built (by request).

## Appendix: owner actions reported per package


### w2-02: POST /register returns no access_token, so every iOS sign-up fails to 

- Run backend/tests/test_backend_contract_api.py on the remote server; the new test reuses the existing client fixture and the _check_rate_limit monkeypatch pattern.
- Run the stockmeTests target in Xcode to confirm AuthDecodingTests compiles and passes.
- Still open from closed #476: RegisterRequest (backend/helpers.py) has no username or password constraints. Track it under ARCH-01 or a separate auth item.

### w5-06: App lock: Face ID and notification prompts fire on the first frame bef

- Run the stockmeTests XCTest target in Xcode, which includes AppLockPolicyTests.
- Check on a device that a fresh install shows no Face ID or notification prompt before login.
- Check on a device that after login, failing Face ID until lockout falls back to the passcode and never unlocks without it.
- Check on a device that a device with no passcode stays locked and offers Sign out.
- Check on a device that after login, setting the clock back while Nivesh is in the background still relocks the app on return.

### w5-08: Options payoff flags put-side risk with the wrong sign: a naked short 

- Run backend/tests/test_options_engine_extremes.py and test_backend_contract_financial.py on the remote server.
- iOS type-check/build was not run (project rule). Verify OptionsStrategyScreen compiles in Xcode: computeLocal's 6-element localMetrics tuple and its nested reduce closures.

### p2-69: [Docs/Repository] Transaction-ledger branch deletes root agent guidanc

- Orchestrator: stage the move with `git add -A AGENTS.md CLAUDE.md GEMINI.md README.md mkdocs.yml pyrightconfig.json .TextFiles/` so the deletions under .TextFiles/ and the new root files are both recorded (git will detect renames).
- Owner: confirm the July move into .TextFiles/ (852b22a deleted them in a merge-conflict commit, c5c0de3 re-added them under .TextFiles/) was accidental. If you want them kept in .TextFiles/, revert this and add thin root AGENTS.md/CLAUDE.md pointing to .TextFiles/AGENTS.md instead.

### p1-03: 'Export PDF' never produces a PDF, ignores HTTP status, and fires an u

- Product sign-off: Export PDF now produces a factual Portfolio Summary (holdings, totals, watch items, a 'Not investment advice' footer) instead of the AI-written 'Overall Recommendation' review. Any future narrative text must come from the new research engine, behind the grounding validator, the per-user quota and the per-day cache, not from a direct Sonnet call.
- Confirm fpdf2 (>=2.8.1, from requirements) is installed in the production backend environment. Without it the endpoint now returns 503 'PDF export unavailable' instead of a text file.
- Run backend/tests/test_portfolio_pdf_export.py on the remote server (pytest -q backend/tests/test_portfolio_pdf_export.py).
- Ship a new iOS build so users get the HTTP-status and MIME checks, the .pdf filename and the inline error message. Older builds will now receive a real PDF, but they still share whatever file arrives.

### p3-05: About 5,200 lines in 18 Swift files have no externally referenced symb

- Build in Xcode and smoke-test Home, Portfolio, Stock Profile (Overview/Financials/Dividends/Sentiment tabs), Alerts and Copilot to confirm that removing the 19 files and the Dashboard Pulse code did not break the build.
- UX-31 decision: CompareScreen, HistoryScreen and WatchlistScreen were deleted per the recommended default; they can be recovered with git show <base>:<path> if the product wants them wired into navigation instead.
- Go through the 9 pre-existing unreferenced files on the ALLOWLIST in scripts/find_unreferenced_swift.py (AppSoundManager, PremiumUpsellBanner, StockTapActionSheetModifier, FundamentalsService, ValuationCalendarService, UniversalSearchView/ViewModel, StockCorporateActionsView, StockFinancialsView) as their owning audit items land; remove each entry once its file is wired up or deleted.

### w4-13: Opening any holding or ticker silently starts a paid multi-agent AI an (+1 more)

- Product: confirm the new default is that opening a ticker or holding without a saved report does NOT auto-run an analysis. It shows an idle screen with a RUN ANALYSIS button instead (recommended; it matches the app's own 'takes time and credits' wording). Users who turned on 'auto-regenerate stale' still get automatic re-runs, but only when they already have a cached report.
- Manual check on a device or simulator build: open a holding with no saved report and confirm there are zero POST /analyze requests until RUN ANALYSIS is tapped. Then start a standard analysis for stock A, go back, open stock B and tap Run. You should see the 'An analysis for A is already running' error, not a blank screen. Re-opening A while its job is running should attach and show progress.
- Run the new XCTest files (AnalysisAutoStartTests, AnalysisStartOutcomeTests) in Xcode. They could not be compiled here.
- The server-side half (auth plus per-user quota on /analyze, LLM-02/IOSCORE-04) is still needed. This client change reduces accidental spend but does not enforce limits.

### w5-05: Regulated-finance features would fail App Review: demo flows ship in n (+1 more)

- Create the IAP subscription products (Pro/Elite monthly and yearly) in App Store Connect and configure App Store Server Notifications V2. StoreKit 2 work can start after that: Product.products, Transaction.updates, and server-side verification to replace POST /api/v1/subscription/upgrade, which also closes #666.
- Confirm the Apple developer account type. If loans, FDs or KYC ever ship in Release, submit under an organization (legal-entity) account per guideline 5.1.1(ix), and add the maximum APR (<=36%) and payment due date to the loan cards per 3.2.2(ix).
- Decide what Release users are entitled to while IAP is absent. Recommended: unlock all tiers server-side, so Release users (who now see 'All features are free during the beta') do not hit 402s from server-gated endpoints (UX-11).
- Sign off on the design of the deeper light-mode green/red/amber (006954/B91919/785716), the darker light accents, the lighter dark-mode inkTertiary values, and near-black text on accent/status fills in dark mode.
- Run the stockmeTests target in Xcode (ReleaseGateTests, ThemeContrastTests). Make a Release build and check that Markets shows no Loans, FD, Finance Tracker or Pre-IPO cards and that Settings > Subscription shows the beta notice.

### p2-07: IPO Hub serves frozen mock rows: statuses never derived from dates (a  (+2 more)

- Run the backend suite on the server: test_ipo_status.py, test_notifications_inbox_producer.py, test_auth_rate_limit.py, test_comprehensive.py, and the existing login-heavy suites (test_ios_endpoints*, test_backend_contract_routes). This confirms the new 5/min login cap and the morning-summary auth gate break nothing.
- Decision (CMON-17): keep the fictional sample IPOs? Recommended default (already implemented): keep them, labelled 'SAMPLE DATA' through is_sample. With dates derived, all seed rows now show as 'listed', so the Hub's open/upcoming/closed tabs are empty until a real NSE/BSE IPO harvester exists or the seed dates are refreshed.
- Follow-up (CMON-19): move the rate-limit store to the shared Redis once a sync client exists, so the limit applies across all 4 uvicorn workers instead of per worker.

### w5-04: Release readiness gaps: ATS fully disabled, no privacy manifest, no pu

- Apple Developer portal: enable Push Notifications on App ID saumypatel.stockme, then regenerate the development and distribution provisioning profiles. On archive/export Xcode switches aps-environment to production.
- App Store Connect: fill in the App Privacy nutrition labels to match stockme/PrivacyInfo.xcprivacy (Name, Email, Phone, User ID, Device ID, Other Financial Info; linked, not tracking, purpose App Functionality). The widget manifest declares no collected data, only UserDefaults CA92.1. After upload, confirm that no ITMS-91053 warning appears for either stockme.app or PlugIns/NiveshWidgetExtension.appex.
- Run an Xcode build to confirm that the widget target bundles NiveshWidget/PrivacyInfo.xcprivacy and that the app still compiles. Type-checking was not possible here.
- Confirm the nivesh:// scheme on a device: run `xcrun simctl openurl booted nivesh://analyze/INFY`, and send a test push with payload {"ticker":"INFY"}. Both should open the INFY action hub.

### w5-07: Stress test drops the Nifty shock in 9 of 14 scenarios and uses placeh (+3 more)

- Confirm that the static PSU_TICKERS list and the AMFI-style market-cap cut-offs in backend/services/stress_test.py (LARGE_CAP_MIN_INR=1e12, MID_CAP_MIN_INR=3.3e11) are acceptable approximations. Refresh them when the AMFI list or the PSU set changes.
- Run the backend suites on the remote server: pytest backend/tests/test_stress_test_math.py backend/tests/test_stress_test_data_quality.py backend/tests/test_stress_test_engine.py backend/tests/test_stress_test_jobs.py backend/tests/test_backend_contract_financial.py
- Merge note: packages p2-14 (FAKE-18) and p2-35 (MATH-03) also edit backend/services/stress_test.py, and p2-35 also creates backend/tests/test_stress_test_math.py. This package already covers their stress-test parts using the same keys ('yf_symbol', 'is_estimated'). Resolve conflicts in favour of this version.
- Behaviour change for users: a stress-test job now FAILS with 'Insufficient market data' when less than 50% of the stock value can be priced live. Results also change (correct signs, realistic VaR, liquidity and concentration scores).

### p3-45: Finance Tracker fabricates balances/income/spend server-side, counts c

- Run backend/tests/test_finance_tracker_summary.py on the remote server.
- Check on iOS by hand: block only /api/finance/summary and confirm the red partial-error banner appears with accounts still listed and the summary not reset to ₹0. Also check that a credit-card-heavy demo user shows a negative NET BALANCE.

### p2-54: Dynamic Type is disabled by design: root pins .dynamicTypeSize(.large)

- Design acceptance: officialStampFont, serialNumberFont and microLabel now render at 11pt or more at the default text size, up from 7-10pt across about 814 call sites. If design rejects this, set Theme.microTextFloor to 0 in Utilities/Theme.swift, which keeps the scaling and drops the floor, and remove testMicroTextFloor.
- Manual layout pass before release: set Settings > Accessibility > Display & Text Size > Larger Text to AX2 and open Home, Portfolio, Alerts, Settings and a BanknoteDialog. Check that text grows, no key control is clipped off screen, and dense rows with fixed frames or lineLimit(1) do not truncate badly. Also confirm the widget still builds, since Theme.swift is compiled into NiveshWidgetExtension.
- Run ThemeScalingTests in Xcode (the agent may not run xcodebuild).
- Known limitation: Theme helpers read the system category through UITraitCollection.current rather than the SwiftUI environment. A text-size change while the app is running only takes effect when each view re-renders.

### p3-35: Route table audit: one duplicate METHOD+path, one double-prefixed alia (+1 more)

- Run backend/tests/test_route_table.py and backend/tests/test_lazy_singletons.py in CI or on the remote server. Backend tests are not run locally, by project rule.
- Stage the deletion of backend/routers/markets.py when committing. It currently shows as an unstaged ' D'.

### p2-48: Admin dashboard is blind and misleading: split-brain dashboard state,  (+2 more)

- On the server, run backend tests: pytest backend/tests/test_admin_dashboard.py backend/tests/test_error_contracts.py backend/tests/feature_tests/harvesters/test_rag_ingestion.py
- After deploy, open the admin dashboard and check that tables still render. Escaped values should show as plain text, and the stuck-job cancel button should still work through data-job.
- Make sure RAG_DB_USER is set in the server environment; it no longer has a default.

### p2-57: User-facing errors are developer-console output: endpoint paths, HTTP  (+1 more)

- Password reset (UX-14): the users table has no email or phone column, so the app has no channel to send a reset to, and no forgot-password path was added. Recommended for now: no in-app reset; document that support resets passwords by hand (an admin sets a new bcrypt hash for the user). The alternative is a product decision: collect a verified email at registration, which needs a new User column, an Alembic migration, an email provider and reset-token endpoints.
- API behaviour change to note in the deploy: POST /register now returns 400 for passwords shorter than 8 characters or longer than 72 UTF-8 bytes (bcrypt limit). Older app builds will show the raw JSON for this 400 until they are updated.
- After CMON-01 (/register returns access_token) lands, test sign-up end to end on a device. Also check that password managers offer to save credentials on the new textContentType fields; that needs the app's associated domains to be configured.

### p2-59: Currency and number formatting defects: '₹₹' double symbol, rupee symb

- Run IndianFormatterTests on the simulator. The exact strings assume en_IN NumberFormatter output with no space after the symbol ('₹1,23,456.00'). The source-scan test reads the host checkout through #filePath, and skips if that path cannot be reached.

### p2-31: Hot-path DateFormatter allocations and silent '?? Date()' fallbacks in (+2 more)

- Build the app in Xcode and run the stockmeTests target (WireDateTests, ChartMathTests, PollOptionDraftTests). xcodebuild and swiftc typecheck are not allowed in this workflow.
- Manual check on the Portfolio tab: add or sell a holding, pull to refresh, and confirm the risk card, red flags and valuation hero chart update. Switch tabs and come back, and confirm those three do not refetch.
- Optional follow-up outside this package: add `.droppingUndated` to priceHistory90d at Views/Analysis/AnalysisCoreSections.swift:215.

### p2-66: Search still decodes a bare array from /api/v1/search, but the backend (+1 more)

- Run `pytest backend/tests/test_search_api.py` on the remote server to confirm the five regression tests pass.

### p2-68: [Backend/Data] NSE filings scraper sends misspelled Referer domain

- On the remote server, run `_nse_session().get('https://www.nseindia.com/api/corporate-announcements?index=equities', timeout=15).json()` and check that it returns JSON records with the keys symbol, sm_name, desc, an_dt and attchmntText. If NSE uses other names, adjust the mapping in `_scrape_nse_filings()` and the `detail` lookup in `extract_auditor_info()` in backend/services/filings_extractor.py.
- After deploy, check the logs for 'NSE filings scrape failed (<Type>)'. If it keeps appearing, harvest_filings is still falling back to Moneycontrol (source='moneycontrol').

### p2-62: Custom replacements for system alerts, back button and toasts drop acc

- Build in Xcode and run MotionPolicyTests.
- Manual VoiceOver pass: Portfolio long-press > Remove. Focus should land on the dialog title, a two-finger Z (escape) should close it, and the background rows should not be reachable.
- Edge-swipe back from AnalysisScreen opened directly from Portfolio, Home, Search, Earnings Dashboard and Technical Momentum. Also check that the hero-chart drag scrub still works and does not conflict with the swipe.
- Visually check the AnalysisScreen back button. It now uses the shared BanknoteBackButton: same chevron coin, plus a fine border and a fixed glyph size.
- Settings > Reduce Animations on (or system Reduce Motion on): there should be no shimmer, pulse, typing-dot or SeverityDot motion.
- Optional follow-up outside this package: StockActionHubView.swift:175 can drop its own HapticManager.selection() from the banknoteBackButton closure, because the button already plays the haptic.

### p2-71: Piotroski grade applies absolute 7/4 thresholds to a variable number o

- Run backend/tests/test_piotroski_grading.py on the remote server. It loads the real services/piotroski.py from its file because conftest mocks both services.piotroski and yfinance.
- After deploy, invalidate the disk_cache 'piotroski' namespace so cached grades are recomputed with the new grading.
- Out of scope, needs a separate ticket: backend/routers/analysis.py:1072-1073 compares the dict returned by compute_piotroski(ticker) with `< 7`. That raises a TypeError, the except swallows it, and so that screener path never returns results.

### p2-74: Unattended agent loops run with approvals and sandboxing disabled, one

- On the production server 192.168.1.122, run `crontab -l | grep -v run-opencode-scanner | crontab -`, then `crontab -l` to confirm the entry is gone.
- On the same server, stop any running Codex loop with `pkill -f codex_issue_loop.sh` and check that no opencode or codex agent process is left.
- If you still want the agent loops, set them up on a separate machine or Unix user with a fresh git clone that has no backend/.env and no *.db files. Give them a fine-grained GitHub token limited to this repo's issues, and limit egress to github.com where possible. Run the OpenCode scanner only inside a disposable container or VM with NIVESH_SCANNER_REPO=<clone> and NIVESH_AGENT_SANDBOXED=1.
- If you suspect a scanner run on the server processed a malicious issue, rotate the API keys that were in backend/.env on that host.

### p2-75: Migration tests and CI's alembic check are tautological (root migratio

- Run on the remote/CI: pytest backend/tests/test_backend_contract_migrations.py backend/tests/migrations/test_alembic_health.py. Expect test_alembic_downgrade_roundtrip to show XFAIL and every other test to pass.
- After w5-02 (DB-07) merges and fixes the 163d downgrade: if test_alembic_downgrade_roundtrip reports XPASS(strict), remove the xfail marker; if it still fails, update the reason to name the next broken revision.
- Merge note: w5-02 also edits backend/tests/migrations/test_alembic_health.py. This package only deletes line 53 there.

### p2-61: Community forum ships user-generated content with no report, block or 

- Owner: replace the placeholder ForumModeration.contactEmail in ios/StockApp/stockme/stockme/Views/Forum/ForumModerationViews.swift with the real moderator/grievance contact email (Apple 1.2 requires published contact info; REG-13 asks for a Grievance Officer under IT Rules 2021).
- Owner/legal: approve or edit the community-guidelines text in ForumGuidelinesSheet before App Store submission.
- Run the Alembic upgrade to e3c2837fd058 on the server (after backups per OPS-03), then run backend/tests/test_forum_moderation_api.py and the migration contract tests there.
- Until admin tooling exists, someone must review GET /api/forum/admin/reports?status=open within 24h and resolve each report via POST /api/forum/admin/reports/{id}/resolve with {action: hide|dismiss}. A 'hide' is permanent through the API; reversing one currently means editing forum_posts.moderation_action directly.

### p3-44: Forum vote counters are denormalised and updated with ORM read-modify-

- Run on the server: pytest backend/tests/test_forum_vote_counters.py (cannot be executed locally per project rule).
- Optional: if live counters have already drifted, run a one-off backfill: UPDATE forum_posts SET upvotes/downvotes from COUNT(forum_votes), and the same for forum_poll_options.vote_count.

### p3-47: [Testing/API] Route registration verifier checks stale critical paths

- Run backend/tests/test_verify_route_registration.py on the remote server; it was not executed here.

### p3-49: [Backend/Dead Code] alpha_validation_service.generate_reports is unrea

- Merge order: package #652 (FAKE-12, the regime breakdown constants) edits the same file. If it also deletes generate_reports, take either side when the hunks conflict.

### p3-29: ml-engine :8001 is unauthenticated, published on all interfaces, accep (+1 more)

- Before the next deploy, confirm on the server that nothing besides the host backend uses :8001, for example: ss -tnp | grep 8001.
- After redeploying with scripts/deploy_ml_engine.sh, check from another machine that the port is closed: curl http://192.168.1.122:8001/health should be refused. Then check that curl http://localhost:8001/health on the server still returns ok.
- Watch the container for an OOM restart loop under the new --memory 2g / --cpus 2 caps (docker stats ml-engine; docker inspect -f '{{.State.OOMKilled}}' ml-engine). Change ML_MEMORY/ML_CPUS in the deploy scripts if needed.
- Expected change in behaviour: ML signals are now 'unavailable' when fewer than 120 completed bars exist, or the input is stale or invalid; they are no longer zero-filled predictions. ml_signal_service now downloads 1y of yfinance history instead of 3mo.

### p3-50: [Ops/Credit Risk] run_analysis.sh can start paid /analyze jobs without

- Callers of scripts/run_analysis.sh must now export ALLOW_PAID_ENDPOINTS=1, and NIVESH_TOKEN once #633 adds auth to /analyze.

### p3-51: [Testing/API] smoke_all_endpoints.py treats stale missing routes as he

- Run backend/tests/test_smoke_endpoints_contract.py and scripts/check_backend_health.sh on the remote server to confirm the expected statuses.
- If a later package changes these legacy routes from 401 to 403, update the expected numbers in ENDPOINTS.

### p3-53: [iOS/API] Quant Lab prediction horizon query is ignored by backend end

- Manual check: open the Quant Lab screen and confirm calibration, pillar attribution and model versions still load.

### p3-54: CrashInterceptor runs non-async-signal-safe code (allocation, JSON, fi

- Manual on-device test (a): trigger a forced-unwrap crash. Check that the app terminates promptly with no hang and the crash appears in Xcode > Devices > View Device Logs.
- Manual on-device test (b): raise an NSException. Check that CrashLabView lists it after relaunch.
- Note: CrashLabView will no longer list signal crashes; only NSException crashes are recorded in the app.

### p3-55: RSI numpy fallback uses SMA (not Wilder) and returns 50 instead of 100

- Run backend/tests/test_factor_engine_rsi.py on the remote server.

### p3-62: fix_buttons.py is a stale, buggy one-shot rewriter that silently does 

- Delete the untracked file ios/StockApp/stockme/fix_buttons.py in the root checkout /Users/saumya/Desktop/career/nivesh: rm /Users/saumya/Desktop/career/nivesh/ios/StockApp/stockme/fix_buttons.py (agents may not modify that checkout).
- Optional: ios/GEMINI.md:9 still points to the stale path /Users/saumya/Desktop/nivesh/backend/run.sh. Either update or remove that line, keeping in mind the rule that the backend runs only on the remote server.

### p3-22: Dynamic Type pinned to .large app-wide; 21 accessibilityLabel for ~329

- Run the UI tests manually in Xcode against a signed-in simulator: stockmeUITests/AccessibilityAuditUITests. The UI target is not in the CI scheme. Expect the first run to flag issues that existed before this package, such as fixed-size fonts and sub-44pt icons at AX5. If so, narrow the audit types or add an issue-handler closure.
- Manual check: Settings > Accessibility > Larger Text at AX2. Home, Portfolio and Analysis should stay usable, and VoiceOver should announce the Morning brief, Search/Close search, Show calendar/Show list and Add holding/Add to watchlist buttons.
- Build in Xcode to confirm the label additions type-check. Only swiftc -parse was run.

### p2-56: Entitlement gating has no client path: HTTP 402 is never handled, Prem

- Run the stockmeTests target in Xcode (NetworkErrorEntitlementTests plus the existing NetworkErrorCopyTests) to confirm the code compiles and the tests pass.
- Manual check in a Debug build as a free user: Options Strategy 'compute' and Strategy Lab 'Run Backtest' should show the PRO upsell banner, which opens PaywallView. Pre-IPO advisory cards should be blurred and locked unless the account is Super PRO.

### p2-30: Money, percent and unit formatting defects: double rupee sign, rupee s (+4 more)

- Build in Xcode and run stockmeTests (IndianFormatterTests, DonutGeometryTests, CalendarHeatGridTests, ChartPeriodAndFilterTests, AppLockPolicyTests).
- Manual app-lock check on a device: enable the app lock (timeout Immediately), open a stock profile tab, background and foreground, unlock. You should return to the same screen.
- Manual app-lock check, sheet case: open any sheet (for example Portfolio brief with P&L, or a stock-profile sheet), background past the lock timeout and return. The lock must draw above the sheet and the sheet must not respond to touches until you unlock. After unlocking, the sheet must still be there.
- Manual privacy check with a sheet open: swipe to the app switcher. The snapshot must show the NIVESH cover, not the sheet's balances. Also check that pulling down Control Center shows the cover and that it clears on return.
- Manual: fail Face ID repeatedly. You should get the passcode prompt and the app must never unlock on its own. Also confirm the device-passcode fallback UI appears above the lock window. Check that VoiceOver focus stays on the lock screen and that dark mode renders the lock correctly.
- Manual: the cold-launch lock must appear only after the launch animation finishes, and Sign out from the lock screen must hide the lock window and show login.

### p2-55: VoiceOver semantics are almost absent: 22 accessibility modifiers for  (+1 more)

- Manual VoiceOver pass on Home, Portfolio, Settings, Search, Copilot, the Loan/FD booking flows and the calculators. Expected: icon buttons announce their labels; settings pickers announce e.g. 'Font Size, Standard, pop-up button'; sliders announce rupee or month values; Settings section headers appear under the rotor's Headings.
- Manual check of Markets > Sector Rotation. A free-tier user should see the PRO upsell (Debug) or the friendly upgrade copy (Release), not a decoding error. A Pro user should see sectors, and the request should carry Authorization: Bearer.
- Follow-up (not done): hide hindiFont text from VoiceOver at the remaining call sites outside SettingsGroup, which lives in Theme.swift outside this package.

### docs-research: Research engine methodology, compliance and runbook docs

- Once ml-models-registry is integrated, check the exact argument shape of 'python -m research.registry promote/verify' and adjust RUNBOOK.md sections 5 and 7.1 if it differs from '<model_id>'.
- Before Stage 1, verify the ISINs in RUNBOOK.md section 2.2 (marked 'to be verified on the first backfill' in the spec).

### be-db-ledger: Research tables, Alembic migration and repository

- Before merging, re-check that t4u5v6w7x8y9's down_revision (s3t4u5v6w7x8) is still the single Alembic head on the integration line.
- CI still needs to run backend/tests/test_research_repo.py and 'alembic upgrade head && alembic check'. They could not run locally because of the project rule.

### ml-contract: ml-engine research package skeleton, frozen config, ResearchReport contract, formatting, schema and fixtures

- Confirm that keeping top-level `coverage` (universe membership) exempt from the banned-names test is acceptable. It departs from brief acceptance check 1, but every downstream package codes against it.
- Pin pydantic 2.13.4 wherever `export_contract --check` runs in CI, because the generated schema depends on the pydantic version.
- Resolve the be-prose 5-vs-3-sentence conflict in the spec, and the iOS mapping of label_definition and coverage (carried over from the implementer).
- Optional, before gates.py is written: rename GATES['P']['min_auc_ci_low_every_year'] to an explicit strict '>' key (spec 5.6 says CI low > 0.52), then re-pin config_sha256 and regenerate the fixtures. Also decide whether the dev-only FAST block should stay inside config_sha256.
- ml-descriptive must use the same range interpretation as this package: the 252 minimum counts returns in the window, not sessions of history.

### ios-research-models: iOS ResearchReport Codable models, network extension and fixture decoding tests

- Run the stockmeTests ResearchReportDecodingTests suite in Xcode, since xcodebuild is not allowed for agents.
- Make sure be-serve-api's model-card summary returns `horizons` as an array of {horizon_days, tier_text}. ResearchModelCard decoding throws on the dict-keyed shape that ml-engine's /model-card uses.

### ml-descriptive: Risk metrics, historical return ranges and fundamentals (values only)

- When report assembly integrates this package (ml-assembly-pipeline), pass risk_block's universe_vol_pct as 100 x the universe's vol_252 feature values on the as-of date. Fill fundamentals peer_pes with fundamentals.pe_ttm(payload) for same-sector universe peers, excluding the stock itself.

### ml-validation: Walk-forward folds, HAC metrics, daily-path portfolio costs, gates and JSON-to-markdown report

- Downstream packages ml-models-registry and ml-assembly-pipeline must supply slices.vol_tercile as {name: {mean_ic}} for gates.py, in addition to data_checks, positive_period_share and bss_ci95_lockbox. portfolio_returns returns fractions, and gross is not an active return, so the assembler must subtract the benchmark before filling any *_pct active field.

### be-prose: Facts payload, grounding validator, templates and DeepSeek formatter

- Run backend/tests/test_research_validator.py and backend/tests/test_research_formatter.py in CI or on the server. They were not run locally (backend code is never executed here). The ci-research package should add them to backend_ci.yml.
- Callers (be-ingest-jobs, be-serve-api): call generate_narrative(report_dict, known_symbols=..., company_names=..., allow_llm=..., calls_remaining=...), taking the symbols and names from repositories.research_repo.known_symbols_and_names(session, exclude_symbol=report['symbol']). Store narrative['status'], attempts and failures through set_narrative_once. For a template-only narrative at serve time, use allow_llm=False.

### ml-marketdata: Bhavcopy ingest, gap-fill, entity linking, adjustments, quality checks, store and PIT universe

- Run the first live smoke download only with your approval; it needs RESEARCH_HTTP_CONTACT set. It should confirm the UDiFF column names (marked [verify on the first live file]) and how far back the legacy archive goes (spec 3.9). If 2008-era files lack ISIN or TOTALTRADES, the backfill fails closed with BhavcopySchemaError.
- After the first backfill, check panel.attrs['backfill_failed'] (the CLI prints it as failed_dates) and re-run to retry those dates.
- OPS: review `python -m research.marketdata.store events --kind ca_unverified` for price moves absorbed after an entity spent time outside EQ (reviewer note a).
- Downstream packages should key point-in-time logic on 'suspect' or source, not on the 'delisted' quality flag (reviewer note b).

### be-ingest-jobs: Fail-closed research flags, ml-engine client, scheduler jobs and dashboard key

- Run backend/tests/test_research_jobs.py on the remote server (pytest is not allowed locally).
- ml-api-deploy must accept the request bodies {symbol} for /compute and {items} for /outcomes, which this client sends.

### ml-models-registry: Baselines, LightGBM procedure, calibrator, registry/manifests, trial ledger and walk-forward training CLI

- OPS order (spec 12.4) is now enforced. On the server, open the lockbox once per horizon with a second reviewer: python -m research.train --horizon H --source store --open-lockbox --confirm-config-sha <config_sha256>. Then run --train-production; it reuses the recorded models/lockbox/rg-lgbm-v1-hH.json. A non-dev --train-production without a recorded lockbox is refused.
- At freeze, also commit models/lockbox/rg-lgbm-v1-h21.json and -h63.json to docs/research/validation/ with LOCKBOX_LOG.jsonl, because the logged result_sha256 can only be checked against that file. Never edit or delete it: later runs fail closed on a mismatch.
- To retrain the same data and config after a manifest exists, use a new data snapshot or config (new model_id). Rewriting a manifest-bound artefact directory is refused.

### p3-41: 'Income-tax calculator' is ticked done but exists only as an unused ba (+1 more)

- Decide whether you want an in-app income-tax calculator. The default is no (the dead module is now deleted). If yes, it is a new feature: a POST /api/v1/calculators/income-tax endpoint with a tax_year parameter, plus a fourth CalculatorsView tab. Someone must also supply FY2026-27 slab, 87A rebate, standard deduction, marginal relief and 4% cess values checked against the Finance Act. The audit's values come only from general knowledge and must not be shipped.
- Build the iOS app in Xcode to confirm it is green after removing AuthManager.shared and the UniversalSearch files (no type-check could be run here).

### w2-04: ChangeBadge prints a '+' on every loss (abs() fed into a formatter wit

- Run the stockmeTests target in Xcode (ChangeBadgeTests). It could not be compiled or run here because xcodebuild and swiftc -typecheck are not allowed.

### w1-03: Unauthenticated /charts StaticFiles mount serves every user's portfoli

- The repo is PUBLIC and user 2's real portfolio charts are in git history. Purge them with `git filter-repo --path backend/charts --invert-paths` (or BFG), force-push all branches and tags, ask collaborators to re-clone, and if needed ask GitHub support to drop cached views and forks.
- On the production server, delete the stale backend/charts/* files (rm backend/charts/chart_*.png backend/charts/meta_*.json) before or at deploy. The pull will remove the tracked files, but locally generated ones stay on disk.
- Ship a new iOS build. Installed builds lose portfolio chart images until then, because the public /charts mount is gone.
- Run backend/tests/test_portfolio_chart_auth.py on the remote server with pytest.
- Optional follow-up: add a backend/.dockerignore that excludes charts/, and document the new image route in docs/architecture/API_CONTRACT_MAP.md, docs/codebase/API_CONTRACT_MAP.md and docs/ios-api-endpoints.md.

### w1-10: Root-level backend/test_*.py scripts make paid Claude/DeepSeek calls a

- On the remote host after deploy, run `cd backend && python -m pytest --collect-only -q | grep -v '^tests/'`. It should print no node ids, only the summary line. Also run `python -m pytest tests/test_suite_hygiene.py` there.
- A bare `pytest` from backend/ no longer runs backend/tests_suite/. Run `python -m pytest tests_suite/` explicitly if you want that suite.
- Out of scope, left untouched: scripts/scratch/test_morning.py calls asyncio.run() when imported and writes to the real cache. The new root pytest.ini keeps it out of bare runs, but `pytest scripts/scratch` would still import it. Consider renaming or deleting it. GH-613 (paid sections in scripts/test_all.sh) is a separate item.
- Close GH-612 and GH-624 once this is merged (no GitHub writes from this agent).

### w1-08: Analysis start/poll/cancel/active and NL-screener calls send no Bearer

- Run the stockmeTests target in Xcode on a simulator, in particular AuthRequestTests. It was neither run nor type-checked here because xcodebuild is not allowed.
- Manual check: on a dev build, use Proxyman or Charles to confirm that these requests carry Authorization: Bearer, X-App-Version and X-App-Build: POST /analyze, GET /analyze/job/*, GET /analyze/active, POST /analyze/*/cancel and POST /api/v1/screener/natural-language.
- Release order: when archiving this iOS build, bump CURRENT_PROJECT_VERSION (it is 1 in every target today) so the build number is identifiable. Ship the build and let it reach users. Only after that, deploy the AUTH-08 backend enforcement: require_auth on POST /analyze, /analyze/job/{id}, /analyze/active and /analyze/{id}/cancel; ignore the client's user_id; return 404 for jobs owned by someone else. AUTH-08 should answer requests with no X-App-Build, or a value below this build number, with a 426 'update required' payload.

### w1-09: Info.plist lacks microphone/speech/calendar purpose strings: voice sea (+1 more)

- Land the conflict-marker repair commit 0925ba8 on main before or together with this commit. Otherwise static-checks fails every PR, because main at 1a16f08 still contains conflict markers and injection breakers.
- Run a real Xcode build of the stockme scheme (or let build-ios run on the PR) to confirm that the app compiles with the Info.plist and EarningsDashboardView changes.
- After the first green run, mark both 'static-checks' and 'build-ios' as required status checks in main's branch protection.
- Optional: update .TextFiles/README.md:567, which still says ios_ci is triggered by 'Push to ios/**'. It now runs on every PR to main.

### w4-14: Dashboard SSE stream and AI-engine monitor leak all users' jobs to any

- scripts/test_all.sh lines 425 and 715-719 (manual live-server smoke script, outside this package) still expect 200 or 422 for /api/v1/dashboard/stream when called with a normal user token. They now return 403, or 401 with no token. Update the expected statuses when that script is next touched.
- The admin page in main.py fetches /api/v1/dashboard/ai-engine with 'Bearer admin' (the ADMIN_TOKEN override, which resolves to user_id 1). That now works only if user 1 is in the in-memory admin set, i.e. is saumya or nirav (see AUTH-18/REL-08).
- The shipped iOS DialecticProgressView will now get 403 from /dashboard/stream and fall back to its scripted progress. Real progress already comes from /analyze/job checkpoints. IOSCORE-18 should remove the stream client.

### w4-15: APNs price-alert pushes always fail when APNs is configured: httpx htt

- After the next deploy (deploy.yml runs pip install -r requirements.txt), check on the server: venv/bin/python -c 'import h2, cryptography'. It should exit 0.

### p2-01: main.py keeps shadow copies of dashboard state, caches and DataHarvest (+2 more)

- Confirm whether production runs Redis. If it is not at localhost:6379, set REDIS_URL in the server .env (the cache now reads it, as routers/health.py already does). Without a reachable Redis the cache is a bounded per-process in-memory TTLCache, the same behaviour as today's silent fallback, and each Redis failure triggers a 30 s backoff.
- Build the iOS app in Xcode once. Check that Resources/nse_bse_symbols.json appears under the stockme target's Copy Bundle Resources (it is picked up by the synchronized folder group) and that the bundled app contains nse_bse_symbols.json. Then run StockDatabaseTests.
- Run the backend suite on the server, including the new tests: pytest tests/test_dashboard_state_single_source.py tests/test_cache_service_sync.py tests/test_stock_universe.py tests/morning_briefing/test_cache.py tests/morning_briefing/test_regression.py

### w3-02: ML engine labels every stock BULLISH: a 3-tree binary booster's probab

- Owner to confirm the product choice: hide the ML direction and confidence on the stock-profile ML card and the QuantLab Model Signal section until a model passes the ML-05 promotion gate. The implemented default shows the warning 'This model has not shown out-of-sample skill, so no direction is shown.' with label 'NO VALIDATED SIGNAL'.
- Deploy the backend and the ml-engine in either order: the backend treats a missing signal_state from the current engine as no_edge. After restarting the ml-engine, check that GET /model/status shows model_validated=false and that POST /predict/single returns signal_state 'no_edge' with direction 0 and confidence 0.0. Then ship the iOS update; until then the App Store build shows '— NEUTRAL' and 'CONF --' on the profile card.
- On the server, run: pytest backend/tests/test_ml_signal.py backend/tests/test_ml_client_integration.py backend/tests/test_ml_production_integration.py backend/tests/test_fallback_safety.py
- When a model is promoted under ML-05/ML-07, models/MANIFEST.json must contain gate.passed=true, base_rate as a fraction in (0,1) and neutral_band in [0,0.5). Otherwise the ml-engine refuses to start; without a manifest it serves no_edge.

### w4-12: [Security/Deployment] ML deploy script disables SSH host-key verificat (+1 more)

- Before the first run with StrictHostKeyChecking=accept-new, confirm that the host key for 192.168.1.122 in ~/.ssh/known_hosts is the real one. On the server console, run `ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub`. Locally, run `ssh-keygen -F 192.168.1.122 -l`. Compare the two fingerprints. If they differ, remove the wrong entry with `ssh-keygen -R 192.168.1.122` and reconnect.
- Run deploy_ml_engine.sh from inside the local repo on a commit that has been pushed to origin. DEPLOY_SHA defaults to the local HEAD, and it must be a descendant of the server checkout's HEAD.
- Run one ML deploy on the server to validate the new flow. While it runs, `watch curl -s localhost:8000/ping` and confirm the backend PID does not change. Tune ML_MEMORY/ML_CPUS for the box (default 2g/2 CPUs). If ML_CPUS is higher than the host's CPU count, the run fails and rolls back.
- Follow-ups outside this package: docs/research/RUNBOOK.md:60-61 still describes the old pkill behaviour and flags that do not exist, and docs/codebase/DEPLOYMENT_MAP.md:73 still says the script restarts backend Uvicorn. Also note in the deploy docs that Step 2 updates the shared server checkout without restarting the backend.

### p3-57: `git add -A` helpers plus .gitignore gaps would commit a dangling syml (+1 more)

- Orchestrator, at commit time: stage the deletions of scripts/commit.sh and backend/deploy_update.sh explicitly (git rm or git add of those paths).
- If AUTH-04 has not already done it, run 'git rm -r --cached backend/charts' so the tracked chart_2_*.png and meta_2.json stop being tracked; the files stay on disk and are now ignored.
- In the main checkout (/Users/saumya/Desktop/career/nivesh), remove the dangling root symlink: 'rm /Users/saumya/Desktop/career/nivesh/nivesh' (it points to /Users/saumya/Desktop/Desktop/nivesh, which does not exist).
- Decide whether to delete the untracked agent state in the main checkout (.claude-flow/, .swarm/, agentdb.rvf, agentdb.rvf.lock). They are now ignored, so they will no longer show in git status.
- If the backend/charts PNGs or meta JSON hold real user portfolio data, consider purging them from history (see AUTH-04).

### p3-58: Deploy runbook's 'critical endpoint audit' calls a paid DeepSeek endpo

- Merge after or alongside OPS-06 and AUTH-02, which edit the same runbook sections (Steps 1/2/6 and the admin auth line). Expect small textual conflicts on the SHA line in Step 1.

### w2-03: Ledger replay ignores pre-ledger holdings: once #655 is fixed, the fir (+2 more)

- Run on the remote server, from backend/: `../venv/bin/pytest tests/test_portfolio_ledger.py tests/test_portfolio_price_unavailable.py tests/test_transaction_ledger.py -v`. test_transaction_ledger.py Part 1 already fails on `session=`; that failure is pre-existing.
- Before the ARCH-01/#655 fix ships, run this detection query on a prod DB copy. It lists ledger keys whose holdings row is missing: `SELECT t.user_id, t.ticker, SUM(CASE t.transaction_type WHEN 'BUY' THEN t.quantity WHEN 'BONUS' THEN t.quantity WHEN 'SELL' THEN -t.quantity ELSE 0 END) AS ledger_shares FROM portfolio_transactions t LEFT JOIN portfolio p ON p.user_id = t.user_id AND p.ticker = t.ticker AND p.group_name = 'holdings' WHERE p.id IS NULL GROUP BY t.user_id, t.ticker HAVING SUM(CASE t.transaction_type WHEN 'BUY' THEN t.quantity WHEN 'BONUS' THEN t.quantity WHEN 'SELL' THEN -t.quantity ELSE 0 END) > 0;`. This is approximate: it ignores SPLIT and ADJUST. The new reconcile writes ADJUST 0 for these keys on their next ledger write, so no manual repair is needed. If you want the ledger clean beforehand, insert one ADJUST (quantity 0, price 0) per listed (user, ticker) in its default group.
- Also on the prod copy, list rows whose shares differ from the ledger, i.e. rows re-seeded or edited outside the ledger: join portfolio (group_name='holdings') to the same per-(user, ticker) SUM and compare it with ROUND(p.shares, 2). These rows are restated to the row's values by an ADJUST on their next trade. Check that the row, not the ledger, is the correct one, especially for populate_portfolio and reset_mock_user seeds.
- Confirm whether scripts/migrate_ledger.py was ever run in production. Check the group_id mismatch case: if a legacy row's ledger sits in a 'Legacy Holdings' group that get_or_create_default_group does not return, the reconcile seeds an opening balance in the resolved default group. Verify this on a prod DB copy. Duplicate default groups are DB-09's concern.
- ARCH-01 (#655: PortfolioAddRequest.transaction_type, and the PortfolioUpdateRequest bindings) must land together with or after this package. PUT /portfolio/update still returns 500 until it does, on req.target_price, before any write happens.
- Run the iOS unit test PortfolioHoldingPriceStatusTests from Xcode. It cannot be run here. Optionally, show the new 'estimated' flag from /api/v1/portfolio/valuation-history on the hero chart.
- Optional follow-up outside this package: add a same-day retry cron for snapshot_all_users in harvest_worker.py, for example 13:00 UTC. A skipped day would then be filled when the price miss was transient. The 3-day bound already prevents a permanent freeze.

### w3-06: Mutual-fund NAV chart plots a fabricated pseudo-random walk as real hi

- Decide whether to build a real mutual-fund catalog and NAV-history feed. That means seeding real AMFI scheme codes (the current mock codes are ISIN-like, so amfi_nav_harvester never matches them), adding an AMFI historical-NAV harvester and a nav_history table (via a new Alembic revision), then backing get_nav_history with it and re-adding 3Y/5Y ranges once the backend's days limit is raised. Until then the chart shows its empty state and the catalog is labelled as sample data.
- After deploying, run backend/tests/test_mutual_fund_provenance.py on the remote server, and run MutualFundDecodingTests in Xcode.

### w3-12: Mock/demo-backed hubs live in production navigation with inconsistent 

- Product decision: Release currently hides Finance Tracker, Loans, FD, Pre-IPO and Account Security until real data and services back them. Decide whether IPO Hub and Mutual Funds keep a SAMPLE banner (FAKE-06; they can reuse .demoDataRibbon()) or are hidden too by adding them to ReleaseGate.hiddenInRelease.
- Run stockmeTests in Xcode (MarketSectionGatingTests, ReleaseGateTests). Then check a Release-configuration build: no Finance Tracker, Loan, FD, Pre-IPO or Account Security entries, no 'GET EXPERT ADVICE' panel on News. Check a Debug build: the demo hubs and Account Security show the DEMO DATA ribbon.

### w1-05: Test DB isolation relies on os.environ.setdefault while main.py loads  (+1 more)

- Commit backend/tradingagents-core/pytest.ini with `git add -f`. backend/.gitignore:28 ignores tradingagents-core/ even though its files are tracked, so `git add -A` will silently skip the new file. The 'placeholder' DEEPSEEK_API_KEY in backend/conftest.py keeps the live DeepSeek class skipped even without it, but the ini is the preferred isolation.
- On the remote server, run `pytest tests tests_suite` and `pytest tradingagents-core/tests` from backend/ and check two things: backend tests pass against the per-session temp SQLite DB, and TestDeepSeekLiveStructuredOutput is skipped when no real key is exported in the shell.
- Release a new iOS build: shipped builds have no AI Processing consent toggle, so users cannot opt in to AI portfolio features (and LLM portfolio features stay off for everyone) until the new KYCConsentType.aiProcessing build ships.

### w3-15: QuantLab regime breakdown returns constant BULL/BEAR metrics and a sel

- Run backend/tests/test_alpha_validation_no_constants.py, test_alpha_validation.py and test_quantlab_api.py on the remote server to confirm they pass.

### w3-16: Withdrawing a KYC consent in the app does not revoke it: POST granted=

- Run backend/tests/test_kyc_consent_withdrawal.py on the approved remote test runner.

### w1-07: /analyze/batch generates data-free Sonnet 'analyses' from a bare ticke (+3 more)

- After deploying: restart the backend so the scheduler registers the new db_backup job (02:30 IST). Then run the new and touched tests on the server: `cd /home/saumyapatel/Desktop/nivesh/backend && ../venv/bin/python -m pytest tests/test_backup_service.py tests/test_batch_routes_removed.py tests/test_paid_guard.py tests/test_job_manager.py tests/test_comprehensive.py -q`.
- OPS-03 server setup: (1) Check which DB is live: DATABASE_URL in backend/.env. (2) BACKUP_DIR defaults to ~/nivesh-backups (= /home/saumyapatel/nivesh-backups, outside the checkout); set it in backend/.env only to change it. (3) If DATABASE_URL is Postgres or RAG_DB_PASS is set, install postgresql-client matching the server's major version, so pg_dump exists. Otherwise the nightly run and the pre-migration gate will report failure. (4) Create a free healthchecks.io check (period 1 day, grace 2h), put its ping URL in BACKUP_HEARTBEAT_URL in backend/.env, and route alerts to phone or email. (5) Add the off-host copy to the service user's crontab, e.g. `30 4 * * * rclone copy /home/saumyapatel/nivesh-backups remote:nivesh-backups && rclone delete --min-age 60d remote:nivesh-backups`. Use copy, not sync, or rsync -a without --delete to another machine. (6) Run `cd backend && ../venv/bin/python scripts/backup_db.py` once by hand, then do the restore drill in docs/codebase/BACKUP_RESTORE.md. (7) From now on, run every server migration as `../venv/bin/python scripts/backup_db.py && ../venv/bin/alembic upgrade head`.
- LLM-03 data purge (after a successful backup_db.py run): `cd backend && ../venv/bin/python scripts/purge_batch_analysis_rows.py`. That is a dry run printing a per-ticker count and analysis_date range. Review the list, then re-run with `--apply`. Separately, decide whether to delete the signal_events rows that batch-saved signal flips created for those tickers on those dates; they cannot be matched to batch rows reliably, so check them by ticker and event_date by hand.
- Stale docs left for the next doc regeneration (not touched, to keep the change set small): docs/codebase/API_CONTRACT_MAP.md rows for POST /analyze/batch and GET /analyze/batch/{batch_id}, backend/tests/TEST_INVENTORY.md rows 13-14, the two batch requests in backend/tests/nivesh_api.postman_collection.json, and nav entries for BACKUP_RESTORE.md in docs/codebase/README.md and .TextFiles/mkdocs.yml. .TextFiles/CLAUDE.md, an identical copy of AGENTS.md, does not yet have the new backup-gate rule.
- Pre-existing bug noticed but out of scope: in backend/services/harvest_worker.py, _run_notification_cleanup and _run_backfill_preferences call `logger.info`, but no `logger` is defined in that module (only `logging`), so both nightly jobs raise NameError when they run.

### w3-08: Home-screen widget timeline is fully hardcoded (₹12.5L portfolio, +₹45 (+1 more)

- Register the App Group 'group.saumypatel.stockme' in the Apple Developer portal for both the app and NiveshWidgetExtension bundle IDs, and regenerate the provisioning profiles.
- Add the UserDefaults required-reason 1C8F.1 (App Group access) to PrivacyInfo.xcprivacy for the app and the widget.
- Merge together with FAKE-08: /api/v1/earnings/sync-ratio returns 500 until FAKE-08 lands.
- Run the backend tests on the server, including tests/feature_tests/external_clients/test_scraper.py::test_fetch_market_pulse, test_scraper_honest_fallbacks.py and test_ios_no_fabricated_content.py. test_fetch_momentum already failed on base.

### p3-32: Root README/AGENTS/CLAUDE/GEMINI files are still missing from the root

- Stage the moves with 'git add -A .TextFiles docs/ANTIGRAVITY.md docs/CONFIDENCE_RECOMMENDATIONS.md docs/PRODUCTION_READINESS.md CLAUDE.md GEMINI.md' so git records them as renames.
- Make sure the OPS-20 package adds 'test -f README.md -a -f AGENTS.md -a -f CLAUDE.md' and 'test ! -d .TextFiles' to scripts/check_repo_policy.sh.
- Any other package that edits CLAUDE.md or GEMINI.md should put those edits in AGENTS.md instead, since both files are now one-line imports of it.

### w3-07: Mock catalogs seeded on GET (mutual funds, IPOs, forum) are shown unla

- Take the OPS-03 DB backup before deploying. Then run alembic upgrade on the server to apply e0edc81fbf84, which purges the seeded mock MF and IPO rows. In prod, the MF and IPO lists will then be empty, which is the honest state.
- After deploy, check prod for the old seeded forum thread: SELECT id FROM forum_threads WHERE title='Welcome to the Nivesh Community Forum' AND is_pinned. If its only post is the OP, delete that post and the thread by hand. If real users replied, unpin it and decide by hand.
- Set DEMO_MODE=true only on dev/demo servers and leave it unset or false in production .env. Rows already seeded in prod loan_offers and fixed_deposit_schemes are not purged by this migration; they are left for FAKE-23.

### p3-30: Duplicate, divergent and unconsumed Alpha158 feature stores; the one w (+1 more)

- Owner decision (ML-23): confirm that ml-engine FeatureComputer is the single feature store and that both backend Alpha158 tables can be dropped. The alternative is to keep the tables and turn the backend pipelines into thin callers of a packaged FeatureComputer.
- Before deploying migration 36e47c594dc7, run on production: SELECT count(*) FROM alpha158_features; SELECT count(*) FROM alpha158_features_normalized; If either count is non-zero, export that table first.
- Make sure a production database backup exists (OPS-03) before running alembic upgrade on the server.
- If any Celery worker was started with '-Q alpha158', drop that queue from its command line; the tasks package no longer exists.
- Optional docs cleanup, left out to avoid merge conflicts: remove the Alpha158Feature/Alpha158Features, nightly_pipeline and alpha158_task mentions from CodebaseInformation/ARCHITECTURE.md, CodebaseInformation/ARCHITECTURE_MAP.md and README.md.

### p2-21: [iOS/API] YouTube summary failures return 200 with blank loaded conten (+4 more)

- Run the backend suite remotely: pytest backend/tests/test_ios_endpoints.py (CI file; the test count drops on purpose, from about 670 to 116) plus the new test_multi_asset_transactions.py, test_product_bounds.py, test_device_binding_unique.py and feature_tests/harvesters/test_youtube_summary.py.
- Before deploying, run `alembic upgrade head` on the production DB. 87e47e3f25d3 or ec35eaf96b81 stops with a RuntimeError if multi_asset_transactions has rows that break the new CHECKs or device_bindings has duplicate (user_id, device_id) groups. Clean those rows by hand if that happens; the migrations never delete data.
- The already-failing test_destructive_migration_operations_are_visible_for_audit_report will now also list the two new migrations, because both contain drop_constraint( (as the planner expected).
- API contract change: POST /api/v1/youtube/summary now returns 4xx/5xx on failure, and GET returns 404 for previously cached empty rows. Loan application and FD booking now return 422 for out-of-range or inactive products. The routers/youtube_summary.py docstring still lists only 400/401/503/500; I did not edit it because that file is outside this package.

### w5-02: Alembic history is not authoritative: root revision runs create_all(), (+1 more)

- Run the backend CI (build-and-test plus the new migrations-postgres job). This is the first real execution of the frozen baseline DDL and the new migration tests on SQLite and Postgres.
- Before the next deploy, reconcile production. Confirm the live DB's alembic_version is at or past t4u5v6w7x8y9, then let `alembic upgrade head` apply 117b4057d650, which creates watchlists only if it is missing. Do not re-run the root revision against production.
- Set ENVIRONMENT=production on the server (if it is not already set) so init_db skips create_all and Alembic stays authoritative.

### w1-01: Seeded accounts with a trivial password, admin-by-username promotion a

- Server, in this order: (1) Take a backup from backend/: ../venv/bin/python scripts/backup_db.py. (2) Pull the code and run '../venv/bin/python -m alembic upgrade head' BEFORE restarting nivesh.service. User now maps users.is_admin and users.token_version, so a restart without the migration makes every login and register query fail with 'no such column'. The old code ignores the extra columns, so migrating first is safe. Then restart.
- (3) Run '../venv/bin/python scripts/manage_users.py check-default-passwords'. For every 'DEFAULT PASSWORD: <user>' line, run 'scripts/manage_users.py reset-password <user>', or delete the account if it is unused.
- (4) Admin is no longer granted by name, so right after the deploy there is no admin and admin routes (dashboard, /users, harvest triggers) return 403 (fail-closed). Confirm which row really belongs to the owner (check created_at and portfolio contents, and whether someone else registered 'saumya' or 'nirav'), then run 'scripts/manage_users.py set-admin <owner username>' for that account only.
- (5) If a seeded or published password (123, or StrongPass@123 from reset_mock_user.py) was ever valid on the public server, rotate JWT_SECRET in backend/.env and restart. This logs everyone out. Also make sure ADMIN_TOKEN is unset (w1-02): that bypass still maps to user id 1 until w1-02 lands.
- (6) iOS: ship a build without the QUICK AUTHENTICATION strip; it compiles once WIP-01 lands. Manual check: the login screen shows no quick-auth row.
- (7) The live E2E suite now needs E2E_USERNAME and E2E_PASSWORD (a real account) to run its valid-login test. Postman's Login request now uses {{username}} and {{password}} environment variables.
- Orchestrator notes: w1-02's conftest admin_headers rewrite (register test_admin_9999, set User.is_admin=True) depends on this package's is_admin column. test_search_api.py and test_comprehensive.py mint tokens for fixed user ids 1 and 2, and no seeded users exist behind those ids any more. That matters once verify_access_token starts checking that the user exists (w3-09 / AUTH-13 / w4-02).

### p3-31: Dead or unused ML code carrying known defects (several already-closed  (+2 more)

- OPS-10: In GitHub repo settings > Secrets and variables > Actions, delete SERVER_SSH_KEY and SERVER_SSH_PORT.
- OPS-10: On the server (192.168.1.122), remove the public key that matches SERVER_SSH_KEY from ~saumyapatel/.ssh/authorized_keys. That user has sudo. If CI-driven deploys are wanted later, decide separately on a self-hosted runner on the LAN.
- OPS-11: On any machine where Docker was used, run `docker images | grep -i nivesh`. If a backend image was ever built from backend/ (or pushed or saved), delete it and treat the keys in backend/.env at that time as exposed: rotate ANTHROPIC_API_KEY, DEEPSEEK_API_KEY, YOUTUBE_API_KEY, SCRAPERAPI_API_KEY, FIRECRAWL_API_KEY and JWT_SECRET.
- OPS-11 (optional, needs Docker): `docker build -t nivesh-test backend && docker run --rm nivesh-test sh -c 'test ! -e /app/.env && test ! -e /app/stockapp.db && touch /app/probe'`; `docker build -t ml-engine-test ml-engine && docker run --rm ml-engine-test ls -la /app` (check there is no venv or parquet, and /app is owned by mluser).

### w3-03: Expert Network shows 'SEBI REG'/'SEBI REGISTERED' badges for named rea

- Re-check every INH/INA number in backend/services/sebi_registry.py REGISTERED_CHANNELS against the named entity on SEBI's recognised-intermediaries list (siportal.sebi.gov.in, Research Analysts / Investment Advisers). Remove any entry that does not match, then set REGISTRY_VERIFIED_ON = "YYYY-MM-DD". Until then the app shows these numbers on the owner's June 2026 word.
- Decide whether to contact the registered channels (12 listed in the Registered Channels tab; SOIC and Basant Maheshwari are also stance-harvested) for consent or partnership before their names and numbers are shown.
- Take the OPS-03 database backup first, then run `alembic upgrade head` on the server. Revision 8bd11e06fbf4 irreversibly deletes all advisor_biographies and text_advisory_insights rows, plus advisor_insights rows from the three unregistered channels.
- After deploy, check the backend startup log for 'SEBI credential scrub failed'. The harvester.db credential scrub runs automatically in init_harvester_db.
- On the server run: pytest backend/tests/test_sebi_registry_claims.py backend/tests/test_backend_contract_migrations.py backend/tests/test_ios_endpoints.py -k 'advisors or experts or alembic or migration'.
- Ship a new iOS build for the corrected badge and copy. Shipped apps keep decoding /api/v1/ideas/advisors but still draw the old unconditional 'SEBI REG' stamp, now only on registry channels, with a '0 Years of Market Research' line.
- Follow-up outside this package: CopilotScreen.swift's appNavigationContext tells the LLM copilot that Tab 3 holds ideas 'from SEBI-registered advisors', which can still surface as a claim; consider rewording it.

### w1-06: Paid LLM endpoints are reachable anonymously or without quotas: worst 

- Run `alembic upgrade head` (applies fa04b9414864, the llm_usage table) on the server BEFORE restarting on the new code. Otherwise check_user_budget raises, so copilot, brainstorm and YouTube POST /summary return 500.
- Confirm the current DeepSeek prices and set LLM_PRICE_DEEPSEEK_IN/OUT if needed. The defaults of 0.14/0.28 per 1M tokens may under-count spend.
- Optionally set LLM_GLOBAL_DAILY_BUDGET_USD (default 25) and LLM_USER_DAILY_BUDGET_USD_FREE/PRO/SUPER_PRO.
- Run the backend suite on the server, including tests/test_llm_budget.py and tests/test_fork_safety.py.
- Before committing, `git add` the four paths still unmerged (UU) in the index: backend/routers/analysis.py, backend/routers/portfolio.py, backend/services/copilot_service.py, backend/services/job_worker.py. They contain no conflict markers.

### p2-13: RBI repo rate hardcoded at 6.50% ('update manually') and India VIX sil (+4 more)

- On the production server, set RBI_REPO_RATE_PCT, RBI_REPO_RATE_AS_OF (ISO date of the last MPC decision) and RBI_POLICY_STANCE in backend .env to the current RBI policy values, then restart the backend. Update them after every MPC meeting. Until they are set, /macro-strip, /macro-context and macro-impact report the repo rate as null/'unavailable' and the iOS Macro tab shows 'N/A'.
- The commented example values in backend/.env.example (5.50 / 2026-08-06) only show the format. Check them against the RBI's actual latest decision before copying.

### w2-01: Portfolio add/edit routes bind stale duplicate request models in helpe

- Stage the deletion of backend/schemas.py when committing. It was removed with rm, not git rm, so git status shows ' D'.
- Behaviour change: on POST /portfolio(/add), shares or buy_price <= 0 now returns 422 from Pydantic instead of the router's 400. iOS treats both as invalidResponse. The router's own 400 checks on the add path are now unreachable but harmless; I left them in place (no router edits).
- Expected follow-up (TEST-08 area): tests/test_backend_contract_routes.py::test_portfolio_holding_crud_and_duplicate_prevention still fails. It previously failed at 'created == 200' (the 500 bug); now it gets further and fails at 'duplicate == 409'. The ledger treats a repeated BUY as averaging, by design, so the 409 expectation is from before the ledger and needs a product decision. I did not change it here.

### w3-14: Earnings Surprise API returns and persists hardcoded 'Q4 FY24', mock 1

- Back up the production DB (OPS-03) before running `alembic upgrade head` on the server. Migration 25342fdfb06f deletes earnings_surprise_history rows where quarter = 'Q4 FY24', and its downgrade cannot restore them.
- Run backend/tests/test_earnings_surprise_honest.py on the remote server.
- Product decision: Earnings Surprise will show an empty state until a licensed consensus-estimates feed (quarterly EPS/revenue estimates) is integrated. Decide whether to buy one or hide the screen (UX-22).

### w1-02: ADMIN_TOKEN bypass authenticates as user 1 and the public admin dashbo

- Before or with this deploy, remove ADMIN_TOKEN from the production backend/.env. It is now ignored, so leaving it there is harmless but stale. If anything (scripts, Postman, cron jobs) used 'Bearer <ADMIN_TOKEN>', rotate it, because the old value was in public files.
- Promote a real operator account with the manage_users.py set-admin CLI. After that, use that account's JWT for /dashboard-data, /users and the other admin routes.
- Run the backend test suite on the server, not from the production checkout: pytest backend/tests/test_auth_admin_bypass_removed.py plus the full suite.

### p2-08: Backend validation messages never reach users: iOS maps every non-2xx  (+3 more)

- Run the backend tests on the server or in CI: pytest backend/tests/test_portfolio_ledger.py backend/tests/test_portfolio_add_errors.py
- Build and run the iOS test target in Xcode (stockmeTests: NetworkErrorMappingTests, KeychainStoreTests). The Keychain tests need the app-hosted test target.
- On a device: log in, kill the app and relaunch to confirm the session survives (Keychain migration). Add a holding with a past purchase date, then edit and remove it, and confirm the change sticks.

### w4-03: Admin dashboard renders request paths, display names and DB fields via (+1 more)

- After deploy, open https://<server>/ in Chrome and Safari, enter an admin JWT, and check that DevTools shows no CSP violations. Check that the tabs, harvest buttons, user dropdown, ticker filter, archive 'View' and stuck-job 'X' buttons work, and that the Chart.js charts render (the SRI hash must match what cdnjs serves).
- Older iOS builds call /harvester/sources without a token, so on those builds the Expert Network source-health widget will be empty until they update.

### w4-07: Unvalidated free-text risk_tolerance, language and scan_type are injec (+3 more)

- On the server: `sudo systemctl enable nivesh` so the service survives a reboot.
- On the server: confirm /etc/systemd/system/nivesh.service matches backend/nivesh.service (User and paths), then `sudo systemctl daemon-reload` if it was updated.
- On the server: once, run `pgrep -af uvicorn` and stop any leftover nohup uvicorn processes that are not the systemd main PID. Then check that `systemctl status nivesh` and `ss -ltnp | grep 8000` show the same single PID.
- On the server: add a sudoers entry for the deploy user: `NOPASSWD: /bin/systemctl restart nivesh, /bin/systemctl is-active nivesh`.
- Optional: set journald SystemMaxUse to bound log growth.
- Optional: raise requirements.txt to langchain-core>=0.3.49 (UsageMetadataCallbackHandler) the next time dependencies are touched.

### w4-01: Auth has no default-deny: three competing idioms, 35 hand-rolled token (+3 more)

- On the server, copy backend/nivesh.service to /etc/systemd/system/nivesh.service, then run `sudo systemctl daemon-reload && sudo systemctl restart nivesh`. Confirm with `systemctl status nivesh` that only one uvicorn worker is running.
- Make sure no other uvicorn process (nohup or --reload) is also bound to :8000 (see OPS-06).
- Run the backend test suite on the server, including the four new tests: test_route_auth_inventory, test_llm_gateway, test_process_model and test_legacy_notification_auth.
- iOS contract change: an ownership mismatch on user-scoped routes now returns 403 instead of 401. The client should not treat these as session expiry.

### p1-02: QuantLab Alpha Validation always shows zeros and Regime Breakdown alwa

- Run QuantLabDecodingTests in Xcode (xcodebuild is not allowed in this environment).
- Merge after or together with FAKE-12 (GH-652/ML-08). Otherwise the backend's placeholder BULL/BEAR regime rows and conclusion text, plus the ML-09 backtest-math issues, become visible in QuantLab.

### w5-03: Portfolio watchlist tab cannot remove or tag entries: swipeActions out (+1 more)

- IOSUI-07: check on the simulator. Add 2 stocks to the watchlist, long-press a row and choose Remove: the row should disappear at once and DELETE /watchlist/remove should fire. Turn off the network and remove again: the row should come back with a 'Couldn't remove stock' dialog. Long-press and choose Tag: the TaggingSheet should open and the tag chip filter should work. An empty watchlist should show ADD STOCK.
- IOSUI-14 (already shipped in e680b7d): replace the placeholder ForumModeration.contactEmail ('forum-moderation@example.com') in ios/StockApp/stockme/stockme/Views/Forum/ForumModerationViews.swift with the real grievance / moderation contact. Name a grievance officer as IT Rules 2021 require, approve the community-guidelines text, confirm the auto-hide threshold (REPORT_AUTO_HIDE_THRESHOLD = 3 in backend/services/forum_service.py), and decide who reviews GET /api/forum/admin/reports.
- Mark REG-13 and UX-23 as covered by e680b7d, and do not create migration 93bfb1b90195 for this package.

### p2-64: Paywall 'SERVER-VERIFIED ENTITLEMENTS' lists three features that do no (+2 more)

- WIP-07: after this cleanup Super Pro has no exclusive enforced feature, since every enforced key is 'pro'. Decide whether to hide the Super Pro tier on the paywall or build a real Super Pro-gated feature. See REG-02/AUTH-14, which may remove paid tiers altogether.
- WIP-09: owner/legal should confirm the gratuity eligibility wording (5-year continuous service; exceptions for death/disablement and for fixed-term employees after 1 year) and the Rs 20 lakh ceiling against the Code on Social Security, 2020.
- Run backend/tests/test_entitlement_catalog.py on the remote server, and run NetworkErrorEntitlementTests in Xcode.

### p2-24: Tickers with '&' (M&M, M&MFIN, L&TFH, J&KBANK, ARE&M, GVT&D) break que (+3 more)

- Run the stockmeTests bundle in Xcode, in particular URLQueryEncodingTests, AnalysisPollPolicyTests and DeepLinkTests. Type-checking was not run here, as the project rules require.
- Manual check: open M&M from search and confirm the profile, quick-info, history and fundamentals screens load.
- Manual check: put the device in airplane mode during an analysis. Polling should back off and then show a 'lost contact' error. Cancelling from the global pill should not stop the watcher.
- Manual check: tap an analysis-complete notification and confirm it opens that stock.

### p3-11: Technical Momentum 'OI Trends' tab relabels advance/decline counts as  (+4 more)

- Product decision for FAKE-23: confirm that loans, FDs and the finance tracker (/api/finance/*, /api/fixed-deposits/*) and GET /api/kyc/fraud-signals should return 404 in production until real lender and bank integrations exist. The default implemented here is yes, gated by DEMO_MODE.
- Set DEMO_MODE=true in the env of any demo or staging server that should keep serving those screens. Production keeps DEMO_MODE unset or false, and the shipped iOS app will show its existing error state on those screens there.
- Optional feature work (FAKE-21): editable display name, password change, 2FA and session management need new authenticated backend routes before those controls can come back.

### p2-17: Device-binding 'KYC gate' is client-asserted and unreliable: arbitrary (+1 more)

- Decide whether device binding should be a real security control. If yes: enable App Attest (or DeviceCheck) for the app in the Apple Developer portal, add the entitlement to the iOS target, and approve a new server endpoint that checks the attestation before bind_device is trusted. Until then the gate stays a clearly labelled mock that rests on the client's word.
- Run the new backend tests on the remote server: pytest backend/tests/test_kyc_device_binding.py backend/tests/test_finance_terms_validation.py backend/tests/test_device_binding_unique.py backend/tests/test_product_bounds.py
- API contract changes: a rejected device bind now returns 409 instead of 200 {bound:false}, and FD calculator input errors return 422 instead of 400. Shipped iOS builds already treat any non-2xx as an error.

### p2-70: [Testing/Finance] Personal finance, KYC, subscription, and compliance 

- Run remotely: pytest backend/tests/test_finance_loans.py backend/tests/test_fixed_deposits_api.py backend/tests/test_kyc_consent_api.py backend/tests/test_subscription_compliance_api.py

### p3-38: The conftest rate-limit bypass is a no-op; tests_suite errors entirely (+1 more)

- Product decision recorded as the default for UX-12: the paywall advertises only features the server enforces. To sell watchlist, alert or deep-scan quotas as paid perks, first enforce them server-side (CMON-22 / LLM-02), then add the key to entitlement_service.FEATURE_MIN_TIER and FEATURE_TITLES; it then appears on the paywall automatically, and test_entitlement_catalog requires a matching require_entitlement("<key>") in routers.
- Run backend/tests/test_rate_limit_isolation.py, test_entitlement_catalog.py and test_comprehensive.py on the remote server, plus the /analyze tests in forward and reverse order (e.g. -p randomly with a fixed seed), to confirm limiter isolation.
- Build the iOS app and run the stockmeTests NetworkErrorEntitlementTests in Xcode; this was only parse-checked here.
- Optional: backend/.dockerignore still lists tests_suite/. It does no harm and was left unchanged to keep the diff small.

### p2-16: Loan disbursement and booking POSTs are non-atomic with no idempotency (+3 more)

- Reopen GitHub issue #674 (loan KYC device binding): the fix bd42b09 was never merged into main. Close it once this commit lands.
- Manual iOS check for FINSEC-15: with a fresh user who has never opened Account Security and a mock credit score above the offer minimum, submit a loan application. The status should be 'approved', and the backend should have a kyc_consents credit_check row and a device_bindings row with is_primary=1. A repeat application on the same device should create no new binding row.

### p3-63: Any HTTP 422 on thread creation is reported as 'flagged and blocked', 

- Run CreateThreadViewModelTests in Xcode (stockmeTests target).

### p2-22: [iOS/API] KYC device-binding fraud rejections return a shape Swift can (+3 more)

- Before deploying GH-670, back up the production DB (OPS-03), then run `alembic upgrade head` on the server. If the upgrade fails with 'loan applications with more than one completed disbursement: [...]', reconcile those loan_disbursements rows by hand and re-run. The migration deliberately never deletes money records.
- Owner decision (shared with CMON-15/FINSEC-28): decide how an iOS user creates a loan-marketplace LinkedBankAccount. Until then, an in-app disbursement request returns 409 'Link a bank account and mark it primary before requesting disbursement.' The app now shows that message, and retrying is safe because no rows pile up.
- API contract changes for shipped clients: POST /api/kyc/device-binding rejections are now 409 (previously 200 with bound=false). POST /api/finance/loan-applications/{id}/disburse business-rule rejections are now 409 (previously a 200 failed row, or 404). GET /api/forum/boards/{id}/threads defaults to 50 threads, pinned first. Shipped iOS builds already showed generic errors for these cases, so nothing breaks for them.
- Run the new backend tests on the remote server: tests/test_kyc_device_binding.py, tests/test_loan_disbursement.py, tests/test_forum_query_counts.py, tests/test_dashboard_data_payload.py and tests/migrations/test_alembic_health.py. Run DeviceBindRejectionTests in Xcode.

### p3-61: No tests cover the new local money math (EMI, Gratuity, SIP projection

- Run the stockmeTests target in Xcode (Product > Test, or just CalculatorTests) and confirm all 6 tests pass.
- Until TEST-17 adds Testables to the shared scheme, CI will not run these tests.

### p3-17: [Security/API] Legacy authenticated routes miss no-store cache headers (+2 more)

- Run backend/tests/test_cache_control_headers.py on the remote server.
- Run the iOS unit tests in Xcode (MoneyPostRequestTests, ServerURLPolicyTests, NLScreenerTests).
- Manual check for GH-695: log in, open Portfolio, log out, then confirm Library/Caches/<bundle>/Cache.db holds no portfolio or watchlist responses.
- Manual check for IOSCORE-17: with Network Link Conditioner at 100% loss, submit an FD booking and retry. A proxy should show the same Idempotency-Key on both attempts. The server ignores the header until FINSEC-14 lands.

### p3-60: Placebo and hygiene problems inflate the suite: a latency test that ti

- Run backend/tests/test_predictions_performance.py and backend/tests/test_suite_hygiene.py on the remote server to confirm the exact-count assertions hold against the shared stockapp_test.db.

### p2-67: Real-looking personal portfolio ('Dad') and a hard-coded account email

- Rotate the password of the 'saumya' account in every environment (including production) where reset_mock_user.py or populate_portfolio.py was ever run, or where the account still uses '123' or 'StrongPass@123'. Both passwords are public in git history. `scripts/manage_users.py` can detect accounts still using a published password.
- Decide whether the old DAD_HOLDINGS seed (in git history of backend/database.py) is a real person's portfolio. If yes, either purge it, the hard-coded email and the old script passwords from history with git filter-repo, then force-push, have collaborators re-clone, and re-clone the CI and server checkouts; or make the GitHub repository private in its settings.
- If history is rewritten, ask GitHub Support to purge cached views and dangling commits of the old SHAs.
- The reset script is now run as: ENVIRONMENT=development python backend/scripts/reset_mock_user.py --yes [--username NAME]. ALLOW_DEV_SEED=1 no longer applies.

### p2-63: Charts and status indicators are visual-only: custom Canvas/Shape char (+3 more)

- Confirm the CI xcodebuild step passes with IPHONEOS_DEPLOYMENT_TARGET = 17.0. If an iOS 18+ API breaks the build, raise the target to the lowest version that compiles; scripts/ios_release_checks.sh allows anything up to 18.0.
- Before App Store submission: enable the Push Notifications capability (and the App Group group.saumypatel.stockme) for bundle id saumypatel.stockme in the Apple Developer portal so automatic signing picks up stockme.entitlements.
- Check that the collected-data list in stockme/PrivacyInfo.xcprivacy matches the App Store Connect privacy nutrition label.
- Confirm the export-compliance answer ITSAppUsesNonExemptEncryption=false (the app only uses standard HTTPS).
- Manual VoiceOver check: the Portfolio and stock hero charts read a summary, and swiping up or down steps through dates; Piotroski cells read '<check>: pass/fail'; Home index chips read as one element; the Copilot Stop and Retry buttons work, a reply is announced, and each reply shows the disclaimer caption; Settings > Tools > Calculators opens the sheet with the EMI tab showing 'MONTHLY EMI'.

### p2-25: Wire dates use locale/calendar-dependent formatters (70 DateFormatter, (+2 more)

- Run the iOS unit tests in Xcode: WireDateTests, EnginePollingPolicyTests, PortfolioMathTests.
- Manual check of IOSCORE-22: start an analysis and tap Cancel while the loading screen shows (before results arrive). Confirm POST /analyze/{job_id}/cancel is sent, the server job ends as CANCELLED, and no 'Analysis Complete' notification fires later.
- Product decision: the watcher's terminal local notification now actually fires. NotificationManager.willPresent returns [.banner, .sound], so a user watching a run in-app gets a banner and a sound when it finishes. Confirm this is wanted.
- Follow-up (separate bug, not in this package): backend/portfolio_charts.py around lines 203-206 subtracts a naive strptime datetime from datetime.now(timezone.utc). That raises TypeError, which is silently swallowed, so hold_days is None for every holding, including new yyyy-MM-dd rows.
- Follow-up: AnalysisEngineManager decodes the full StockAnalysis through pollJob. If that decode fails on SUCCEEDED, the watcher stops with status left at RUNNING and sends no notification. Consider pollJobRaw.
- Follow-up: wire-date formatters remain outside this package in AlertModels, IPOHubView, StrategyLab, EarningsSurprise, DividendsTab and HomeFeedModels.

### p2-49: Stress-test and copilot spawn unbounded subprocesses with no per-user  (+4 more)

- Before deploying, open the server's backend/.env (the EnvironmentFile of nivesh.service) and check variable names and lengths only, without pasting values: ENVIRONMENT=production must be set, otherwise neither the startup guard nor the JWT fail-fast runs.
- Confirm JWT_SECRET is set, at least 32 characters long, and not the old .env.example placeholder. If it is missing or weak, generate one with python3 -c "import secrets; print(secrets.token_hex(32))". With ENVIRONMENT=production the backend now refuses to start without a valid one. Rotating it logs every user out once.
- Confirm ALLOWED_ORIGINS does not contain '*'. Empty is fine for the iOS-only API, and production now refuses to start with '*'.
- API docs (/docs, /redoc, /openapi.json) are now off by default. Set ENABLE_API_DOCS=true on the server only if you want them.
- Optional: set MAX_CONCURRENT_JOBS (default 6) to the number of concurrent analysis plus stress-test worker processes the droplet's RAM can hold.
- In the production DB, check whether users saumya/nirav/ankur still exist with the old seed password '123' from earlier init_db seeding. If they do, change those passwords or disable the accounts.

### p2-39: Quant-engine outputs are hard-coded heuristics presented as SHAP / con (+1 more)

- Manual iOS check: open an analysis and the Quant Inspector. Confirm the labels 'RULE-BASED FACTORS', 'HEURISTIC CONFIDENCE', 'Rule-based factor adjustment' and 'Heuristic confidence', and that an analysis with calibrated_confidence=null and confidence_math_breakdown={} renders without a crash.
- Run the backend tests on the server: backend/tests/test_quant_engine.py, backend/tests/feature_tests/ai_orchestration/test_confidence_engine.py and backend/tests/test_analysis_pipeline_regressions.py.
- Cached AnalysisHistory rows keep their old 'conformal' 0.0 bounds and old wording until they are recomputed.

### p2-58: Portfolio capture journey: two inconsistent add flows (the '₹' button 

- Run TradeEntryValidatorTests in Xcode.
- After ARCH-01 (#655) lands, record a BUY dated 2021-06-01 and confirm the POST body's purchase_date is 2021-06-01 and the holding shows that date.
- Server-side oversell rejection is still needed (CMON-V1 / ledger work); the client SELL check is UX only.

### p2-15: Privacy notice and consent content are placeholders: policies are labe

- Owner/legal: write the real Privacy Policy and Terms of Use (processors, retention, grievance officer, DPDP rights). Replace the interim sections and the _MOCK_DISCLAIMER body of 'privacy_policy' and 'terms_of_use' in backend/services/disclosure_service.py, and remove the '(Demo)' suffix from the titles.
- Choose the policy version string. Keep backend disclosure_service.CURRENT_POLICY_VERSION and iOS PolicyVersion.current (Models/KYCModels.swift) identical, and bump both whenever either text changes.
- Host both policies at stable public URLs and enter the Privacy Policy URL in App Store Connect.
- Decide whether policy_version becomes mandatory on POST /api/kyc/consents (and accepted_policy_version on /register) once X-App-Version gating ships. For now both are optional so the shipped app keeps working, and missing values are stored as NULL.
- Decide whether the app is publicly distributed; how severe this finding is depends on that.
- Run 'alembic upgrade head' on the server during deploy (revision 7e646d25afe3) and run backend/tests/test_consent_notice_versioning.py there.

### p2-28: iOS test coverage is ~440 lines (24 funcs, 3 template stubs); scheme h (+2 more)

- The new 'Unit tests' step in iOS CI runs the whole stockmeTests suite for the first time. Any existing test that is already failing on main will turn the build-ios job red, so check the first CI run.
- On the first Cmd-U, confirm that Xcode keeps the shared scheme's new <Testables> block and does not rewrite it into an autocreated test plan.

### p2-76: The feature checklist overstates delivery: 355 boxes were bulk-checked

- Run `pytest backend/tests/test_feature_stack_evidence.py` on the remote/CI environment. It does pure file I/O, but project rules forbid running pytest on backend/ locally, and backend CI currently runs only test_ios_endpoints.py.
- Fix the Shareholding wiring bug noted in money_control_feature_stack.md. iOS calls /api/v1/fundamentals/shareholding, which ignores the ticker; it should call /api/v1/fundamentals/{ticker}/shareholding. Re-tick Shareholding and the Promoter/FII/DII lines once fixed.

### p2-10: Analysis jobs have no atomic state machine: duplicate paid jobs on con (+3 more)

- Before deploying, run `alembic upgrade head` on the server with DATABASE_URL set to production Postgres. Migration f32cf73ca308 marks duplicate active analysis_jobs rows FAILED and then creates the partial unique index uq_analysis_jobs_active_user_scan.
- Deploy hardening (DB-14 deploy half / OPS-06): .github/workflows/deploy.yml no longer exists, so the documented deploy path (nivesh-deploy SKILL.md and scripts) must be updated by hand. Use set -euo pipefail, run alembic upgrade head and then check that `alembic current` shows (head), restart with `sudo systemctl restart nivesh` instead of nohup uvicorn --reload, and finish with a strict `curl -fsS` health check. The deploy user needs a non-interactive sudoers entry for systemctl restart nivesh, nivesh.service must be enabled, and any stray nohup uvicorn on :8000 must be stopped once.

### p2-09: Right-to-erasure cannot be executed: DELETE /api/me/account is a no-op (+3 more)

- DB-06 owner decisions (defaults already implemented in compliance_service.ERASURE_POLICY / ERASURE_GRACE_DAYS): (a) confirm the retention list: kyc_consents, audit_log_entries, data_deletion_requests, forum threads/posts/votes/reports and the blocked side of user_blocks are kept; loan_applications/loan_disbursements, user_subscriptions, fixed_deposit_bookings and all portfolio/finance data are hard-deleted. Change entries to 'retain' if RBI/GST record-keeping requires it. (b) Confirm the 7-day grace period. (c) Confirm forum content is kept under 'Deleted user'. (d) Immediate JWT revocation depends on AUTH-13/FINSEC-03 honouring token_version; erase_user already bumps it.
- DB-08, before running 'alembic upgrade head' in production: take a backup, restore it to a scratch database, and run the violation queries from 2057be030154 there. The queries: SELECT COUNT(*) FROM portfolio WHERE group_name <> 'watchlist' AND (shares <= 0 OR buy_price <= 0); SELECT COUNT(*) FROM price_targets WHERE target_price <= 0; SELECT COUNT(*) FROM portfolio_transactions WHERE quantity < 0 OR price < 0 OR transaction_type NOT IN ('BUY','SELL','SPLIT','BONUS','DIVIDEND','ADJUST'). If any count is non-zero, fix or delete those rows by hand first; otherwise the upgrade stops with a RuntimeError.
- Run the backend test suite on the remote server: tests/test_account_erasure.py, tests/test_consent_withdrawal.py, tests/test_kyc_consent_withdrawal.py, tests/test_portfolio_ledger.py, tests/migrations/. For the Postgres concurrency test, set TEST_DATABASE_URL=postgresql://.../<name containing 'test'>.
- Optional, iOS: send an Idempotency-Key header on POST /portfolio(/add) (IOSCORE-17). The backend accepts it optionally, so there is no contract break.

### p2-02: Transport and exposure: ATS fully disabled, user-editable server URL,  (+1 more)

- Update .claude/skills/nivesh-deploy/SKILL.md Step 2 (the live backend restart path that replaced deploy.yml). Replace `--host 0.0.0.0 --port 8000 --reload` with `--host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips 127.0.0.1` (dropping --reload covers GH-690), or switch it to `sudo systemctl restart nivesh`. Until this is done, every skill-driven deploy publishes the backend on 0.0.0.0:8000 with --reload.
- Before switching the backend to loopback, confirm the TLS tunnel or reverse proxy for api.nivesh.qzz.io runs on the same host. If it runs elsewhere, set NIVESH_BIND_HOST=<private-interface-ip> in the server's backend/.env.
- Install the updated unit: `sudo cp backend/nivesh.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl restart nivesh`. Then check `curl -s http://127.0.0.1:8000/ping` on the server and `curl -s https://api.nivesh.qzz.io/ping` from outside.
- Firewall the origin ports: `sudo ufw deny 8000/tcp && sudo ufw deny 8001/tcp`. From another host, confirm `curl -m 5 http://192.168.1.122:8000/ping` and `curl -m 5 http://192.168.1.122:8001/health` both fail.
- Generate the ml-engine secret with `python3 -c 'import secrets;print(secrets.token_hex(32))'` and add `ML_ENGINE_API_KEY=<value>` to the server's backend/.env. Restart the backend so it sends the header, then redeploy the ml-engine with scripts/deploy_ml_engine.sh so the container receives the key. Deploy the backend change first or at the same moment: the engine rejects keyless calls once it has a key.
- Optional cleanup: README.md, AGENTS.md and backend/changes.md still mention http://192.168.1.122:8000 or uvicorn --host 0.0.0.0. That is documentation only, left for OPS-09.

### w4-04: PRO-gated endpoints are unreachable from iOS: options payoff and secto (+2 more)

- Run backend/tests/test_fork_safety.py and backend/tests/feature_tests/ai_orchestration/test_copilot_service.py on the remote/CI Linux host. The fork test needs os.fork, and psycopg2 and pgvector must be importable or it skips.
- Run the iOS unit tests (NetworkErrorMappingTests) in Xcode.
- Manual check: as a free user, open Sector Rotation and the Options payoff builder and confirm the upsell banner appears.
- Optional follow-up: StockProfileViewModel.fetchValuation and fetchRiskSignals are never called and no valuation view exists. Either wire them into a view with a paywall banner or delete them.

### w6-05: Each worker re-embeds the whole news/advisor corpus at startup; torch 

- Optional (deferred, needs an owner decision): split the backend Docker image into a web image without torch/transformers/sentence-transformers and a worker image. This only pays off once FinBERT (sentiment_engine) and the RAG query embedding (rag_tools) run only in the scheduler/job process, not in web workers.

### p2-43: Community forum has no report/block mechanism, published contact or gr

- Set GRIEVANCE_OFFICER_NAME and GRIEVANCE_OFFICER_EMAIL in the production server .env (read by backend/services/disclosure_service.py). Until they are set, the Contact & Grievance Officer screen, which both Settings and the forum now link to, shows 'to be published'.
- Assign a named moderator to work the admin queue (GET /api/forum/admin/reports, then POST /api/forum/admin/reports/{id}/resolve with 'hide' or 'dismiss'). Acknowledge each complaint within 24 hours and resolve it within 15 days, as IT Rules 2021 Rule 3(2) requires.

### p2-65: NL screener: when the DeepSeek parse fails it returns the entire stock (+1 more)

- Run the backend tests on the remote server: pytest backend/tests/test_nl_screener_fix.py backend/tests/test_nl_screener_cache_key.py backend/tests/test_nl_screener_exhaustive.py
- LLM-02 (auth/quota on routers/nl_screener.py) had not landed in this tree. When merging, keep its dependency on natural_language_screener alongside the new 422/503 except-clauses. If the route then requires auth, the tests here will need auth headers.

### w6-01: No contract source of truth between FastAPI and Swift: 166 of 247 rout (+1 more)

- ARCH-04: after this lands, the backend CI 'Check OpenAPI contract snapshot is current' step fails because backend/openapi.json does not exist yet. Download the 'openapi-json' artifact from that run, save it as backend/openapi.json and commit it. Prefer the CI artifact over a local `python backend/scripts/export_openapi.py`: the local 3.14 venv has different FastAPI/pydantic versions and would produce a snapshot that CI never matches.
- OPS-16: on the server run `/home/saumyapatel/Desktop/nivesh/venv/bin/python -V` and confirm the minor is 3.11. If it is not, change .python-version and the two FROM lines in backend/Dockerfile to match, or rebuild the server venv on 3.11.
- OPS-16: on the server run `/home/saumyapatel/Desktop/nivesh/venv/bin/pip freeze --exclude-editable > /tmp/requirements.lock` and commit it as backend/requirements.lock. Check it installs on CI's ubuntu-latest: if a server-only wheel (for example a CUDA torch build) fails there, replace it with the plain PyPI pin and add a comment explaining the exclusion. Then tighten the yfinance/pandas/numpy/lxml caps in backend/requirements.txt to the locked majors.
- OPS-16: run `docker run --rm <ml-engine image> pip freeze > /tmp/ml.lock` and commit it as ml-engine/requirements.lock.
- OPS-16: in a maintenance window, after a DB backup (OPS-03), rebuild the server venv with `pip install -r backend/requirements.lock` and note in the deploy runbook (AGENTS.md / OPS-06) that installs use the lock.

### w5-12: Zero tests for the money-control and account surface (finance, FD, KYC

- Run on the remote server: pytest backend/tests/test_money_control_contracts.py backend/tests/test_community_contracts.py
- Check separately: the existing test_fixed_deposits_api.py and test_finance_loans.py do not enable DEMO_MODE, but /api/fixed-deposits and /api/finance are demo-gated (FAKE-23). Unless something else enables DEMO_MODE in the test environment, their non-401 cases may answer 404. The new files set DEMO_MODE themselves.

### p3-04: About 6,700 lines of unreachable backend code: 21 unwired math engines

- Commit the 44 deletions in the same commit as the other three changes (backend_ci.yml, the trimmed test_math_engines_phase1.py and the new scripts/find_unreferenced_modules.py); they are unstaged deletions in the worktree, so stage them with git add -A or git rm.
- Confirm that none of the deleted 'parked' engines should be kept for future work. The default is to delete them: git history keeps them, and the research engines live in ml-engine.
- Decide the Celery/outcome-tracking path (REL-12/DB-03) before celery_tasks, tasks/alpha158_task and nightly_pipeline can be deleted; then remove their scanner ALLOWLIST entries.
- Optional follow-ups: remove the stale iOS comments that reference backend/services/mutual_fund_calculators.py (Models/MutualFundModels.swift:219,232, Views/SIPCalculatorSheet.swift:7, stockmeTests/CalculatorTests.swift:6), and drop nightly_jobs.py and outcome_backfill.py from CodebaseInformation/ARCHITECTURE*.md.
- Delete the untracked ios/StockApp/stockme/fix_buttons.py from the main checkout; it hardcodes a stale path.
- Expect a merge-order conflict in .github/workflows/backend_ci.yml with ARCH-04/AUTH-25.

### w4-09: Async request handlers run synchronous yfinance/LLM/yt-dlp/subprocess  (+2 more)

- Run the backend test suite on the remote server, in particular tests/test_event_loop_blocking.py, test_scheduler_jobs.py, test_morning_brief_pregen.py, test_earnings_surprise_honest.py and test_backup_service.py.
- After deploy, check that the scheduler's 2-hourly jobs start at staggered times and that /ping stays responsive while earnings or analysis endpoints are busy.

### p3-14: AuthManager.shared (uncommitted) creates a second, divergent identity  (+5 more)

- GH-550: confirm the AGENTS.md rule change (option a: services may query via get_session(); routers may not; shared or money-path queries go in repositories/<domain>_repo.py, moved there when a service is touched for a bug). If you would rather schedule the XL refactor of about 55 service files into repositories (option b), revert the two AGENTS.md hunks and plan that work separately.
- FINSEC-33: before App Store submission, check that the NSPrivacyCollectedDataTypes list in ios/StockApp/stockme/stockme/PrivacyInfo.xcprivacy (Name, UserID, DeviceID, OtherFinancialInfo, OtherUserContent; linked, not tracking, used for app functionality) matches the privacy nutrition label in App Store Connect.
- GH-610: on the remote server, run backend pytest for tests/test_telemetry_logging.py and tests/test_route_table.py, and run the DB integrity runner (tests/database_integrity_tests/run_all.py).

### p2-38: Prediction logging is lossy and non-idempotent: a new row on every cac (+1 more)

- After the OPS-03 database backup, apply the migration on the server: cd backend && alembic upgrade head (it adds revision 2b3e6056a7c7, prediction-logging provenance columns and the partial unique index).
- Recreate the local ml-engine venv on Python 3.12: rm -rf ml-engine/venv && python3.12 -m venv ml-engine/venv && ml-engine/venv/bin/pip install -r ml-engine/requirements-dev.txt (the current venv is Python 3.14 and was installed by hand). Training now uses requirements-train.txt.
- Choose versioned storage for raw training OHLCV snapshots. For each model release, archive the raw parquet together with training.provenance.dataframe_sha256 / file_sha256, because yfinance auto_adjust history changes after corporate actions.
- Rebuild the ml-engine serving image on the next deploy: pins are now exact, and build-essential, torch, onnxruntime, jugaad-data and httpx are gone. Confirm the ML-17 model-contract and trained-model-loading tests pass in the new image. LGB_NUM_THREADS (default 4) can be set at training time.

### p3-09: Paywall sells tier limits the server never enforces (watchlist/alert c (+2 more)

- Run backend tests on the remote server: pytest backend/tests/test_tier_quotas.py backend/tests/test_ios_route_inventory.py.
- Run the iOS unit tests in Xcode: NetworkErrorEntitlementTests and NotificationRoutingTests.
- Manual check on a free account: add an 11th watchlist stock from Portfolio. A 'Couldn't add to watchlist' dialog should read 'Your plan allows 10 watchlist stocks. Upgrade to Nivesh PRO for more.' Then set a 6th active price alert in Alerts; the inline error should show the alert-cap upsell.
- Owner decision (CMON-22): billing is still mock ('Upgrade (Mock)', no StoreKit). Confirm free-tier caps (10 watchlist, 5 active alerts) should be enforced now. Free users already over the caps keep their items; only new adds are blocked.
- Owner decision (CMON-26): keep or delete the /api/me router (backend/routers/account.py), which has no iOS client and duplicates /api/v1/subscription and /api/kyc/consents. It was kept for now, and its DELETE now records the client IP.
- Follow-up (CMON-26): sync quiet hours to the server, and do a one-time alerts_enabled sync on login so users who disabled alerts before this build are honoured.

### p3-23: Deployment target iOS 26.4 vs widget 17.0; code written for iOS 17 API (+1 more)

- IOSCORE-40: the minimum iOS version is already 17.0 for every target. Confirm the owner wants 17.0, rather than 18.0 or staying on 26.x, and check that the CI xcodebuild run (IOSCORE-28) shows no availability errors at the lower target.

### p3-18: Notification, quiet-hours and 'Biometric for Trades' settings are iner

- Run on the remote server: pytest backend/tests/test_push_preferences_gate.py backend/tests/test_notifications_inbox_producer.py
- Product: confirm removing the inert signal-alert toggles (Alert on BUY/SELL, Mute HOLD, Min Confidence, Signal Change Alerts, Min Market Cap) instead of building per-category server preferences.
- Product: quiet hours are now enforced by default at 22:00-07:00 every day, matching what QuietHoursView displays. If they should be off by default, add an explicit enable toggle in QuietHoursView as a follow-up.
- Manual iOS check: toggle Notifications master OFF and confirm the proxy shows PUT /api/v1/preferences {"alerts_enabled": false}; relaunch and confirm the toggle state is reloaded from the server; with master OFF, confirm no morning brief and no analysis-complete local notifications.

### p3-26: Haptics codemod residue: 98 duplicated and 51 triple HapticManager.sel

- Delete the stray codemod script fix_buttons.py from the main checkout (/Users/saumya/Desktop/career/nivesh). It holds owner uncommitted work, so the agent did not touch it.
- Build and run on device or simulator, and tap-test a few buttons (search mic, Copy Link, screener clear) to confirm one haptic tick per tap. Agents may not run xcodebuild.

### p3-46: [Deployment] health_check.sh targets stale domain and does not issue P (+1 more)

- Tell us how api.nivesh.qzz.io reaches 192.168.1.122: a cloudflared tunnel, a router port-forward plus a reverse proxy, or something else, and on which host it runs. Fill in the 'Ingress & TLS' section of docs/codebase/DEPLOYMENT_MAP.md, and commit the tunnel/proxy config with credentials removed.
- If the proxy runs on another host: in backend/.env set NIVESH_BIND_HOST=0.0.0.0, change --forwarded-allow-ips in nivesh.service to the proxy IP, allow 8000 only from that IP, then run `sudo systemctl daemon-reload && sudo systemctl restart nivesh`.
- On the server, run `ss -ltnp | grep -E ':8000|:8001'` and confirm both are bound to 127.0.0.1. From another LAN device, `curl http://192.168.1.122:8001/health` should fail.
- Enable ufw for ports 8000 and 8001. Docker-published ports bypass ufw, so the ML engine relies on its 127.0.0.1 publish.
- Plan a move from the free qzz.io subdomain to a domain you own (#611).
- Run BASE_URL=https://api.nivesh.qzz.io bash scripts/health_check.sh after the next deploy.

### p3-42: Duplicate haptic calls remain: about 224 lines in 57 files (BanknoteBa

- Build in Xcode to confirm it is green, since only swiftc -parse ran.
- Spot-check on a device: the Back button, the CompactNewsCell context-menu actions, NL screener clear, voice search, stress-test Run and the chart copy-error button should each fire one haptic per tap.
- Still open from WIP-13, outside this package: MarketAnomalyScreen.swift filterRow (lines 129-131) has `.simultaneousGesture(TapGesture().onEnded { HapticManager.selection() })` on a Button whose action already calls selection(). Delete the modifier in the package that owns that file (p2-27 or w6-04).

### p3-06: helpers.py is both a re-export hub and a second implementation; test f

- Run on the remote server: pytest backend/tests/test_helpers_reexport_only.py backend/tests/test_dashboard_state_single_source.py backend/tests/test_error_contracts.py

### p3-01: Money-control calculators: new EMI/Gratuity screens are unreachable, i (+1 more)

- Once ARCH-04's export script and backend/openapi.json land, run `python backend/scripts/export_openapi.py` and commit the result. The only expected diff is GET /fundamentals/piotroski/{ticker} changing tags from ["Portfolio"] to ["Fundamentals"]; paths and operationIds should not change.
- On the server or CI, run the backend suites affected by the split: tests/test_router_split.py, test_route_table.py, test_route_inventory.py, test_backend_contract_routes.py, test_transaction_ledger.py, test_portfolio_pdf_export.py, test_portfolio_price_unavailable.py, test_error_contracts.py, test_earnings_*_honest.py, test_dashboard_*.py, tests/morning_briefing/, tests/api/test_ios_endpoints_comprehensive.py and tests/feature_tests/.
- iOS: run SIPCalculatorTests and CalculatorTests in Xcode. Open the SIP sheet from a fund detail screen and confirm in Proxyman or Console that no network request fires.
- Gratuity legal decision (MATH-14): the owner must confirm the in-force date of the Code on Social Security, 2020, and whether to model an employment-type toggle (regular = 5-year eligibility; fixed-term = pro-rata from 1 year). The current iOS code applies the 5-year rule.

### p2-46: Redis cache bridge spawns a thread, event loop and Redis connection pe (+1 more)

- Merge p2-46 after w4-09 (REL-01), or at least before deploying. yf_acquire sleeps while holding _YF_BUCKET_LOCK, and some async handlers still call the guarded wrappers on the event loop: market earnings_estimates_endpoint, post_result_movers_endpoint, portfolio_endpoint inline _to_ns, portfolio_attribution_endpoint _resolve_ticker, and alerts_service._poll_once inline _to_ns. Once the 30-token burst is spent, the loop can stall for seconds.
- Run backend/tests/test_cache_service_sync.py, backend/tests/test_yfinance_client_guards.py and feature_tests/external_clients/test_yfinance_client.py on the remote server.
- After deploy, watch for the global yfinance breaker opening. /api/v1/earnings/estimates takes an unauthenticated ticker, and every _yf_fetch_info exception counts toward the shared threshold of 10.
- The global 0.5/s token budget may slow portfolios with more than 30 holdings and the alert cycle. Tune it in config/settings.py if needed.

### w3-13: Fundamentals v1 alias routes ignore the requested ticker and always re

- Owner decision (the plan defaults to option a, which is what this change implements): the company_financials, shareholding_patterns, corporate_actions, company_valuations and risk_signals tables appear empty in the dev DB. If they are also empty in prod, the iOS Fundamentals tabs will show 'unavailable' (HTTP 404) instead of the old wrong RELIANCE data. Either (a) accept 'unavailable' for now, or (b) fund a follow-up that populates these tables, or that backs financials, valuation and corporate-actions with yfinance.
- Run on the remote server: pytest backend/tests/test_fundamentals_v1_aliases.py backend/tests/test_ios_endpoints.py -q

### p3-59: Feature tests still target non-existent routes after the #684 'fix'; o

- Run on the server: pytest backend/tests/test_route_inventory.py -q, which needs main.app.
- Follow-up outside this package: test_portfolio_ledger.py:444,459 and test_transaction_ledger.py:472 call GET /me, which does not exist, so those tests always skip. Point them at the user_id from the /login response, then drop ('GET', '/me') from INTENTIONAL_404.
- After TEST-09 merges, drop ('GET', '/api/v1/portfolio') from INTENTIONAL_404 if test_endpoint_contracts no longer calls it.

### w6-04: iOS god files and scattered networking: HomeScreen 3,052 lines/20 type

- Simulator check, one screen per method with a logged-in user: Sector Rotation, Anomalies, Technical Momentum (trends and top movers), Earnings Surprise (list and calendar), Expert Network, Copilot chat, NL Screener, Correlation, Strategy Lab, Stress Test (start and poll), the live analysis progress stream and the sidebar market cards. With the server stopped, each should show an error state, not an empty list.
- Follow-up outside this package: move PortfolioScreen.swift's inline NetworkManager.shared.session call (~line 2691, IOSUI-30) and the URLSession.shared/URLRequest use in HomeFeedService, ValuationCalendarService and FundamentalsService into NetworkManager.
- Note for the orchestrator: most files are staged in the index (from git apply --3way of the earlier partial diff); later edits to ios_ci.yml, NetworkManager.swift, NetworkManager+Tools.swift and NLScreenerScreen.swift are unstaged. Review with git diff HEAD.

### w4-08: Production safety depends on unvalidated, fail-open env defaults (ENVI (+1 more)

- On the server, set ENVIRONMENT=production and a real JWT_SECRET (at least 32 chars, not the placeholder) in backend/.env before deploying. Otherwise the API refuses to start (intended).
- On your local machine, add ENVIRONMENT=development to backend/.env (the local file has no ENVIRONMENT key, and unset now means production).
- Decide whether production should serve /docs. It is now off by default, so set ENABLE_API_DOCS=true explicitly if you want it.
- Set APNS_AUTH_KEY_PATH, APNS_KEY_ID, APNS_TEAM_ID (and APNS_ENVIRONMENT=production) in the server .env, or set ALERTS_PUSH_DISABLED=true to acknowledge that pushes are off.
- After every deploy, check the startup config warnings with: journalctl -u nivesh -b | grep -E "APNs not configured|APNS_ENVIRONMENT is not|ENVIRONMENT is unset". Do not use `-p crit`: these lines reach journald as plain stderr at info priority.
- Install log rotation: sudo cp backend/deploy/logrotate-nivesh.conf /etc/logrotate.d/nivesh && sudo logrotate -d /etc/logrotate.d/nivesh (dry run).
- After REL-18 deploys, create an external uptime monitor (UptimeRobot or healthchecks.io) on https://api.nivesh.qzz.io/health every 5 min, alerting your phone.
- Optional: decide whether to add Sentry (sentry-sdk). It is a new dependency, so it is deferred.

### p3-28: FD bookings compute maturity dates with 30.44-day months (1 day early  (+2 more)

- MATH-21: Senior-citizen status is self-declared through the new toggle (mock product). Confirm that is acceptable, or later derive it from the KYC date of birth.
- MATH-22: The default applied keeps the capital-gains, XIRR and IV engines (now fixed), adds no tax features, and leaves the plan checklist items unchecked. Confirm this, or choose the alternative of deleting the engines (ARCH-19).
- Run the new backend tests on the remote server: pytest tests/test_fd_booking_dates.py tests/test_capital_gains.py tests/test_xirr_iv_engines.py tests/test_net_worth_ledger.py tests/test_portfolio_price_unavailable.py tests/test_fixed_deposits_api.py

### p3-08: Vendored tradingagents-core is a silently modified fork (11.6k lines,  (+2 more)

- On the server, before the next deploy: take a DB/venv backup (OPS-03). `pip install -r requirements.txt` will now upgrade langchain-core to >=0.3.81, langgraph to >=0.4.8 and langchain-anthropic to >=0.3.15 if older versions are installed.
- On the server: run `venv/bin/pip show tradingagents`. If a pip-installed copy exists (editable or from PyPI), run `venv/bin/pip uninstall tradingagents` so the sys.path copy in backend/tradingagents-core is the only one.
- After deploying, start one analysis and check that the job_worker log shows tradingagents imported from backend/tradingagents-core (for example, log `tradingagents.__file__` once).
- Run on the server or in CI: `cd backend && venv/bin/pytest tests/test_vendored_tradingagents_path.py tests/test_portfolio_export_isolation.py -v`.
- Owner: run an Xcode build of ios/StockApp/stockme (xcodebuild is not allowed in this pipeline) to confirm the CMKT-16 deletions compile.

### p2-34: RAG ingestion: chunk IDs collide (no source row id) so documents overw (+3 more)

- LLM-25 decision: before setting NIVESH_HAIKU_MODEL or NIVESH_SONNET_MODEL to a 5.x model on the server, run a frozen-input eval of about 30 tickers comparing current and newer models on JSON validity and number fidelity, with LLM-09 telemetry. Recommended default: leave the env vars unset, which keeps claude-haiku-4-5-20251001 and claude-sonnet-4-6.
- LLM-25: after deploy, the anthropic/openai pins resolve to the versions already installed (0.107.1 and 2.41.0). Bump them deliberately after testing.
- LLM-22: the one-time full re-embed of legacy chunks happens on the first leader-scheduler 'rag_ingest' run after deploy (REL-21 design). Expect one CPU-heavy run on the worker holding the scheduler lock.

### p2-42: In-app privacy policy is demo text, the 'official terms of use' users 

- Legal/owner: the Privacy Policy and Terms of Use are interim wording. Supply the final reviewed text and bump CURRENT_POLICY_VERSION together with iOS PolicyVersion.current (Models/KYCModels.swift).
- Set GRIEVANCE_OFFICER_NAME and GRIEVANCE_OFFICER_EMAIL in the server .env. Until they are set, the policy shows 'to be published'. That address is now the only way users can request account deletion, so it must be monitored.
- Dependency on in-app account deletion (UX-04/IOSCORE-26): iOS has no Delete Account control and no client for /api/v1/compliance/deletion-requests. Apple 5.1.1(v) requires in-app deletion for apps that create accounts. Ship that control, then change the 'How long we keep it' and 'Your rights' sections to name the in-app path and bump CURRENT_POLICY_VERSION. Until then, operators must handle emailed deletion requests by creating the deletion request on the user's behalf. That starts the existing 7-day grace period.
- Breaking change: /register now requires accepted_policy_version and age_confirmed. Older iOS builds get 422 at sign-up, so release the iOS update together with the backend deploy.
- The 18+ check is a self-attestation checkbox, not verified age. Confirm this is acceptable for launch.
- Run the backend test suite on the server (backend tests cannot run locally), especially tests/test_register_consent.py and the tests that post /register.
- scripts/test_all.sh /register cases were already stale (they use email and expect 201). Update them separately if that script is still used.

### p3-07: Architecture docs exist in three diverging copies and describe unwired

- When staging, run git add -A on backend/ and docs/backend-notes/ so git records the 13 moves as renames rather than deletes plus adds.
- After the REL-12 and ARCH-19 decisions on Celery and the outcome tracker, update the 'Not scheduled anywhere' wording in the scheduler section of docs/codebase/ARCHITECTURE_MAP.md.

### p3-03: Same financial rules implemented 2-4 times: Piotroski x4, Black-Schole

- Run on the server: pytest backend/tests/test_kyc_gate.py backend/tests/test_single_implementations.py backend/tests/feature_tests/ai_orchestration/test_copilot_service.py backend/tests/feature_tests/external_clients/test_yfinance_client.py backend/tests/test_route_inventory.py backend/tests/test_route_table.py

### p2-73: Backtest math is silently wrong: nonexistent 20D/60D return columns re

- Run backend/tests/test_alpha_validation.py, test_alpha_validation_no_constants.py, test_quantlab_tdd.py, test_utility_routes_auth.py and test_quantlab_api.py on the remote server.
- The strategy sweep now returns 336 in-sample iterations. The iOS table only shows the first 10.

### p3-19: ~520 lines of dead/stub networking, view-model and helper code; second (+1 more)

- Optional fuller prune (IOSCORE-32): on a machine with internet access (not the production server), run `python3 backend/scripts/refresh_nse_symbols.py` from the repo root. It rewrites backend/data/nse_bse_symbols.json and the iOS Resources copy, removing other delisted or renamed symbols and fixing scraped BSE names such as 'Sharia Bees' and 'Gradiente'. Commit both files; test_stock_universe::test_ios_copy_in_sync and test_ios_stock_directory_sync keep them in step.
- iOS manual check: in Portfolio > Record Trade, type 'eter'; ETERNAL should appear, and ZOMATO and TATAMOTORS should not.

### w1-04: Job status, active-job and cancel endpoints have opt-in ownership chec (+2 more)

- On the server, run the backend test suite for the changed and new tests: test_job_endpoints_ownership, test_job_admission, test_rate_limiter, test_analyze_api, test_ios_endpoints, test_worker, test_stress_test_jobs, test_ios_endpoints_comprehensive, test_backend_contract_api and test_auth_rate_limit.
- Optionally set MAX_JOBS_PER_USER (default 2) and MAX_CONCURRENT_JOBS (default 6) in the server .env, then restart the backend.
- scripts/run_analysis.sh now requires NIVESH_TOKEN, a JWT for the --user account. Export it before running the script.

### p3-16: [Backend/Docs] Implementation plan marks stub parsers and harvesters c (+5 more)

- Before merging the blocking Bandit step, generate the baseline it now needs. With bandit==1.7.10 in a throwaway venv, run from the repo root: bandit -r backend/ -ll -ii -x backend/tradingagents-core,backend/tests,backend/.venv,backend/venv -f json -o backend/.bandit-baseline.json . Read the findings and commit the file; if there are none, commit it anyway. Without it, the Run Bandit step fails with a missing-baseline error. Findings likely to appear (from a grep, not a bandit run): B324 hashlib.md5 in routers/stock_financials.py:55, B306 tempfile.mktemp in scripts/verify_model_migration_drift.py:22, B310 urlopen in scripts/refresh_nse_symbols.py:64 and services/math_engines/deterministic_dcf.py:62, B108 /tmp lock in services/harvest_worker.py:115, and B608 f-string SQL in services/vector_store.py and some migrations.
- Run the new and affected backend tests on the remote server: tests/test_unwired_stub_services.py, tests/test_removed_stub_routes.py, tests/test_linked_bank_account_masking.py, tests/test_checkpoints.py (fails to import without the late __future__ fix), tests/test_route_table.py and tests/test_finance_loans.py.
- Optional: run a read-only query on the server for linked_bank_accounts.masked_account_number values that do not match ^[Xx*]{2,16}[0-9]{4}$. Rows stored before this fix could contain full account numbers.
- Decide separately whether to add `extra_args: --only-verified` to the trufflehog step. I left it out because it would make the scan report only verified secrets.

### p3-43: New gratuity calculator shows payable gratuity for 1–4 years of servic (+2 more)

- Run the stockmeTests target in Xcode: GratuityCalculatorTests, LoanTenureAndGratuityTests and the existing CalculatorTests.
- Manual check: in Calculators, set the EMI loan amount, switch to SIP and back, and confirm it persists. An EMI over Rs 1 lakh should show full rupees. Gratuity with 4 yr 11 mo should show NOT ELIGIBLE with an estimate.

### p3-21: Quiet-hours weekday mapping is off by one and defaults are never persi (+2 more)

- Fill in backend/data/nse_holidays.json. Under "holidays", add the official NSE equity-segment trading-holiday dates for 2026 and 2027, copied from the NSE holiday circular on nseindia.com, as "YYYY": ["YYYY-MM-DD", ...]. Until a year is present, /api/v1/market/status reports calendar_known=false and uses the clock only.
- When NSE announces special sessions (for example Muhurat trading), add {"date": "YYYY-MM-DD", "open": "HH:MM", "close": "HH:MM", "label": "Muhurat"} entries under "special_sessions". Times are IST.
- Run the backend tests on the server: pytest backend/tests/test_market_calendar.py backend/tests/test_route_auth_inventory.py. Run the iOS unit tests in Xcode: QuietHoursTests, IndianFormatterTests and TechnicalIndicatorsTests.

### p3-48: [Docs/API] API map is stale against current router inventory

- Re-run `python3 scripts/route_inventory.py` after GH-243 and GH-692 (and any other route-changing packages) are integrated, and paste the output over the 'Full Route Inventory' table in docs/codebase/API_CONTRACT_MAP.md.
- Decide whether backend/routers/research.py should be mounted in backend/main.py or deleted. It defines 5 routes, but no include_router call mounts it.

### p3-40: Interactive targets below 44pt with a global .controlSize(.small): 40p (+3 more)

- Run backend/tests/test_compliance_deletion_audit.py on the remote server along with test_money_control_contracts.py, test_subscription_compliance_api.py and test_account_erasure.py.
- Build the iOS app and check with Accessibility Inspector that Home header icons, the toolbar newspaper, the Back button, the Quiet Hours chips, the Alerts Dismiss button, error RETRY and the Stock Profile tabs are all 44pt or larger. Then check Settings rows (Toggle/menu Picker) and other screens for overflow now that the global .controlSize(.small) is gone.
- Manual: Settings > Haptic Feedback off should stop haptics on taps and on index ticks. Choosing Default Scan Type 'Deep' with Auto-run on should start a deep scan in StockActionHubView. Settings should push sub-screens with a single back bar.

### p3-02: Three URL conventions and four response envelopes: 106 unversioned rou

- Regenerate backend/openapi.json with backend/scripts/export_openapi.py on a machine allowed to import the app, once ARCH-04's snapshot exists. Only the /api/v1/<name> money paths should appear.
- After merging the parallel packages, run backend/tests/test_api_versioning.py and test_route_auth_inventory.py. If another package added an unversioned route, the fix is to move it under /api/v1, not to extend the frozen fixture.
- Follow-up release: switch the iOS NetworkManager and the Finance/KYC/FixedDeposits/Forum/IPO/MF/account calls to /api/v1/<name>, then delete the legacy alias include line in main.py and _ALIASES in the test.

### be-serve-api: Serving policy and /api/v1/research router

- Run backend/tests/test_research_api.py on the remote server (backend code must not run locally).

### ml-assembly-pipeline: Report assembly, nightly pipeline with gap-fill, outcome scoring and live metrics with A1 kill-switch

- On the real store, check that the on-demand /compute stays within the 15 s budget: it builds membership and features over the full 6-year panel on every request.
- W5 integration: do not read run-level degraded reasons in RunStatus.error as a failure, and pass a price panel that reaches back to the oldest pending as_of when scoring outcomes.

### ml-api-deploy: ml-engine research API, wiring, dependency pins, image and deploy script

- On the server, rebuild and deploy ml-engine with scripts/deploy_ml_engine.sh. The new image creates /app/data and /app/cache with mode 1777, so the container starts under --user "$(id -u):$(id -g)" for any host uid. An old :previous image built before this change still lacks those directories. If the host uid is not 1000, rollback to that image will fail until one good build has rotated into :previous.
- Set RESEARCH_API_KEY in the ml-engine env file before deploying. Without it, /research/* returns 503.

### p2-45: Analysis/copilot subprocesses are forked with the parent's live SQLAlc (+2 more)

- On the server, run the backend test suite, in particular test_stress_test_jobs.py, test_job_manager.py, test_job_spawn_context.py, test_worker.py, test_scheduler_jobs.py and test_deploy_topology.py.
- After deploying, start one analysis and one stress test, then confirm in journalctl that the spawned children start and that their INFO logs appear in the structlog/JSON format.
- Confirm that nivesh.service on the server still runs uvicorn with --workers 1 and no --reload.

### p3-33: Cache ignores REDIS_URL, grows without bound per worker when Redis is  (+4 more)

- Orchestrator: `git add` backend/services/harvest_worker.py (index shows UU, but the working-tree file has no conflict markers). Also add the untracked backend/ruff.toml and scripts/check_repo_policy.sh and stage the deletion of .github/workflows/stale_branches.yml before committing.
- Run Alembic migration 620b1e83d21e on the server off-hours, after a DB backup.
- Confirm the 90-day retention windows for news_articles and alert/price-target rows.
- Confirm the deletion of the stale-branch auto-delete workflow (stale_branches.yml).
- Move `from __future__ import annotations` to the top in the 7 known late-import modules (F404 under ruff 0.8.4, not selected yet; a future ruff upgrade may report them as syntax errors).

### p3-34: iOS polling lacks backoff; one job is tracked by three channels and a  (+5 more)

- Integration must `git add backend/services/harvest_worker.py`. It is still UU in the index, but the working-tree file has no conflict markers.
- Run the new backend tests (test_gzip_middleware, test_ipo_no_gmp_no_apply, test_performance_claims_admin_only, test_scheduler_jobs_smoke) and the updated ones on the remote server. Deploy with starlette>=0.46.
- Build in Xcode and run OffMainDecodeTests. Check on device: during an analysis, open the global running pill and confirm the checkpoint list updates live. When the analysis completes, the result should appear with no flash of the idle screen.
- Follow-up (#643/#696): clean the fabricated gmp values out of existing ipo rows, and stop sentiment_engine.py:264 from using them.

### p2-11: Three analytics queries use SQL that PostgreSQL rejects (round(double  (+4 more)

- Optional (DB-22): on the production Postgres, run SHOW max_connections and compare it with 4 workers x 30 connections per process (pool_size 10 + max_overflow 20); pool sizing is tracked under PERF-21.
- Optional (DB-22): if any legitimate production query or transaction gap needs more than 60 s of statement time or 120 s idle in transaction, set DB_STATEMENT_TIMEOUT_MS / DB_IDLE_TX_TIMEOUT_MS in the server .env before deploying.

### p2-18: Identity and money endpoints have no effective throttling; the /auth/l (+1 more)

- On the production host, confirm Redis is running (systemctl status redis or redis-cli ping). If it is not at redis://localhost:6379, set REDIS_URL in the server backend/.env and restart nivesh.service. Without Redis the limiter silently falls back to per-worker memory, so each limit is multiplied by the 4 workers.
- Confirm proxy-header trust for real client IPs (uvicorn --proxy-headers --forwarded-allow-ips set to the reverse proxy address in nivesh.service). Otherwise every per-IP bucket, including POST /login 5/min, is keyed on the proxy IP. This server-side change belongs with AUTH-11.
- Optional: decide whether to add a per-username failed-login backoff (assigned to AUTH-11 in the plan; not implemented here).

### w3-10: Analyses never refresh: POST /analyze returns the newest cached row of (+1 more)

- Run on the remote server: pytest backend/tests/test_registry_only_videos.py backend/tests/test_analysis_cache_freshness.py backend/tests/feature_tests/repositories/test_analysis_repo.py backend/tests/feature_tests/youtube_harvester/test_youtube_harvester.py
- Product decision (LLM-V1, deferred): should Regenerate on the same day force a new paid analysis run? That would need a force_refresh field on AnalyzeRequest, gated by auth and quota, plus an iOS change. The recommended default is no: same-day reports are reused and the next IST day regenerates automatically.
- Optional, from the reviewer's non-blocking note: if a channel is ever removed from services.sebi_registry.REGISTERED_CHANNELS, purge its youtube_videos rows or null their sebi_reg, because is_registry_video trusts the stored sebi_reg.

### w5-11: Orchestrator discards every math-engine result (Venn-Abers, calibratio

- Run backend/tests/test_calibration_pipeline_unwrap.py, test_analyze_request_validation.py and test_orchestrator_logging.py on the remote server (backend tests must not run locally).

### w4-02: GET /api/v1/earnings/alerts is unauthenticated and returns any user's  (+2 more)

- AUTH-14 owner decision: with mock purchases off and no StoreKit, no user can reach PRO features (fundamentals valuation and risk signals, sector rotation, strategy backtest, options payoff). Pick one: (A, recommended) keep the gates and ship StoreKit 2 with App Store Server API / Server Notifications v2 receipt verification before turning upgrades on; or (B) temporarily set those keys to 'free' in backend/services/entitlement_service.py FEATURE_MIN_TIER until payments exist. Also confirm the paywall copy (CMON-22/UX-12) so the app does not sell features it cannot deliver.
- On the production server, make sure ALLOW_MOCK_PURCHASES is unset or 0 in backend/.env. Any account that already self-upgraded via /upgrade keeps its user_subscriptions tier; check that table and reset unpaid tiers to 'free' if you want.
- Run the backend test suite on the remote server to confirm (tests could not be executed here): tests/test_auth_sessions.py, test_earnings_alerts_auth.py, test_entitlements_fail_closed.py, test_route_auth_inventory.py, test_subscription_compliance_api.py, test_search_api.py, test_error_contracts.py, test_comprehensive.py, test_portfolio_chart_auth.py, api/test_ios_endpoints_comprehensive.py, test_api_versioning.py.
- Optional iOS follow-up, outside this package: SettingsScreen.swift still adds .demoDataRibbon() to AccountSecurityView, but password change and sign-out-everywhere are now real server calls.

### p3-10: Cache-hit path inserts a new AnalysisPrediction on every request and n (+4 more)

- Take a production DB backup (OPS-03) before running migration 814a5ca5bc07: it permanently deletes duplicate legacy analysis_predictions rows.
- Run the new backend tests on the remote server (test_prediction_logging, test_mock_flow_idempotency, test_latest_signals_query, test_schema_limits_and_json_defaults, feature_tests/harvesters/test_harvester_db).
- After deploy, harvester.db switches to WAL and will create harvester.db-wal and harvester.db-shm next to it (already git-ignored).

### w3-09: Account erasure is not implemented: deletion requests are never proces (+2 more)

- Run the backend test suite on the server, in particular backend/tests/test_account_erasure.py, test_compliance_deletion_audit.py, test_money_control_contracts.py, test_subscription_compliance_api.py, test_llm_fallback_not_persisted.py and test_smart_cache_gate.py.
- Confirm the deletion policy: a 7-day grace period (DB-06's daily erasure job), with consent and audit rows kept with IP scrubbed and forum posts kept under a 'Deleted user' tombstone. Both deletion routes now require the password and share a 10-per-hour per-user rate limit.
- Before deploy, take a DB backup (OPS-03). Then review any existing 'pending' data_deletion_requests rows in production: the daily job will erase them once they are past the grace period.
- iOS: build in Xcode and check the Settings > DELETE ACCOUNT sheet by hand (wrong password shows 'Incorrect password.', success logs out). Also check that NLScreenerScreen shows an error state on 422/503.

### p3-12: Dead or preview-only mock code compiled into app and backend (unused d (+2 more)

- FINSEC-11 owner decision: the QuantLab routes /api/v1/predictions/calibration, /pillar-attribution, /model-versions, /calibration/health and /fusion-weight-recommendations are still require_auth and are shown to all users through QuantLabView. REG-11 made /predictions/performance admin-only because hit rates of the app's own calls are unverified (no PaRRVA). Decide whether these 5 should also be require_admin (calibration/health and fusion-weight-recommendations look like internal ops), which would mean hiding QuantLab's calibration tabs on iOS, or stay user-visible. Do not gate them behind a paid tier, since that would sell the hit-rate claims REG-11 removed.
- FINSEC-13 behaviour change to confirm: paid plans now revert to free on the first read after renews_at, and a paid row with renews_at NULL is treated as lapsed. If production has manually granted paid rows with no renews_at, give them a renews_at before deploying.

### p2-36: FD bookings and loan applications still bypass product min/max amount  (+3 more)

- Run on the server: pytest backend/tests/test_fusion_weight_gating.py backend/tests/test_confidence_fusion_properties.py backend/tests/test_analysis_cache_confidence.py backend/tests/test_ml_signal.py backend/tests/test_ml_production_integration.py backend/tests/test_fallback_safety.py backend/tests/test_lazy_singletons.py
- Behaviour change: for fresh analyses the headline confidence_pct no longer includes an ML pillar unless the model is gated (trained_live_calibrated), and missing pillars are renormalized. Dynamic fusion weights stay off unless FUSION_DYNAMIC_WEIGHTS_ENABLED=true is set deliberately.
- Pre-existing, outside this package: backend/tests/test_fd_booking_dates.py's fd_env fixture calls monkeypatch.setattr(fds, '_check_kyc_gate', ...), but fixed_deposit_service has no _check_kyc_gate (it calls check_kyc_gate), so that fixture raises AttributeError. It should patch 'check_kyc_gate' instead.

### p3-37: Error-telemetry writers swallow their own failures with `pass`, the da (+3 more)

- Confirm that the GitHub-hosted `macos-26` runner image exists and ships Xcode 26.5, and that maxim-lobanov/setup-xcode resolves '26.5'. If not, change runs-on/xcode-version in .github/workflows/ios_ci.yml to an image/Xcode pair that has the iOS 26.5 SDK (the local machine only has Xcode-beta 27.0).
- After merging, run 'Security & Secrets Scan' once by hand (Actions > Run workflow), which scans the full git history. Open the TruffleHog result and triage every verified or unknown hit. Rotate any real secret on the provider side and in the server's .env yourself (agents must not do this).
- Deploys stay manual through the nivesh-deploy runbook. deploy.yml was already deleted earlier; reintroduce an Actions deploy only with a self-hosted LAN runner (OPS-10).
- On the remote server, run `pytest --collect-only -q backend/tests` and confirm it shows no *_integrity_tests or TestRunner nodes, then run backend/tests/test_error_telemetry_self_reporting.py, test_telemetry_logging.py and test_ops_monitoring.py.
- Periodically check `gh run list --limit 50 --json workflowName,conclusion` for any workflow with 3 consecutive failures (alerting is owned by OPS-14).

### w6-03: Async analyze, job-poll, home-feed, valuation, attribution and SSE han (+2 more)

- Run the backend tests on the remote server: pytest backend/tests/test_yfinance_gateway.py backend/tests/test_event_loop_responsiveness.py backend/tests/test_analysis_history_queries.py backend/tests/test_portfolio_price_unavailable.py backend/tests/test_portfolio_group_filter.py
- After deploy, check that GET /sector-performance returns on cold start across several worker restarts. It used to risk hanging when the outer and inner keys shared a lock stripe.

### w3-01: AI Analysis 'Signal Accuracy Timeline' plots fabricated BUY/SELL calls (+3 more)

- Run on the server: pytest tests/test_reformatter_grounding.py tests/test_stock_financials_removed.py tests/test_ios_no_fabricated_content.py tests/test_stock_universe.py tests/test_analysis_pipeline_regressions.py tests/test_analyze_request_validation.py tests/test_token_stats.py tests/test_prediction_logging.py tests/test_ml_signal.py tests/test_quantlab_api.py tests/test_quantlab_tdd.py tests/test_ios_endpoints.py tests/test_ios_route_inventory.py tests/test_event_loop_blocking.py. Two existing analyze() tests now also make one stubbed _yf_price call (about a 1 s retry sleep each).
- Build the iOS app in Xcode and run stockmeTests (ReleaseGateTests, MarketSectionGatingTests). This also confirms the exhaustive MarketSection switches compile without .unlisted.
- Manual check: run an analysis and confirm 'SIGNAL ACCURACY TIMELINE' is gone from the analysis view, the full view and the shared image; confirm the Markets hub shows no Pre-IPO / UNLISTED card in Debug or Release.
- LLM-04 only takes effect once LLM-01 (the pipeline crash) lands; ship them in the same release. Then purge or flag earlier AnalysisHistory and AnalysisPrediction rows whose current_price_inr / entry_price came from the LLM (every report generated before this change, per the audit).
- Follow-up, outside this containment: on extreme scans, valuation_bands.current_price and the scenario prices are still LLM numbers (REG-02 / research engine).
- Docs still describe the removed stock_financials endpoints and the Pre-IPO screen: docs/ios-api-endpoints.md, docs/codebase/API_CONTRACT_MAP.md, docs/architecture/APP_NAVIGATION_MAP.md.

### w6-02: No market-data gateway: ~94 direct yfinance calls in 30 files, 9 modul (+2 more)

- Run on the server: pytest backend/tests/test_market_data_gateway.py backend/tests/test_env_loading.py backend/tests/test_architecture_imports.py backend/tests/test_test_isolation.py backend/tests/test_earnings_estimates_honest.py backend/tests/test_earnings_surprise_honest.py backend/tests/test_event_loop_blocking.py
- ARCH-11 follow-up (part 1): move the 69 remaining direct yfinance call sites in 23 files (12 in routers/market.py) onto the services.yfinance_client helpers, lowering _YF_DIRECT_CALL_BASELINE in test_market_data_gateway.py as each file moves.
- ARCH-11 follow-up (part 2): move the roughly 7 remaining modules that open their own nseindia.com sessions onto services.nse_client.
- ARCH-12: .env no longer overrides the process environment. Check that the systemd EnvironmentFile and backend/.env on the server do not disagree on any key; where they do, the systemd/process value now wins.
- ARCH-12 follow-up: remove the stale override=True guidance in docs/codebase/ROUTER_MIGRATION_RUNBOOK.md:69, docs/prompts/BETTER_AI_ANALYSIS_PROMPT.md:560 and .claude/skills/nivesh-deploy/SKILL.md:83.
- Watch the yfinance rate limiter after deploy. nse_data_provider callers now go through yf_acquire (token bucket 0.5/s, burst 30); tune it with the YF_RATE_LIMIT_* env vars if fan-outs slow down.

### p2-72: Training evaluation leaks and over-fits its folds: no purge/embargo on (+2 more)

- After 'ML Engine CI' (.github/workflows/ml_engine_ci.yml) is green on main, add it as a required status check in the main branch protection settings on GitHub (tracked by TEST-01).
- The first CI run is the first real `ruff check ml-engine --select F821,F811`; ruff could not be run locally. If it flags pre-existing code in research/ or sandbox/, fix those names rather than dropping the step.
- Retrain to regenerate the committed candidate reports under the new protocol (embargo, nested early stopping, cross-fitted calibration, holdout). The committed calibration_report.json with ECE 0.0 is stale (ML-25).

### p3-36: Numeric query params, list bodies and param-keyed caches are unbounded (+2 more)

- REL-27: on the server, run `/home/saumyapatel/Desktop/nivesh/venv/bin/python --version` and confirm it is 3.11, matching /.python-version, the Dockerfile and CI. If it is not, rebuild the venv on 3.11 in a maintenance window.
- REL-27: on the server, from the backend directory, run `venv/bin/pip freeze --exclude-editable > requirements.lock` (the command in the requirements.txt header), then review and commit backend/requirements.lock. The Dockerfile and backend_ci.yml pick it up automatically.
- REL-27: switch the manual deploy procedure (the nivesh-deploy skill or runbook) to `venv/bin/pip install -r requirements.lock` instead of requirements.txt. After the first lock-based deploy, smoke-test /ping, /api/v1/market/dashboard-pulse and one analysis.
- REL-23: if the reverse proxy (nginx) has no client_max_body_size, set one (for example 1m). The new app-level 413 only checks Content-Length, so chunked bodies are not covered. MAX_REQUEST_BODY_BYTES can override the 1 MiB default.
- CI: backend_ci.yml runs `export_openapi.py --check`, but backend/openapi.json is not committed at this tip. Regenerate and commit it with `python backend/scripts/export_openapi.py` in an environment allowed to import the backend; the new Query/Field bounds add minimum/maximum to the schema.
- Run the new tests on the server: pytest backend/tests/test_input_bounds.py backend/tests/test_morning_brief_degraded.py

### p2-05: Legacy /earnings-calendar (Home and Analysis screens) lists earnings f (+3 more)

- Run the backend tests on the server: tests/test_earnings_calendar_auth.py, tests/test_market_logging.py, tests/test_market_single_flight.py, tests/test_route_auth_inventory.py and tests/test_comprehensive.py::TestMarketEndpoints::test_earnings_calendar.
- After the backend deploys, shipped iOS builds call /earnings-calendar without a token and get 401, which they already map to an empty list. The Home and Analysis earnings strip stays empty until the new build ships with authRequest.

### p2-52: ML pillar degrades invisibly: the backend client returns None with zer (+2 more)

- Run the backend suite on the remote server. At minimum run backend/tests/test_degraded_responses.py, test_ml_client_logging.py and test_piotroski_real.py, plus the full suite, because the conftest stubs changed and tests that relied on the old MagicMock modules may surface.

### p2-20: Key Fact Statement and APR figures do not correspond to the applicant' (+2 more)

- Run alembic upgrade head on the remote server so migration 3b38ab41c39c (kfs_apr, kfs_processing_fee, kfs_acknowledged_at on loan_applications) is applied before the backend deploy.
- Run the backend CI suite on the remote server or in CI to confirm the newly listed money and identity modules pass with the DEMO_MODE fixtures.
- Orchestrator: widen file ownership for p2-20 to cover backend/tests/test_finance_loans.py, backend/tests/test_fixed_deposits_api.py and backend/tests/test_kyc_consent_api.py (each gained only an autouse DEMO_MODE fixture).

### p2-06: Benchmark sheet decodes keys the backend never sends (all nil), and th (+3 more)

- Run on the server: pytest backend/tests/test_portfolio_benchmark.py backend/tests/test_portfolio_group_filter.py backend/tests/test_portfolio_price_unavailable.py
- Build iOS in Xcode to type-check PortfolioToolsCard.swift (BenchmarkData keys changed; NetworkManager.fetchBenchmark is unchanged).

### w4-06: Systemic error swallowing (176 try?, 42 in views, 21 try? JSONDecoder) (+1 more)

- Apple Developer portal (team HL32Z2K3ZU): enable Push Notifications for App ID saumypatel.stockme and regenerate the provisioning profiles; Xcode automatic signing then picks up the aps-environment entitlement.
- Create an APNs Auth Key (.p8) in the Apple Developer portal and store it on the server outside the repo.
- Server .env: set APNS_TOPIC=saumypatel.stockme, APNS_KEY_ID, APNS_TEAM_ID=HL32Z2K3ZU and APNS_AUTH_KEY_PATH, plus APNS_ENVIRONMENT=production for TestFlight/App Store builds or development for Xcode debug builds. Then restart the service.
- Verify one real push end to end on a device build. Sign in, and the log should show 'Token synced to backend' with only the last 6 token characters. A DeviceToken row should exist for that user. Create a price alert and confirm the push arrives.
- Run the iOS unit tests in Xcode (SearchDecodingTests is new). Manually check that with airplane mode on, Portfolio keeps the last loaded holdings and shows the error card and the offline banner, Alerts shows an error instead of 'NO ALERTS SET', and a failed note save or export shows the 'Action failed' dialog.

### w5-01: Outcome tracking is dead end-to-end: three evaluators read a price key (+4 more)

- Run on the server: pytest backend/tests/test_outcome_scheduling.py backend/tests/test_corporate_actions.py backend/tests/test_portfolio_benchmark.py backend/tests/test_portfolio_ledger.py backend/tests/test_transaction_ledger.py. The yfinance package must be importable, because test_feedback_block_reads_current_price_inr monkeypatches yfinance.download.
- After deploy, check the first 02:00 UTC corporate_actions run log ([corporate-actions] counts). splits_added should be small and only cover ex-dates after the holding was entered in the app.
- After the first 21:10 UTC run, confirm GET calibration health shows last_outcome_run.

### p2-51: iOS drops the APNs token when the user is not yet logged in, still pri (+2 more)

- On the server, run backend/tests/test_pipeline_degradation.py, backend/tests/feature_tests/harvesters/test_harvester_health_honesty.py, backend/tests/test_analysis_pipeline_regressions.py and backend/tests/test_orchestrator_logging.py.
- On the server, check feature_tests/ai_orchestration/test_orchestrator.py::test_analyze_full_run. A failed _save_and_fetch_advisors now re-raises, so any stub that relied on it failing silently needs updating.
- Build the iOS app in Xcode and confirm the APNs token syncs after login (the logs show 'deferred' before login and 'synced' after).

### p2-60: Many settings do nothing or mislead: push categories and master switch (+2 more)

- Decide on guest browsing (read-only market screens without an account). It needs auth-optional backend routes and a split tab view. Recommended: not now; revisit after the IOSCORE-04/AUTH-* work. Also confirm the onboarding copy ('AI-verified analysis…') with the REG-02 decision.
- Quiet Hours now gates only on-device notifications (NotificationManager.scheduleLocal). Server-sent APNs price-alert pushes ignore it. Either add quiet-hours fields to the backend push path or state the limitation in the Quiet Hours row copy.
- Build in Xcode and run the stockmeTests targets (AnalysisRequestTests, LaunchSequenceTests, SettingsBehaviourTests). Then turn on Settings > Hide Portfolio Values and check that the Home hero chart shows no rupee header, that long-press scrubbing shows no price tooltip on Home or Portfolio, and that VoiceOver reads 'Values hidden'.
- Follow-up (non-blocking): the comment near L140 of AnalysisEngineManager.swift still says the notification sound applies. The legacy email/phone PII is purged only on logout; consider a one-time purge at launch.

### p2-37: Calibration dashboards double-count boundary values and mix matured an (+1 more)

- After the OPS-03 backups, on the server: cd backend && alembic upgrade head. This applies 4d6fc9064c23 (adds outcome_status / outcome_attempts / benchmark_return_30d / hit_vs_benchmark_30d / actual_return_target / hit_direction_target / brier_score_target and ix_ap_outcome_status to analysis_predictions). Then run the backend tests listed in tests_added on the server.
- Optional data decision: AnalysisHistory rows already labelled by the old feedback_injector/evaluator logic (arbitrary horizon, CAUTIOUSLY_* scored as wrong) keep their old was_correct. To re-score them under the new rule, clear outcome_checked_at/outcome_delta_pct/was_correct on those rows so the evaluator reselects them. This step is deliberately not automated.

### w4-10: Price-alert poller: duplicate pushes across processes, session held ac (+3 more)

- After deploy, repoint the external uptime monitor (UptimeRobot/healthchecks.io) from https://api.nivesh.qzz.io/healthz to https://api.nivesh.qzz.io/health/ready; /healthz now returns 401 without an admin JWT.
- Make sure the h2 package is installed in the backend environment if APNs pushes are expected. Without it, send_apns logs once and returns NOT_CONFIGURED.

### p2-12: All 89 DateTime columns are timezone-naive while code mixes UTC, serve (+1 more)

- Before deploying DB-24, run `SHOW timezone;` on the production Postgres and `timedatectl` on the server. If Postgres TimeZone is not UTC (UAE_OFFSET suggests Asia/Dubai), existing naive timestamps hold local wall time, while rows written after deploy are UTC. Recommended: accept the one-time skew, in which rows from about 4 h before the deploy can sort after newer rows and old rows look 4 h newer in staleness. Alternative, only with the owner's approval and after the OPS-03 backup: a one-off data fix of UPDATE <table> SET <col> = <col> - interval '4 hours' on every DateTime column.
- Manual iOS check for DB-26: on one simulator, log in as A, log out, then log in as B. Confirm the device_tokens row now has B's user_id and that a price alert for A no longer reaches the device.

### p2-03: Insecure-by-default configuration: ENVIRONMENT defaults to development (+2 more)

- Before deploying, the server's backend/.env must set ENVIRONMENT=production (or leave it unset), a real JWT_SECRET of at least 32 characters, and an explicit ALLOWED_ORIGINS without '*'. Remove any ADMIN_TOKEN: it does nothing now and logs CRITICAL at startup.
- Run the backend test suite on the server, in particular tests/test_auth_admin_bypass_removed.py, tests/test_startup_config.py and tests/test_auth_credentials.py.
- Check production data for accounts created before UX-14 with passwords longer than 128 characters. LoginRequest now rejects those passwords with 422.
- Decide whether registration needs verification (email OTP, phone OTP or App Attest) and set per-tier daily LLM quotas (AUTH-24).

### w2-05: Every fresh analysis crashes: orchestrator.py calls logging at 39 line

- Do not deploy this before LLM-02 and AUTH-17 are live. Restoring the pipeline re-enables paid DeepSeek and Claude generation on the /analyze path. The plan recommends shipping it with LLM-04, LLM-07 and LLM-08.
- On the server, run: pytest backend/tests/test_orchestrator_logging.py backend/tests/test_analysis_pipeline_regressions.py backend/tests/test_token_stats.py. test_token_stats::test_graph_usage_is_logged also calls run_trading_agents, so it only passes with this fix. test_orchestrator.py imports through the `backend.` prefix, so it needs `python -m pytest` run from the repo root.
- Out of scope, not changed: the two job_worker tests in test_orchestrator.py are stale. test_state_transitions_failed expects the raw exception text 'Something broke', but AUTH-08 now stores the generic 'Analysis failed. Please try again.' Also, run_job does `import database` locally, so patching `backend.services.job_worker.database` probably has no effect.
- Out of scope, not changed: in routers/morning_brief.py, morning_summary_endpoint imports logging inside except blocks (lines 87 and 128). That makes `logging` local to the whole function, so the logging calls at lines 177, 182, 231, 248 and 259 raise UnboundLocalError. Check whether SILENT-14 covers this.

### p2-40: No production ML monitoring: /health is unconditional, the deploy heal (+3 more)

- Run the backend tests on the remote server: test_cache_service_sync.py, test_macro_reference_values.py, test_market_single_flight.py, test_alerts_batch_quotes.py, test_ml_signal_cache_key.py.
- The first deploy after /ready is added rolls back to an image with no /ready, so the deploy script reports that rollback as unhealthy even though the old container is serving. Verify with curl -fsS http://127.0.0.1:8001/health in that case (see ml-engine/docs/OPERATIONS.md).
- Optional: install the cron check from ml-engine/docs/OPERATIONS.md on the server and pipe its output to a notification channel. It no longer fires while the model is unvalidated (no_edge).

### p2-44: YouTube audio is downloaded with account cookies to evade IP blocks, a (+2 more)

- REG-14: Decide whether to keep any use of YouTube transcripts. The code now reads only public captions through youtube-transcript-api, unauthenticated, and the YouTube ToS still bars automated access without permission. Recommended: get written permission from the registry channels, or drop transcripts and link out only. That would disable YouTube summaries and advisor stance extraction.
- REG-14 ops: delete backend/cookies.txt on the server if it exists, then sign out of or rotate the Google account whose cookies were used. Optionally pip-uninstall yt-dlp and faster-whisper from the server venv; they are no longer in requirements.txt.
- REG-14: Without YOUTUBE_API_KEY on the server, channel and advisor harvesting now skip entirely, with no scraping fallback. Confirm the key is set.
- REG-14: Pick licensed or RSS sources with snippet-reuse terms to replace the removed CNBC-TV18 and Moneycontrol expert-column cards. Rating-agency pages are now fetched without ScraperAPI JS rendering and may return 0 cards; source health will show this.
- REG-15: Confirm the statute citation and when the Code on Social Security's gratuity chapter took effect (the audit cites 21 Nov 2025, S.O. 5319(E)). Also confirm the pro-rata 1-year rule for fixed-term employees. The 5-year rule holds under either statute.

### p2-53: Three live '*_real' harvester tests hit YouTube Data API, RSS and web  (+2 more)

- Run `cd ios/StockApp/stockme && xcodebuild test -project stockme.xcodeproj -scheme stockme -destination 'platform=iOS Simulator,name=iPhone 17' -only-testing:stockmeTests` once on your Mac or in CI. Check that the bundle builds and the log shows 'Executed N tests' with N > 0. Agents may not run xcodebuild.
- Run the full backend suite on the remote server with `pip install -r backend/requirements-dev.txt` installed. The new network guard turns any test that quietly used the network into a 'network blocked in tests' failure. Fix each one by patching that test's network call, or set ALLOW_NETWORK_TESTS=1 only for live runs such as test_e2e_api against a remote NIVESH_LIVE_E2E_BASE_URL.
- Optional, to widen bandit to medium: on a machine with bandit==1.7.10, run `bandit -r backend/ -ll -ii -x backend/tradingagents-core,backend/tests,backend/.venv,backend/venv -f json -o backend/.bandit-baseline.json`, commit the file, and change security_scan.yml to `-ll -ii -b backend/.bandit-baseline.json`.
- Before adding F821 to backend/ruff.toml, fix the existing undefined names: missing `import pytest` in tests/morning_briefing/test_regression.py, missing `timezone` import in tests/test_calibration_engine.py, and `literally` at tests/morning_briefing/test_edge_cases.py:179. Also add a noqa for the deliberate NameError probe in tests/backend_integrity_tests/test_06_python_builtins_exceptions.py:79.
- Generate backend/requirements.lock from the server venv (owned by OPS-16), then check that the requirements-dev.txt pins still match it.

### p2-41: Failed or partial upstream results are cached for full TTLs (24 h brie (+3 more)

- PERF-21: The owner confirms the production topology: the uvicorn worker count (systemd says 4, Docker says 1), Postgres max_connections, and whether Redis runs on the server. Recommended: 1 worker until rate-limit, cache and job-registry state moves to Redis. Then apply the systemd unit change on the server with: sudo systemctl daemon-reload && sudo systemctl restart nivesh.
- REG-10: Business and licensing decision. Before monetising, contract an NSE-authorised data vendor or a broker API with display and redistribution rights, then route every consumer through services/nse_data_provider.py.
- Merge order: land p2-44 (REG-14, which removes the ScraperAPI helper from harvester_expert.py) before or together with this package. Until then, test_no_scraping_evasion.py::test_no_residential_proxy_fetches fails.

### p3-15: [Backend/Architecture] Analysis job import graph cycles through main.p (+5 more)

- GH-615: confirm the incremental approach (default yes). Move one router cluster per change, following docs/codebase/ROUTER_MIGRATION_RUNBOOK.md. Earnings alerts are done here; portfolio holdings reads and the analysis PKScreener/News queries remain as follow-up clusters.
- GH-630 changes the status for a mismatched path user on GET /trade-journal/{user_id}/stats to 403, matching the neighbouring routes. No iOS caller exists.
- Run the new and changed backend tests on the remote server after integration: test_no_main_imports, test_earnings_alerts_service, test_earnings_alerts_auth, test_trade_journal_stats_auth, test_removed_stub_routes, test_ios_endpoints, feature_tests/harvesters/test_harvester_db, test_router_split.

### w4-18: Auth and IDOR assertions cannot fail: 291 status checks accept both 20

- Run on the server: pytest backend/tests/test_auth_matrix.py backend/tests/test_route_auth_inventory.py backend/tests/test_stress_test_engine.py backend/tests/api/test_endpoint_contracts.py backend/tests/test_comprehensive.py -q. Expected: KNOWN_GAPS rows (POST /analyze, /api/v1/screener/natural-language, /api/v1/notifications/register) show as xfail. Any other matrix failure is either a real auth gap or a route that a public route shadows. Add it to KNOWN_GAPS with an audit ID rather than loosening the assertion.
- When merging, keep test_route_auth_inventory.py's names PUBLIC_ROUTES and KNOWN_GAPS. test_auth_matrix.py imports both. If w4-01/p2-04 also edited KNOWN_GAPS, keep the removal of the stale /brainstorm and /api/v1/copilot/chat entries.

### w4-05: JWT and profile PII live in plaintext UserDefaults; logout clears only (+3 more)

- Run the iOS tests (SessionExpiryTests, SessionStorageTests, AuthRequestTests, ResearchReportDecodingTests) with xcodebuild in a simulator. They need the app test host for Keychain and Documents access. The tests save and restore the Keychain session, NetworkManager.authToken and saved_reports.json, but the host app's own LocalReportManager also receives the test's logout notification, so its in-memory saved reports are cleared in that simulator.
- Run backend tests on the server: tests/test_morning_summary_push.py, tests/test_alerts_contract.py, and the existing tests that touch these routes (test_ios_endpoints.py alerts tests, tests/morning_briefing/, test_ai_consent_gate.py, test_comprehensive.py morning-summary push, test_route_table.py).
- Decide whether a normal logout should also call POST /api/v1/auth/logout. It is left out because that call signs the user out on every device (there is no per-session revocation). Today a stolen token is revoked only by 'sign out everywhere' or a password change.
- Before shipping, make sure JWT_SECRET is set in production (OPS-13). Any authenticated 401 now signs the user out, so if each uvicorn worker generated its own secret, users would be bounced to login at random.
- Behaviour change: GET /alerts/check/{user_id} now marks crossed alerts as triggered and writes the inbox row, so the background poller will not send an APNs push for those alerts.

### p2-26: No privacy manifest, export-compliance flag, or in-app account deletio

- Owner/legal: confirm the collected-data-types list in ios/StockApp/stockme/stockme/PrivacyInfo.xcprivacy (Name, UserID, DeviceID, OtherFinancialInfo, OtherUserContent) and make the App Store Connect privacy nutrition labels match. Decide whether SearchHistory should be added: the plan listed it, but the backend does not appear to store per-user search or copilot queries.
- Confirm the export-compliance answer: the app uses only standard HTTPS and OS crypto, so ITSAppUsesNonExemptEncryption=false (exempt) should be correct.
- Manual check on a device: Settings > Delete Account > enter password should create a pending deletion request (GET /api/v1/compliance/deletion-requests/status returns 'pending') and log the user out. In Xcode, Archive > Generate Privacy Report should list the declared types.
- Retire the uncommitted /api/me/account route (backend/routers/account.py in the main checkout, WIP-04) so /api/v1/compliance is the only deletion surface.

### p2-04: No automated enforcement of auth invariants: CI runs one test file, sc (+2 more)

- Generate backend/requirements.lock on the production server (venv/bin/pip install -r requirements.txt && venv/bin/pip freeze --exclude-editable > requirements.lock) and commit it. CI, the Dockerfile and the pip-audit job switch to it automatically.
- Check that the first CI run on this change is green. The newly gated suites (route-auth inventory, auth, rate-limit, ownership and isolation tests, and the two new CMKT tests) could not be run locally. If pip-audit reports an advisory with no fixed release, upgrade the dependency or add --ignore-vuln <ID> with a written reason.
- Once CI is green, update branch protection on main to require the build-and-test, trufflehog, bandit and pip-audit checks (TEST-01).
- Manual iOS check (CMKT-04): point /quick-info at a failing stub and confirm the Overview, Governance and Risk tabs still show the profile data, and that a stock whose price feed failed shows no price rather than ₹0.00.

### w4-11: Function-local 'import logging' makes 'logging' an unbound local in 17 (+1 more)

- On the remote host, run `cd backend && python -m pytest tests/test_logging_unbound_regressions.py tests/feature_tests/ai_orchestration -q` and then `python -m pytest tests --collect-only -q` to confirm zero collection errors.

### p3-13: Linked-bank endpoint stores whatever string the client sends as the 'm (+2 more)

- FINSEC-20 (server, read-only first): count linked_bank_accounts rows whose masked_account_number does not match ^[Xx*]{2,16}[0-9]{4}$. If any exist, redact each to 'XXXX'+last4 by hand. Resolve them one row at a time, because the unique (user_id, masked_account_number) constraint can collide.
- FINSEC-22 (server/ops): set FORWARDED_ALLOW_IPS in the server .env to the reverse proxy's IP, so request.client.host, which audit rows store, is the real client IP.
- FINSEC-22 / FINSEC-03: decide whether audit_log_entries should be append-only at the DB level (REVOKE UPDATE, DELETE ON audit_log_entries FROM the app role). Coordinate this with FINSEC-03 erasure, which must anonymise these rows. Note that after erase_user the audit details still hold bank_name, the masked account number and the user_agent in _ctx, so the anonymisation has to cover those fields too.

### w3-11: Loan & FD marketplaces present offers under real RBI-regulated lenders (+1 more)

- REG-05: run migration a8fd0770d4d1 on the server only after the OPS-03 backup; it renames existing loan_offers, loan_disbursements and fixed_deposit_schemes rows to the fictional names.
- REG-05, before any real lending launch (not code): operate only as an LSP under signed agreements with RBI-regulated entities and list the app on RBI CIMS. Source bank data through the Account Aggregator framework and credit scores from a CICRA-licensed credit information company. Appoint a grievance officer, add a cooling-off period, and keep the data stored in India.
- UX-04: counsel must review the Privacy Policy, Terms of Use and Third-Party Data Sharing text in backend/services/disclosure_service.py. Set GRIEVANCE_OFFICER_NAME and GRIEVANCE_OFFICER_EMAIL in the server .env, and confirm the 7-day deletion grace period.
- UX-04: publish the Privacy Policy and Terms at stable URLs and enter them in App Store Connect. Enter the App Privacy labels there too, including DeepSeek and Anthropic as AI subprocessors.
- UX-04: CURRENT_POLICY_VERSION and the iOS PolicyVersion.current are both now '2026-10-11.1'. Deploy the backend and the iOS build together, because registration rejects a version that does not match exactly.

### p2-35: Benchmark and stress-test paths send bare NSE symbols to yfinance: HAL (+4 more)

- Run the backend tests on the server: test_portfolio_benchmark.py, test_portfolio_group_filter.py, test_portfolio_ledger.py, test_stress_test_math.py, test_kfs_apr.py and test_loan_disbursement.py.
- Note: ledger rows written before MATH-11 are dated at insertion time, so a back-dated SELL that conflicts with them now returns 422.

### p2-14: Stress test silently values holdings it fails to price at cost basis w (+2 more)

- Run the backend test suite on the remote server, especially tests/test_comprehensive.py::TestNotifications, tests/test_morning_summary_push.py, tests/test_morning_summary_fallback.py, tests/morning_briefing/test_endpoint.py, tests/test_stress_test_estimated_flags.py and tests/test_placeholder_routes_removed.py.
- Build the iOS app in Xcode and check the EST. badge on the stress test screen and the hidden mood line on Home when mood is 'unavailable'.
- Note the behaviour change: users without AI-processing consent now get a 503 from the morning-summary push instead of a canned 'cautious' brief.

### p2-50: Transient provider failures are cached as authoritative (ticker resolu (+2 more)

- Deploy runs `alembic upgrade head` to create scheduler_job_status (revision c09c3ec5ab68); take the usual pre-migration backup first (OPS-03).
- If Redis is meant to be shared in production, set REDIS_URL in the server .env (no env or compose file sets it today). After deploy, grep the journal for 'REDIS_URL configured but Redis unreachable'; that CRITICAL means every worker is using a private memory cache.
- Product/privacy decision (UX-04): confirm that sending anonymised client error reports (path only, status, error class, a message capped at 500 chars, app version, server-side user_id) to our own backend fits the privacy policy. If not, remove the reportClientError call in ErrorDiagnoser.swift and rely on MetricKit.
- Manual iOS check: with Network Link Conditioner (100% loss for about 1 s) on a GET screen that uses dataWithRetry, confirm one retry. Trigger a tracked error while signed in and confirm a 'nivesh.client' WARNING line in the backend journal.
- Land SILENT-21's UtilityModels.swift change (PromoterHistoryPoint.fii/dii as Double?) with or soon after this package; until then the app's fallback decoder drops promoter history whenever a row has a null fii/dii.

### p1-01: Quarterly charts use an invalid strftime directive '%q', producing dup

- Run the backend tests on the remote server: pytest backend/tests/test_quarter_label.py backend/tests/test_degraded_cache_ttl.py backend/tests/test_earnings_surprise_honest.py
- Quarter labels change from the broken 'Q%q 2025' to the fiscal format 'Q1 FY26'. Old disk-cached payloads expire on their own (1 hour for quarterly financials, 15 minutes for stock profile).

### w5-09: iOS Benchmark Comparison decodes keys the backend never returns, so ev

- Run stockmeTests/BenchmarkDecodingTests in Xcode.
- Manual check: open Portfolio Tools -> Benchmark Comparison; the rows should show values, and the labels should follow return_basis.
- This depends on MATH-04 (the money-weighted benchmark math in portfolio_service.compute_benchmark), which is already present at this integration tip.

### w3-05: quick-info still returns fabricated DII/FII/pledge figures (issues clo (+1 more)

- CMON-05 purge of already-persisted synthetic rows on production (destructive, needs owner approval): 1) take a DB backup: cd backend && ../venv/bin/python scripts/backup_db.py (OPS-03). 2) Dry run: ../venv/bin/python scripts/purge_synthetic_valuation_history.py and review the per-user counts and date ranges. 3) Only if they look right: ../venv/bin/python scripts/purge_synthetic_valuation_history.py --apply.
- Reference or reopen closed issues #256, #304, #306 and #462 when this lands: quick-info kept the fabricated DII and inflated FII figures after they were closed.
- API contract change: fii_holding_pct and dii_holding_pct are now null instead of fabricated numbers; institutional_holding_pct is new; stock-profile debt_to_equity is now a ratio (36.6 -> 0.37); valuation-history drops the `estimated` key and returns an empty list until nightly snapshots exist. The shipped iOS build decodes all of these as optionals and shows FII/DII as 0 until the new build ships.

### p3-27: Dead or broken AI plumbing: DLQ never called, Celery analysis task mis (+6 more)

- MATH-10: decide whether POST /portfolio with is_virtual=true should stay rejected with a 400 (current behaviour) or get a separate virtual-portfolio ledger.
- Run the backend tests on the remote server: test_stress_test_math.py, test_portfolio_ledger.py, test_portfolio_attribution.py and test_dead_ai_plumbing.py.

### w5-10: Model promotion gate is vacuous (Brier < 0.2529 is worse than a consta (+1 more)

- Run the new scripts/deploy_ml_microservice.sh against the server manually. On the first run, confirm the backend stays up and ml-engine:<sha> passes the candidate readiness check (integrity_ok and the expected manifest version) before the swap.
- Keep the current unregistered models/lgb_model.txt (it serves no_edge without a manifest) until a retrained model passes the promotion gate, or delete it.
- After the next retrain, check gate_result.json in the artifact. The gate now scores the raw booster output (p_raw), so a model that only looks skilled after isotonic calibration will be rejected.

### p2-33: Outcome and calibration loop never records an outcome: three evaluator (+4 more)

- LLM-17: Check the current DeepSeek API docs. 'deepseek-chat' must still be a non-thinking model with an 8K max output. If it has become a thinking model, raise the per-caller max_tokens budgets in llm_utils callers.
- LLM-18: Confirm that DeepSeek's OpenAI-compatible chat API accepts a message history containing assistant tool_calls and tool-role messages when the request has no `tools` parameter (the final call at the tool-loop cap). If it rejects that, change create_optimized_analyst_node in backend/services/orchestrator.py to keep the tools bound with tool_choice='none'.
- After deploy, watch for truncated output where budgets dropped: research/formatter MAX_TOKENS is effectively 3500 -> 700, and the NL screener and Copilot defaults are 2560 -> 1024.
- Run the backend test suite on the remote server, including test_llm_utils, test_outcome_evaluator, test_analyst_tool_loop_cap, test_llm_read_endpoint_caching, test_ticker_validation and test_llm_budget.

### p2-47: main.py is a 2,595-line monolith: inline admin HTML, duplicated ticker

- Run the backend suite on the server, especially tests/test_import_graph.py, test_admin_dashboard*.py, test_dashboard_*.py, test_startup_leader.py, test_process_model.py, test_startup_config.py, test_catalog_seeding.py, test_route_auth_inventory.py, test_auth_matrix.py, smoke/test_app_startup.py and tests/test_ios_endpoints.py. Every route path is unchanged, but the move touches imports and monkeypatch targets.
- Follow-up (not done here): move routers/morning_brief.build_morning_summary into a service so services/user_service.py stops importing routers, then drop its _KNOWN entry in tests/test_architecture_imports.py.
- Optional cleanups left out to keep the diff tight: the unused `price_alert_poller as _price_alert_poller` alias in routers/alerts.py, stale 'main._seed_catalogs' comments in services/ipo_service.py, forum_service.py and mutual_fund_service.py (now core.lifecycle._seed_catalogs), and the stale main.py description in backend/AGENT_MAP.md.

### ios-legacy-containment: Contain legacy analysis surfaces in the new iOS build

- Build the iOS target in Xcode to confirm it type-checks (swiftc -parse only was possible here).
- Optional follow-up: delete the now-unreferenced QuantInspectorSheet.swift and StockProfile/StockMLSignalCard.swift, and drop the language/debateRounds @AppStorage reads in AnalysisScreen.swift.

### p2-27: No unified request pipeline: ~25 copy-pasted request/decode blocks, 54

- Run the stockmeTests target in Xcode (type-check and NetworkManagerContractTests); agents cannot build iOS here.
- git apply --3way left the reused hunks staged in the worktree index; nothing was committed.
- find_unreferenced_swift.py reports 3 files this package did not touch (ResearchModels.swift, NetworkManager+Research.swift, DalalStreetConsensusCard.swift); check whether that already fails at the integration tip.

### p2-23: [iOS/API] Profile screen reports saved display-name changes without pe (+4 more)

- Run backend/tests/test_account_profile.py on the remote server (backend tests are not run locally).
- Run the stockmeTests target in Xcode (LocalReportManagerTests, LogoutCleanupTests, AppLockPolicyTests); xcodebuild is not run by agents.
- Manual iOS check: edit the display name, kill and relaunch the app, and confirm it persists. In airplane mode, confirm an error shows and PROFILE SAVED does not. Log out and in as another user, and confirm email/phone and saved reports are empty.
- Confirm routers/account.py stays the canonical /api/me surface (WIP-05 suggested deleting it); this package assumes it stays.
- Deploy the backend so PATCH /api/v1/me/profile exists before shipping the iOS build that calls it.

### be-cutover: Legacy 410 gate, copilot fork removal and ml-signal retirement

- Run backend/tests/test_research_cutover.py and backend/tests/test_copilot_service.py in CI (both rely on the DEEP_ANALYSIS context card using the normalised symbol).
- Make sure be-wiring registers app.middleware('http')(legacy_gate) in main.py; this package does not edit main.py.

### money-flags: money-flags

- On the server, set FEATURE_MONEY_* in backend/.env only to override defaults (on: holding_detail, xirr_card, journal_scoring; off: cas_import, xray, commission_drag, tax_report, crisis_replay). Restart the backend after any change.
- Integration pass: if platform-flags, data-flags, ai-flags, habit-flags or ios-flags-be land their own flag modules, merge them into backend/core/feature_flags.py (register their keys in FLAGS) rather than keeping a second mechanism.
- Check that the SecurityHeadersMiddleware change (an explicit route Cache-Control is now kept) is acceptable. It also lets the research router's 'private, max-age=300' reach clients in production.

### ios-report-ui: Stock report screen, cards, sheets, AnalysisScreen routing and paywall copy

- The commit must include the 5 unstaged deletions: DialecticProgressView, AnalysisErrorStateView, AnalysisIdleStateView, AnalysisLoadingStateView and DalalStreetConsensusCard. Use git add -A or git rm.
- Compliance sign-off is still needed on the fhs_ewma VaR sentence ('is estimated to be worse than'), which is the implementer's own wording.
- Optional follow-ups (not blocking): restart startPricePolling when the archived AnalysisScreen reappears after a Stock profile push, and have ResearchLossRow show nothing when `level` is nil instead of defaulting to '1 in 20'.

### p3-20: Backend-supplied URL strings are opened with UIApplication.shared.open (+1 more)

- Run the stockme unit tests in Xcode (SafeURLTests, NetworkErrorMessageTests, NetworkErrorCopyTests). xcodebuild is not allowed in this environment.
- Behaviour change: http:// news and video links (and any other non-https scheme) now do nothing on tap instead of opening.

### p2-29: Stock profile ships 4 of 12 tabs as permanent 'unavailable' stubs whil (+2 more)

- Owner: confirm removing the Forecast, MC Insights, Peers and Corporate tabs from the stock profile until a real data source backs them. The alternative is keeping the 'unavailable' stubs. Forecast and MC Insights should only come back once the new research engine backs them.
- Owner: confirm the product wants the Tools card (Export PDF, Benchmark, FD and other calculators) on the Portfolio screen. Also confirm the statutory gratuity rules: the ₹20 lakh ceiling, 5 years of service for regular employees, and 1 year pro-rata for fixed-term employees under the Code on Social Security, 2020.
- Run the iOS unit tests in Xcode (SessionStorageTests, CalculatorTests, GratuityCalculationTests). Then open a stock profile and check that 9 tabs show, the Dividends tab loads, and the Portfolio Tools card appears.

### money-ios-flags: money-ios-flags

- Run FeatureFlagsTests in CI or Xcode. They could only be parse-checked locally.

### be-wiring: Mount the research router and legacy gate, guard job registration, add the /healthz research block

- Run the backend test suite on the remote server, especially test_research_wiring.py, test_route_auth_inventory.py, test_batch_routes_removed.py and test_comprehensive.py.

### p2-32: 149 UIScreen.main sizings, pinned Dynamic Type, 515 sub-10pt text styl (+2 more)

- Run backend/tests/test_copilot_hardening.py, test_llm_gateway.py and feature_tests/ai_orchestration/test_copilot_service.py on the remote server.
- Sign off on the iPhone-only change: TARGETED_DEVICE_FAMILY=1 and Portrait-only orientation on iPhone, with iPad orientations removed.
- Do a visual pass on the app and the widget (both share Theme.swift): text below 11pt is now floored at 11pt, so widget text that was 10pt is now 11pt.
- Optional: on the server, truncate copilot history items longer than 8000 chars instead of returning 422. A long Haiku reply that iOS resends as history makes every later turn in that chat fail until the screen is reset.

### w4-17: Ledger and money-precision tests are broken or red, and nothing runs t

- On the remote server, run `python -m pytest backend/tests/test_transaction_ledger.py backend/tests/test_portfolio_ledger.py backend/tests/test_backend_contract_routes.py backend/tests/test_backend_contract_database.py backend/tests/test_backend_contract_db_integrity.py -rsx`. Expect 0 skipped apart from the Postgres-only concurrency test when not on Postgres, and the 2 Decimal tests reported as XFAIL.
- When DB-25 (Float to Numeric(18,4) migration) merges, remove the two strict xfail markers. strict=True will fail the run as a reminder if you forget.
- If test_portfolio_listing_handles_decimal_money_columns still fails remotely, look into the listing handler itself. Do not mark it xfail.

### p3-39: iPad and Vision are declared targets but layouts hard-code UIScreen.ma (+3 more)

- Confirm the product decision for v1: iPhone-only and portrait-only (TARGETED_DEVICE_FAMILY = 1, no iPad, Vision or landscape). Nothing has shipped yet, so this can still be reversed; re-adding iPad later needs adaptive layouts (containerRelativeFrame or size classes instead of the 149 UIScreen.main sizings) and an update to check_iphone_portrait_only.
- After integration, build on an iPhone simulator. Check: the device stays portrait when rotated; the Xcode target General tab shows iPhone only; the Home header bell opens Alerts and fits on iPhone SE width; the Alerts tray icon opens the inbox; the tab bar reads 'Experts'; Portfolio shows the TOOLS card; Settings > Delete Saved Reports asks for confirmation and Cancel leaves the badge count unchanged.

### w4-16: Backend CI runs one generated file (test_ios_endpoints.py) whose 516 t

- Before merging the CI switch, run `cd <repo> && python -m pytest backend/tests --collect-only -q -p no:cacheprovider` and then `python -m pytest backend/tests -q -p no:cacheprovider -rfE` once on the remote host with PYTHONPATH=backend and FIRECRAWL_API_KEY/FRED_API_KEY/HF_TOKEN=mock. Mark any remaining failures xfail with an issue reference, or fix them, and approve that list. Backend CI will stay red until this suite is green, so merge this package last in the TEST chain.
- After it is green, confirm with a canary branch that deletes one route: CI should turn red through test_route_inventory / test_auth_matrix. Then make Backend CI a required check in branch protection.
- Close GH-637 as covered by TEST-06; #527 (CI scope) is also resolved by this change.

### w3-04: App issues BUY/SELL calls, 3M/12M/3Y price targets and personalized 'w (+2 more)

- Product/legal decision (REG-02): decide whether to register a SEBI Research Analyst entity (and an Investment Adviser for personalised output) before any public or paid launch. Until then keep ADVISORY_OUTPUT_ENABLED unset in production. Enabling it brings back report price targets, extreme-scan scenarios and fair value, the Excel Target columns, and the IA-type /portfolio/timeframe-conflicts text.
- Decide what to do with the BULLISH/BEARISH signal stamp, which is still shipped. It is a recommendation-class output not stripped by this change.
- Remove or rework the Pre-IPO 'SUPER PRO ADVISORY' screen (PreIPOMarketplaceView.swift): entry/target/stop-loss on unlisted shares with hardcoded data.
- Implement the 30-day price lag for anything labelled educational (SEBI revision effective 1 Jul 2026), if relying on the education carve-out.
- Decide whether the DPDP data export in main.py should keep including stored target_*/upside values.
- Follow-up: the sidebar still labels the card "Today's Action" (NiveshNavigationSidebar.swift:23/41), and LLM narrative fields can still mention prices because there is no free-text output filter.

### ci-research: CI jobs for ml-engine, backend and iOS research tests, plus scheme test target

- After merge, check the first GitHub Actions runs of ML Engine CI, Backend CI and iOS CI. The new backend test_research_* suites and the iOS Research contract tests step have not run anywhere yet: backend tests may not run locally and xcodebuild is not allowed here.

### p3-24: About 8,500 lines in 23 files (plus roughly 1,500 lines of dead subvie

- Run a full Xcode build of stockme plus stockmeTests to confirm the deletion-only change still compiles (type-checking is not allowed here).
- The 'Check for unreferenced Swift files' iOS CI step still fails on Models/ResearchModels.swift and NetworkManager+Research.swift (research.v1, no UI caller yet). Either wire the research UI or decide how to handle those two files.
- Smoke-test Home, Markets, Portfolio, Stock profile (Overview and Fundamentals tabs) and Analysis.

### money-ledger-schema: money-ledger-schema

- Run backend tests on the server: tests/test_ledger_money_property.py, test_reconcile_ledger.py, test_money_schema_migration.py, test_multi_asset_transactions.py, test_account_erasure.py, tests/migrations/, test_auth_matrix.py, test_portfolio_ledger.py, test_transaction_ledger.py, test_corporate_actions.py
- Before running alembic upgrade on production, run it on a restored backup (prod was stamped, FIX DB-07). The migration rebuilds portfolio_transactions and portfolio in batch mode on SQLite and uses plain ALTERs on Postgres.
- Run backend/scripts/reconcile_ledger.py on a restored prod backup and review the CSV. Then run it on prod after an OPS-03 backup, using --apply only after that review.

### p3-25: Oversized view files with natural split seams (HomeScreen 3,052, Portf

- Build stockme in Xcode and run stockmeTests. Nothing here was type-checked (swiftc -parse only). The riskiest new pieces are HomeTopSection's @FocusState.Binding plus @EnvironmentObject memberwise init and the 13 Home*Section call sites in HomeScreen.renderSection.
- Smoke-test Home: search open/close and picking a result, the morning brief's READ FULL BRIEF and DISMISS buttons, the YouTube channel chips, tapping news and video tickers, Customize Layout scroll targets. Also smoke-test Portfolio sheets, all six Earnings tabs, QuantLab and AnalysisScreen.
- Review with `git diff --color-moved=zebra --color-moved-ws=allow-indentation-change`.

### money-holding-api: money-holding-api

- Run backend/tests/test_money_returns.py, test_money_holding_detail.py, test_portfolio_group_filter.py, test_portfolio_price_unavailable.py, test_portfolio_benchmark.py and test_router_split.py on the server or CI, since backend tests cannot run here.
- When data-instruments lands, check that its Instrument columns match the names money_mf_meta.scheme_info uses (asset_class, isin, isin_alt, amfi_scheme_code); test_scheme_info_maps_a_seeded_fund will then run instead of skipping.

### money-ios-holding-detail: money-ios-holding-detail

- Run the stockmeTests target in Xcode or CI, including HoldingDetailDecodingTests (only parse-checked here).
- Manual check on a stub server with moneyXirrCard on: start with no holdings (card hidden), add a first holding (card appears without a relaunch), record or delete a trade and pull to refresh (each re-fetches /portfolio/benchmark).
