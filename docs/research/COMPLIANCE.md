# Research Engine v1: compliance

This document fixes what the stock report may show and say, who may see it, and which texts are frozen. It is derived from the approved implementation spec (revision 2). The fixed texts in section 3 are byte-identical to spec section 6.4, to backend `services/research/templates.py` and to the fixtures in `docs/research/contract/fixtures/`. Change them only together, and only after legal review.

Companion documents: [METHODOLOGY.md](METHODOLOGY.md) and [RUNBOOK.md](RUNBOOK.md).

## 1. Position

- Nivesh is **not registered** with SEBI as a research analyst (RA) or investment adviser. The engine runs in compliance mode `unregistered_educational`.
- The product is called **"Stock report"**: never "research report", "AI analysis" or "recommendation".
- No stock-level number about the future is shown (D10, REG-02). The only forward-looking output is an evidence tier per horizon, shown as fixed text chosen by code.
- No user-facing performance, accuracy, coverage or track-record figures, and no per-gate results (REG-11).
- Stock reports are free for everyone; the paywall no longer sells AI analysis.

## 2. Display policy

### 2.1 Per served tier

| Served tier | What the user sees | Stock-level number |
|---|---|---|
| `validated_edge` | `tx-2` text. Reachable only if G7 passed **and** `RESEARCH_SEBI_RA_REG_NO` is effective, which is impossible in v1 (section 6) | None in v1 (cohort has no UI) |
| `weak_evidence` | `tx-2` text | None |
| `no_reliable_edge` | `tx-2` text | None |
| `out_of_universe` | `tx-2` text, then the descriptive sections | None |
| `unavailable` | `tx-2` text (expired snapshot, data quality flag, insufficient history, manifest invalid) | None |

Every tier card also shows the server `event` string, for example "finishes in the top half of the 200 most-traded NSE stocks by price return (dividends excluded) over the next 21 trading days", and a "What we tested" link to the model-card sheet (tier text, data period, universe, limitations; never gates). Tier badges are neutral (`Theme.inkSecondary` with a `Theme.securityGold` outline), never bull or bear colours.

**Unregistered cap (D37).** The served tier is at most `weak_evidence` unless G7 passed and `RESEARCH_SEBI_RA_REG_NO` is effective. A capped horizon carries `live_shadow_collecting` and/or `policy_hidden`.

### 2.2 Per flag

| Flag | Values (default first) | Display effect | Precondition |
|---|---|---|---|
| `RESEARCH_ENGINE_MODE` | off / shadow / on | off: API 404 `RESEARCH_DISABLED`. shadow: admin-only. on: signed-in users | `ML_ENGINE_API_KEY` when not off |
| `RESEARCH_OUTLOOK_DISPLAY` | tier_only / cohort_frequency | tier_only strips every cohort and appends `policy_hidden`. cohort_frequency allows a cohort only on a served `validated_edge` horizon; iOS v1 still has no cohort UI | Effective registration number |
| `RESEARCH_TRACK_RECORD_PUBLIC` | false / true | false: `live_track_record.visible = false`, states only, never rates or IC. Live numbers only on admin `/track-record` | Effective registration number |
| `RESEARCH_SEBI_RA_REG_NO` | unset / `^INH\d{9}$` | Lifts the unregistered cap (with G7) | Section 6 |
| `RESEARCH_LEGACY_RETIRED` | false / true | true: every `/analyze*` route, `POST /batch` and `/daily-action/*` return 410 `LEGACY_GONE_TEXT`. Set at Stage 3, **never unset** | Mode on |
| `RESEARCH_LLM_PROSE` | true / false | false: template prose only | — |

Any invalid combination fails closed for research only: CRITICAL log, effective mode off, `tier_only`, track record private, reasons in `/healthz` (D36). Effective flags are stamped into the report's `compliance` block. No API changes flags.

### 2.3 What is shown as descriptive data

- Snapshot price facts with "price return (dividends excluded)" labels; 52-week high and low adjusted for splits and bonuses.
- Risk: volatility, beta ± SE, VaR/CVaR only for methods whose backtest is green ("The loss model failed its backtest for this stock" otherwise), drawdowns, and the historical return range sentence with % bars only (no ₹ levels).
- Factor profile: five neutral 0-100 bars with plain-language labels, "compared with the 200 most-traded NSE stocks".
- Fundamentals as values without judgement: "Source: Yahoo Finance, fetched {date}, not point-in-time; display only, not used in the outlook"; Piotroski as "6 of 8 available checks" (no grade); Altman Z″ and Beneish M as values only with the fundamentals caption, or "Not applicable to banks, NBFCs and insurers". Zone and flag thresholds are admin-only (METHODOLOGY.md section 8.3) and never emitted.
- The disclaimer footer (`disclaimer_text` plus `ai_disclosure`) is always shown.

## 3. Fixed texts (verbatim from spec 6.4)

### 3.1 Tier texts (`tx-2`)

- `validated_edge`: "This method met all of its pre-set statistical checks at this horizon. It is not a forecast for this stock."
- `weak_evidence`: "Testing found some evidence at this horizon, but not enough to show a stock-level estimate."
- `no_reliable_edge`: "No reliable edge at this horizon: in testing, the model did not rank stocks better than simple rules with enough confidence, so no stock-level estimate is shown. This says nothing good or bad about this stock."
- `out_of_universe`: "Outlooks are computed only for the 200 most-traded NSE stocks. The figures below are descriptive."
- `unavailable`: "The outlook is unavailable for this report."

### 3.2 Disclaimer (`disclaimer_id: research_v1`)

"Nivesh is not registered with SEBI as a research analyst or investment adviser. This stock report is general, educational information computed from public market data. It is not investment advice, a research report or a recommendation to buy, sell or hold any security, and it does not consider your finances or goals. Figures describe the past; statistical patterns can weaken or vanish. Investments in the securities market are subject to market risks. Read all related documents carefully before investing."

### 3.3 AI disclosure (`ai_disclosure`)

"An AI language model (DeepSeek) turns the computed figures into sentences. It does not compute or choose any number; an automated checker verifies every sentence, and a fixed template is shown if the check fails. Only public market data is sent to the AI provider."

### 3.4 `LEGACY_GONE_TEXT`

"Stock reports have moved. Update Nivesh to see the new stock report."

Returned as `410`, `text/plain`, with no compute, no auth and no History writes. Shipped builds display it verbatim through `NetworkError.serverError`.

### 3.5 Range sentence (`rr-1`, ml-engine `formatting.range_text`)

"Over {period}, 8 in 10 of this stock's {h}-trading-day returns fell between {low} and {high}. This is not a forecast."

{period} is "the last 3 years" at 756 sessions, otherwise "the last {n} months" with n = round(window / 21). {low} and {high} are the server `display` strings of the 10th and 90th percentile facts (%, never ₹).

### 3.6 Fundamentals caption (iOS)

"Accounting ratios from Yahoo Finance; descriptive, not a judgement on the company."

### 3.7 Registered disclaimer

`RA_DISCLAIMER_TEXT = None`. v1 has no registered-entity disclaimer, so a set `RESEARCH_SEBI_RA_REG_NO` is invalid config until legal supplies that text.

### 3.8 Other user-facing captions

- LLM prose caption: "Phrased by an AI model from the figures below; it adds no analysis."
- Template prose caption: "Generated automatically from the figures below."
- Archived legacy report banner: "Archived report from the previous engine. Its figures were not computed or validated by the current method."
- Paywall: "Stock reports are free for everyone".

## 4. LLM boundaries

- **What DeepSeek receives:** only `ok` facts from snapshot, risk, factor profile and fundamentals (id, label, unit, display, sign), percentile band phrases, the as-of date, the company name and symbol, and the allowed names [company name, symbol, "Nifty 50", "NSE", "the 200 most-traded NSE stocks"].
- **What it never receives:** outlook or cohort facts, user ids, holdings, portfolios, watchlists or headlines (FINSEC-04).
- **What it never writes:** outlooks, tier texts, disclaimers, the model card or the range sentence. These are fixed server text.
- **How it writes:** placeholders only (system prompt `rf-1`). Any leftover digit or number word fails validation (D17).
- **Validator `gv-1`:** structure, format, placeholder and section checks, literal numbers, lexicon `lx-1`, ungrounded qualifiers (need a band placeholder), direction words (need a signed placeholder with a matching sign within 6 tokens), foreign entities (other tickers and fuzzy company names), and required facts. Unvalidated text is never stored.
- **Retry and fallback:** attempt 1 at temperature 0.2, attempt 2 at temperature 0 with the failures listed, otherwise the fixed template (`tf-1`). Any exception gives the template immediately.
- **When:** nightly between 19:30 and 00:25 IST only (D19). No LLM call on any request path; on-demand reports always use templates.
- **Budget:** at most 800 calls per IST day (`RESEARCH_LLM_MAX_CALLS_PER_DAY`). A first-pass rate below 70% after 20 generations stops the LLM for the night; a 7-day template rate above 20% alerts.
- **Transport:** only `llm_utils.deepseek_chat(..., log_endpoint="research_formatter")`. No direct `OpenAI(` or `Anthropic(` clients (ARCH-03).
- English only (D20); the Language and Debate Rounds settings are removed.

## 5. Lexicon `lx-1`

Word-bounded, case-insensitive. Any match fails validation.

| Code | Words |
|---|---|
| ADVICE | buy, sell, hold, accumulate, "add to", exit, "book profit", "switch to", avoid, trim; plus obfuscation forms `b[\W_]*u[\W_]*y`, `s[\W_]*e[\W_]*l[\W_]*l`, `h[\W_]*o[\W_]*l[\W_]*d` |
| RATING | bullish, bearish, overweight, underweight, outperform, underperform, rating, rated, "top pick", "best stock", multibagger, signal, call |
| TARGET | target, "fair value", "intrinsic value", upside, downside, "stop loss", stop-loss, stoploss, entry |
| DIRECTIVE | recommend\*, advis\*, suggest\*, should, must, ought, you, your, "we think", "we believe" |
| PROMISE | guarantee\*, assured, risk-free, sure-shot, certain\*, definitely |
| FORECAST | will, shall, "going to", may, might, could, expect\*, likely, unlikely, poised, "set to", forecast\*, predict\*, projected, outlook, probability, chance, odds |
| EVIDENCE | edge, validated, significant\*, reliable, proven, accurate, accuracy, predictive, confidence, confident, "track record", model |
| CAUSAL | because, "due to", "driven by", "thanks to", "on the back of", "as a result of", "owing to", "led by" |
| REGISTRATION | SEBI, registered, regulator\* |
| HINGLISH | kharid, khareed, bech, pakka, munafa |

Also rejected: digits and number words (zero, two to twenty, thirty to ninety, hundred, thousand, lakh(s), lac, crore(s), million, billion, trillion, half, double, twice, triple, thrice, dozen, percent, "per cent"); `!`, URLs, markdown, emoji and Devanagari; ungrounded qualifiers (high, low, large, small, big, cheap, expensive, strong, weak, attractive, undervalued, overvalued, risky, safe, volatile, stable, healthy, robust, impressive, worrying, elevated, modest, substantial) without a band placeholder in the same sentence.

Fixed server texts (section 3) are not passed through the validator; they are reviewed here instead. They intentionally contain words such as "edge", "model" and "forecast" in negated or explanatory form.

## 6. `RESEARCH_SEBI_RA_REG_NO` preconditions

- Must match `^INH\d{9}$`. Any other value is invalid config.
- **Any value is invalid in v1**, because `RA_DISCLAIMER_TEXT = None`: there is no registered-entity disclaimer yet. Setting it makes research fail closed (effective mode off) with a reason in `/healthz`.
- Before it may be set, all of the following are needed: an actual SEBI RA registration; a registered-entity disclaimer text supplied by legal and added as `RA_DISCLAIMER_TEXT` in a code change; legal-approved cohort wording and an iOS cohort UI (none in v1).
- It gates: serving `validated_edge` (with G7), `cohort_frequency`, and a public track record. It never changes what the LLM receives.

## 7. iOS copy rules

- Screen name "Stock report". Never "research report" or "AI analysis".
- **Never** in any string literal under `Views/Research/`: buy, sell, hold, target, signal, call, pick, recommend, rating, bullish, bearish, accuracy, confidence, "% chance", "coverage-checked". A unit test (`ResearchCopyLexiconTests`) scans these files.
- No colour-coded verdicts. Meaning is never carried by colour alone. Colours only through `Theme.*` tokens.
- Render server `display` strings exactly as they arrive; never format, round or convert numbers on the client. Amounts in ₹, lakh and crore, never million or billion.
- Always name the reference class ("the 200 most-traded NSE stocks") and the horizon.
- AI text passes through `stripEmoji` and carries the AI or template caption.
- No cohort, dot grid or "k of 100" in v1.
- Loading states show redacted skeletons, never agent names (IOSCORE-18).
- The Forecast and MC Insights stock-profile tabs stay hidden (IOSUI-08; METHODOLOGY.md section 17).

## 8. Paywall copy

- Remove the "AI Deep Scan analysis" row and the "Deeper AI analysis" copy from `PaywallView.swift`.
- Add "Stock reports are free for everyone".
- No paid feature may be described as AI analysis, signals, recommendations or forecasts of stocks.

## 9. Data licence and honest client

- **Licence prerequisite for Stage 3.** The snapshot shows raw NSE end-of-day data (last close, 52-week high and low, turnover) inside a commercial app. That is exchange data redistribution, not "derived analytics only". Before `RESEARCH_ENGINE_MODE=on`, legal must confirm an NSE end-of-day data licence or a licensed vendor for the snapshot prices.
- **Honest User-Agent.** The bhavcopy downloader sends `NiveshResearch/1.0 (+{RESEARCH_HTTP_CONTACT})` and refuses to run without `RESEARCH_HTTP_CONTACT`. It throttles to one request per 2.5 s with jitter. If NSE blocks it, the client is never disguised (no browser User-Agent, no rotating proxies); switch to a licensed vendor instead.
- Yahoo Finance data is used for display and cross-checks only, labelled with its source and "not point-in-time".

## 10. What we never claim

- SEBI registration, advice, recommendation, rating, target, entry, exit or stop.
- That any stock will rise, fall, beat or lag. No ₹ levels or ₹ ranges.
- Accuracy, hit rate, coverage or returns of our outputs in the user UI, before RA registration and legal clearance.
- That a tier describes one stock's future.
- That past return ranges forecast future returns; they describe the past.
- "Calibrated" or "validated" unless the stored gates passed.
- Point-in-time correctness of fundamentals, or that accounting scores judge a company.
- That backtests are achievable returns; they are hypothetical, net of estimated costs, before tax.
- That the AI analysed anything.
- That old `analysis_history` or `analysis_predictions` rows are evidence for this engine.

No API field anywhere is named `signal`, `rating`, `target*`, `upside*`, `downside*`, `stop_loss`, `entry*`, `confidence*`, `zone`, `flag` or `*coverage*`; a contract test enforces this.

## 11. Open legal questions

| # | Question | Default until answered |
|---|---|---|
| 1 | Does SEBI's January 2025 clarification for education-only persons, which allows market price data of the **preceding three months**, apply to the snapshot (last close, 52-week high and low, 12-month returns, 3-year ranges)? [verify] | `tier_only`; legal to confirm before Stage 3 |
| 2 | May a stock-level frequency (cohort) be shown while unregistered? | No. `tier_only`; no cohort UI |
| 3 | RA registration path, required for cohort display and any public track record. PaRRVA (past risk and return verification) is offered only to registered IAs and RAs [verify], so a verified track record is out of scope until registered | Unresolved; live numbers admin-only |
| 4 | NSE end-of-day data licence or licensed vendor for the snapshot prices (section 9) | Stage 3 blocked until confirmed |
