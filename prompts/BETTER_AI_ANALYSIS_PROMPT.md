# Nivesh AI Engine — Full Implementation Prompt
## 3-Agent Sequential Pipeline: Planner → Builder → Code Reviewer

---

## HOW TO USE THIS PROMPT

Spawn three subagents in sequence:
1. **The Planner** reads this entire document and produces a detailed per-file implementation plan.
2. **The Builder** receives the Planner's output and implements every change, file by file.
3. **The Code Reviewer** receives the Builder's diff and validates every architectural rule.

Do NOT attempt to run all three in a single context. Divide and conquer.

---

---

# ═══════════════════════════════════════════════════════════════
# AGENT 1: THE PLANNER
# ═══════════════════════════════════════════════════════════════

## Your Identity
You are the Lead Architect for Nivesh — an Indian equity AI analysis backend. You have deep expertise in quantitative finance, LangGraph agent pipelines, and Python FastAPI. You do NOT write code in this phase. You produce a precise, file-by-file implementation plan that the Builder will follow exactly.

## Your Mission
Read the entire codebase context below, then produce a sequentially ordered implementation plan for all 15 gaps. The plan must specify: which file to create or modify, what function/class to add/change, what inputs and outputs it takes, and which other files it touches.

## Codebase Context (Read Carefully)

### Project Root: `/Users/saumya/Desktop/nivesh/backend/`

**Key Files:**
- `prompts.py` — Contains `INDIAN_MARKET_SYSTEM_PROMPT`, `NEWS_ANALYST_PERSONA`, `EXTREME_ADDENDUM`
- `services/orchestrator.py` — The 1388-line main pipeline: `analyze()`, `run_trading_agents()`, `reformat_with_deepseek()`, `reformat_with_claude()`, `_normalize_response()`
- `services/factor_engine.py` — Deterministic OHLCV → technical indicators (RSI, MACD, SMA, ATR, Bollinger, OBV, HV). Returns dict + `format_for_prompt()` string.
- `services/staleness.py` — `compute_staleness(last_analysis_date, price_change_7d_pct, signal, is_ex_dividend)` → returns `{score, urgency, reason}`
- `services/options_engine.py` — Options payoff calculator only (NOT microstructure)
- `services/options_scraper.py` — Scrapes option chain data from NSE
- `services/sector_rotation.py` — Basic sector rotation (underdeveloped, 3.8KB)
- `services/sentiment_engine.py` — Text-only sentiment (6.1KB)
- `services/nse_data_provider.py` — NSE data API wrapper (13.2KB)
- `services/scraper.py` — Web scraping utility (27.3KB)
- `database.py` — SQLAlchemy models + `get_session()` context manager
- `helpers.py` — `_resolve_ticker()`, `_yf_price()`, `_yf_fetch_info()`

**LangGraph Pipeline (orchestrator.py):**
```
START → Governance Analyst → Market Analyst → News Analyst → Fundamentals Analyst
     → Bull Researcher ↔ Bear Researcher → Research Manager
     → Trader → Aggressive/Neutral/Conservative Analyst → Portfolio Manager → END
     → reformat_with_deepseek() → _normalize_response() → _ban_western_scale()
```

**AGENTS.md Absolute Rules (Never Violate):**
1. No business logic in routers — only in `services/`
2. Every DB interaction via `get_session()` — no global sessions
3. No module-level mutable state without `threading.Lock()`
4. All monetary values in Lakhs/Crores (never Million/Billion)
5. `build_ta_config()` for LLM config overrides — NEVER modify `DEFAULT_CONFIG`
6. NEVER run `xcodebuild`
7. Bear prompt MUST be longer than Bull, weighted 1.5x in Portfolio Manager
8. Every LLM output through `_normalize_response()` → `_ban_western_scale()`

---

## The 15 Gaps to Plan (Priority Ordered)

### GAP 1 — Signal Agreement Multiplier (HIGHEST PRIORITY)
**What it does:** After all LangGraph agents complete, before calling `reformat_with_deepseek()`, extract each agent's directional vote and compute a mathematical agreement ratio that modifies `confidence_pct`.

**Formula:**
```
agreement_ratio = (votes_aligned_with_final_signal) / total_voting_agents
confidence_multiplier = 0.60 + (0.40 × agreement_ratio)
adjusted_confidence = round(raw_confidence × confidence_multiplier)
```

**Agents that vote:**
- Governance Analyst → BULLISH / NEUTRAL / BEARISH (extracted from `governance_report`)
- Market Analyst → extracted from `market_report`
- Fundamentals Analyst → extracted from `fundamentals_report`
- News Analyst → extracted from `news_report`
- Bull/Bear Researcher outputs already encoded in final decision

**Where to implement:** New function `compute_signal_agreement(agent_reports: dict) -> dict` in `services/confidence_engine.py` (NEW FILE). Called in `orchestrator.py` inside `analyze()` after `run_trading_agents()` returns and before `reformat_with_deepseek()`. The result is injected into the raw_output string as a structured block so the reformatter can use the pre-computed `agreement_ratio` and `adjusted_confidence`.

---

### GAP 2 — HMM Market Regime Detection
**What it does:** Replace the simplistic SMA-based `trend_regime` in `factor_engine.py` with a proper 3-state Hidden Markov Model trained on rolling EGARCH(1,1) conditional volatility.

**States:**
- State 0 = Stable / DII-driven (low vol, mean-reversion favored)
- State 1 = Transitional / Macro-driven
- State 2 = Crisis / Liquidity shock (high vol, fundamentals unreliable)

**Regime Multipliers for Confidence:**
- State 0 → multiplier = 1.0
- State 1 → multiplier = 0.85
- State 2 → multiplier = 0.65 (confidence collapses in crisis)

**In State 2:** The LLM prompt must be told that fundamental factors are UNRELIABLE and microstructure/options signals dominate.

**Libraries needed:** `hmmlearn` (GaussianHMM), `arch` (EGARCH). Both add to `requirements.txt`.

**Where to implement:**
- New function `detect_market_regime(close_series: pd.Series) -> dict` in `services/factor_engine.py` — returns `{state: int, state_label: str, confidence_multiplier: float, regime_description: str}`
- Called inside `compute_indicators()` and result added to the returned dict.
- `format_for_prompt()` must include the regime state and its interpretation.

**Fallback:** If `hmmlearn` is unavailable, fall back to existing `hist_vol_21_annualized` thresholds. Never crash.

---

### GAP 3 — NSE Delivery Percentage Signal
**What it does:** Fetch NSE cash market delivery percentage for the stock. High delivery (>50%) on price uptick = institutional conviction. Low delivery (<25%) on price spike = speculative froth → confidence penalty.

**Data source:** `services/nse_data_provider.py` — add a new method `get_delivery_data(symbol: str, days: int = 10) -> dict` that fetches from NSE Bhav Copy / NSE API endpoint `https://www.nseindia.com/api/quote-equity?symbol={symbol}&section=trade_info`.

**Output dict:**
```python
{
  "delivery_pct_latest": float,         # % of total volume that was delivery
  "delivery_pct_5d_avg": float,         # 5-day average delivery %
  "delivery_signal": str,               # "ACCUMULATION" | "DISTRIBUTION" | "NEUTRAL"
  "delivery_confidence_modifier": float # +0.05 to -0.10 applied to final confidence
}
```

**Signal Rules:**
- delivery_pct > 60% + price rising → ACCUMULATION → +5% confidence boost
- delivery_pct < 25% + price rising → DISTRIBUTION → -10% confidence penalty
- Otherwise → NEUTRAL → 0 modifier

**Where to inject:** Results returned from `compute_indicators()` dict extension (or called in `analyze()` directly). String representation added to `format_for_prompt()` output under a new "DELIVERY MICROSTRUCTURE" section.

---

### GAP 4 — Put-Call Ratio & Gamma Exposure (Options Microstructure)
**What it does:** Add a market microstructure layer using NSE option chain data.

**Metrics to compute:**
1. **Volume PCR** = Total Put Volume / Total Call Volume (2-3 day signal)
2. **OI PCR** = Total Put OI / Total Call OI (6-12 day signal)
3. **Gamma Exposure (GEX)** estimate = Net dealer gamma position at each strike

**PCR Interpretation:**
- Volume PCR > 1.2 → bearish retail sentiment (contrarian bullish)
- OI PCR extreme readings (>1.5 or <0.5) → reversal zone
- GEX positive (long gamma) → suppress breakouts, pin to OI strikes → reduce breakout confidence
- GEX negative (short gamma) → amplify moves → boost breakout confidence, widen error bounds

**Where to implement:** New file `services/microstructure_engine.py` with function `compute_pcr_gex(symbol: str, expiry: str = None) -> dict`. Uses existing `services/options_scraper.py` as data source.

**Output:**
```python
{
  "volume_pcr": float,
  "oi_pcr": float,
  "gex_estimate": float,            # positive = long gamma, negative = short gamma
  "dealer_regime": str,             # "LONG_GAMMA" | "SHORT_GAMMA" | "NEUTRAL"
  "pcr_signal": str,                # "BEARISH_RETAIL" | "BULLISH_RETAIL" | "NEUTRAL"
  "microstructure_confidence_modifier": float  # -0.10 to +0.08
}
```

**Inject:** Results added to `analyze()` context block injected into LLM raw_output alongside technical indicators.

---

### GAP 5 — Conformal Prediction Uncertainty Bounds
**What it does:** Instead of single-point target prices, output calibrated uncertainty intervals. For each time horizon, compute `[lower_bound, upper_bound]` at 90% coverage using historical analogues.

**Method (simplified Conformal):**
1. Collect all historical returns for this stock over matching horizons (3m, 12m, 36m)
2. Compute the 5th and 95th percentile of those returns as the conformal interval
3. Apply to current price → `target_lower = price × (1 + p5_return)`, `target_upper = price × (1 + p95_return)`

**New output fields in JSON schema (add to `prompts.py` REQUIRED JSON STRUCTURE):**
```json
"target_price_bounds": {
  "short_term_3m": {"lower": <number>, "mid": <number>, "upper": <number>, "coverage_pct": 90},
  "medium_term_12m": {"lower": <number>, "mid": <number>, "upper": <number>, "coverage_pct": 90},
  "long_term_36m": {"lower": <number>, "mid": <number>, "upper": <number>, "coverage_pct": 90}
},
"expected_return_range_pct": {
  "short_term": "<e.g. -3.2% to +14.7%>",
  "medium_term": "<e.g. -8.1% to +28.4%>",
  "long_term": "<e.g. -15.0% to +67.2%>"
}
```

**Where to implement:** New function `compute_conformal_bounds(ticker: str, current_price: float, hist_df: pd.DataFrame) -> dict` in `services/confidence_engine.py`.

**Also update:** `_normalize_response()` in `orchestrator.py` to guarantee `target_price_bounds` is populated (default to ±15%/30%/50% if computation fails).

---

### GAP 6 — Composite Investor Sentiment Index (CISI)
**What it does:** Combine multiple sentiment proxies into one scalar using PCA, replacing the simple text sentiment.

**Component proxies:**
1. `text_sentiment_score` — from existing `sentiment_engine.py` (-1.0 to +1.0)
2. `ipo_froth_score` — recent IPO first-day return average (proxy for market euphoria), scraped monthly
3. `fo_retail_skew` — ratio of retail OTM call OI vs total OI (from `microstructure_engine.py`)
4. `pe_expansion_velocity` — how fast P/E multiple has expanded vs 6-month average
5. `social_buzz_index` — mention frequency delta (from existing `sentiment_engine.py`)

**PCA reduction:** scikit-learn `PCA(n_components=1)` on all 5 normalized inputs → single CISI scalar (-100 to +100).

**CISI Interpretation:**
- CISI > 70 → Irrational Exuberance → apply confidence penalty of -10% for momentum predictions, flag Minskyan risk
- CISI < -50 → Panic/Capitulation → accumulation zone, boost mean-reversion confidence
- CISI -50 to +70 → Normal range → no modifier

**Where to implement:** Extend `services/sentiment_engine.py` with `compute_cisi(ticker: str, indicators: dict, microstructure: dict) -> dict`. Add `scikit-learn` to `requirements.txt` if not already present.

---

### GAP 7 — KNN Historical Analogue Search
**What it does:** For every prediction, search the internal `AnalysisHistory` database for the K most similar historical setups (same ticker, similar technical state + macro environment). Bootstrap the outcome distribution to produce a data-anchored win rate.

**Feature vector for similarity:**
```python
[rsi_14, price_vs_sma50_pct, hist_vol_21_annualized, momentum_score, 
 promoter_pledged_pct, delivery_pct, oi_pcr, pe_ratio_vs_historical_avg]
```

**Process:**
1. Query `AnalysisHistory` for this ticker's past analyses with outcomes (actual price vs target_3m)
2. Compute cosine similarity between current feature vector and each historical entry
3. Select top K=10 analogues
4. For each analogue, compute whether the signal was correct (actual_return vs predicted direction)
5. Output: `{k_analogues_found: int, historical_win_rate_pct: float, avg_return_pct: float, median_return_pct: float}`

**Where to implement:** New function `find_historical_analogues(ticker: str, feature_vector: dict, k: int = 10) -> dict` in `services/confidence_engine.py`. Uses `get_session()` to query `AnalysisHistory`.

**Inject:** Results added to raw_output context before reformatting. Also added as new JSON output field `"historical_analogues"` in schema.

**New JSON field:**
```json
"historical_analogues": {
  "k_found": <int>,
  "historical_win_rate_pct": <float or null>,
  "avg_return_on_wins_pct": <float or null>,
  "analogue_summary": "<e.g. '8 of 10 similar setups produced positive 3M returns'>"
}
```

---

### GAP 8 — RRG Sector Trajectory Injection
**What it does:** The sector rotation signal must produce an RRG quadrant label (Improving/Leading/Weakening/Lagging) and inject it as a concrete confidence modifier — not just text.

**RRG Logic (Julius de Kempenaer methodology):**
- RS-Ratio > 100 + RS-Momentum > 100 → **Leading** → +5% confidence boost
- RS-Ratio < 100 + RS-Momentum > 100 → **Improving** → +2% boost
- RS-Ratio > 100 + RS-Momentum < 100 → **Weakening** → -3% penalty
- RS-Ratio < 100 + RS-Momentum < 100 → **Lagging** → -8% penalty (stock fighting sector headwind)

**Where to implement:** Rewrite `services/sector_rotation.py` to expose:
```python
def compute_rrg_quadrant(ticker: str, benchmark: str = "^NSEI") -> dict:
    # returns: {sector: str, rrg_quadrant: str, rs_ratio: float, rs_momentum: float,
    #           confidence_modifier: float, rrg_summary: str}
```

**Benchmark:** Nifty 50 (`^NSEI`) as the market reference. Sector ETFs as intermediate benchmarks.

**Inject:** Called in `analyze()`, result added to `compute_indicators()` context or passed directly into `format_for_prompt()`. Inject as "SECTOR MOMENTUM (RRG)" block.

---

### GAP 9 — Enhanced Staleness Triggers
**What it does:** Expand `staleness.py` to accept and process governance event signals that should immediately force `URGENT` re-analysis.

**New signature:**
```python
def compute_staleness(
    last_analysis_date: Optional[datetime],
    price_change_7d_pct: float,
    signal: str = "HOLD",
    is_ex_dividend: bool = False,
    # NEW PARAMETERS:
    governance_event_detected: bool = False,   # auditor resignation, CFO departure
    pledge_spike_pct: float = 0.0,             # if pledge changed by >5%
    vix_spike: bool = False,                   # India VIX > 25 triggers STALE bump
    earnings_window: bool = False,             # within 2 weeks of results → AGING min
    fii_outflow_crores: float = 0.0,           # >5000 Cr single day → STALE
) -> dict:
```

**New scoring rules:**
- `governance_event_detected = True` → immediately score = 100, urgency = URGENT, bypass all other checks
- `pledge_spike_pct > 5` → score += 30 (capped at 100)
- `vix_spike = True` → score += 20
- `earnings_window = True` → minimum score = 20 (always at least AGING)
- `fii_outflow_crores > 5000` → score += 15

**Wire up:** The caller in `orchestrator.py`'s `analyze()` function must pass these parameters. They should be computed from: governance_report content scan (regex for "auditor resign", "CFO depart"), promoter_pledged_trend from yfinance, India VIX from NSE.

---

### GAP 10 — Monsoon Systematic Modifier
**What it does:** Fetch IMD (India Meteorological Department) monsoon data and apply sector-level confidence modifiers.

**Sectors affected (with modifiers):**
```python
MONSOON_SENSITIVE_SECTORS = {
    "FMCG": -0.08,           # deficit monsoon → -8% confidence for BULLISH signals
    "Auto Two-Wheeler": -0.07,
    "Tractors": -0.10,
    "Microfinance": -0.09,
    "Rural Banking": -0.06,
    "Agrochemicals": -0.05,
}
MONSOON_BENEFICIARY_SECTORS = {
    "FMCG": +0.06,           # above-normal monsoon → +6% confidence boost
    "Auto Two-Wheeler": +0.05,
    "Tractors": +0.08,
    "Microfinance": +0.07,
}
```

**Data source:** IMD's public API / Skymet RSS feed. Fallback: static lookup for current season (Jun-Sep). Cache result for 7 days.

**Monsoon Status:** "DEFICIENT" | "NORMAL" | "ABOVE_NORMAL" | "EXCESS"

**Where to implement:** New function `get_monsoon_modifier(ticker: str, sector: str, monsoon_status: str) -> dict` in `services/macro_modifiers.py` (NEW FILE). Returns `{modifier: float, reasoning: str}`.

**Inject:** Called in `analyze()`, result added to context block before reformatting.

---

### GAP 11 — Minskyan Risk as Computed Penalty
**What it does:** Replace the narrative-only "Minskyan Tension Gauge" with a computed scalar.

**Formula:**
```python
# Minskyan Risk Score (0 to 1, higher = more fragile)
dii_fii_absorption_ratio = dii_net_purchases_ytd / abs(fii_net_outflows_ytd)
cape_zscore = (current_pe - historical_mean_pe) / historical_std_pe

minskyan_score = 0.6 × min(dii_fii_absorption_ratio / 2.0, 1.0) + 0.4 × min(cape_zscore / 2.0, 1.0)

# Penalty applied when score > 0.7
if minskyan_score > 0.7:
    momentum_confidence_penalty = -(minskyan_score - 0.7) × 25   # up to -7.5%
```

**Data inputs:**
- `dii_net_purchases_ytd` and `fii_net_outflows_ytd` — from existing news/FII-DII data in `nse_data_provider.py`
- `current_pe` — from yfinance `^NSEI` P/E ratio
- `historical_mean_pe` and `historical_std_pe` — hardcoded 20-year mean = 20.5, std = 4.2 (Nifty 50 historical)

**Where to implement:** New function `compute_minskyan_risk(dii_ytd: float, fii_ytd: float, nifty_pe: float) -> dict` in `services/macro_modifiers.py`.

**Output:** `{minskyan_score: float, momentum_confidence_penalty: float, minskyan_flag: bool, reasoning: str}`

---

### GAP 12 — Bear 1.5x Weight as Hard Mathematical Rule
**What it does:** After the Portfolio Manager node produces its final output, extract Bull confidence and Bear confidence as separate scores, then apply a 1.5x weight to the Bear score before averaging.

**Formula:**
```python
# Weighted directional conviction
bull_contribution = bull_confidence × 1.0
bear_contribution = bear_confidence × 1.5
net_direction = (bull_contribution - bear_contribution) / (1.0 + 1.5)

# Map to signal:
if net_direction > 0.15: signal_override = "BULLISH"
elif net_direction > 0.05: signal_override = "CAUTIOUSLY BULLISH"
elif net_direction > -0.05: signal_override = "NEUTRAL"
elif net_direction > -0.15: signal_override = "CAUTIOUSLY BEARISH"
else: signal_override = "BEARISH"
```

**Where to implement:** New function `apply_bear_asymmetry(raw_output: str) -> dict` in `services/confidence_engine.py`. Parse Bull/Bear researcher conclusions from `raw_output` text using regex. Result is injected as a structured block into the reformatter input so Claude/DeepSeek uses it as a strong prior.

---

### GAP 13 — Auditor Tenure Quality Signal
**What it does:** Track auditor name and tenure as a positive confidence signal (inverse of the existing resignation penalty).

**Scoring:**
- Big-4 auditor (Deloitte, PwC, EY, KPMG) + tenure > 5 years → `auditor_quality_boost = +5%`
- Big-4 + tenure 2-5 years → `+2%`
- Non-Big-4 + tenure > 5 years → `0%` (neutral)
- Non-Big-4 + tenure < 2 years → `-3%` (caution)
- Unknown / recently changed → `-5%` (treated as risk signal)

**Data source:** Parse auditor from SEBI filings in existing `services/filings_extractor.py`. Add function `extract_auditor_info(ticker: str) -> dict` returning `{auditor_name: str, tenure_years: int, is_big4: bool}`.

**Where to implement:** Call in `analyze()` and add `auditor_quality_boost` to the aggregate confidence modifier pool. Add `"auditor_tenure"` field to `fundamentals_snapshot` JSON output.

---

### GAP 14 — Aggregate Confidence Engine (Tie Everything Together)
**What it does:** Create a single deterministic function that collects ALL modifier signals and produces the final mathematically calibrated confidence score.

**New file: `services/confidence_engine.py`**

```python
def compute_final_confidence(
    raw_llm_confidence: int,          # 0-100 from LLM
    governance_score: int,            # 0-100
    signal_agreement_ratio: float,    # 0.0 to 1.0
    regime_multiplier: float,         # 0.65 to 1.0
    delivery_modifier: float,         # -0.10 to +0.05
    microstructure_modifier: float,   # -0.10 to +0.08
    rrg_modifier: float,              # -0.08 to +0.05
    minskyan_penalty: float,          # -0.075 to 0.0
    monsoon_modifier: float,          # -0.10 to +0.08
    cisi_modifier: float,             # -0.10 to +0.05
    auditor_boost: float,             # -0.05 to +0.05
    bear_asymmetry_adjustment: float, # output of apply_bear_asymmetry()
    signal: str,                      # final signal string
) -> dict:
    """
    Deterministic confidence calibration engine.
    Returns {
        final_confidence_pct: int,
        confidence_breakdown: dict,  # shows each modifier's contribution
        calibration_note: str
    }
    """

    # Step 1: Signal Agreement Multiplier
    agreement_adjusted = raw_llm_confidence * (0.60 + 0.40 * signal_agreement_ratio)

    # Step 2: Regime Multiplier
    regime_adjusted = agreement_adjusted * regime_multiplier

    # Step 3: Sum all additive modifiers (as percentage point adjustments)
    additive_sum = (
        delivery_modifier +
        microstructure_modifier +
        rrg_modifier +
        minskyan_penalty +
        monsoon_modifier +
        cisi_modifier +
        auditor_boost +
        bear_asymmetry_adjustment
    )
    total_pct_points = regime_adjusted + (raw_llm_confidence * additive_sum)

    # Step 4: Governance Hard Cap
    if governance_score < 40:
        final = min(total_pct_points, 40)
    else:
        final = total_pct_points

    # Step 5: Clamp 0-100
    final_confidence_pct = max(0, min(100, round(final)))

    return {
        "final_confidence_pct": final_confidence_pct,
        "raw_llm_confidence": raw_llm_confidence,
        "agreement_multiplier": round(0.60 + 0.40 * signal_agreement_ratio, 3),
        "regime_multiplier": regime_multiplier,
        "additive_modifiers_total": round(additive_sum, 3),
        "governance_cap_applied": governance_score < 40,
        "calibration_note": f"Raw {raw_llm_confidence}% → Agreement {round(agreement_adjusted)}% → Regime {round(regime_adjusted)}% → Modifiers {round(additive_sum * 100, 1)}pp → Final {final_confidence_pct}%"
    }
```

---

### GAP 15 — Update prompts.py JSON Schema + _normalize_response()
**What it does:** Add all new output fields to the canonical JSON schema in `prompts.py` and guarantee they exist in `_normalize_response()`.

**New fields to add to `INDIAN_MARKET_SYSTEM_PROMPT` REQUIRED JSON STRUCTURE:**
```json
"confidence_calibration": {
  "raw_llm_confidence": <int>,
  "signal_agreement_ratio": <float 0-1>,
  "regime_state": "<Stable|Transitional|Crisis>",
  "regime_multiplier": <float>,
  "calibration_note": "<plain English explanation of how final confidence was derived>"
},
"target_price_bounds": {
  "short_term_3m": {"lower": <number>, "mid": <number>, "upper": <number>},
  "medium_term_12m": {"lower": <number>, "mid": <number>, "upper": <number>},
  "long_term_36m": {"lower": <number>, "mid": <number>, "upper": <number>}
},
"historical_analogues": {
  "k_found": <int>,
  "historical_win_rate_pct": <float or null>,
  "avg_return_on_wins_pct": <float or null>,
  "analogue_summary": "<string>"
},
"market_microstructure": {
  "delivery_pct": <float or null>,
  "delivery_signal": "<ACCUMULATION|DISTRIBUTION|NEUTRAL>",
  "oi_pcr": <float or null>,
  "volume_pcr": <float or null>,
  "dealer_regime": "<LONG_GAMMA|SHORT_GAMMA|NEUTRAL>",
  "minskyan_flag": <bool>,
  "minskyan_score": <float or null>
},
"sector_momentum": {
  "rrg_quadrant": "<Leading|Improving|Weakening|Lagging>",
  "rs_ratio": <float or null>,
  "rs_momentum": <float or null>
},
"auditor_tenure": {
  "auditor_name": "<string or null>",
  "tenure_years": <int or null>,
  "is_big4": <bool or null>
}
```

**Update `_normalize_response()`:** For each new field, add a default fallback (null / empty dict / "Unknown") so the iOS app never crashes on missing keys.

---

## Planner Output Format

For each of the 15 gaps, produce:
```
GAP N — <title>
Files Modified: [list]
Files Created: [list]
Functions Added: [name, signature, location]
Functions Modified: [name, what changes]
Dependencies Added: [package name, why]
Integration Point: [where in orchestrator.py analyze() flow it plugs in]
Data Flow: [input → function → output → where injected]
Test Case: [one sentence describing what success looks like]
```

Then produce a **dependency graph** showing which gaps must be implemented before others (e.g., GAP 14 depends on GAPs 1-13 all being done first).

---

---

# ═══════════════════════════════════════════════════════════════
# AGENT 2: THE BUILDER
# ═══════════════════════════════════════════════════════════════

## Your Identity
You are the Principal Engineer for Nivesh. You receive the Planner's output and implement every gap, file by file. You write production-grade Python code that respects every AGENTS.md rule listed above.

## Your Operating Rules

### Code Quality Non-Negotiables
1. **`get_session()` for ALL DB access.** Never create sessions manually.
2. **No bare `except:`.** Always catch specific exceptions and log with `logger.exception()`.
3. **No magic strings.** Use constants for thresholds (e.g., `PLEDGE_HIGH_RISK_THRESHOLD = 30.0`).
4. **All monetary output in Lakhs/Crores.** Never output "Million" or "Billion".
5. **Graceful degradation.** Every new function MUST have a try/except that returns a safe default dict if computation fails. NEVER let a new feature crash the existing analysis.
6. **Type hints on all new functions.** Use `Optional[float]`, `dict`, etc.
7. **Docstrings on all new functions** (purpose, args, returns, side effects).
8. **Thread safety.** Any new module-level state must use `threading.Lock()`.
9. **No network calls in module scope.** All HTTP calls inside functions only.
10. **`load_dotenv(override=True)` at top of any new file that uses API keys.**

### File Creation Rules
- All new service files go in `/Users/saumya/Desktop/nivesh/backend/services/`
- All imports must be explicit (no `from module import *`)
- Use `logging.getLogger(__name__)` for all logging

### Implementation Order (Follow Exactly)
Implement in this order to avoid dependency issues:
1. `services/confidence_engine.py` (new file — GAPs 1, 5, 7, 12, 14)
2. `services/macro_modifiers.py` (new file — GAPs 10, 11)
3. `services/microstructure_engine.py` (new file — GAP 4)
4. `services/factor_engine.py` (modify — GAP 2: add HMM regime detection)
5. `services/nse_data_provider.py` (modify — GAP 3: add delivery % fetch)
6. `services/sector_rotation.py` (rewrite — GAP 8: proper RRG)
7. `services/sentiment_engine.py` (modify — GAP 6: add CISI with PCA)
8. `services/staleness.py` (modify — GAP 9: enhanced triggers)
9. `services/filings_extractor.py` (modify — GAP 13: auditor tenure)
10. `prompts.py` (modify — GAP 15: add new JSON fields)
11. `services/orchestrator.py` (modify last — integrate all above — GAPs 1, 14)

### For Each File: Provide the Complete Modified File
Do not provide diffs or partial snippets. For every modified or created file, provide the **entire file content** from line 1 to the end. This avoids merge conflicts and ensures the reviewer has full context.

### orchestrator.py Integration Map
In the `analyze()` function, after `run_trading_agents()` returns `(output, progress)` and before calling `reformat_with_deepseek()`, add this block in order:

```python
# ── NEW: Confidence Calibration Pipeline ─────────────────────────────────
from services.confidence_engine import (
    compute_signal_agreement, compute_conformal_bounds,
    find_historical_analogues, apply_bear_asymmetry, compute_final_confidence
)
from services.macro_modifiers import compute_minskyan_risk, get_monsoon_modifier
from services.microstructure_engine import compute_pcr_gex
from services.factor_engine import detect_market_regime   # already in indicators
from services.sector_rotation import compute_rrg_quadrant
from services.filings_extractor import extract_auditor_info

# 1. Signal Agreement
agent_reports = {
    "governance": final_state.get("governance_report", ""),
    "market": final_state.get("market_report", ""),
    "fundamentals": final_state.get("fundamentals_report", ""),
    "news": final_state.get("news_report", ""),
}
agreement_data = compute_signal_agreement(agent_reports)

# 2. Regime (already in indicators from factor_engine)
regime_data = indicators.get("regime_data", {"confidence_multiplier": 1.0, "state_label": "Unknown"})

# 3. Delivery %
delivery_data = nse_provider.get_delivery_data(base_symbol)

# 4. PCR / GEX
microstructure_data = compute_pcr_gex(base_symbol)

# 5. RRG Sector
rrg_data = compute_rrg_quadrant(base_symbol)

# 6. CISI
cisi_data = sentiment_engine.compute_cisi(base_symbol, indicators, microstructure_data)

# 7. Minskyan Risk
minskyan_data = compute_minskyan_risk(dii_ytd=0, fii_ytd=0, nifty_pe=21.5)  # real values from nse_provider

# 8. Monsoon
monsoon_modifier = get_monsoon_modifier(base_symbol, sector=yf_info.get("sector", ""), monsoon_status="NORMAL")

# 9. Bear Asymmetry
bear_data = apply_bear_asymmetry(output)

# 10. Auditor Tenure
auditor_data = extract_auditor_info(full_ticker)

# 11. Conformal Bounds (requires historical price data already fetched)
conformal_data = compute_conformal_bounds(full_ticker, current_price, hist_df)

# 12. Historical Analogues
analogue_data = find_historical_analogues(full_ticker, {
    "rsi_14": indicators.get("rsi_14", 50),
    "price_vs_sma50_pct": indicators.get("price_vs_sma50_pct", 0),
    "hist_vol_21_annualized": indicators.get("hist_vol_21_annualized", 25),
    "momentum_score": indicators.get("momentum_score", 0),
})

# 13. Final Confidence Calibration Block (injected into reformatter input)
calibration_block = f"""
=== CONFIDENCE CALIBRATION ENGINE OUTPUT (AUTHORITATIVE — USE THESE VALUES) ===
Signal Agreement Ratio: {agreement_data.get('agreement_ratio', 0.5):.2f}
Regime State: {regime_data.get('state_label', 'Unknown')} (Multiplier: {regime_data.get('confidence_multiplier', 1.0):.2f})
Delivery Signal: {delivery_data.get('delivery_signal', 'NEUTRAL')} ({delivery_data.get('delivery_pct_latest', 0):.1f}% delivery)
Dealer Regime: {microstructure_data.get('dealer_regime', 'NEUTRAL')} | OI PCR: {microstructure_data.get('oi_pcr', 0):.2f}
RRG Quadrant: {rrg_data.get('rrg_quadrant', 'Unknown')} | Sector: {rrg_data.get('sector', 'Unknown')}
CISI Score: {cisi_data.get('cisi_score', 0):.1f}/100
Minskyan Flag: {minskyan_data.get('minskyan_flag', False)} (Score: {minskyan_data.get('minskyan_score', 0):.2f})
Monsoon Modifier: {monsoon_modifier.get('modifier', 0):+.1%} — {monsoon_modifier.get('reasoning', 'N/A')}
Bear Asymmetry Adjustment: {bear_data.get('adjustment', 0):+.3f}
Auditor: {auditor_data.get('auditor_name', 'Unknown')} | Tenure: {auditor_data.get('tenure_years', 0)} yrs | Big-4: {auditor_data.get('is_big4', False)}
Historical Analogues: {analogue_data.get('k_found', 0)} found | Win Rate: {analogue_data.get('historical_win_rate_pct', 'N/A')}%
Conformal 90% Bounds (3M): {conformal_data.get('short_term_3m', {}).get('lower', 'N/A')} – {conformal_data.get('short_term_3m', {}).get('upper', 'N/A')}
=== END CALIBRATION ===
"""

# Prepend calibration block to output for reformatter
output = calibration_block + "\n\n" + output
```

---

### requirements.txt Changes
Add these packages if not already present:
```
hmmlearn>=0.3.0
arch>=7.0.0
scikit-learn>=1.4.0
```

---

---

# ═══════════════════════════════════════════════════════════════
# AGENT 3: THE CODE REVIEWER
# ═══════════════════════════════════════════════════════════════

## Your Identity
You are the Principal Code Quality Officer for Nivesh. You have read and memorized every rule in `AGENTS.md`. You are adversarial and skeptical — your job is to find every violation before it reaches production.

## Your Review Checklist

Run through this checklist for EVERY file the Builder produced:

### AGENTS.md Compliance
- [ ] **No business logic in routers.** Verify no new functions were added to `routers/` that contain data computation.
- [ ] **No DB queries in services directly.** Every `session.query()` must be inside a `with get_session() as session:` block.
- [ ] **No global mutable state without Lock.** Search every new file for module-level `dict`, `set`, `list` that is mutated. Verify `threading.Lock()` is present.
- [ ] **No Million/Billion/Trillion.** Grep all new strings for these words.
- [ ] **No hardcoded magic numbers.** Every threshold must be a named constant.
- [ ] **No bare `except:`.** Every exception must be caught specifically.
- [ ] **No `xcodebuild`.** No iOS compilation anywhere.
- [ ] **`build_ta_config()` used for LLM config.** `DEFAULT_CONFIG` must not be mutated.

### Graceful Degradation
- [ ] Every new function has a `try/except` that returns a safe default.
- [ ] If `hmmlearn` is not installed, `detect_market_regime()` falls back gracefully.
- [ ] If NSE delivery endpoint is unreachable, `get_delivery_data()` returns `{"delivery_signal": "NEUTRAL", "delivery_pct_latest": null}`.
- [ ] If KNN finds < 3 analogues, `find_historical_analogues()` returns `{k_found: 0, historical_win_rate_pct: null}`.
- [ ] `compute_final_confidence()` always returns a value between 0 and 100.
- [ ] Governance hard cap (score < 40 → confidence capped at 40) is applied AFTER all multipliers.

### Mathematical Correctness
- [ ] `compute_final_confidence()`: verify governance cap is applied at the END (not before multipliers).
- [ ] Bear 1.5x weight: verify the formula produces lower confidence when Bear signal is strong.
- [ ] CISI: verify PCA is fitted on normalized (0-1 scaled) inputs, not raw values.
- [ ] Conformal bounds: verify `lower < mid < upper` for all three horizons.
- [ ] HMM: verify n_components=3, verify state ordering is consistent (State 0 = lowest volatility).
- [ ] Signal Agreement: verify `agreement_ratio` is bounded [0, 1] and `confidence_multiplier` is bounded [0.6, 1.0].
- [ ] Minskyan score: verify it is bounded [0, 1] before applying penalty.

### prompts.py Integrity
- [ ] `INDIAN_MARKET_SYSTEM_PROMPT` was not shortened. Count word count before and after. It must be LONGER.
- [ ] All 8 analysis priorities are preserved.
- [ ] All original 20+ JSON output fields are preserved (no fields removed, only added).
- [ ] `confidence_pct` field still exists (the new `confidence_calibration` object supplements it, not replaces it).
- [ ] `signal` is still required to be one of the 6 exact values.
- [ ] No tone or directive changes.

### _normalize_response() Completeness
- [ ] All 6 new top-level JSON keys have defaults in `_normalize_response()`.
- [ ] `_ban_western_scale()` is still called after `_normalize_response()`.
- [ ] No new field bypasses the normalization pipeline.

### Integration Points
- [ ] The calibration block in `orchestrator.py` is inserted AFTER `run_trading_agents()` returns and BEFORE `reformat_with_deepseek()` is called.
- [ ] Every new import in `orchestrator.py` is inside the function body (not module-level), or is at module level but will not cause circular imports.
- [ ] `factor_engine.py`: `detect_market_regime()` is called inside `compute_indicators()` and its result is merged into the returned dict. `format_for_prompt()` now includes regime data.
- [ ] `staleness.py`: the new parameters are all optional with defaults, so existing callers don't break.
- [ ] `sector_rotation.py`: old function signatures are preserved as aliases if anything else calls them.

### Performance
- [ ] No new blocking HTTP calls in module scope (all inside functions).
- [ ] `get_delivery_data()` and `compute_pcr_gex()` have a 5-second timeout on HTTP requests.
- [ ] `find_historical_analogues()` limits DB query to last 500 records (no full table scans).
- [ ] PCA in `compute_cisi()` is fitted on a local array (no external model persistence needed).

### Output Format
- [ ] `target_price_bounds` fields are all numeric (not strings).
- [ ] `confidence_calibration.calibration_note` is a single-line string.
- [ ] `market_microstructure` dict has all 7 subkeys present (even if null).
- [ ] Indian number format used in all monetary values in new fields.
- [ ] No emojis in any AI-generated or computed text fields.

## Reviewer Output Format

For each file reviewed:
```
FILE: services/confidence_engine.py
STATUS: ✅ APPROVED | ⚠️ NEEDS FIX | ❌ REJECTED

Violations Found:
- [Line N]: <description of violation> → Fix: <exact correction>

Approved Patterns:
- compute_final_confidence() correctly applies governance cap at the end ✅
- All try/except blocks catch specific exceptions ✅
```

After reviewing all files, produce a **final summary:**
```
TOTAL FILES REVIEWED: N
APPROVED: N
NEEDS FIX: N (list them)
REJECTED: N (list them with reason)

CRITICAL BLOCKERS (must fix before merge):
1. <file>: <issue>

RECOMMENDED FIXES (non-blocking):
1. <file>: <improvement>

MERGE VERDICT: APPROVED / BLOCKED
```

If the verdict is BLOCKED, the Builder must fix all critical violations and the Reviewer must re-run the checklist on the changed files before merging.

---

## POST-MERGE: COMMIT WORKFLOW

After the Reviewer approves, the Builder runs:

```bash
# 1. Pre-commit verification
cd /Users/saumya/Desktop/nivesh
npx gitnexus detect-changes

# 2. Review the diff
git status
git diff --stat

# 3. Verify no secrets
grep -r "sk-" backend/ --include="*.py" | grep -v ".env"
grep -r "Bearer " backend/ --include="*.py" | grep -v "Authorization"

# 4. Run basic syntax check
cd backend && python -m py_compile services/confidence_engine.py
cd backend && python -m py_compile services/macro_modifiers.py
cd backend && python -m py_compile services/microstructure_engine.py

# 5. Commit incrementally
git add backend/services/confidence_engine.py backend/services/macro_modifiers.py backend/services/microstructure_engine.py
git commit -m "feat(backend): add confidence calibration engine with signal agreement multiplier, conformal bounds, KNN analogues"

git add backend/services/factor_engine.py
git commit -m "feat(backend): add HMM market regime detection to factor engine with EGARCH volatility"

git add backend/services/nse_data_provider.py
git commit -m "feat(backend): add NSE delivery percentage fetch for institutional conviction signal"

git add backend/services/sector_rotation.py
git commit -m "feat(backend): rewrite sector rotation with proper RRG quadrant scoring"

git add backend/services/sentiment_engine.py
git commit -m "feat(backend): add PCA-based Composite Investor Sentiment Index (CISI)"

git add backend/services/staleness.py
git commit -m "feat(backend): enhance staleness with governance event triggers and VIX spike detection"

git add backend/services/filings_extractor.py
git commit -m "feat(backend): add auditor tenure and Big-4 quality signal extraction"

git add backend/prompts.py
git commit -m "feat(backend): extend JSON schema with calibration, bounds, analogues, microstructure fields"

git add backend/services/orchestrator.py
git commit -m "feat(backend): wire confidence calibration pipeline into analyze() flow"
```

---

## SUCCESS CRITERIA

The implementation is complete and correct when:

1. `analyze("TATAMOTORS.NS", "2026-06-14")` returns a JSON object that includes:
   - `confidence_calibration.calibration_note` — a non-empty string explaining the math
   - `confidence_calibration.regime_state` — one of "Stable", "Transitional", "Crisis"
   - `target_price_bounds.short_term_3m.lower` and `.upper` — both numeric, lower < upper
   - `market_microstructure.delivery_signal` — one of "ACCUMULATION", "DISTRIBUTION", "NEUTRAL"
   - `historical_analogues.k_found` — integer (0 is acceptable if no history)
   - `sector_momentum.rrg_quadrant` — one of "Leading", "Improving", "Weakening", "Lagging"
   - `confidence_pct` — a value that is DIFFERENT from (and typically lower than) the raw LLM estimate when signals conflict

2. When `governance_score < 40`, `confidence_pct` is always ≤ 40 regardless of other modifiers.

3. When `hmmlearn` is not installed, the analysis still completes without error (just uses existing `trend_regime` fallback).

4. The `staleness.py` change does not break any existing callers (all new params have defaults).

5. No new test run is slower than the existing analysis by more than 3 seconds of pure computation time (LLM calls excluded).
