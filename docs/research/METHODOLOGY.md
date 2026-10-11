# Research Engine v1: methodology

This document describes how the Research Engine (engine version `re-1.0.0+fv1`, procedure `rg-lgbm-v1`) computes every number in a stock report. It is derived from the approved implementation spec (revision 2). Every constant named here is frozen in `ml-engine/research/config.py`, and `config_sha256()` of those constants goes into every model manifest. Changing a constant after out-of-sample results have been seen makes a new trial or a new procedure version (section 9.1).

Companion documents: [COMPLIANCE.md](COMPLIANCE.md) (what may be shown and said) and [RUNBOOK.md](RUNBOOK.md) (how to operate it).

## Contents

1. Principles
2. Data and entity linking
3. Price basis, corporate actions and quality
4. Universe `NSE_LIQ200`
5. Labels
6. Features fv1 and the factor profile
7. Model, baselines and calibration
8. Descriptive analytics: historical return ranges, risk, fundamentals
9. Validation: dates, purge, lockbox
10. Metrics: HAC, t\*, DSR, PBO
11. Cost model and portfolio test
12. Gates and tiers
13. Live ledger, G7 and the kill-switch
14. Power and expected outcome
15. Residual biases
16. Limitations
17. Product decisions (IOSUI-08)

---

## 1. Principles

- **Code computes, the LLM phrases.** Every displayed number is a typed `Fact` (`value, unit, display, status, source, as_of, method`) computed by versioned ml-engine code from a hashed data snapshot. DeepSeek only writes placeholders such as `{{risk.vol_ewma_ann_pct}}`; a deterministic validator (`gv-1`) checks every sentence and a fixed template is used when the check fails.
- **Missing data is explicit.** A fact that cannot be computed has `status: "unavailable"` and a reason code; NaN is never zero-filled.
- **No stock-level call.** No rating, signal, target, upside, stop or entry level, no imperative text. The only output about the future is an evidence tier per horizon, chosen by code from pre-declared gates and shown as fixed text.
- **Point in time.** Every computation at date t uses only data available at t.
- **Horizons.** h ∈ {21, 63} trading sessions. Nothing shorter, no intraday, no F&O.

## 2. Data and entity linking

### 2.1 Sources (all free)

| Data | Source | Use |
|---|---|---|
| Daily OHLCV, prev close, turnover, trades, ISIN for every EQ symbol | NSE CM bhavcopy: legacy format to 2024-07-05, UDiFF from 2024-07-08 | All prices, the session calendar, the universe |
| Dividends and splits | yfinance `Ticker.actions` (weekly, at most 100 symbols a night) | Classifying corporate-action events only |
| Raw daily bars | yfinance `history(auto_adjust=False)` | Fallback rows and the bad-tick cross-check only |
| Nifty 50 price index | yfinance `^NSEI` (`NIFTY50_PR`) | Benchmark, beta, holiday check |
| Fundamentals | yfinance `.info` plus statements | Display only, `point_in_time: false` |
| Symbol changes | NSE symbolchange file | Optional cross-check of linking |
| Dev mode | `RESEARCH_LOCAL_CSV` (49 symbols) | Code testing only; always `survivorship_biased` |

Not used in v1: risk-free rate, ASM/GSM, shareholding, pledge, FII/DII, total-return indices.

Both bhavcopy formats are parsed into the common columns `date, symbol, series, isin, open, high, low, close, prev_close, volume, turnover_inr, trades`, keeping `series == "EQ"`. A missing column raises `BhavcopySchemaError` and fails the run closed. Raw zips are immutable and their sha256 is appended to `raw/MANIFEST.jsonl`.

### 2.2 Entity linking (D33)

The stable key is `entity_id` = "E" + the first ISIN seen for the entity (dev mode: the symbol). Keying by ISIN alone would treat every face-value split as a delisting, because NSE issues a new ISIN for splits and consolidations while the symbol stays. Keying by symbol alone would break on renames, where the ISIN stays.

Linking runs per session in date order, looking back over the previous 5 sessions:

1. A known (ISIN, symbol) pair maps to its entity.
2. A new ISIN whose symbol was held by entity E maps to E (`isin_change`: face-value split or consolidation).
3. A new symbol whose ISIN was held by E maps to E (`symbol_change`: rename).
4. Otherwise a new entity starts (`new_listing`).

If both the ISIN and the symbol change on the same day, a new entity starts; the OPS continuity check lists such cases. Episodes persist in `curated/entities.parquet` (`entity_id, isin, symbol, valid_from, valid_to, link_reason`). Linking uses only past sessions.

## 3. Price basis, corporate actions and quality

### 3.1 `px_idx` (D35)

All labels, features, risk figures, historical ranges and display returns use one price basis: `px_idx`, a forward-chained, split- and bonus-adjusted price index.

- `px_idx` = 1.0 on the entity's first valid row and uses only data up to t, so it is truncation-safe (deleting later rows never changes earlier values).
- It is NaN on non-traded days (zero volume) and on suspect days.
- **Dividends are excluded everywhere in v1.** Dividend data exists only for surviving companies, so adding it would bias returns towards survivors. Every return label in the product says "price return (dividends excluded)".
- A display close back-adjusted to date T is `close_T · px_idx_s / px_idx_T` (used for example for the 52-week high and low).

### 3.2 PREVCLOSE factor (D34)

For each row, the adjustment factor is f_t = prev_close_t / close_p, where p is the entity's previous valid row. A row in `research/ref/adjustment_overrides.csv` (`isin, ex_date, factor, note`) takes precedence.

- An event is recorded when |f_t − 1| > 0.5%.
- **The factor is always applied:** px_idx_t = px_idx_p · close_t / (close_p · f_t), with f = 1 on non-event days.
- yfinance fallback rows have no PREVCLOSE and therefore no factor, except that a yfinance split dated that day is applied.

Real crashes, demergers and rights issues produce genuine PREVCLOSE adjustments, so they are not treated as errors.

### 3.3 Event classification (quality note only; never changes `px_idx`)

| Class | Rule |
|---|---|
| `split` | A yfinance split on the ex-date with 1/f matching within 2% |
| `override` | An override row exists |
| `dividend` | A yfinance dividend D on that date with \|(1 − f) − D/close_p\| < 0.2% |
| `ca_unverified` | None of the above. A note for OPS review (admin status and `store events`), **not** a suspect flag |

### 3.4 Quality checks (every run)

- OHLC ordering, positive prices, unique (date, entity_id).
- **Zero volume** means not traded: the return is NaN and `px_idx` skips the day.
- **Bad tick (`suspect`).** A candidate is a day with abs(adjusted daily return) > 25%. It is suspect only if either:
  1. the yfinance raw close for that date exists and differs from the bhavcopy close by more than 2%, or
  2. the log move reverses by 80% or more within the next 3 sessions with no corporate-action event. This rule is applied retroactively once the reversal appears.

  A suspect close is skipped by `px_idx`, so both adjacent returns are NaN; a label starting that day is NaN; that day's report has outlooks and risk facts unavailable (`data_quality_flag`). Confirmed large moves are valid returns and keep their labels and universe membership. On the local 2019-2026 panel there are 7 daily moves above 25%, and none of them meets the 80%-reversal rule (largest reversal 0.58).
- **Row accounting.** Any step dropping more than 2% of expected rows fails the run (ML-06).
- **Monthly cross-check.** 5% of symbols against yfinance raw closes; a mismatch over 1% raises an alert.

### 3.5 Gap-fill and fallback rows

- Before processing market date D, the nightly run fetches every missing bhavcopy date between the last stored session and D, bounded to **15 calendar days** including weekends. A 404 means no session that day. Longer gaps need `store backfill` (see RUNBOOK).
- When D's bhavcopy is unavailable, yfinance fallback rows are used (`auto_adjust=False`, `prev_close` NaN, `source=yfinance`). Predictions made on such rows carry the reason code `prices_fallback_yfinance` and are excluded from live metrics.
- Fallback rows are replaced as soon as their bhavcopy becomes available, and the affected curated partitions and features are recomputed. A non-404 failure on an older date marks the run degraded (`gap_fill_incomplete`).

### 3.6 Sessions and holidays

The session calendar is the union of bhavcopy dates, kept complete (including special sessions such as Muhurat or Saturday sessions) by gap-fill. "h sessions later" uses that calendar. Holidays are inferred from data: at the 07:15 IST re-kick, no bhavcopy and no `^NSEI` bar for D records `skipped_holiday`. `expected_maturity_date` projects weekdays; the outcome scorer uses the true calendar.

## 4. Universe `NSE_LIQ200` (D1, D2)

A rule-based, point-in-time universe built from bhavcopy and keyed by `entity_id`. It keeps names that later delisted and needs no index-membership history, so the product can truthfully say "the 200 most-traded NSE stocks".

- **Recompute** on the last session of month m; the result applies to month m+1. Only data on or before the recompute date is used.
- **Eligibility:**
  - series EQ;
  - at least 252 sessions since the entity first appeared;
  - median raw close over the last 21 sessions ≥ ₹20;
  - volume > 0 on at least 95% of the last 126 sessions.
- **Ranking:** 126-session median `turnover_inr`.
- **Fixed-size buffer rule:** existing members ranked 240 or better are kept in rank order, up to 200; the remaining places are filled with the best-ranked non-members. This gives exactly 200 names whenever at least 200 entities are eligible. The first month takes the top 200. A member ranked 241 leaves; a member ranked 230 stays when fewer than 200 members rank above it.
- **Output:** `membership(panel, quality)` → `date, entity_id, in_universe, turnover_rank`.
- **Non-PIT data** (dev mode, local CSV): all symbols, `universe_quality = "survivorship_biased"`. Gate G0 then fails and every outlook is `no_reliable_edge` with reason `survivorship_biased_universe`. On the local 49-name panel, survivorship alone produced t > 3 for Amihud illiquidity.

## 5. Labels (D4, D5)

For entity i in the universe U_t, with px = `px_idx`:

| Label | Definition |
|---|---|
| Simple return | R_i = px_exit / px_t − 1, where px_exit is the last valid px on or before session t+h |
| `stale_exit` | True when that exit row is more than 5 sessions before t+h (delisted, suspended or untraded) |
| Log return | y_i = log(1 + R_i) |
| Excess | xs_i = y_i − median_j y_j |
| Top half | top_i = 1[R_i > median_j R_j] |
| Target | rank_i = (rank(y_i) − 0.5) / N_t − 0.5 (centred uniform percentile rank, matching RankIC) |

- A suspect day at t makes the label NaN. Live outcome scoring uses the same rule (void `suspect_price`).
- Delisting is an outcome, not a void: the label uses the last valid price and is flagged `stale_exit`.
- Labels do not depend on dividend data.
- Output: `make_labels(panel, membership, horizons=(21, 63))` indexed (date, entity_id) with `ret_h, xs_h, top_h, rank_h, label_end_h, stale_exit_h`.

The same rule (close(t) to close(t+h) on `px_idx`) is used for training, the ledger and live scoring. The portfolio test (section 11) uses daily `px_idx` between actual execution dates instead.

## 6. Features fv1 and the factor profile

### 6.1 Conventions

- r_t = log(px_t / px_{t−1}), NaN on non-traded or suspect days. m_t = equal-weight mean of r over U_t.
- A window needs at least 80% non-NaN values, otherwise the feature is NaN. NaN is never zero-filled.
- Ranking within U_t: pct = (rank − 0.5) / n, scaled to 2·pct − 1. Off-universe symbols are placed against the universe distribution.
- LightGBM handles NaN natively. Training drops rows with more than 30% of features NaN and counts them.
- Every price feature uses only `px_idx` up to t, so features are truncation-invariant.

### 6.2 The 19 features (`FEATURE_VERSION = "fv1"`)

| id | Family | Definition |
|---|---|---|
| mom_12_1, mom_6_1, mom_3_1 | momentum | log(px_{t−21} / px_{t−252 \| 126 \| 63}) |
| mom_12_1_vs | momentum | mom_12_1 / vol_252 |
| dist_52wh | momentum | px_t / max(px_{t−251..t}) − 1 |
| rev_5, rev_21 | reversal | −log(px_t / px_{t−5 \| 21}) |
| vol_21, vol_63, vol_252 | risk | std(r) · √252 |
| beta_252 | risk | Dimson b0 + b1 on [m_t, m_{t−1}] |
| idio_vol_63 | risk | std(residuals of r on m) · √252 |
| max_ret_21 | risk | max r over 21 sessions |
| downside_vol_63 | risk | sqrt(mean(min(r, 0)²)) · √252 |
| log_adv_63 | liquidity | log(median turnover_inr over 63 sessions) |
| amihud_63 | liquidity | log(1e9 · mean(abs(R_daily) / turnover_inr) over 63 sessions) |
| turnover_ratio_21_126 | liquidity | median(turnover, 21) / median(turnover, 126) − 1 |
| ma50_ma200 | trend | SMA50(px) / SMA200(px) − 1 |
| rsi_14 | trend | Wilder RSI(14) on px; None below 15 observations; 100 with no losses (MATH-23) |

### 6.3 Display orientation and the factor profile

Model features are used as defined above. For display only, `DISPLAY_ORIENTATION` is +1 for every feature except `amihud_63`, `rev_5` and `rev_21`, which are −1. This makes every displayed percentile follow the plain-language label: "higher" always means the direction named in the family label.

| Family | Members | Label |
|---|---|---|
| momentum | mom_12_1, mom_6_1, mom_3_1, mom_12_1_vs, dist_52wh | Momentum (higher = rose more over the past 3 to 12 months) |
| reversal | rev_5, rev_21 | Recent short-term move (higher = rose more) |
| risk | vol_21, vol_63, vol_252, beta_252, idio_vol_63, max_ret_21, downside_vol_63 | Risk (higher = more volatile) |
| liquidity | log_adv_63, amihud_63, turnover_ratio_21_126 | Liquidity (higher = easier to trade) |
| trend | ma50_ma200, rsi_14 | Trend (higher = stronger recent uptrend) |

- **Metric percentile** = universe percentile of `DISPLAY_ORIENTATION[f] × raw`.
- **Family percentile** = universe percentile of the mean of the oriented member percentiles.
- **Displayed values:** returns as simple % ((exp(x) − 1) × 100); reversal metrics as the plain 5- and 21-session return; `log_adv_63` as ₹ crore; `amihud_63` as "Average price move per ₹100 crore traded" (%, 2 decimals); RSI with 0 decimals.

No sentiment, drivers or SHAP in v1. Any future attribution must be exact TreeSHAP, shown for validated horizons only (ML-20).

## 7. Model, baselines and calibration

### 7.1 Procedure `rg-lgbm-v1` (D6, D8)

- LightGBM 4.6, L2 regression on `rank_h`.
- Parameters: `num_leaves` 15, `max_depth` 4, `learning_rate` 0.03, `min_data_in_leaf` 500, `feature_fraction` 0.7, `bagging_fraction` 0.7, `bagging_freq` 1, `lambda_l2` 10, `max_bin` 63, `deterministic` true, `force_row_wise` true, `num_threads` 3, `verbose` −1.
- Five date-offset seeds {11, 23, 37, 51, 73}: seed k trains on sessions with `session_index % 5 == k`.
- Early stopping on inner-validation L2: patience 100, at most 1500 rounds; then a refit on the full purged window at the best iteration.
- Score = mean over seeds. `rank_pct` = percentile within U_t. `bucket` = min(5, floor(5·rank_pct) + 1).

One configuration is pre-declared, which keeps the trial count low.

### 7.2 Baselines (identical folds; G0 checks the fold hashes)

| ID | Baseline |
|---|---|
| B0 | Random (seeded) |
| B1 | Constant p = training base rate (probability metrics only) |
| B2 | Always top half (probability metrics only) |
| B3 | 20-day momentum |
| B4 | 12-1 momentum |
| B5 | Low volatility (−vol_252) |
| B6 | rev_21 |
| B7 | Equal-weight mean of the ranks of B4, B5 and B6 |
| B8 | Ridge on the 19 ranked features (NaN → 0 for ridge only), α ∈ {1, 10, 100} chosen on inner validation |

### 7.3 Trial ledger

- A trial is a unique (procedure_id, horizon, scorer_id, config_sha256, data_sha256) from a `source=store` run. Repeats deduplicate on that key.
- `TRIALS.jsonl` rows: `trial_id, procedure_id, horizon, scorer_id, config_sha256, git_sha, data_sha256, created_at, metrics, monthly_net_active`.
- `--fast`, `--null-calibration` and `local_csv` runs go to `TRIALS_DEV.jsonl` and never count.
- N for the DSR = distinct trials for that horizon, at least 7.

### 7.4 Probability calibrator (D9)

- **Fit.** For each test quarter, a 5-bucket histogram calibrator is fitted on out-of-sample predictions from the prior 36 months whose `label_end` precedes the test start. At least 24 months are required, otherwise p is unavailable.
- f_b = mean(top) per bucket; p = f_bucket.
- Bucket CIs: circular block bootstrap over dates (block 2h, 2000 replications, seed 20261010). n_b = rows in the bucket; a bucket is `neutral` when its CI covers 0.5.
- Production calibrator JSON: `{buckets: [{bucket, frequency, ci_low, ci_high, n, neutral}], period, base_rate}`.
- **The ledger always stores p.**
- **Cohort (not displayed in v1).** The contract has a `cohort` block per horizon. ml-engine emits it only when the artefact tier is `validated_edge` and gate P passed; the backend serves it only under an effective `cohort_frequency`, which needs `RESEARCH_SEBI_RA_REG_NO`. iOS v1 has no cohort UI, and the wording is deferred to legal review. A per-stock frequency shown by an unregistered entity would amount to a rating.

## 8. Descriptive analytics

### 8.1 Historical return ranges (D11; `risk.py`)

- For h ∈ {21, 63}: the overlapping returns R_s = px_s / px_{s−h} − 1 for every s in the last 756 sessions. At least 252 sessions of history are required, otherwise `unavailable` (`insufficient_history`).
- `low_pct` = 10th percentile and `high_pct` = 90th percentile (numpy linear interpolation), in %, never ₹.
- Fixed sentence `rr-1` (`formatting.range_text`): see COMPLIANCE.md. {period} is "the last 3 years" at 756 sessions, otherwise "the last {n} months" with n = round(window / 21).
- This is a description of the past, not a forecast. There is no conformal method, no adaptive conformal inference, no coverage figure and no gate R. Ranges are not stored in the ledger.

### 8.2 Risk (`risk.py`)

- **Volatility.** EWMA (λ = 0.94), realised 63-day and 252-day, annualised by √252, plus a universe percentile.
- **One-day VaR and CVaR** at 95% and 99%, on daily simple `px_idx` returns, expressed as negative returns, by two methods: historical over 500 days, and filtered historical simulation with EWMA volatility (FHS-EWMA).
- **Backtest** over the last 250 days, one step ahead, with Kupiec POF and Christoffersen independence tests:
  - 99% is green iff exceptions ≤ 4 and Christoffersen p ≥ 0.05;
  - 95% is green iff Kupiec p ≥ 0.05 and Christoffersen p ≥ 0.05;
  - only green methods are shown; if none is green, `var_status = backtest_failed` (D30).
- **Beta** against `^NSEI`: 252 daily price returns, Dimson b0 + b1, standard error from the OLS covariance, Blume adjustment 0.67β + 0.33. At least 200 pairs, otherwise unavailable.
- **Drawdowns** on `px_idx`: maximum over 1, 3 and 5 years; current drawdown; sessions since peak; Ulcer index over 1 year; a weekly series for 156 weeks.

### 8.3 Fundamentals (display only; `fundamentals.py`)

- Source yfinance, `point_in_time: false`, 7-day cache, at most 60 refreshes a night. `stale` when `fiscal_period_end` is more than 15 months before the as-of date. Not used by the model.
- **Financials** (banks, NBFCs, insurers) are detected by sector or industry; Altman and Beneish are then `applicable: false`.
- **Valuation:** `pe_ttm` (only if > 0), `pb`, `ev_ebitda`, `dividend_yield_pct`, `market_cap_cr`, `pe_sector_pctl` (needs at least 5 sector peers in the universe).
- **Quality:** ROE, operating margin, debt/equity, CFO/PAT.
- **Piotroski:** 9 signals, each `null` when inputs are missing; shown as "f of max_possible available checks". No grade.
- **Altman Z″-EM** = 6.56·X1 + 3.26·X2 + 6.72·X3 + 1.05·X4, and **Beneish M** (8 variables, 2 years of data), are emitted as **values only**.

#### Admin reference only: zone and flag thresholds

These thresholds are documented for administrators reading raw values. They are **never emitted** in any API response, never sent to the LLM, and never shown or paraphrased in the app (no "safe zone", "distress", "manipulator" or similar words).

| Score | Threshold | Conventional reading (admin only) |
|---|---|---|
| Altman Z″-EM | > 2.6 | Conventional "safe" zone |
| Altman Z″-EM | 1.1 to 2.6 | Conventional "grey" zone |
| Altman Z″-EM | < 1.1 | Conventional "distress" zone |
| Beneish M | > −1.78 | Conventional earnings-manipulation flag |

The research Piotroski score is availability-normalised and differs from `backend/services/piotroski.py` (absolute 7/4 thresholds), which is left to the MATH track (MATH-18).

## 9. Validation: dates, purge, lockbox

### 9.1 Pre-registration

`research/config.py` holds every constant; `config_sha256()` goes into every manifest. Any change after out-of-sample results have been seen is a new trial (counted in the DSR) or a new procedure version.

### 9.2 Dates (`config.DATES`)

| | Production | Dev (code only) |
|---|---|---|
| Data start | 2008-01-01 | 2018-01-01 |
| Training start | 2010-01-01 | 2019-01-01 |
| Initial training end (expanding window) | 2014-12-31 | 2020-12-31 |
| OOS as-of window | 2015-01-01 to 2024-06-30, 38 quarterly refits | 2021-01-01 to 2024-06-30 |
| Probability metrics from | 2017-01-01 | 2023-01-01 |
| Lockbox | 2024-07-01 to 2026-06-30 | 2024-07-01 to 2026-03-20 |
| Live | From the Stage 1 date | — |

If the bhavcopy archive is shallower than 2008, every production date shifts by the same offset while keeping at least 96 OOS months.

### 9.3 Purge, embargo and nesting (session-index arithmetic; D7)

- **Outer purge and embargo.** A training row at index i requires i + h + 21 < idx(test_start): purge h plus a 21-session embargo.
- **Lockbox boundary.** An OOS test row requires idx(label_end) ≤ idx(lockbox_start) − 21, so the last OOS as-of dates fall about h + 21 sessions before 2024-07-01 and no lockbox return enters OOS. Lockbox rows start at lockbox_start and use only labels ending on or before the data cut-off.
- **Inner validation.** The last 252 allowed sessions, with the same gap. Early stopping and ridge α are chosen only here.
- **Calibration windows.** Only predictions whose label end precedes the test start.
- **No look-ahead.** Same-date ranks; month-m membership from data before m; linking uses only past sessions.
- **`Fold.hash`** = sha256 of the index arrays, identical for the model and every baseline (checked by G0).

### 9.4 Lockbox mechanics and lockbox-spent status (D13)

- `research.train` refuses lockbox dates without `--open-lockbox --confirm-config-sha <sha>`, and refuses if `LOCKBOX_LOG.jsonl` already holds that procedure and horizon. Each opening appends `procedure_id, horizon, config_sha256, git_sha, data_sha256, opened_at, result_sha256`.
- **Lockbox spent.** The design agents saw data covering 2024-07 to 2026-06, so `rg-lgbm-v1` is treated as lockbox spent: `validation.json` always records `lockbox_spent: true`. G6 is still run once and recorded, but **the live ledger (G7) is the binding holdout**.

### 9.5 Pipeline calibration tests

- **Null calibration (OPS).** `research.train --horizon 21 --null-calibration 20` permutes identities in the label panel (1 seed, 300 rounds; written to `TRIALS_DEV.jsonl`). Pass: at most 2 of 20 permutations reach `weak_evidence` and none reaches `validated_edge`.
- **CI.** A noise panel gives `no_reliable_edge`; a planted IC ≈ 0.10 panel passes G1.

## 10. Metrics (`validation/metrics.py`)

| Metric | Definition |
|---|---|
| Daily RankIC | Spearman(score, y) over U_t; at least 40 names |
| HAC t (`hac_t`) | mean / √(LRV / T). LRV = Hansen–Hodrick (uniform kernel, lags 1..h−1); Bartlett at L = 4h when the HH value is ≤ 0. Used in G1, G2, G6, G7 and live metrics |
| t\* | min(HAC t on the daily series, median over the h offsets of the non-overlapping t) |
| ICIR | mean / sd of non-overlapping IC × √(252/h) |
| CIs | Circular block bootstrap; block 2h (daily) or 3 (monthly); 2000 replications; seed 20261010 |
| Paired baseline | HAC t on daily IC(model) − IC(best of B3-B8, chosen after the fact) |
| Hit rate | Excludes neutral buckets; reports n and n_eff = rows / h |
| Probability | Brier; Brier skill score vs the ex-ante base rate; log loss; per-year AUC with CI; ECE over 5 bins |
| DSR | See below |
| PBO | See below |
| Row accounting | Drops over 2% fail |

**Why Hansen–Hodrick.** Daily IC on overlapping h-session labels is an MA(h−1) process. In a simulation of MA(20) with unit weights (h = 21, T = 200,000), Bartlett at L = 2h recovered 0.850 of the true long-run variance and Bartlett at L = 4h recovered 0.922, while Hansen–Hodrick at lag h−1 recovered 1.015. Bartlett understates the variance and so overstates t; HH is used, with Bartlett 4h only as a fallback when HH is not positive.

**Why t\* is a minimum.** On the local panel the 21-day reversal signal had HAC t 2.39 while its non-overlapping t ranged from 0.56 to 2.70 across offsets. Taking the minimum of the HAC t and the median non-overlapping t guards against one lucky offset.

**Deflated Sharpe ratio** (Bailey and López de Prado, 2014), on **monthly** units:

- SR = mean / sd of monthly net active returns (not annualised); γ3 and γ4 = skewness and (non-excess) kurtosis of that series; T = number of months.
- N and V[SR_n] come from the monthly series in `TRIALS.jsonl`; γ_E is the Euler–Mascheroni constant.
- SR₀ = √V · ((1 − γ_E) · Φ⁻¹(1 − 1/N) + γ_E · Φ⁻¹(1 − 1/(N·e)))
- DSR = Φ((SR − SR₀) · √(T − 1) / √(1 − γ3·SR + (γ4 − 1)/4 · SR²))

**Probability of backtest overfitting** (CSCV): the T-month matrix of trial returns is cut into S = 16 contiguous blocks; all 12,870 splits are evaluated; PBO = the share of splits where the in-sample best trial's out-of-sample logit rank is ≤ 0.

Multiple testing: t ≥ 3 stays significant under Holm across the 2 horizons; trial multiplicity is handled by DSR and PBO.

## 11. Cost model and portfolio test (`validation/costs.py`, model `nse_delivery_2026_v1`)

`portfolio_returns(scores, px_idx_daily, membership, adv, h, slippage_mult)` returns a monthly frame `[gross, net, turnover, active]`.

### 11.1 Daily-path construction

- **h = 21.** Signal on the last session of each month; execute at the close of t+1; equal weight across the top quintile; hold until the next execution close.
- **h = 63.** Three tranches of one-third each; tranche k rebalances at month-ends m ≡ k (mod 3).
- **Returns and weights.** Holding returns come from daily `px_idx` between actual execution dates. Weights drift daily. Turnover = Σ|w_target − w_drifted| at each execution.
- **Delisted holdings** sit as cash at the last valid price until the next rebalance.
- **Active return** = portfolio − equal-weight U_t buy-and-hold over the same dates.

### 11.2 Costs per side on |Δw|

| Component | Rate |
|---|---|
| STT | 0.1% |
| Stamp duty (buy side) | 0.015% |
| Exchange charge | 0.00297% (configurable) |
| SEBI fee | 0.0001% |
| GST | 18% on exchange charge plus SEBI fee |
| DP charge | ₹15.93 per sell on a ₹50,000 ticket |

| One-way slippage by 63-day median ADV | bp |
|---|---|
| > ₹500 crore | 4 |
| ₹100-500 crore | 8 |
| ₹20-100 crore | 18 |
| < ₹20 crore | 40 |

- A ₹1,00,000 round trip at zero slippage costs about ₹239 (unit-tested).
- Results are reported at 1× and 2× slippage. Taxes are excluded and disclosed.
- A buffered variant (hold until below the 60th percentile) is reported for robustness only.
- Backtest returns are hypothetical, net of estimated costs, before tax. Annualised Sharpe is for admin display only.

## 12. Gates and tiers (`validation/gates.py`; ML-05, ML-07)

| Gate | Statistic | `validated_edge` | `weak_evidence` |
|---|---|---|---|
| G0 data | `universe_quality == "pit"`; drops ≤ 2%; identical fold hashes; manifest verifies | required | required |
| G1 skill | t\* on OOS daily RankIC | ≥ 3.0 | ≥ 2.0 |
| G2 baselines | Paired HAC t vs the best of B3-B8 | ≥ 2.0 | point estimate ≥ 0 |
| G3 stability | Share of OOS periods with mean IC > 0; mean IC > 0 in every volatility tercile | ≥ 0.7, every tercile > 0 | ≥ 0.6 |
| G4 economics | Net mean monthly active (1× slippage); DSR; net vs B4 | > 0, DSR ≥ 0.95, beats B4 | > 0 |
| G5 overfitting | PBO | ≤ 0.20 | ≤ 0.50 |
| G6 lockbox (one shot; spent) | Mean daily RankIC HAC t; net monthly active | t ≥ 1.65 and net > 0 | mean IC > 0 |
| G7 live (backend applies) | `live_gate_passed` (section 13) | required | — |
| P probability | BSS CI low > 0 (OOS from 2017, and lockbox); AUC CI low > 0.52 in every OOS year; lockbox ECE ≤ 0.03 with n_eff ≥ 2000 | required for `cohort` | — |

### 12.1 Artefact tier (ml-engine)

- `validated_edge` = G0 ∧ G1v ∧ … ∧ G6v.
- `weak_evidence` = not validated, and G0 ∧ G1w ∧ … ∧ G6w.
- Otherwise `no_reliable_edge`.
- Reason codes: `survivorship_biased_universe`, `gate_failed:Gx`.

### 12.2 Served tier (backend `serve.py`)

1. An expired snapshot (3 or more sessions old) → `unavailable` (`snapshot_expired`).
2. A horizon `under_review` (kill-switch) → `no_reliable_edge` (`live_under_review`).
3. **Unregistered cap (D37).** An artefact `validated_edge` is served as `weak_evidence` unless G7 passed **and** `RESEARCH_SEBI_RA_REG_NO` is effective. Reasons: `live_shadow_collecting` (G7 not yet passed) and/or `policy_hidden` (no effective registration number).

Symbols outside the universe get `out_of_universe`. ml-engine already marks a horizon `unavailable` when the stock's own close is suspect (`data_quality_flag`), its history is too short (`insufficient_history`) or the active artefact fails verification (`manifest_invalid`). Because v1 ships with `RA_DISCLAIMER_TEXT = None`, no registration number can be effective, so in v1 the highest served tier is `weak_evidence`.

At 63 sessions gate P cannot pass (lockbox n_eff ≈ 1,590 < 2,000), and G7 needs about 3 years of live data.

### 12.3 validation.json (admin only)

`validation.json` holds the full gate record (`gates [{id, level, passed, value, threshold}]`, `tier`, `probability_display_passed`), the RankIC block, baselines, hit rate, portfolio (including the cost model and 2× slippage), probability metrics, overfitting (`n_trials`, `pbo`), the lockbox result with `lockbox_spent: true`, and slices (calendar year, volatility tercile, Nifty 63-day sign, ADV half, period halves, COVID 2020-02 to 2020-06). The renderer `validation/report.py` prints PASSED only when `passed` is true, writes no verdict prose, emits no literal "\n" and fails if a stress window is absent (ML-25, GH-626, GH-697). Gate results never reach the user UI.

## 13. Live ledger, G7 and the kill-switch

- **Ledger.** Nightly ingest writes exactly one prediction per (report, horizon) for every in-universe, artefact-verified, quality-ok symbol, whatever its tier. `entry_close` is the raw close from the same snapshot. Prediction columns are never updated; outcome columns are written once through `write_outcome_once`.
- **Outcome scoring** uses the label rule of section 5: `realized_return_pct` = 100 · (px_exit / px_t − 1), `stale_exit` when the exit row is more than 5 sessions old, `realized_excess_pp` vs the U_t median, `realized_top_half`, `nifty50_return_pct`. A row is void only for `entry_price_mismatch` (|entry_close − stored raw close| / entry_close > 0.0001) or `suspect_price`. It stays pending until h true sessions have passed.
- **Live metrics** are computed per procedure and horizon on matured rows only, excluding `prices_fallback_yfinance` rows. `independent_periods` = floor(matured_dates / h); the state is `collecting` below 12. ECE is reported only when n_eff ≥ 500.
- **G7 (`live_gate_passed`)** requires all of: independent_periods ≥ 12 (about 13 months at 21d, about 3 years at 63d); live mean RankIC HAC t ≥ 1.65; live mean IC ≥ 0.5 × the OOS mean IC (`validation.json` `rank_ic.mean`); no A1 alarm.
- **Kill-switch A1 only (D28).** A rolling 12-month mean IC < 0 at 6 consecutive month-ends sets `under_review`, evaluated only once independent_periods ≥ 12. Reinstatement only through a new procedure version promoted by hand.
- **Admin warnings** (no status change): `calibrator_drift` (a live bucket frequency outside its stored CI for 3 consecutive months, for buckets with at least 100 matured rows in the month) and `psi_warning` (score PSI > 0.25).
- Deleted from the design: CUSUM A2, class-balance A3 and coverage A4. If a validated horizon is ever served, add a CUSUM with k = μ₀/2 and a simulated in-control ARL of about 120 months.

## 14. Power and expected outcome

- Monthly IC standard deviation on the local panel is 0.21-0.25. The minimum detectable mean IC at t ≥ 3 is 0.032-0.051 at 21 sessions (114 months) and 0.056-0.088 at 63 sessions (38 quarters). Good cross-sectional models reach 0.02-0.06.
- An IC of 0.05 corresponds to AUC ≈ 0.523 and a Brier skill score ≈ 0.002, so probability gates are hard to pass.
- A leak-free re-estimate on the local panel gave purged AUC 0.493-0.524 and per-year t ≤ 1.38.
- Local daily RankIC evidence (49 names, 2019-2026, survivorship-biased): 21-day reversal +0.037 (NW t 2.39), 12-1 momentum +0.007 (0.36), low volatility −0.047 (−2.29), Amihud illiquidity +0.062 (4.03, a survivorship artefact).
- **Expected v1 outcome:** `no_reliable_edge` at 63 sessions; `weak_evidence` or `no_reliable_edge` at 21 sessions. The product is honest descriptive analytics; outlooks will usually read "no reliable edge".

## 15. Residual biases

- **Fundamentals are not point-in-time.** yfinance returns current statements; they are display only and never enter the model.
- **Dividends excluded.** Returns understate total return for high-yield stocks, consistently across training, ledger and display.
- **Corporate-action classification depends on yfinance**, which covers survivors better. This affects only the `ca_unverified` quality note, never `px_idx`.
- **Lockbox contamination.** The design saw 2024-07 to 2026-06 data, so the lockbox is spent and G7 is binding.
- **Universe at month granularity.** Eligibility is recomputed monthly; a stock that becomes illiquid mid-month stays in the universe until the next recompute.
- **Survivorship in dev data.** `RESEARCH_LOCAL_CSV` contains only current Nifty 50 names and always forces `no_reliable_edge`.
- **Validator blind spots.** The grounding validator cannot detect mis-attribution within a section (a correct placeholder in a misleading sentence). Mitigations: section prefixes, label masking, a weekly audit of 50 samples.
- **Unverified inputs** until the first live backfill: UDiFF column names, the ISINs of the face-value splits used for continuity checks, NSE PREVCLOSE treatment of large dividends.

## 16. Limitations

- No horizon under 21 sessions, no intraday, no F&O.
- No PIT fundamentals in the model, no sentiment, no news, no drivers or SHAP.
- English only (D20).
- No forward return ranges, no cohort UI, no user-facing performance, accuracy, coverage or track-record figures, no per-gate results.
- Statistical power is low: about 13 months of live data at 21 sessions and about 3 years at 63 sessions are needed before G7 can pass.
- Backtests are hypothetical, net of estimated costs, before tax, and not achievable returns.
- Home-server operation: outages show as stale reports (fresh 0, stale 1-2, expired 3 or more weekday sessions).
- Old `analysis_history` and `analysis_predictions` rows are not evidence for this engine.

## 17. Product decisions

### IOSUI-08: Forecast and MC Insights tabs stay hidden

IOSUI-08 found that `StockProfileView.swift` mounts four tabs (Forecast at case 2, MC Insights at case 3, Peers at case 5, Corporate at case 10) as permanent "unavailable" stubs, while finished but orphaned views exist elsewhere.

**Decision:** the **Forecast** (analyst forecasts and price projections) and **MC Insights** (Monte Carlo price paths) tabs stay hidden and are not populated by the Research Engine or any other source in v1.

Reasons:

- Both would show forward-looking, stock-level price figures. That conflicts with the v1 non-goals (no targets, no forward return ranges, no forecasts; REG-02, REG-11) and with D11, which replaced forward ranges with a descriptive historical range.
- The only forward-looking output of v1 is the evidence tier, shown as fixed text in the stock report's "What testing found" cards.
- The `out_of_universe` and `no_reliable_edge` texts already tell users that no stock-level estimate is shown; a Forecast tab would contradict them.

Consequences: the iOS tracks must not mount any forecast, price-projection or Monte Carlo view in these tabs. They may remove the two tabs entirely; if kept, they show no figures. The other two stub tabs (Peers, Corporate) are outside this decision and stay with the iOS UI track. Reopening this decision requires SEBI RA registration, legal review and a validated horizon that passed G7.
