# PORTFOLIO STRESS TEST — Autonomous Build for Antigravity CLI

Paste into Antigravity CLI. Do not ask. Build end-to-end.

---

## GOAL

Stress test engine: user picks shock scenarios, system computes exact portfolio impact using betas and sector correlations. Tornado chart of which holdings get hit hardest.

---

## REUSE (DO NOT REBUILD)

Portfolio holdings from GET /portfolio. Stock betas from yfinance .info. Sector data from StockDatabase.swift. Theme + Charts from existing design system.

---

## BACKEND: backend/services/stress_test.py

Pure math, zero LLM. 8 pre-built scenarios:

1. NIFTY_CRASH: Nifty -20%, high-beta stocks -30%, low-beta -10%
2. OIL_SHOCK: crude +$40, oil sectors -15%, aviation -25%, IT +5%
3. RATE_HIKE: RBI +100bps, NBFCs -20%, banks mixed, infra -10%
4. FII_EXODUS: FII outflow 50K Cr, Nifty -12%, midcaps -20%
5. GLOBAL_RECESSION: Nifty -25%, IT -15%, pharma +5%
6. POLICY_SHOCK: Nifty -18%, PSUs -30%, defence +10%
7. CURRENCY_CRASH: INR 90/USD, importers -20%, IT +12%, pharma +8%
8. CUSTOM: user sets Nifty % and sector overrides

Logic: per holding = holding_weight * beta * scenario_shock + sector_adjustment
Sum all holdings = portfolio impact. Include cash as buffer.

Endpoint: POST /api/v1/portfolio/stress-test
Request: {scenarios: ["nifty_crash"], portfolio_id: "holdings"}
Response: {results: [{name, impact_pct, impact_inr, holdings: [{ticker, impact_pct, impact_inr}]}]}

Register route in backend/main.py.

---

## iOS: ios/StockApp/stockme/stockme/Views/StressTestScreen.swift

New screen, add to navigation sidebar. Layout:

1. HERO: "Stress Test" title + description
2. SCENARIO CHIPS: horizontal scroll, 8 chips with SF Symbols
3. MULTI-SELECT: tap chips to select 1-3 scenarios, run button
4. TORNADO CHART: horizontal BarMark, red bars ranked worst to best
5. HOLDING CARDS: per-stock "RELIANCE: -Rs 45,000 (-18.3%)" with bar
6. SUMMARY: "Portfolio down Rs 2,85,000 (-22.7%)"
7. BUFFER CARD: if cash position exists, show offset

States: loading shimmer, empty, error. All Theme tokens. All INR via IndianFormatter.

---

## VERIFY

Nifty Crash on portfolio -> all holdings negative. Oil Shock -> Reliance negative, IT stocks positive. Multiple scenarios -> tornado chart.

## RULES

Zero LLM. Pure math. Reuse existing portfolio endpoint. Account for cash. New files only unless route registration.
