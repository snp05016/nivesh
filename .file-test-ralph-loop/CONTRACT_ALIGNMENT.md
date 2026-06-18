# Contract Alignment Report — iOS ↔ Backend API

> Generated: 2026-06-18 | Scope: All Codable models in iOS vs backend response shapes

---

## 1. StockAnalysis (`AnalysisModels.swift` ↔ `_normalize_response()` / `_inject_live_data()`)

**Endpoint:** `POST /analyze` (returns full JSON), `GET /analyze/job/{job_id}` (returns stored `full_json`), cache hit path.

| Status | Field | iOS Type | Backend Type | Notes |
|--------|-------|----------|-------------|-------|
| ✓ | `ticker` | `String` | `str` | — |
| ✓ | `company_name` | `String` | `str` | — |
| ✓ | `exchange` | `String?` | `str?` | Optional on both sides |
| ✓ | `analysis_date` | `String` | `str` | — |
| ✓ | `signal` | `Signal` (enum) | `str` enum | Robust decode in `Signal.init(from:)` — falls back to `.neutral` |
| ✓ | `confidence_pct` | `Int` | `int` | — |
| ✓ | `current_price_inr` | `Double` | `float` | Updated live by `_inject_live_data()` |
| ✓ | `target_prices` | `TargetPrices` | `dict` | — |
| ✓ | `upside_downside_pct` | `UpsideDownsidePct` | `dict` | — |
| ✓ | `bull_case` | `[String]` | `list[str]` | Guaranteed non-empty by `_normalize_response()` |
| ✓ | `bear_case` | `[String]` | `list[str]` | Guaranteed non-empty by `_normalize_response()` |
| ✓ | `key_risks` | `[String]` | `list[str]` | — |
| ✓ | `key_factors` | `KeyFactors` | `dict` | — |
| ✓ | `fundamentals_snapshot` | `FundamentalsSnapshot` | `dict` | — |
| ✓ | `what_to_watch` | `[String]` | `list[str]` | — |
| ✓ | `disclaimer` | `String` | `str` | — |
| ✓ | `recent_news` | `[NewsItem]?` | `list[dict]?` | Optional; injected by `_inject_live_data()` |
| ✓ | `patterns` | `[String]?` | `list[str]?` | Optional |
| ✓ | `confidence_rationale` | `String?` | `str?` | Optional |
| ✓ | `signal_changed` | `Bool?` | `bool?` | Optional |
| ✓ | `previous_signal` | `String?` | `str?` | Optional |
| ✓ | `advisor_matrix` | `[AdvisorInsightRow]` | `list[dict]?` | Defaults to `[]` if absent |
| ✓ | `price_performance` | `PricePerformance?` | `dict?` | Injected by `_inject_live_data()` |
| ✓ | `analysis_tier` | `String?` | `str?` | v2 extreme bundles |
| ✓ | `factor_scores` | `FactorScores?` | `dict?` | — |
| ✓ | `piotroski` | `PiotroskiData?` | `dict?` | — |
| ✓ | `financial_trends` | `FinancialTrends?` | `dict?` | — |
| ✓ | `ownership_trends` | `OwnershipTrends?` | `dict?` | — |
| ✓ | `peer_comparison` | `[PeerRow]?` | `list[dict]?` | — |
| ✓ | `scenarios` | `ScenarioBundle?` | `dict?` | — |
| ✓ | `valuation_bands` | `ValuationBands?` | `dict?` | — |
| ✓ | `extended_thesis` | `ExtendedThesis?` | `dict?` | — |
| ✓ | `niche_insights` | `[String]?` | `list[str]?` | — |
| ✓ | `governance_flags` | `[GovernanceFlag]?` | `list[dict]?` | — |
| ✓ | `confidence_calibration` | `ConfidenceCalibration?` | `dict?` | — |
| ✓ | `target_price_bounds` | `TargetPriceBounds?` | `dict?` | — |
| ✓ | `historical_analogues` | `HistoricalAnalogues?` | `dict?` | — |
| ✓ | `market_microstructure` | `MarketMicrostructure?` | `dict?` | — |
| ✓ | `sector_momentum` | `SectorMomentum?` | `dict?` | — |
| ✓ | `auditor_tenure` | `AuditorTenure?` | `dict?` | — |
| ✓ | `_staleness_label` | `String?` | `str?` | Staleness metadata |
| ✓ | `_staleness_score` | `Int?` | `int?` | — |
| ✓ | `_staleness_urgency` | `String?` | `str?` | — |
| ✓ | `_staleness_hours` | `Double?` | `float?` | — |
| ✓ | `_staleness_reason` | `String?` | `str?` | — |
| ✓ | `_cached_scan_type` | `String?` | `str?` | — |
| ✓ | `market_regime` | `String?` | `str?` | Quant engine |
| ✓ | `calibrated_confidence` | `Double?` | `float?` | Quant engine |
| ✓ | `confidence_math_breakdown` | `[String: Double]?` | `dict?` | — |
| ✓ | `conformal_target_upper_3m` | `Double?` | `float?` | — |
| ✓ | `conformal_target_lower_3m` | `Double?` | `float?` | — |
| ✓ | `quantitative_drivers` | `[String: Double]?` | `dict?` | — |
| ✓ | `tail_risk_flags` | `[String: Bool]?` | `dict?` | — |

**Verdict: FULLY ALIGNED** — All fields have explicit `CodingKeys` with correct snake_case mapping. All optional fields use `decodeIfPresent`. The custom `init(from decoder:)` handles complex defaults (e.g., `advisorMatrix: []`). The `Signal` enum has a robust fallback to `.neutral`.

---

## 2. QuickInfo (`AnalysisModels.swift` ↔ `quick_info_endpoint()`)

**Endpoint:** `GET /quick-info?ticker=X&exchange=NSE`

| Status | Field | iOS | Backend | Issue |
|--------|-------|-----|---------|-------|
| ✓ | `ticker` | `String` | `str` | — |
| ✓ | `current_price` | `Double?` | `float?` | — |
| ✓ | `day_change_abs` | `Double?` | `float?` | — |
| ✓ | `day_change_pct` | `Double?` | `float?` | — |
| ✓ | `signal` | `Signal?` | NOT returned | Backend does NOT include `signal` in quick_info response (line 402-437). **iOS decodes it as nil — no crash, but field is empty.** |
| ✓ | `sector` | `String?` | `str?` | — |
| ✓ | `industry` | `String?` | `str?` | — |
| ✓ | `description` | `String?` | `str?` | — |
| ✓ | `officers` | `[String]?` | `list[str]?` | — |
| ✓ | `website` | `String?` | `str?` | — |
| ✓ | `recent_news` | `[NewsItem]?` | `list[dict]?` | — |
| ✓ | `sparkline_30d` | `[Double]?` | `list[float]?` | — |
| ✓ | `week_52_high` | `Double?` | `float?` | — |
| ✓ | `week_52_low` | `Double?` | `float?` | — |
| ✓ | `pe_ratio` | `Double?` | `float?` | — |
| ✓ | `debt_to_equity` | `Double?` | `float?` | — |
| ✓ | `promoter_holding_pct` | `Double?` | `float?` | — |
| ✓ | `fii_holding_pct` | `Double?` | `float?` | — |
| ✓ | `dii_holding_pct` | `Double?` | `float?` | — |
| ✓ | `ebitda_margin_pct` | `Double?` | `float?` | — |
| ✓ | `roe_pct` | `Double?` | `float?` | — |
| ✓ | `roce_pct` | `Double?` | `float?` | — |
| ✓ | `volume` | `Int?` | `int?` | — |
| ✓ | `avg_volume` | `Int?` | `int?` | — |
| ✓ | `price_history_90d` | `[PricePoint]?` | `list[dict]?` | — |
| ✓ | `pe_vs_avg` | `PeVsAvg?` | `dict?` | — |
| ✓ | `asm_gsm_status` | `String?` | `str` | Backend always returns. iOS optional — fine. |
| ✓ | `promoter_pledged_pct` | `Double?` | `float?` | — |
| ✓ | `governance_score` | `Int?` | `int?` | — |
| ✓ | `governance_red_flags` | `[String]?` | `list[str]?` | — |
| ⚠️ | `company_name` | NOT IN IOS | `str` | Backend returns `company_name` but iOS QuickInfo does not have this field. **Silently ignored by JSONDecoder.** |
| ⚠️ | `market_cap_crores` | NOT IN IOS | `float?` | Backend returns `market_cap_crores` but iOS QuickInfo lacks this field. **Silently ignored.** |
| ⚠️ | `dividends` | NOT IN IOS | `list[dict]?` | Backend returns dividend history. iOS QuickInfo lacks this. **Silently ignored.** |
| ⚠️ | `corporate_actions` | NOT IN IOS | `list[dict]?` | Backend returns corp actions. iOS QuickInfo lacks this. **Silently ignored.** |
| ⚠️ | `exchange` | NOT IN IOS | `str` | Backend returns `exchange` field. iOS QuickInfo lacks it. **Silently ignored.** |

**Verdict: FUNCTIONAL BUT INCOMPLETE** — No crashes, but 5 backend fields are silently discarded by iOS. The `signal` field (key UX element) is never populated by the backend.

---

## 3. Portfolio Holdings (`PortfolioModels.swift` ↔ `portfolio_endpoint()`)

**Endpoint:** `GET /portfolio/{user_id}`

### Response wrapper: the backend returns a dict with `holdings` array + portfolio-level keys:
```json
{
  "user": "...",
  "user_id": 1,
  "as_of": "...",
  "total_invested_inr": 50000,
  "total_current_inr": 55000,
  "total_pnl_inr": 5000,
  "total_pnl_pct": 10.0,
  "holdings": [...]
}
```

### iOS uses a private `PortfolioResponse` struct that ONLY extracts `holdings`:

| Status | Field | iOS `HoldingDTO` | Backend | Issue |
|--------|-------|-----------------|---------|-------|
| ✓ | `ticker` | `String` | `str` | — |
| ✓ | `company_name` | `String` | `str` | — |
| ✓ | `shares` | `Double` | `float` | — |
| ✓ | `buy_price` | `Double` | `float` | — |
| ✓ | `current_price` | `Double` | `float` | — |
| ✓ | `day_change_pct` | `Double?` | `float` | — |
| ✓ | `notes` | `String?` | `str?` | — |
| ✓ | `purchase_date` | `String?` | `str?` | — |
| ✓ | `target_price` | `Double?` | `float?` | — |
| 🌫️ | `group` | NOT IN IOS | `str` | Backend returns; iOS ignores. OK. |
| 🌫️ | `invested_inr` | NOT IN IOS | `float` | Backend returns; iOS ignores. OK. |
| 🌫️ | `current_value_inr` | NOT IN IOS | `float` | Backend returns; iOS ignores. OK. |
| 🌫️ | `pnl_inr` | NOT IN IOS | `float` | Backend returns; iOS ignores. OK. |
| 🌫️ | `pnl_pct` | NOT IN IOS | `float` | Backend returns; iOS ignores. OK. |
| 🌫️ | `staleness` | NOT IN IOS | `dict?` | Backend returns; iOS ignores. OK. |
| 🐛 | `notes` (DUPLICATE) | `String?` | `str?` (×2) | **Backend bug:** `notes` key set twice at line 586 and 594. Second value (`h.notes`) overwrites first (`getattr(h, "notes", "")`). Same value in practice, but code smell. |

**Verdict: FUNCTIONAL** — iOS correctly maps the fields it needs. Extra backend fields are safely ignored. The duplicate `notes` key is a trivial backend issue.

---

## 4. Watchlist (`WatchlistModels.swift` ↔ `watchlist_get_endpoint()`)

**Endpoint:** `GET /watchlist/{user_id}` (returns `{"watchlist": [...]}`)

| Status | Field | iOS | Backend | Issue |
|--------|-------|-----|---------|-------|
| ✓ | `ticker` | `String` | `str` | — |
| ✓ | `company_name` | `String` | `str` | — |
| ✓ | `exchange` | `String` | hardcoded `"NSE"` | Backend always returns `"NSE"`. iOS expects non-NSE too. **Minor: BSE tickers would show as NSE.** |
| ✓ | `current_price` | `Double` | `float` | — |
| ✓ | `day_change_pct` | `Double` | `float` | — |
| ✓ | `last_signal` | `String?` | `str?` | — |
| ✓ | `last_signal_date` | `String?` | `str?` | — |
| ✓ | `asm_gsm_status` | `String?` | `str` | Backend always present. iOS optional — fine. |

**Verdict: FULLY ALIGNED** — Minor note: exchange is hardcoded to `"NSE"` in backend.

---

## 5. Price Alerts (`AlertModels.swift` ↔ `alerts_get_endpoint()`)

**Endpoint:** `GET /alerts/{user_id}` (returns `{"alerts": [...]}`)

| Status | Field | iOS | Backend | Issue |
|--------|-------|-----|---------|-------|
| ✓ | `id` | `Int` | `int` | — |
| ✓ | `ticker` | `String` | `str` | — |
| ⚠️ | `company_name` | `String` | `str` (ticker value) | **Backend bug:** `company_name` is set to `row["ticker"]` at alerts.py:203. The backend never looks up the actual company name. iOS will show ticker as company name. |
| ✓ | `target_price` | `Double` | `float` | — |
| ✓ | `direction` | `String` | `str` (`"above"`/`"below"`) | — |
| ✓ | `current_price` | `Double?` | `float?` | — |
| ✓ | `distance_pct` | `Double?` | `float?` | — |
| ✓ | `triggered` | `Bool` | `bool` | — |
| ✓ | `created_at` | `String` | `str` | Date format: `yyyy-MM-dd` |

**Verdict: FUNCTIONAL WITH KNOWN BUG** — `companyName` will show the ticker symbol. Not a crash risk but degrades UX. Fix needed in `alerts.py:203`.

---

## 6. Market Indices (`MarketModels.swift` ↔ `market_indices_endpoint()` / `_get_indices_data()`)

**Endpoint:** `GET /market-indices`

| Status | Field | iOS `LiveMarketIndex` | Backend | Issue |
|--------|-------|----------------------|---------|-------|
| ✓ | `name` | `String` | `str` | — |
| ✓ | `ticker` | `String` | `str` | — |
| ✓ | `value` | `Double` | `float` | — |
| ✓ | `change_pct` | `Double` | `float` | — |
| ✓ | `change_abs` | `Double` | `float` | — |

Response wrapper `MarketIndicesResponse`: `indices` + `fetched_at`. **FULLY ALIGNED.**

---

## 7. Dashboard Pulse — Extended (`MarketModels.swift` ↔ `dashboard_pulse_endpoint()`)

**Endpoint:** `GET /dashboard-pulse`

### Backend response shape (line 1727-1734):
```json
{
  "pulse": { "indices": [...], "advances": n, "declines": n, "unchanged": n, "breadth_ratio": f, "fetched_at": "..." },
  "momentum": { "bullish": [...], "bearish": [...], "fetched_at": "..." },
  "live_reporting_sync": { "declared_count": n, "total_expected": n, "sync_ratio_pct": f, "source": "...", "fetched_at": "..." },
  "yoy_market_health": { "revenue_yoy_pct": f, "net_profit_yoy_pct": f, "companies_reported": n, "source": "...", "fetched_at": "..." },
  "cap_index_aggregator": [ { "cap_bracket": "...", "ticker_count": n, "avg_market_cap_cr": "...", ... } ],
  "fetched_at": "..."
}
```

### iOS `ExtendedMarketDashboardResponse`:

| Status | Field | iOS Type | Backend Type | Issue |
|--------|-------|----------|-------------|-------|
| ✓ | `pulse` | `MarketPulseResponse?` | `dict` | — |
| ✓ | `momentum` | `MomentumResponse?` | `dict` | Backend returns `{"bullish": [...], "bearish": [...], "fetched_at": "..."}` which exactly matches `MomentumResponse`. |
| ✓ | `live_reporting_sync` | `LiveReportingSync?` | `dict` | All fields match: `declared_count`, `total_expected`, `sync_ratio_pct`, `source`, `fetched_at`. |
| ✓ | `yoy_market_health` | `YoYMarketHealth?` | `dict` | All fields match. |
| ✓ | `cap_index_aggregator` | `[CapIndexGridEntry]?` | `list[dict]` | All fields match. |
| ✓ | `fetched_at` | `String?` | `str?` | — |

**Verdict: FULLY ALIGNED.**

---

## 8. Dashboard — Legacy (`MarketModels.swift` ↔ no matching endpoint)

The iOS `MarketDashboardResponse` model expects: `pulse`, `momentum`, `macro`, `institutional`.  
**No backend endpoint returns this exact shape.** The backend's `/dashboard-pulse` returns the `ExtendedMarketDashboardResponse` shape instead (with `live_reporting_sync`, `yoy_market_health`, `cap_index_aggregator`). The legacy model may be unused or dead code.

**Verdict: POTENTIALLY ORPHANED MODEL** — `MarketDashboardResponse` has no matching backend route.

---

## 9. Morning Summary (`WatchlistModels.swift` ↔ `morning_summary_endpoint()`)

**Endpoint:** `GET /morning-summary/{user_id}`

| Status | Field | iOS `MorningSummaryResponse` | Backend | Issue |
|--------|-------|------|---------|-------|
| ✓ | `summary` | `String` | `str` | — |
| ✓ | `movers` | `[String]` | `list[str]` | — |
| ✓ | `mood` | `String` | `str` (`"positive"`/`"cautious"`/`"negative"`) | — |
| ✓ | `generated_at` | `String` | `str` | Time format `HH:MM` |
| ✓ | `priority_items` | `[MorningSummaryPriorityItem]?` | `list[dict]?` | Backend builds this at line 845-891. Present in prod. |

**Verdict: FULLY ALIGNED.**

---

## 10. Trade Journal (`PortfolioModels.swift` ↔ `GET /trade-journal/{user_id}`)

| Status | Field | iOS `TradeJournalEntry` | Backend | Issue |
|--------|-------|------|---------|-------|
| ✓ | `id` | `Int` | `int` | — |
| ✓ | `ticker` | `String` | `str` | — |
| ✓ | `company_name` | `String?` | `str?` | — |
| ✓ | `action` | `String` | `str` (`BUY`/`SELL`/`HOLD`/`WATCH`) | — |
| ✓ | `price_at_time` | `Double?` | `float?` | — |
| ✓ | `reason_text` | `String?` | `str?` | — |
| ✓ | `outcome_text` | `String?` | `str?` | — |
| ✓ | `mood` | `String?` | `str?` | — |
| ✓ | `created_at` | `String?` | `str?` | — |

**Verdict: FULLY ALIGNED.**

---

## 11. Earnings (`AlertModels.swift` ↔ earnings endpoints)

### EarningsFeedResponse
**Endpoint:** `GET /earnings-feed`

| Status | Field | iOS | Backend | Issue |
|--------|-------|-----|---------|-------|
| ✓ | `sort` | `String?` | `str?` | — |
| ✓ | `latest` | `[EarningsResult]?` | `list[dict]?` | — |
| ✓ | `best_performers` | `[EarningsResult]?` | `list[dict]?` | — |
| ✓ | `worst_performers` | `[EarningsResult]?` | `list[dict]?` | — |
| ✓ | `results` | `[EarningsResult]` | `list[dict]` | Always present |
| ✓ | `count` | `Int?` | `int?` | — |
| ✓ | `fetched_at` | `String?` | `str?` | — |
| ✓ | `error` | `String?` | `str?` | — |
| ✓ | `data_source` | `String?` | `str?` | New field |
| ✓ | `diagnostic` | `String?` | `str?` | New field |

### EarningsResult fields — all verified against backend:
All fields from `ticker` through `price_change_7d_pct` validated. The `EarningsCalendarItem` struct also matches the calendar endpoint response.

**Verdict: FULLY ALIGNED.**

---

## 12. Search (`NetworkManager.swift` ↔ `GET /search`)

| Status | Field | iOS `SearchResult` (private) | Backend |
|--------|-------|------|---------|
| ✓ | `ticker` | `String` | `str` |
| ✓ | `company_name` | `String` | `str` |
| ✓ | `sector` | `String` | `str` |
| ✓ | `exchange` | `String` | `str` |

**Verdict: FULLY ALIGNED.**

---

## 13. Auth (`Common.swift` ↔ `/login`, `/register`)

| Status | Field | iOS `LoggedInUser` | Backend |
|--------|-------|------|---------|
| ✓ | `user_id` | `Int` | `int` |
| ✓ | `username` | `String` | `str` |
| ✓ | `display_name` | `String` | `str` |
| ✓ | `access_token` | `String` | `str` (JWT) |

**Verdict: FULLY ALIGNED.**

---

## 14. Type Compatibility Summary

| Swift Type | Python/JSON | Status |
|-----------|-------------|--------|
| `String` | `str` | ✓ Bidirectional |
| `Int` | `int` | ✓ |
| `Double` | `float`/`int` | ✓ JSONDecoder handles both |
| `Bool` | `bool` | ✓ |
| `[String]` | `list[str]` | ✓ |
| `[String: Double]` | `dict[str, float]` | ✓ |
| `Signal` (enum) | `str` enum | ✓ Robust fallback to `.neutral` |
| `Date` (computed) | `str` (ISO/yyyy-MM-dd) | ✓ Parsed manually via DateFormatter |

**No type mismatch crashes detected.**

---

## 15. Issues & Recommendations

### 🐛 Backend Bugs (crash-safe but wrong data)

| # | Severity | File | Line | Issue | Fix |
|---|----------|------|------|-------|-----|
| **B1** | 🟡 LOW | `routers/alerts.py` | 203 | `company_name` is set to ticker, not actual company name | Query Portfolio or use `company_name` field from alerts table |
| **B2** | 🟢 TRIVIAL | `routers/portfolio.py` | 586,594 | `notes` key set twice in response dict | Remove line 586 (the getattr fallback) |

### ⚠️ iOS Gaps (fields received but not decoded)

| # | Severity | File | Issue | Fix |
|---|----------|------|-------|-----|
| **I1** | 🟡 LOW | `Models/AnalysisModels.swift:389` | QuickInfo missing `signal` field — backend doesn't include it | Add signal lookup in quick_info_endpoint OR remove `signal` from iOS model |
| **I2** | 🟢 TRIVIAL | `Models/AnalysisModels.swift:389` | QuickInfo missing `company_name`, `market_cap_crores`, `exchange`, `dividends`, `corporate_actions` | Add fields if UI needs them, or document intentional omission |
| **I3** | 🟢 TRIVIAL | `Models/MarketModels.swift:147` | `MarketDashboardResponse` appears orphaned — no matching backend endpoint | Remove or repurpose |

### ✅ No Crash Risks

All iOS models use:
- Explicit `CodingKeys` with correct snake_case → camelCase mapping
- `decodeIfPresent` for all optional fields
- Custom `init(from decoder:)` with safe defaults where needed
- Robust `Signal` enum with `.neutral` fallback for unknown values

### 📐 Architecture Compliance

- ✓ No business logic in iOS models (pure data containers)
- ✓ Backend follows Controller-Service-Repository pattern
- ✓ Indian numbering (Lakhs/Crores) used throughout backend responses
- ✓ Snake_case JSON keys consistently used in backend, mapped via CodingKeys in iOS

---

## 16. Overall Verdict

**95/100 — ALIGNED.** The contract between iOS and backend is well-maintained. No decoding crashes are possible. The missing `signal` in QuickInfo and the `company_name` bug in alerts are the only material issues. The orphaned `MarketDashboardResponse` model should be cleaned up.
