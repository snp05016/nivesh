# Cluster 'ai': AI cost architecture and research surfaces

Roadmap: docs/investigations/2026-10-08_deep-audit/EXPANSION_ROADMAP.md

## Coverage and council handling

| Feature | Status | Verdict handling | Evidence |
|---|---|---|---|
| 6. I19 Grounded Analysis v2 (numbers from code, words from the LLM) | covered_by_engine | Build: the engine builds a stronger version than the roadmap (the LLM never writes a number at all, so no post-hoc numeric overwrite or Devanagari-digit verifier is needed). The roadmap's evidence pack is the ResearchReport fact list. No ai package. | Engine SPEC section 1 goal 1 (every displayed number is a Fact with value/unit/display/status/source/as_of/method), section 6 contract (ml-engine/research/contract.py; never-exist names include signal, target*, confidence*), section 7 formatter: DeepSeek receives only ok facts as placeholders; validator gv-1 rejects any digit or number word (lakh, crore, million), Devanagari, advice/forecast/causal lexicon lx-1; template fallback (7.7); long-press fact detail on iOS (10.1); legacy LLM pipeline returns 410 at Stage 3 (D24). Packages ENG:ml-contract, ENG:be-prose, ENG:ml-assembly-pipeline, ENG:ios-report-ui, ENG:be-cutover. Interim containment of the legacy pipeline until Stage 3: FIX:LLM-04 (reformatter receives the PM decision and facts), FIX:REG-02 (targets and upside zeroed), FIX:FAKE-16 and FIX:ML-20 (placeholder inputs removed, drivers labelled rule-based), FIX:LLM-08 (fallbacks not saved as results). |
| 10. I01 Paid-AI guard: LLM gateway, metering, cost ledger | partial | Build: built through the fix track's gateway, expand-then-contract rollout and CI ban. This cluster adds only the visible-limits layer: ai-flags (flag keys), ai-allowance-be (GET /api/v1/ai/allowance as percent + state, Retry-After, AI_PAUSED), ai-copilot-be (the budget guard runs only for messages that need an LLM, so the computed portfolio answer costs nothing and still works when the allowance is used up or AI is paused) and ai-copilot-ios (allowance line shown only at 80% or more, when used up or when paused; fetched on open and after a failure; the input stays enabled; quota copy). The roadmap's usage_counters/charge_ai/refunds are replaced by the cost ledger, which records only real provider spend (failed calls cost nothing); documented in the spec. | Fix track: FIX:LLM-02 (llm_usage ledger table, pricing, per-user IST-daily cost caps by tier, global spend breaker, require_llm_budget on copilot/brainstorm/YouTube/portfolio AI routes, phase B on /analyze and NL screener after the FIX:IOSCORE-04 Bearer build), FIX:ARCH-03 (single client factory in services/llm_utils.py, static test bans anthropic.Anthropic( and OpenAI( elsewhere), FIX:LLM-09 (usage_summary admin dashboard plus LangChain UsageMetadataCallbackHandler so the debate is metered), FIX:AUTH-17 (global and per-user job admission), FIX:AUTH-24, FIX:LLM-17, FIX:LLM-25, FIX:AUTH-11 (limiter no longer throttles polling), FIX:UX-28 (Copilot error bubbles). Engine: no LLM on request paths, 800 calls/day cap (SPEC 7.6). Gaps: users cannot see their limits; the breaker has no machine-readable code; no Retry-After; LLM-02 puts require_llm_budget('copilot') on the whole chat route, so a question that needs no LLM still fails with 429/503 once the allowance is used up; every cluster plans its own flag module and none exists in backend/ yet (only the iOS ReleaseGate). |
| 14. I22 Analysis cache correctness and LLM cost architecture | partial | Simplify: the smaller version (trading-day key, staleness label, no per-viewer copies, language/risk excluded) is fully delivered by the engine; analysis_views is unnecessary because no per-viewer rows exist. The only delta, the same-symbol compute race, is fixed in the standalone two-file package ai-research-race, so it survives any cut of other feature work; the engine track may take it instead as a one-line note. | Engine: research_reports UNIQUE(symbol, as_of_date, engine_version, origin) (SPEC 8.1, landed in migration t4u5v6w7x8y9 and repositories/research_repo.py), GET never writes (2.3; tested), staleness by weekday arithmetic with 'Data as of {date} close' header and stale/expired banners (D25, 2.5, 10.1), English only and no risk-profile tuning (D20, non-goals), nightly precompute for the universe plus portfolio/watchlist extra_symbols (2.2), no LLM on request paths. Interim legacy fixes: FIX:LLM-V1 (trading-date key, no re-dating), FIX:LLM-16, FIX:DB-17 and FIX:ML-16 (no prediction rows on cache hits), FIX:IOSUI-09. Gap found in code: research_repo.insert_on_demand_report (line 291) calls _existing_report and then inserts with no IntegrityError handling, so two concurrent on-demand computes for one symbol make the second commit raise IntegrityError (500). |
| 17. I20 Prediction Ledger v2 (smaller version) | covered_by_engine | Simplify: exceeded by the engine (insert-only outcome columns, no hash chain, supersede-not-delete because legacy routes 410). No ai package. | SPEC 8.1-8.5: research_predictions written only by nightly ingest, one per (report, horizon) with UNIQUE(report_id, horizon_days) and UNIQUE(symbol, as_of_date, horizon_days, model_id); entry_close is the raw close from the same snapshot; outcomes written once through write_outcome_once; every tier scored against the universe median and the Nifty 50; delistings kept as stale_exit; void rules; weekly live metrics with the A1 kill-switch. ENG:be-db-ledger (landed), ENG:be-ingest-jobs (IST cron), ENG:ml-assembly-pipeline (scorer os-2). Legacy analysis_predictions archived as-is (8.2). Interim: FIX:DB-03, FIX:ML-03, FIX:LLM-14, FIX:ML-16, FIX:DB-17. |
| 29. I26 Honest ML | covered_by_fix_track | Simplify (hide, do not label): the new build hides the card (engine) and old builds show no direction (ML-01). No ai package. | FIX:ML-01 (serve no direction until a gated model exists; card shows 'no validated signal'), FIX:ML-12 (ML fusion weight 0 for heuristic and baseline modes), FIX:ML-13 (reliability key mismatch fixed), FIX:ML-20 (quant drivers relabelled rule-based, not SHAP), FIX:REG-11 (hit-rate chip removed, performance routes admin-only). Engine: ENG:ios-legacy-containment removes StockMLSignalCard( from the Overview (StockProfileView.swift:507 today), ENG:be-cutover returns ml-signal 'UNAVAILABLE' at Stage 3, Stage 4 deletes confidence_fusion.py and quant_engine.py; retraining happens only through the engine's pre-registered rg-lgbm-v1 procedure with gates and live G7. |
| 37. C7 Typed analysis artifact, one presenter, staged analyze() | covered_by_engine | No council verdict (Architecture addition, Step 2): the engine supersedes the orchestrator split. No ai package. | SPEC 6: pydantic ResearchReport (extra=forbid) in ml-engine/research/contract.py with exported JSON schema and fixtures, backend mirrors only backend-owned blocks, iOS decodes leniently; one presenter services/research/serve.py serve_report (staleness, tier policy, cohort stripping, narrative, compliance, ETag); staged nightly pipeline prices > universe > features > scores > risk > fundamentals > assemble (2.2); raw full_json readers die with the legacy routes (Stage 3/4). Packages ENG:ml-contract, ENG:be-serve-api, ENG:ml-assembly-pipeline. |
| 45. C14 Analysis wait redesign | covered_by_engine | No council verdict: the 30-90 s wait disappears, so push-on-completion is unnecessary. No ai package. | SPEC 10.1: no job starts on open; the stock report renders from Postgres (GET p95 under 200 ms); off-universe symbols use a synchronous 15 s compute with a 'Computing from market data' state (10.2); ENG:ios-report-ui acceptance removes startAnalysisJob/pollJobRaw from the live path. Interim: FIX:IOSUI-09 (no auto-start), FIX:IOSUI-10, FIX:IOSCORE-16 (poll loops end), FIX:IOSCORE-22, FIX:PERF-22 (backoff), FIX:UX-21. |
| 50. I13 Offline eval harness (folded into I19) | partial | Simplify (about 20 cases): ai-prose-eval adds a freeze/run harness for the research formatter (deterministic metrics, no LLM-as-judge, CI tests with stubs only, paid runs are owner-only; provider calls are recorded in llm_usage by LLM-02, no research_* rows are written) and ai-copilot-be adds 33 Copilot reply fixtures (19 block, 14 pass) for the advice backstop, all checked locally against the final patterns. | Engine SPEC 11.2: at least 40 validator cases (rupee, lakh/crore, Devanagari, advice, Hinglish, obfuscated buy), formatter tests with a sentinel golden, contract fixtures (6.7). FIX:TEST-13 adds the socket network guard in conftest; FIX:TEST-03/TEST-02 stop paid tests being collected. Gaps: no tool evaluates a prompt or model change on frozen inputs (FIX:LLM-25 leaves the model switch as a human decision with no harness), and Copilot's free-text replies have no fixtures. |
| 51. I24 Copilot: fix it, don't rebuild it | partial | Simplify: ai-copilot-be answers portfolio questions from code (holdings aggregated by symbol; a 'my portfolio/holdings/investments' message skips the LLM intent call and the budget guard), strips computed replies from conversation_history before any LLM message list is built, adds a 14-pattern advice backstop and reply_source; ai-copilot-ios excludes computed replies from history, renders open-stock buttons through DeepLinkRouter, deletes the signal chip and fixes copy. FINSEC-04's rule (holdings reach an LLM only with ai_processing consent) holds as an invariant because no Copilot prompt contains DB holdings or a computed reply; its consent check leaves only the PORTFOLIO branch, which no longer calls an LLM. Free-text chat is still sent to the providers, as disclosed. Tool loop, server-side memory and stock fact Q&A are deferred. | Fix track: FIX:LLM-02 (auth and quota), FIX:LLM-13 (role whitelist, payload caps, sync handler, fixed system prompt, no per-turn summary), FIX:DB-20 and FIX:REL-24 (shares instead of quantity, holdings filter), FIX:REL-22 plus ENG:be-cutover (DEEP_ANALYSIS returns a fixed sentence plus nivesh://analyze/{SYMBOL}, no fork), FIX:FINSEC-04 (consent gate on the PORTFOLIO branch only), FIX:REG-02 (non-advisory rules), FIX:UX-28 (iOS error bubbles, history payload, disclaimer, real navigation map), FIX:UX-34. FINSEC-04, REL-24 and UX-28 have already landed in the worktree. CopilotScreen.historyPayload sends every assistant reply back as conversation_history, and the GENERAL and DEEP_ANALYSIS-without-ticker branches pass that history to DeepSeek or Anthropic, so a portfolio answer would re-enter an LLM on the next turn unless it is removed. The only withCopilot() call (ContentView.swift:88) passes no context, so current_context carries only the navigation map. Gaps in code: portfolio answers still let an LLM restate holdings, there is no output-side advice check, the iOS bubble renders a bull/bear 'Signal:' chip from context_cards and cannot open the nivesh:// link, and the welcome card promises 'Deep research' and 'Market Intel'. |
| 59. I21 Visible track record and calibrated confidence | partial | Deferred: no code (docs only). The engine default stays, and the engine's own RESEARCH_TRACK_RECORD_PUBLIC flag is the switch for when registration is in place; this cluster adds no second one. Two candidate surfaces were dropped after review: a holdings-and-watchlist report list (it duplicates the Portfolio and Watchlist tabs) and a dormant public track record (a performance-claim surface shipped before registration invites App Store 2.3.1 hidden-feature trouble and SEBI advertising exposure, and its metric had no n, confidence interval or benchmark). This deviates from the default Defer handling (build the smaller version behind an off flag) because the smaller version, 'My analyses', needs a per-user view history (a new DPDP surface) and Phase 3 engine report history; it is built in Phase 3 from engine data. ai-i21-docs adds COMPLIANCE.md section 12 with the preconditions (RA registration, G7, PaRRVA verification, legal display sentence, in-app only, production procedure_id only), without dates. | Roadmap: council verdict Defer; smaller version 'My analyses', to be built 'once I22 lands'; final recommendation Phase 3; named risks are PaRRVA and SEBI advertising rules. Engine SPEC 8.6 and D37: live numbers only on the admin /track-record endpoint; RESEARCH_TRACK_RECORD_PUBLIC takes effect only with a valid RESEARCH_SEBI_RA_REG_NO, which v1 cannot have because RA_DISCLAIMER_TEXT is None (docs/research/COMPLIANCE.md section 6); live_track_record carries states only; no cohort UI. FIX:REG-11 makes existing performance claims admin-only. PaRRVA (SEBI's past risk and return verification) applies to registered advisers and research analysts only. |
| 40. I33 Risk flags card | new | Simplify: concentration ships first (ai-riskflags-be, ai-riskflags-ios; flag risk_flags_concentration, default on): post-trade only (the viewed stock must be held), lots aggregated by symbol, at most three flags with source and date, no external data. ASM/GSM comes later through the conditional ai-surveillance-data (flag risk_flags_surveillance, default off), built only after an OPS spike fetches one REG_IND file with the REG-10 honest User-Agent and legal confirms display rights as part of the I07 decision. The file is refreshed by a 6-hourly scheduler job, never on the request path; unknown codes show nothing; iOS hides the Governance banner when the card covers surveillance, so one source is shown. 'Results within 5 days' is deferred until an event-calendar source exists. | Engine cut ASM/GSM from v1 (D32; SPEC 3.1 'Not used'). Today ASM/GSM reaches iOS through /quick-info (routers/analysis.py:399-413, NSE private JSON endpoints via nse_client._get_asm_gsm_lists) and renders as GovernanceSurveillanceBannerView on the Governance tab; the engine leaves /quick-info to its own track. config.settings.get_user_agent() returns fake_useragent's random browser UA (config/settings.py:154) until FIX:REG-10 makes it a constant 'NiveshBot/1.0 (+...)'; REG-10 keeps the private endpoints pending a vendor decision. Concentration logic exists only in the portfolio risk endpoint (routers/portfolio.py, >20% rule) and math_engines/concentration.py. Portfolio stores one row per lot, with tickers as 'TCS' or 'TCS.NS'. Research reports carry a top-level sector and snapshot.last_close as a Fact with a status (SPEC 6). NSE publishes a daily regulatory-indicators file REG_IND{DDMMYY}.csv; per its file-structure PDF, GSM 100 = not applicable, 0 = in GSM, 1-4 and 6 = stages; the ASM codes are not consistently documented and the download URL is unverified. Showing exchange data in a commercial app raises the same licence question as roadmap I07. |

## Spec

# Cluster 'ai': AI cost architecture and research surfaces — implementation plan (revised after adversarial review)

## 0. Notes for the orchestrator
- **Cost alert.** Every Bash call in this revision pass returned the hook message "COST CRITICAL: Session cost is $579–588. Stop and inform the user about high cost before continuing." A workflow subagent cannot pause to ask, so this pass stayed read-only and kept its reads batched. **Please show this alert to the user.**
- No repository files were changed. Scratch checks are in `scratchpad/fix/tmp/ai2/`:
  - `canonical_patterns.py` runs the Copilot advice patterns against the 33 fixtures in `copilot_replies.json` plus 11 extra sentences, with 0 problems.
  - `parts.json` was checked for valid FIX/ENG dependencies, no cycles, 1–10 files per package and no stray control characters.
- The review's critical item, its three high items and all five medium items are applied, as are the three low items (each a one-line change). Two deliberate deviations are explained in §7.
- Landing state checked in the worktree:
  - FINSEC-04, REL-24 and UX-28 have landed (Copilot consent gate, holdings filter, iOS `historyPayload`).
  - IOSCORE-20 has not: `Utilities/DeepLink.swift` still exposes `pendingTicker`.
  - REG-10 has not: `get_user_agent()` still returns a random fake browser UA.

## 1. Coverage summary

| # | Feature | Council | Status | Work here |
|---|---|---|---|---|
| 6 | I19 Grounded analysis v2 | Build | covered_by_engine | none |
| 10 | I01 Paid-AI guard | Build | partial | ai-flags, ai-allowance-be, guard placement in ai-copilot-be, ai-copilot-ios |
| 14 | I22 Cache correctness | Simplify | partial | ai-research-race |
| 17 | I20 Prediction ledger v2 | Simplify | covered_by_engine | none |
| 29 | I26 Honest ML | Simplify | covered_by_fix_track | none |
| 37 | C7 Typed artifact | — | covered_by_engine | none |
| 45 | C14 Analysis wait | — | covered_by_engine | none |
| 50 | I13 Offline eval | Simplify | partial | ai-prose-eval; Copilot fixtures in ai-copilot-be |
| 51 | I24 Copilot fix | Simplify | partial | ai-copilot-be, ai-copilot-ios |
| 59 | I21 Track record | Defer | partial (docs only) | ai-i21-docs |
| 40 | I33 Risk flags | Simplify | new | ai-riskflags-be, ai-riskflags-ios; ai-surveillance-data only after the OPS spike |

The Research Engine replaces the LLM-authored analysis, and its legacy `/analyze*` routes return 410 at Stage 3. The engine covers four features outright and the fix track covers one (I26); fix-track items contain the legacy pipeline until Stage 3.

The remaining work is:
- the visible-limits layer of I01;
- the Copilot fix;
- eval tooling;
- risk flags;
- one engine race fix;
- the I21 preconditions.

**10 packages (one of them conditional), no schema change, no new dependency.**

## 2. Cross-cutting decisions

### 2.1 Feature flags (ai-flags)
- No backend flag mechanism exists yet, and five other clusters each plan one:
  - data and money at `core/feature_flags.py`;
  - platform (which claims ownership, with a DB table) and habit at `services/feature_flags.py`;
  - ios at `config/feature_flags.py`.
- ai-flags does not add another. It registers its keys in whichever module exists when it runs, and adds a `require_feature(key)` wrapper there if that module lacks one.
- Only if no module exists does it create `core/feature_flags.py`: env-backed and read per call; an unknown key fails closed; the 404 body is `{"code":"FEATURE_DISABLED","feature":key}`.
- iOS learns a flag through the surface's own endpoint: a 404 hides that surface. No flags endpoint or client cache is needed.

| Flag | Default | Gates |
|---|---|---|
| `ai_allowance` | on | `GET /api/v1/ai/allowance` and the Copilot allowance line (a kill switch; see §7) |
| `risk_flags_concentration` | on | the holding and sector checks in `GET /api/v1/stocks/{symbol}/risk-flags` |
| `risk_flags_surveillance` | **off** | the ASM/GSM checks and the 6-hourly REG_IND refresh (code ships only with the conditional ai-surveillance-data) |

- The risk-flags endpoint returns 404 `FEATURE_DISABLED` when both risk flags are off.
- The engine's `RESEARCH_TRACK_RECORD_PUBLIC` stays the engine's own switch; this cluster adds none for I21.

### 2.2 Data model
- **No new tables and no Alembic migration.** The features read existing tables: `llm_usage` (FIX:LLM-02), `portfolio`, and `research_reports` (ENG:be-db-ledger).
- The surveillance snapshot lives in `disk_cache` (namespace `surveillance`, key `reg_ind`), and only the refresh job writes it:
  - the cache is Redis through `cache_service`, with OPS-18's in-process fallback;
  - ARCH-07 runs the scheduler and the API in one process.
- Not built:
  - `usage_counters`/`charge_ai`: the cost ledger meters real spend, and a failed call records no cost, which is the refund;
  - `analysis_views`: the engine writes no per-viewer rows;
  - any per-user report view log: I21 is deferred.

### 2.3 API contracts (shared by the backend and iOS packages)

**A. `GET /api/v1/ai/allowance`**
- Auth: Bearer. Flag: `ai_allowance`.
- 200 `{"used_pct": 40, "state": "ok"}`, where `state` is `ok`, `low` (80% or more), `exhausted` or `paused`. No money, cap or tier is returned.
- 401 without a token; 404 `FEATURE_DISABLED` when the flag is off.

**B. Paid AI routes guarded by `llm_budget`**
- 429 `{"detail":{"error_code":"AI_QUOTA_EXCEEDED",...}}` with `Retry-After` (seconds to IST midnight).
- 503 `{"detail":{"error_code":"AI_PAUSED","error_title":"AI paused","error_detail":"AI features are paused for today. Everything else in Nivesh works."}}` with `Retry-After`.

**C. `POST /api/v1/copilot/chat`**
- Auth: `require_auth` (401 without a token).
- The budget guard runs inside the route, and only when the message is not a portfolio question (`\bmy\s+(portfolio|holdings|investments)\b`):
  - portfolio questions cost nothing and still work when the allowance is used up or AI is paused;
  - other messages get 429/503 before any LLM call.
- The response adds `"reply_source": "ai" | "computed"` (default `ai`; additive).
- `conversation_history`: before any LLM message list is built, the server drops every assistant entry that contains the computed-reply footer, along with the user entry just before it. New iOS builds do not send them either.
- From the fix and engine tracks:
  - `reply` may contain `nivesh://analyze/{SYMBOL}` (be-cutover);
  - `context_cards` may contain `{"type":"open_analysis","ticker":"TCS"}` (REL-22).

**D. `GET /api/v1/stocks/{symbol}/risk-flags`**
- Auth: Bearer. 404 `FEATURE_DISABLED` when both risk flags are off.
- 200 response:
  ```json
  {"symbol":"ABC",
   "checks":["surveillance","concentration"],
   "flags":[{"id":"gsm|asm|holding_concentration|sector_concentration","title":"...","text":"...","source":"...","source_url":"https://...|null","as_of":"YYYY-MM-DD|null"}],
   "unavailable":[{"check":"surveillance","reason":"source_unavailable"}]}
  ```
- `checks` lists only the enabled checks, and a disabled check adds no `unavailable` entry.
- At most 3 flags.
- Errors: 401, and 422 `{"detail":{"code":"INVALID_SYMBOL"}}`.

### 2.4 Test conventions

**Backend**
- Hermetic pytest on `backend/tests/conftest.py`:
  - fixtures: client, auth_headers, admin_headers, test_user_id;
  - SQLite database;
  - yfinance, anthropic and openai are mocked;
  - `disk_cache` is a MagicMock, so caching tests monkeypatch a dict-backed fake.
- FIX:TEST-13 blocks network access.
- Locally, run only PYPARSE and PYRIGHT. CI runs the tests once FIX:TEST-06 lands.

**iOS**
- XCTest in `stockmeTests`. Locally, run only `swiftc -parse`.
- CI runs the tests after FIX:TEST-17 and ENG:ci-research.

## 3. Feature specs

### 3.1 I01 — visible AI limits (ai-allowance-be, ai-copilot-be, ai-copilot-ios)
**User story.** When I am close to or past today's AI allowance, Copilot tells me so plainly, including that it resets at midnight India time, instead of showing a raw error. Portfolio questions keep working because they use no AI.

**v1 scope**
- `llm_budget` gains:
  - `allowance(user_id)`: a percentage and a state;
  - `global_paused()`;
  - `seconds_to_ist_midnight()`;
  - `Retry-After` on 429 and 503;
  - the breaker's detail code `AI_PAUSED`.
- The allowance route lives in `routers/copilot.py`, so `main.py` is not edited.
- ai-copilot-be moves the budget guard from the route dependency into the handler, after the portfolio keyword check (§2.3 C).
- iOS (Copilot):
  - The allowance line shows only when the state is `low`, `exhausted` or `paused`. At `ok` nothing is shown: a cost-based percentage varies per query and would only invite questions.
  - The line is fetched when Copilot opens and again after a failed send, not after every reply.
  - The input stays enabled in every state.
  - Errors are mapped by `AIErrorCopy`, which the ios cluster's C8 pipeline can reuse.

**Exact copy**

| Case | Text |
|---|---|
| ok | nothing shown |
| low | "Today's AI allowance: {used_pct}% used" |
| exhausted | "Today's AI allowance is used up. It resets at midnight, India time." |
| paused, and 503 `AI_PAUSED` | "AI features are paused for now. Everything else in Nivesh works." |
| 429 `AI_QUOTA_EXCEEDED` | "You've used today's AI allowance. It resets at midnight, India time." |
| other 429 | existing copy: "Too many requests. Please wait a minute and try again." |
| other 503 | "Copilot is busy. Please retry shortly." |
| 401 | existing copy: "Your session has expired. Please sign in again." |

**Tests**
- 401 and 404 responses;
- each state at 0%, 85% and 100%, plus paused;
- usage from before IST midnight is excluded;
- `Retry-After` range;
- only the two keys are returned;
- the midnight arithmetic (18:29 UTC → 60 s);
- over the cap, a portfolio question returns 200 while "hello" returns 429 with no LLM call.

**Risks**
- The cap check sums before calling, so concurrent in-flight calls can overshoot a cap by their own cost. FIX:AUTH-17 admission and the per-route limits bound this.
- Percentages are relative to the caps the owner sets (an LLM-02 human step).

### 3.2 I24 — Copilot v2 (ai-copilot-be, ai-copilot-ios; includes the I13 Copilot fixtures)
**User story.** When I ask Copilot "how is my portfolio doing?", I get correct numbers computed from my own holdings, and my holdings are not sent to an AI provider. When a reply names a stock, I can open it with one tap. Copilot never gives buy, sell or hold calls, targets or stop-losses.

**v1 scope**
1. **Portfolio questions are answered by code.**
   - Routing: a message matching `\bmy\s+(portfolio|holdings|investments)\b` goes straight to the computed path, with no intent call and no budget guard.
   - Other messages go through the intent router, and intent PORTFOLIO takes the same computed path.
   - Because "my" is required, "What is a portfolio?" is still explained by the LLM.
   - Holdings rows (`group_name='holdings'`, not virtual) are aggregated by `research_repo.normalize_symbol`. Portfolio stores one row per lot, as `TCS` or `TCS.NS`, so lots merge: shares are summed and invested = Σ shares × buy price. "You hold n stocks" counts distinct symbols.
   - Prices come from `_yf_price` (the Portfolio tab's source), in parallel: up to 50 symbols, 10 workers, a 10 s budget.
   - Sums use Decimal. Formatting uses `format_indian_currency` (Lakhs/Crores).
   - Unpriced symbols are listed and left out of the value figures.
   - No LLM call is made, and `reply_source` is `computed`.
2. **Holdings never ride the history into an LLM** (the review's critical finding).
   - Server: `_scrub_history` drops every assistant entry that contains the computed-reply footer, plus the question before it, as the first step of `process_copilot_request`.
     - GENERAL, DEEP_ANALYSIS without a ticker, and the western-scale rewrite retry all use the scrubbed list.
     - Old app builds send computed replies back, because UX-28's `historyPayload` sends every assistant reply. This server-side step is what protects them.
   - Client: `historyPayload` skips computed replies and the question before them.
   - A computed reply never goes through the LLM rewrite retry.
   - FINSEC-04 invariant: DB holdings reach an LLM only with `ai_processing` consent.
     - After this change, no Copilot branch puts DB holdings or a computed reply in a prompt. The consent check therefore leaves only the PORTFOLIO branch, which no longer calls an LLM.
     - A code comment at the scrub requires `has_active_consent` for any future branch that adds holdings to a prompt.
   - What still reaches the providers: text the user types (including holdings they type themselves) and the AI's own replies, as the FINSEC-04 disclosure states.
3. **Advice backstop on every AI reply.**
   - `advisory_guard.find_advice(text)` runs 14 patterns:
     - `first_person_advice` (now also "I'd" and "I’d");
     - `my_recommendation`;
     - `you_should_act`;
     - `consider_acting`;
     - `act_now`;
     - `imperative`: sentence- or bullet-initial "Buy TCS", "Avoid Yes Bank", "Book profits now";
     - `level_with_number`;
     - `hype_terms`;
     - `guaranteed_returns`: exempt when the sentence has a negation;
     - `good_buy`;
     - `worth_acting`;
     - `timing`;
     - `view_terms`: "bullish on HDFC";
     - `hinglish`: "kharid lo", "bech do".
   - Educational text passes: "Exit load is ...", "Sell orders are ...", "buyback", "selling pressure", "stop-loss order", "target maturity fund", "promoters hold 52%", "No mutual fund offers guaranteed returns".
   - A stop-loss explanation that quotes a price is still blocked (accepted as conservative).
   - A match replaces the reply with: "I can't give buy, sell or hold views, price targets or stop-loss levels. I can explain how something works, summarise your holdings, or open a stock's page in Nivesh."
   - Only pattern ids are logged.
   - The exact patterns are in ai-copilot-be. They were run locally against all fixtures plus 11 extra sentences with no failures.
4. **iOS**
   - `nivesh://analyze/{SYMBOL}` links and `open_analysis` cards become "Open {SYMBOL}" buttons.
     - The parser validates each symbol through IOSCORE-20's `DeepLinkRoute.from(url:)`, so the parser and the router accept the same symbols.
     - The button routes through `DeepLinkRouter` to the stock hub.
   - The bull/bear "Signal:" chip renderer is deleted.
   - The caption depends on `reply_source`: "Computed from your Nivesh holdings. Not investment advice." or "AI-generated. Not investment advice."
   - The welcome copy no longer promises deep research or market intel.
5. **Deferred:** the tool loop, server-side memory, and stock fact Q&A from engine facts (the engine's 7.9 portfolio narratives are v1.1).

**Computed reply template.** Sentences are skipped when their inputs are missing. Signs are "+" or U+2212.

> "You hold {n} stocks. Amount invested: {invested}. Current value of the {k} with a price: {value}, against {invested_p} invested, a change of {±amount} ({±pct}%). Largest by current value: {A w%}, {B w%}, {C w%}. [Prices were unavailable for {m} holdings ({T1, T2, T3, …}), so they are left out of the value figures.] These figures are computed from your Nivesh holdings using the latest available prices. They are not investment advice."

The last sentence is the footer the history scrub looks for. If there are no holdings: "You have no holdings in Nivesh yet. Add one from the Portfolio tab to see a summary here."

**I13 fixtures.** `backend/tests/fixtures/copilot_replies.json` holds 33 cases: 19 to block and 14 to pass. The full texts are in ai-copilot-be.

New since the review, to block:
- "I'd recommend buying TCS for the long term."
- "Consider buying TCS before the results."
- "Buy TCS."
- "Avoid Yes Bank for now."
- "We are bullish on HDFC Bank."
- "Abhi kharid lo, price aur badhega."
- "My recommendation is to buy Infosys."

New since the review, to pass:
- "No mutual fund offers guaranteed returns."
- "A stop-loss order is an instruction to sell if the price falls to a level you choose."

**Tests**
- Exact totals: TCS 5 @ 3,500 and INFY 10 @ 1,500, priced at 4,000 and 1,400, give invested ₹32,500, value ₹34,000, +₹1,500 (+4.6%), TCS 58.8%.
- Two TCS lots give "You hold 1 stock", with TCS listed once.
- A keyword portfolio question makes no LLM call. An intent-routed one makes exactly one (the intent call).
- No LLM call argument ever contains a holding ticker, an amount or the footer, including when a computed reply sits in the history (test i).
- The watchlist row is excluded.
- An unpriced holding produces its note.
- The refusal replaces an advice reply.
- The fixture parametrisation passes.
- The reply passes `_ban_western_scale`.
- Over the cap: a portfolio question returns 200 and "hello" returns 429.
- The FINSEC-04, REL-24 and feature tests that assert the old LLM portfolio path are updated.

**Risks**
- Patterns cannot catch every phrasing. The REG-02 system-prompt rules remain the first line of defence.
- A follow-up such as "explain the second one" after a computed summary gets no context, because the summary is scrubbed. This is the privacy trade-off.
- `_yf_price` latency is bounded by the 10 s budget.

### 3.3 I13 — offline prose eval (ai-prose-eval)
**User story.** Before switching the DeepSeek model (LLM-25) or changing prompt rf-1, the owner runs a frozen-input eval and compares deterministic metrics. There is no LLM judge.

**How it works**
- `backend/scripts/research_prose_eval.py freeze --n 20 --out f.jsonl` takes the latest nightly reports in a deterministic order (by symbol hash), with `known_symbols` and `company_names`. It uses report JSON only, with no user data.
- `run --in f.jsonl --max-calls 40 --label X --yes` calls the engine's `formatter.generate_narrative`, which goes through `llm_utils`, so the global breaker and ledger apply.
- It prints:
  - `n_evaluated`, `llm_validated`, `template`;
  - `first_pass_rate`, `validated_rate`, `template_rate`, `mean_attempts`;
  - a histogram of failure codes;
  - `calls_used`, `model`, `prompt_version`, `validator_version`.
- It exits with code 2 in any of these cases: without `--yes`, without `DEEPSEEK_API_KEY`, when `--max-calls` is above 200, when the input is empty, or when run with no arguments.
- It writes no `research_*` rows. LLM-02 records provider calls in `llm_usage`, attributed to `prose_eval` when the ledger's `bind` is available.
- It is never scheduled or run in CI. CI tests use stubs only.

**Adoption rule** (added to RUNBOOK section 10). Adopt a candidate only if all of these hold:
- `validated_rate` is at least 0.90 (the engine's Stage-1 exit) and at least the baseline minus 0.02;
- `template_rate` is not more than 2 points higher;
- 20 rendered samples pass human review.

### 3.4 I33 — risk flags (ai-riskflags-be, ai-riskflags-ios; conditional ai-surveillance-data)
**User story.** On the Overview of a stock I hold, I see at most three plain facts that matter for risk, each with its source and date:
- whether the stock is a large share of my holdings;
- whether its sector is a large share of my holdings;
- once enabled, whether NSE has it under surveillance.

**Phase 1 — concentration** (ships now; flag `risk_flags_concentration`, default on)
- Post-trade only: if the viewed stock is not held, there is no flag. A sector line on a stock the user is only browsing would read as an implicit "don't buy".
- Holdings are aggregated by normalized symbol, so two 15% lots of one stock make 30%.
- The latest report for every held symbol is loaded in one query. `snapshot.last_close` is used only when its Fact status is `ok`.
- Valuation basis:
  - current value if every held symbol has a usable close dated within 5 days (`basis_date` = the oldest close date);
  - otherwise, amount invested.
  - The basis and date are always stated.
- `holding_concentration` appears when the stock is above 20%.
- `sector_concentration` appears when its sector is above 40% and the sector includes at least one other holding.
- Texts:
  - "Large share of your holdings": "{SYM} is {w}% of your holdings by current value, using closing prices from {D}. This line appears when one stock is above 20%." On the invested basis the text reads "... by amount invested. ..." instead.
  - "Large share in one sector": "{Sector} stocks are {s}% of your holdings by {basis}. This line appears when one sector is above 40%."
  - Source: "Your Nivesh holdings".

**Phase 2 — ASM/GSM** (conditional package ai-surveillance-data; flag `risk_flags_surveillance`, default off)
- **Hard prerequisite** (human step 2):
  - An OPS spike fetches one `REG_IND{DDMMYY}.csv` from nsearchives with REG-10's honest `NiveshBot` User-Agent, and confirms the columns and code meanings against NSE's file-structure PDF.
  - Legal confirms that showing the file in a commercial app is allowed without an NSE licence, as part of the roadmap I07 data-licence decision.
  - Without both, the package is not built and the flag stays off. An honest User-Agent addresses deception, not licensing.
- Off the request path:
  - A 6-hourly scheduler job fetches the file. Its function, `refresh_snapshot`, does nothing while the flag is off.
  - `get_snapshot()` only reads the cache. A miss means "unavailable", never a fetch.
  - A failed refresh keeps the last good snapshot until its 36 h TTL lapses, and the file date is always shown.
- No disguise:
  - The fetch runs only when `get_user_agent()` starts with `NiveshBot`. Before REG-10 lands, it logs `blocked_precondition` and makes no request.
  - 401/403 stops the run and is logged. There are no cookies and no rotated identity.
- Code semantics:
  - 100 means not applicable.
  - GSM 0 means "in GSM" and is shown without a stage; 1–4 and 6 are shown as "stage n"; any other code shows nothing and is logged as `schema`.
  - ASM accepts long-term codes {1, 2, 3, 4} and short-term codes {1, 2}. The short-term column is optional.
  - These sets are constants that OPS confirms during the spike.
- Texts:
  - "Under exchange surveillance (GSM)": "NSE lists {SYM} under its Graded Surveillance Measure[ (stage {n})] in its regulatory indicators file dated {D}. Stocks in this framework trade under extra conditions set by the exchange."
  - The ASM text follows the same pattern, with "(long-term stage {a}; short-term stage {b})".
  - Source: "NSE regulatory indicators file", with a link to NSE's surveillance page.
- One source on screen:
  - Today the Governance tab's `GovernanceSurveillanceBannerView` shows ASM/GSM from `/quick-info`. That route reads NSE's private endpoints and stays until REG-10's vendor decision.
  - When the risk-flags response lists `surveillance` in `checks`, the Governance tab hides that banner, so the two sources never disagree on screen.

**iOS**
- `RiskFlagsCard(ticker:)` appears directly after `OverviewTabView` in `StockProfileView`. The money cluster's holding page can reuse it.
- It renders nothing when there are no flags, while loading, on error, when offline, or with the flags off. It never says "no risks".
- Each row shows an amber triangle, the title and two lines of text.
- Tapping a row opens a detail sheet with the source and date. An "Open the NSE page" button is shown only when `SafeURL.web` accepts the link (FIX:IOSCORE-33).

**Deferred:** "results within 5 days" waits for an event-calendar source. The habit cluster's I31 is a candidate.

**Risks**
- NSE may refuse the honest client, or legal may say no. Then only concentration ships, which needs no external data.
- A wrong column could cause false alarms. Schema errors and unknown codes fail closed, and the date is always shown.
- Legal should review the copy (human step 5).

### 3.5 I21 — deferred, docs only (ai-i21-docs)
- The council verdict is Defer. The smaller version is "My analyses", to be built "once I22 lands"; the final recommendation is Phase 3.
- **Not built now:**
  - A holdings-and-watchlist report list. It duplicates the Portfolio and Watchlist tabs. A real "My analyses" needs a per-user view history (a new DPDP surface) and engine report history, so it belongs to Phase 3.
  - A dormant public track record. It would ship a performance-claim surface before registration, which invites App Store 2.3.1 trouble (hidden features enabled after review) and SEBI advertising-code exposure. Its metric (directional hit rate) also lacked n, a confidence interval and a benchmark, and was not shown to be PaRRVA-verifiable.
- **Engine conflict:** the engine default stays. Live numbers appear only on the admin endpoint, and `RESEARCH_TRACK_RECORD_PUBLIC` takes effect only with a valid registration (SPEC 8.6, D37). That engine flag is the switch for when the condition is met; this cluster adds no second one.
- **Deliverable:** `docs/research/COMPLIANCE.md` section 12 lists the preconditions in order:
  1. RA registration and `RA_DISCLAIMER_TEXT`;
  2. G7 passed;
  3. PaRRVA verification of the displayed metric;
  4. a legal display sentence with n, CI and benchmark;
  5. then the engine flag.

  The section also says the figures are shown in-app only and must use only the production `procedure_id`. It contains no dates.

### 3.6 I22 delta — on-demand compute race (ai-research-race)
- `research_repo.insert_on_demand_report` catches `IntegrityError` on commit, rolls back, and returns the row that won the race. It re-raises if there is none.
- This is a standalone two-file package, so it survives any cut of feature work. The engine track may take it instead as a one-line note.

### 3.7 Covered features — what to verify at integration (no packages)

| Feature | Check |
|---|---|
| I19 | gv-1 tests are green (ENG:be-prose); legacy containment from LLM-04 and REG-02 is live until Stage 3. |
| I20 | One prediction per (report, horizon); outcomes written once; legacy tables archived. |
| C7 | serve.py is the only presenter of research JSON. |
| C14 | `AnalysisScreen` has no `startAnalysisJob` or polling on the live path. |
| I26 | StockMLSignalCard is gone from the new build; ml-signal returns `UNAVAILABLE` at Stage 3; ML-12 weight 0. |
| I01 core | LLM-02 401/429 tests, the ARCH-03 static guard, and LLM-09 graph metering. |

## 4. Conflicts with the engine and the fix track (resolved)
- **Copilot DEEP_ANALYSIS.** FIX:LLM-13 step d appends "Latest report signal: {signal}". ENG:be-cutover supersedes it with no signal text, just a fixed sentence plus the deep link. ai-copilot-be keeps that behaviour, and the iOS signal chip is deleted.
- **Copilot PORTFOLIO vs FINSEC-04.** ai-copilot-be replaces FINSEC-04's consent check and the DB-20/REL-24 LLM prompt in this branch, and updates their tests. FINSEC-04's rule holds as an invariant (§3.2 item 2).
- **LLM-02's route dependency.** `require_llm_budget('copilot')` becomes `require_auth` plus an in-route `guard()` for non-portfolio messages. LLM-02's tests (401 without a token; the 429/503 shapes) still hold.
- **Visible track record vs the registration gate.** The engine default is kept, and there is no code here (§3.5).
- **Hindi/Hinglish.** English only (D20); the ios cluster's I23 handles any flagged extension. The advice backstop still catches Hinglish advice phrasing, because users can type it.
- **ASM/GSM.** The engine cut it (D32). This cluster adds it only after the spike and legal sign-off, from the public REG_IND file. The private endpoints that REG-10 leaves in `nse_client` are untouched, and iOS shows only one source at a time.
- **Flag modules.** One module is shared across clusters (§2.1).
- **`main.py`.** Only ai-riskflags-be adds an include line. The allowance route lives in `routers/copilot.py`.

## 5. Risks
1. **SEBI advice exposure in free-text Copilot.** Mitigations: the REG-02 rules, the deterministic portfolio path, and the 14-pattern backstop checked against 33 fixtures. Residual phrasing risk remains; review the logged pattern ids weekly.
2. **Privacy.** Holdings can no longer re-enter an LLM through history: the path is closed on both server and client, and test (i) covers it. Text the user types is still sent to the providers, as disclosed.
3. **The NSE file is blocked or not licensed.** Surveillance is not built until the spike passes, and concentration ships regardless. The client is never disguised.
4. **Allowance semantics.** The percentage depends on the owner's caps, and a small overshoot under concurrency is possible.
5. **Landing order.** Six fix items edit the Copilot files first. IOSCORE-20 has not landed, so ai-copilot-ios starts with a pre-check grep.

## 6. Suggested build order

| Run | Packages | Notes |
|---|---|---|
| 1 | ai-flags, ai-prose-eval, ai-research-race, ai-i21-docs | No intra-cluster dependencies |
| 2 | ai-allowance-be, ai-riskflags-be | |
| 3 | ai-copilot-be, ai-riskflags-ios | ai-copilot-be comes after ai-allowance-be, because both edit `routers/copilot.py` |
| 4 | ai-copilot-ios | Needs both backend contracts and FIX:IOSCORE-20 |
| Conditional | ai-surveillance-data | Only after human step 2 passes; otherwise drop it |

## 7. Changes from the reviewed plan

| Review item | Severity | Change |
|---|---|---|
| Holdings return to an LLM through `conversation_history` | critical | Server `_scrub_history` plus client exclusion, with test (i). FINSEC-04 kept as an invariant. The privacy human step is reworded: holdings are not sent by the portfolio answer, but free-text chat still is. |
| Deferred I21 surfaces built anyway | high | Deleted ai-research-me-ios and the I21 half of ai-research-me-be, along with `research_my_reports`, `RESEARCH_PARRVA_VERIFIED_THROUGH` and `latest_live_metric_on_or_before`. Only COMPLIANCE.md section 12 remains (ai-i21-docs), without unverified dates. |
| Race fix bundled into a deferred package | high | Moved to the standalone package ai-research-race. |
| Surveillance source: licence, feasibility, fake UA, request-path fetch | high | An OPS spike plus legal sign-off (I07) is now a hard prerequisite. Added a `NiveshBot` UA precondition with a test. The fetch moved to a 6-hourly job; the request path reads the cache only; the deadline logic is removed. |
| Gate coupling, pre-trade sector flag, duplicate banner | medium | Two flags; flags are post-trade only; the Governance banner is hidden when surveillance is on. |
| Lot aggregation, close status, N report queries | medium | Both services aggregate by normalized symbol, check the Fact status, and load reports in one query. Added tests for two lots. |
| GSM 0 and unknown codes | medium | Stage-text rules added; an unknown code means no flag plus a schema log. Fixture rows for GSM 0 and GSM 5. |
| Advice regex gaps and false positives | medium | 14 patterns (6 new), with a negation-aware guaranteed/risk-free check and a bullet-aware imperative; 33 fixtures, checked locally. The review's suggested lookbehind for "no guaranteed" would not have passed its own example sentence ("No mutual fund offers guaranteed returns"), so a sentence-level negation check is used instead. |
| Allowance UX and spend | medium | The line shows only when low, exhausted or paused. It is fetched on open and after a failure, and the input stays enabled. The portfolio keyword route runs before the budget guard. |
| Parser vs router symbol validation | low | The parser validates through `DeepLinkRoute.from`, with an IOSCORE-20 pre-check. |
| Prose-eval wording and usage test | low | Wording fixed; test (g) added. |
| ai-flags acceptance grep | low | Replaced. The review's suggested grep misses f-string and `environ.get` reads, so the plan uses a grep checked on samples. |
| **Deviation 1** | — | The `ai_allowance` flag is kept, as a kill switch, because the cluster rules require every new surface to sit behind a server-side flag. The review called it an unneeded knob; it costs one key and one dependency. |
| **Deviation 2** | — | I21 (Defer) is delivered as docs only, not as a flag-off build. The roadmap's smaller version needs I22, Phase 3 engine data and a new personal-data surface, and the engine already holds the registration-gated switch. |


## Owner/ops steps (not for implementers)

- Approve the flag defaults in the server backend/.env, and restart the API after any change: FEATURE_AI_ALLOWANCE=true, FEATURE_RISK_FLAGS_CONCENTRATION=true, FEATURE_RISK_FLAGS_SURVEILLANCE=false. If legal has not approved the risk-flag copy when the iOS build ships, set FEATURE_RISK_FLAGS_CONCENTRATION=false until it has.
- Hard prerequisite for ai-surveillance-data (ASM/GSM): run a one-time spike and get legal sign-off before that package is built.
1. After FIX:REG-10 lands and BOT_CONTACT_URL is set, open https://www.nseindia.com/all-reports in a browser and copy the REG_IND CSV link for the latest trading date.
2. On the server, fetch that one file with the honest User-Agent: curl -sS -o /tmp/reg_ind.csv -w '%{http_code}\n' -A "<the NiveshBot string from config.settings.get_user_agent()>" "<the copied URL>".
3. Confirm HTTP 200, a CSV body, a Symbol column and GSM/ASM columns. Check the code meanings against NSE's REG_IND file-structure PDF (expected: 100 = not applicable, GSM 0 = in GSM, 1-4 and 6 = stages) and confirm the long- and short-term ASM codes.
4. Ask legal whether showing these indicators in a commercial app is allowed without an NSE data licence, as part of the roadmap I07 data-licence decision.
5. Record the result, the URL template and the confirmed codes in the build tracker.
If NSE returns 401/403 or legal says no, do not build ai-surveillance-data, keep FEATURE_RISK_FLAGS_SURVEILLANCE=false, and decide on a licensed data vendor (FIX:REG-10). Never disguise the client.
- After ai-surveillance-data is deployed: set SURVEILLANCE_REG_IND_URL if it differs from the default (keep {ddmmyy} in place of the date), set FEATURE_RISK_FLAGS_SURVEILLANCE=true and restart. Then run once on the server: cd backend && python -c "from services import surveillance_service as s; print(s.refresh_snapshot(), (s.get_snapshot() or {}).get('as_of'))". Spot-check two symbols against NSE's surveillance page. The scheduler refreshes the file every 6 hours after that.
- Set BOT_CONTACT_URL (introduced by FIX:REG-10) to a real contact page or email, so the NiveshBot User-Agent identifies the operator to NSE.
- Have legal review the fixed copy before release:
- the Copilot refusal text and the two captions ('Computed from your Nivesh holdings. Not investment advice.' and 'AI-generated. Not investment advice.');
- the allowance and quota messages;
- the risk-flag texts and their 20% and 40% thresholds, plus the GSM/ASM texts if the spike passes.
- Confirm the per-tier daily AI budgets from FIX:LLM-02 (defaults: $0.25 free, $1 pro and $3 super_pro per user per day; $25 global). The allowance line shows usage as a percentage of these caps, and only once a user reaches 80%.
- Update the AI-processor privacy disclosure written for FIX:FINSEC-04: holdings are not sent by Copilot's portfolio answer, which is computed on Nivesh's server; free-text chat still is (your messages and Copilot's AI replies go to DeepSeek or Anthropic).
- Before switching the DeepSeek model (FIX:LLM-25) or editing the rf-1 prompt, run the offline prose eval in docs/research/RUNBOOK.md section 10.
- Freeze 20 payloads, then run the baseline and the candidate with --yes.
- Each run makes up to --max-calls paid DeepSeek calls (about $0.05 for 60 calls at the engine spec's estimate; verify current pricing), recorded in llm_usage.
- Adopt only if validated_rate is at least 0.90 and no more than 2 points below the baseline, and 20 rendered samples pass your review.
- Keep the public track record (roadmap I21) off until every precondition in docs/research/COMPLIANCE.md section 12 is met: SEBI RA registration with the legal RA_DISCLAIMER_TEXT change, the engine's G7 live gate, PaRRVA verification of the displayed metric (confirm current rules with counsel), and a legal-approved display sentence in code. Only then set RESEARCH_TRACK_RECORD_PUBLIC=true. Never use these figures in marketing, share cards, push notifications or App Store copy.
- Nothing to set up in App Store Connect, APNs or entitlements for this cluster, and no new data types to declare in the privacy manifest. Every new surface uses data the account already has.
