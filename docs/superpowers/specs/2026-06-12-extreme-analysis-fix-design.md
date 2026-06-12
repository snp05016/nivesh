# Extreme Analysis — Fix, Full-Profile Display, Decode Test & Runner Script

**Date:** 2026-06-12
**Status:** Approved (design)
**Branch target:** `main` (commit per task, no `xcodebuild`)
**Server:** `root@165.22.221.18` (`/root/nivesh`, `nivesh` systemd service, sqlite `stockapp.db`)

---

## 1. Problem & Diagnosis

Tapping **Run Extreme Analysis** in the iOS app surfaces an error toast and the
extreme report does not generate.

Root causes, confirmed against the running server:

1. **Primary — 409 `ALREADY_RUNNING` blocks extreme.**
   `routers/analysis.py:analyze_endpoint` calls
   `database.get_active_job_for_user(user_id)` and returns HTTP 409
   (`ALREADY_RUNNING`) if the user has **any** `QUEUED`/`RUNNING` job —
   regardless of `scan_type`. So when a normal analysis is in progress (or a
   stale job is stuck active), starting an extreme job is rejected → error
   toast. This matches the requirement: extreme must generate even if a normal
   analysis is going on.

2. **Secondary — dead reformatter model.** `SONNET_MODEL =
   "claude-3-5-sonnet-latest"` returns `404 not_found_error` on every reformat
   attempt (server log), silently degrading to the DeepSeek fallback. Approved
   fix: switch to `claude-sonnet-4-6`.

3. **Already fixed (recent commits, verified):** extreme no longer returns a
   cached *standard* row. Smart-cache is skipped for `scan_type == "extreme"`
   (`orchestrator.py:1011`) and DB lookups are `scan_type`-scoped
   (`get_analysis_for_date`). The stored RELIANCE extreme row (id 14) contains
   all superset blocks: `analysis_tier`, `factor_scores`, `piotroski`,
   `financial_trends`, `extreme_thesis_md`, `scenarios`, `valuation_bands`,
   `extended_thesis`, `governance_flags`, `niche_insights`.

4. **Decode path is safe:** every iOS extreme struct uses `decodeIfPresent` with
   optional fields, so `null`/empty values (`ownership_trends: null`,
   `peer_comparison: []`) do not crash decode.

---

## 2. Deliverables

### D1 — Extreme runs even when a normal analysis is active

**Backend, `routers/analysis.py` + `database.py`:**

- Change dedup to **one active job per `(user_id, scan_type)`**. Extreme and
  standard may run concurrently; two extremes (or two standards) still dedup.
- Add `database.get_active_job_for_user_and_type(user_id, scan_type)` (scoped
  query on `status in (QUEUED, RUNNING)` AND `scan_type == scan_type`).
- `analyze_endpoint` uses the scoped lookup; the 409 payload keeps its current
  shape (`error_code`, `error_title`, `error_detail`, `job_id`, `ticker`,
  `suggested_action`) so the existing iOS error handling is unchanged.
- **Stale-job guard:** treat jobs older than their wall-clock limit
  (`extreme` 600s, `standard` 300s, from `job_worker._WALLCLOCK_LIMITS`) as not
  active, so a crashed worker never permanently blocks new runs.
- Fix `SONNET_MODEL` → `claude-sonnet-4-6` in the LLM config (`orchestrator.py`
  / config module). Update CLAUDE.md §4.4 note: the old ID is retired.

### D2 — Full StockProfile content inside the extreme result screen

**iOS, approach A (refactor into reusable view):**

- Extract the section bodies currently inside `StockProfileView`
  (overview, charts/technical, governance, macro/financials, financials table)
  into a reusable `StockProfileSections(vm: StockProfileViewModel)` view
  (new file `Views/StockProfileSections.swift`). `StockProfileView` is rewired
  to render `StockProfileSections` inside its existing TabView so its behaviour
  is byte-for-byte unchanged.
- The extreme result screen (in `AnalysisScreen.swift`) gains a TabView:
  **[Extreme AI Report]** (existing AI sections + `extremeChartSections`) plus
  the reused profile tabs **[Overview · Charts · Governance · Macro ·
  Financials]**, all driven by a `StockProfileViewModel(ticker:exchange:)` the
  extreme screen owns and loads via the existing fetch methods
  (`fetchStockProfile`, `fetchChart`, `fetchFinancials`, `fetchHolders`).
- No new endpoints; reuse `NetworkManager` calls exactly as `StockProfileView`
  does. Theme/spacing/haptic ordinance (AGENTS.md §2) preserved — reuse keeps
  existing compliant components.
- Gating: profile tabs render only for `analysisTier == "extreme"` (standard
  analyses keep their current single-scroll layout).

### D3 — Cache/decode "hit" test (no LLM credits)

**Backend, `backend/tests/test_extreme_decode_contract.py`:**

- Load a cached extreme `full_json` (fixture captured from the real RELIANCE
  extreme row, committed under `backend/tests/fixtures/`).
- Run it through `_normalize_response(result, scan_type="extreme")`.
- Assert the **iOS decode contract**: all required top-level fields present with
  correct types (`signal` enum string, `confidence_pct` int 0–100,
  `current_price_inr` float, `target_prices`/`upside_downside_pct` dicts with
  all three horizons, non-empty `bull_case`/`bear_case`/`key_risks` arrays,
  `disclaimer` string) **and** the extreme superset
  (`analysis_tier == "extreme"`, `factor_scores`, `piotroski`,
  `financial_trends`, `extreme_thesis_md`, `scenarios`, `valuation_bands`).
- A second test fetches an existing SUCCEEDED job's result via the DAO to prove
  the polling payload (`JobStatus.result`) carries the same well-formed object.
- Runs under the existing pytest suite (`backend/tests/`); no network, no LLM.

### D4 — `run_analysis.sh` (local → remote server)

- New `scripts/run_analysis.sh` (repo root `scripts/`).
- Usage: `./scripts/run_analysis.sh --ticker RELIANCE --mode extreme --user <id>
  [--exchange NSE] [--host http://165.22.221.18]`. Default host
  `http://165.22.221.18` (port 80, matching the iOS `NetworkManager.defaultURL`).
- `--mode` maps to `scan_type` + `deep_scan`: `normal`→standard, `deep`→standard
  +deep_scan, `extreme`→extreme(+deep_scan).
- `POST /analyze` → capture `job_id` → poll `GET /analyze/job/{id}?user_id=`
  every few seconds, printing `stage` / `progress_pct` / checkpoints.
- **Safe upper-limit timeout:** extreme 600s, deep/normal 300s (configurable via
  `--timeout`); on timeout, print last status and exit non-zero (does not hang).
- On `SUCCEEDED`, print `signal`, `confidence_pct`, target prices, and
  `analysis_tier`. On 409, print the `ALREADY_RUNNING` detail. Requires only
  `curl` + `python3`/`jq` for JSON parsing.

---

## 3. Out of Scope (YAGNI)

- No changes to the LLM agent graph, prompt content, or `EXTREME_ADDENDUM`.
- No new StockProfile data sources; reuse existing endpoints only.
- No `xcodebuild` / iOS compilation (reference-only project).
- No Redis (server already falls back to in-process dict).

---

## 4. Verification & Enforcement

- After each Python edit: `python3 -m py_compile <file>` (recursively fix until
  clean). Run affected `backend/tests/` subset.
- `gitnexus_detect_changes()` before each commit; scan diff for raw hex, magic
  spacing, `.system(size:)`, Western number scales, business logic in routers.
- iOS changes are inspected for AGENTS.md §2 compliance (Theme tokens, spacing
  tokens, haptics, `.banknoteCard()`, `GuillocheDivider`) but **not compiled**.
- Commit to `main` per discrete task (AGENTS.md §6.4 format).
- Server testing uses SSH with bounded timeouts; never dump `.env`.

---

## 5. Risk Notes

- `analyze_endpoint` and `get_active_job_for_user` are on the analysis hot path —
  run `gitnexus_impact` before editing; expected blast radius is the analyze
  flow + dashboard active-job panel.
- `StockProfileView` is 2426 lines; the section extraction is mechanical but
  must keep every `Theme.*`/haptic/`.banknoteCard()` usage intact. Diff-review
  the extraction carefully since it cannot be compiled here.
