# Nivesh Analysis Engine v2 — Design Spec

> Date: 2026-06-12 · Status: Approved (brainstorming) · Scope: Backend (Phase 1). iOS observability is Phase 2 (separate spec, built against the frozen job API).

## 1. Problem

The "extreme" AI analysis runs for 15–20 minutes, burning DeepSeek + Claude credits, and the user cannot tell whether it is running, cannot navigate the app while it runs, and cannot stop it.

### Confirmed root causes
1. **Runaway config.** `build_ta_config("extreme")` (`backend/services/orchestrator.py:401`) sets `deepseek-reasoner` (a slow chain-of-thought model) on **every** agent node (governance, market, news, fundamentals, bull, bear, trader, 3 risk debators), with `max_debate_rounds=3`, `max_risk_discuss_rounds=2`, `max_tokens=16000`, and no wall-clock or token kill-switch. ~20+ reasoner calls × 30–90 s ≈ 15–20 min.
2. **Token inflation.** `llm_utils.deepseek_chat:73` computes `effective_max = max_tokens × 8` for the reasoner → up to 128K requested tokens per call.
3. **Connection-tied lifetime.** `POST /analyze` (`routers/analysis.py:474`) runs the analysis *inside the request*, polling `request.is_disconnected()` and calling `p.terminate()` when the client drops (`:537-551`). Navigating away or backgrounding the app **kills the run**. Progress lives in a racy module-level dict keyed by ticker.

## 2. Goals / Non-Goals

**Goals (Phase 1, backend):**
- Extreme run is bounded: **≤ 600 s wall-clock hard cap + token-budget kill-switch**, depth-first.
- Analysis is a **server-side background job** decoupled from the HTTP connection; survives navigation/backgrounding/app-close.
- **One running job per user**; user can **cancel** to stop credit spend immediately.
- **DB-backed job state** is the single source of truth; crash → job marked `FAILED`, re-runnable.
- **Per-agent checkpoints** (1 line each) + progress % streamed via a poll endpoint.
- **Extreme output is materially richer than normal**: superset schema with longer narrative + four graph-ready data bundles.

**Non-Goals (Phase 1):**
- iOS UI (Phase 2).
- Analyst parallelism (Approach B) — deferred optimization.
- Auto-resume of crashed jobs (explicitly rejected; mark FAILED instead).

## 3. Architecture

### 3.1 Job model — `AnalysisJob` (new SQLAlchemy table in `database.py`)

| field | type | purpose |
|---|---|---|
| `job_id` | String(12) PK | handle the app polls |
| `user_id` | Integer FK | owner (nullable for anon) |
| `ticker`, `exchange`, `scan_type` | String | request identity |
| `status` | String | `QUEUED`→`RUNNING`→`SUCCEEDED`/`FAILED`/`CANCELLED`/`TIMEOUT` |
| `stage` | String | current checkpoint label |
| `progress_pct` | Integer | 0–100 |
| `checkpoints` | Text(JSON) | append-only `[{ts, stage, agent, message, state}]` |
| `pid` | Integer | worker PID (for registry/watchdog) |
| `heartbeat_at` | DateTime | updated each checkpoint; drives crash sweep |
| `tokens_used` | Integer | running total; drives budget kill-switch |
| `error` | Text | failure detail when FAILED/TIMEOUT |
| `result_id` | Integer FK→`analysis_history.id` | link to stored result |
| `created_at`, `started_at`, `finished_at` | DateTime | timing |

The job row is the single source of truth. The existing in-memory `_active_analyses` / `_running_analyses` dicts (`helpers.py`) become a lock-guarded cache layered on top (AGENTS.md §3.4), not authoritative.

### 3.2 Decoupled execution + supervision

- **`POST /analyze` → `202 {job_id, status:"QUEUED"}` immediately.** Enforces **one running job per user** via DB (if a `RUNNING`/`QUEUED` job exists → `409` returning the existing `job_id` so the app attaches or cancels). Replaces the current "2 concurrent" semaphore. Spawns a `multiprocessing.Process` (AGENTS.md §3.3) and returns. **No `is_disconnected` polling, no connection-tied lifetime.**
- **Worker** (`_run_analysis_worker` refactored): re-imports deps + `load_dotenv(override=True)` inside subprocess; writes `RUNNING`/heartbeat/checkpoints/result directly to DB via `get_session()`. The `multiprocessing.Queue` round-trip is removed.
- **Self-contained kill-switches inside the worker** (robust to a parent restart):
  - **Wall-clock watchdog thread** → hard-terminate at **600 s** → status `TIMEOUT`.
  - **Token-budget guard** → abort when `tokens_used` exceeds the extreme ceiling (**default 400,000 total tokens** across the run — a runaway tripwire well above a normal extreme completion; tunable) → status `TIMEOUT`.
  - **Cancel check** → between stages, if `job.status == CANCELLED`, exit cleanly.
- **Registry + immediate cancel.** Module-level `_job_registry: dict[job_id, Process]` under a `threading.Lock`. `POST /analyze/{job_id}/cancel` sets DB status `CANCELLED` and `p.terminate()`s the local process (instant credit savings).
- **Crash recovery (startup sweep).** On app boot, any job in `RUNNING`/`QUEUED` with `heartbeat_at` older than **90 s** → marked `FAILED` (honest error; user re-runs).

### 3.3 Checkpoints + per-agent transparency

`CheckpointEmitter(job_id)` is threaded into the run. Each node calls `emit(stage, agent, message, pct)` → appends to `job.checkpoints`, updates `stage`/`progress_pct`/`heartbeat_at`. The existing global `get_progress_events()` in `tradingagents-core/tradingagents/graph/setup.py` is refactored to be **job-scoped** (removes the cross-user ticker-dict race). Each event carries `state ∈ {running, ok, retry, error}` so the app shows live activity and can detect stalls via heartbeat age.

Stage → progress mapping (approx): analysts 0–50 %, debate 50–70 %, risk 70–85 %, synthesis 85–95 %, reformat 95–100 %.

Example lines:
```
50%  Bear Researcher · scanning promoter pledging, FII/DII flows & governance flags
70%  Research Manager · weighing bear case (1.5×) vs bull case
85%  Portfolio Manager · forming position sizing & risk-adjusted call
```

### 3.4 Engine retune (Approach A — the runaway fix)

`build_ta_config("extreme")` (`orchestrator.py:401`):

| param | before | after |
|---|---|---|
| `quick_think_llm` | `deepseek-reasoner` | `deepseek-reasoner` (kept — depth-first) |
| `max_debate_rounds` | 3 | **2** |
| `max_risk_discuss_rounds` | 2 | **1** |
| `max_tokens` | 16000 | **8000** |
| analyst tool-loop cap | none | **≤ 3 iterations** |
| LangGraph `recursion_limit` | default | **explicit bound** |

`llm_utils.deepseek_chat:73`: replace `effective_max = max_tokens × 8` with a sane reasoning headroom, e.g. `min(max_tokens + 8000, 16000)`.

**Untouched (AGENTS.md compliance):** Dialectical Asymmetry §4.2 (Bear 1.5× weight, longer Bear prompt, asymmetric rounds preserved by keeping debate ≥ risk), `INDIAN_MARKET_SYSTEM_PROMPT` §4.3 (never shortened), Smart Cache Gate §4.1 (`compute_staleness` still gates runs), model tiers §4.4.

### 3.5 Extreme output — superset schema (the "way better than normal" requirement)

Extreme returns **all normal fields (20+, per §5.2)** plus extreme-only blocks. Additive only: normal analysis leaves them empty, so `_normalize_response` for normal is unchanged; an extended normalizer guarantees the extreme blocks **only when `scan_type == "extreme"`**.

**Split of responsibility (robustness + token cost):**
- **Deterministic, computed in Python** (real numbers for charts, near-zero extra tokens), attached post-analysis like the existing `_inject_live_data` / `_inject_piotroski`:
  - `factor_scores` — value/quality/momentum/growth/low_volatility (0–100) from `services/factor_engine.py`.
  - `piotroski` — `{f_score, max_possible, grade, checks{...}}` from `services/piotroski.py`.
  - `financial_trends` — `{years[], revenue_cr[], net_profit_cr[], operating_margin_pct[], operating_cashflow_cr[]}` from `nse_data_provider` / balance-sheet/income/cashflow.
  - `ownership_trends` — `{quarters[], promoter_pct[], promoter_pledged_pct[], fii_pct[], dii_pct[]}` (best-effort; omit series with no data).
  - `peer_comparison` — `[{ticker, name, pe, roe_pct, rev_growth_pct, debt_to_equity, marketcap_cr}]` (self + sector peers; best-effort).
- **LLM-generated** via an **extreme prompt addendum** (added on top of the base system prompt, never replacing it — §4.3), in the synthesis/reformat step:
  - `scenarios` — `{bull, base, bear}` each `{price_3m, price_12m, price_36m, probability_pct, narrative}`.
  - `valuation_bands` — `{current_price, fair_value, bull_value, bear_value, method, pe_band{low,mid,high}}`.
  - `extended_thesis` — `{bull_deep_dive, bear_deep_dive, management_quality, competitive_moat, sector_positioning}` (long text blocks → "way longer answers").
  - `niche_insights` — array of non-obvious, useful findings.
  - `governance_flags` — `[{flag, severity, detail}]` (auditor/CFO/MD changes, related-party, contingent liabilities), built from the governance forensics report already produced by `run_trading_agents`.
- `analysis_tier: "extreme"` marker so the client knows to render the extra sections/graphs.

**Longer answers:** raise the extreme reformat/synthesis token budget (Haiku synthesis + Sonnet reformat ~4000 → ~8000). One-shot calls, so within the 600 s budget.

All numbers obey AGENTS.md §5 (Lakhs/Crores, `_ban_western_scale`); all text passes `stripEmoji` (§5.3) and `_normalize_response` → `_ban_western_scale` (§5.2).

### 3.6 API surface

| endpoint | role |
|---|---|
| `POST /analyze` | start job → `202 {job_id}` (one-per-user guard, `409` with existing job) |
| `GET /analyze/job/{job_id}` | poll: `{status, stage, progress_pct, checkpoints[], tokens_used, result?}` |
| `GET /analyze/active?user_id=` | the user's current running job (app launch / global indicator) |
| `POST /analyze/{job_id}/cancel` | set `CANCELLED` + terminate worker |
| `GET /api/v1/dashboard/stream` | existing SSE, now reads job rows (live dashboard, optional) |

App polls `GET /analyze/job/{job_id}` every ~2 s. **Polling is the reliable backbone**; SSE stays as an optional live channel so backgrounding never breaks observability.

## 4. Error handling

- Worker wraps each stage; on exception records a checkpoint with `state:"error"` and continues to the existing DeepSeek fallback reformat path (`reformat_with_claude` → DeepSeek fallback) before marking `FAILED` with `error` detail.
- Cache-eviction / API-unavailable errors keep the existing retry/backoff (`reformat_with_claude:531-589`, `deepseek_chat` 3× backoff).
- All client-facing failures reuse `_build_analysis_error` shape so the app's existing error UI keeps working; the job row mirrors `error`.

## 5. Testing strategy

- Unit: `AnalysisJob` lifecycle (create→running→succeeded/failed/cancelled/timeout); one-per-user guard; crash sweep marks stale RUNNING→FAILED; cancel sets status + terminates.
- Unit: `build_ta_config("extreme")` returns bounded values; `deepseek_chat` effective_max is capped.
- Unit: extreme normalizer guarantees the 4 graph bundles + narrative fields when `scan_type=extreme`, and leaves normal untouched.
- Unit: deterministic enrichers (`factor_scores`, `piotroski`, `financial_trends`, `ownership_trends`, `peer_comparison`) degrade gracefully when source data missing (omit, don't crash).
- Integration: `POST /analyze` returns `202` fast and does **not** block on the worker; `GET /analyze/job` reflects progress; disconnecting the client does **not** kill the job.
- Budget: a synthetic long-running stage trips the 600 s watchdog → `TIMEOUT` (no real LLM credits in test).

## 6. AGENTS.md compliance checklist

- §3.1 Controller/Service/Repository: job orchestration logic lives in a **service** (e.g. `services/job_manager.py`); routers only validate + spawn + read.
- §3.2 DB via `get_session()`; no session crosses the process boundary (worker opens its own).
- §3.3 multiprocessing with re-import + `load_dotenv(override=True)`; terminate on cancel/timeout.
- §3.4 module-level `_job_registry` guarded by `threading.Lock`.
- §4.1–4.4 Smart Cache Gate, Dialectical Asymmetry, Prompt Integrity, model tiers all preserved.
- §5 Indian numbering + normalization + emoji stripping on all new output.
- §6 Commit per phase; run `gitnexus_impact` before editing each symbol and `gitnexus_detect_changes` before each commit; **no `xcodebuild`** (§6.2).

## 7. Phase boundary

**Phase 1 (this spec):** §3.1–3.6, §4, backend only. Ships + verified independently. Freezes the job API.

**Phase 2 (separate spec, later):** iOS — `AnalysisEngineManager` (`@Observable`, `@Environment`), global running pill/banner on every screen, Engine Activity screen (live checkpoints + cancel), browse StockProfile/charts while running, local notification on completion/failure, and Banknote-compliant charts for the four extreme graph bundles.
