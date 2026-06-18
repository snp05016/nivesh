# iOS Dead Code Audit — Nivesh/StockApp

**Date:** 2026-06-18  
**Scope:** `/ios/StockApp/stockme/stockme/` (119 Swift files, excluding `build/` and `Pods/`)  
**Method:** Symbol-level cross-reference using `grep -rn` across all Swift files

---

## 1. DEAD View Structs (defined but never instantiated)

These `struct X: View` types exist but `Foo(` is never called anywhere — no `.sheet()`, no navigation destination, no direct body reference.

| View Struct | File | Line | Notes |
|---|---|---|---|
| `CountUpNumber` | `Utilities/Theme.swift` | 363 | Animated number counter — never used |
| `MicroTextStrip` | `DenominationBackground.swift` | 90 | Decorative micro-text — never used |
| `AnalysisLimitationsCard` | `Views/AnalysisScreen.swift` | 1031 | Disclaimer/limitations card — never instantiated (not even via `.sheet()`) |
| `SignalBadgePill` | `Components/SharedDarkComponents.swift` | 108 | Dark-mode signal badge — never instantiated |
| `GlowLineChart` | `Components/SharedDarkComponents.swift` | 133 | Dark-mode glowing chart — never instantiated |
| `ExpertProfileCard` | `Views/ExpertNetworkView.swift` | 498 | Expert profile card — never instantiated in ExpertNetworkView or elsewhere |

---

## 2. COMPLETELY ORPHANED FILE

| File | Issue |
|---|---|
| `Views/LaunchScreenView.swift` | Defines `LaunchScreenView` (line 98). Never referenced by any other file. The app uses `LaunchSequenceView` instead. **Entire file is dead.** |

---

## 3. TRIVIAL / EMPTY BODY VIEWS

These have `var body: some View { EmptyView() }` — they render nothing but some are still used as decorative placeholders.

| View Struct | File | Line | Status |
|---|---|---|---|
| `SecurityThread` | `BanknoteDesignSystem.swift` | 23 | `EmptyView()` body — never instantiated. Dead. |
| `RupeeWatermark` | `BanknoteDesignSystem.swift` | 29 | `EmptyView()` body — **still used** in `PortfolioScreen.swift` as a decorative element. Live but trivial. |

---

## 4. DEAD EXTENSION METHODS (never called outside definition file)

All defined in `Utilities/Extensions.swift`:

| Method/Computed Property | Line | Signature |
|---|---|---|
| `horizontalScrollFixed(height:)` | 29 | `func horizontalScrollFixed(height: CGFloat? = nil) -> some View` |
| `inkCard()` | 43 | `func inkCard() -> some View` |
| `timeGreeting` | 115 | `var timeGreeting: String` (Date extension) |
| `isBeforeMarketOpen` | 124 | `var isBeforeMarketOpen: Bool` (Date extension) |
| `generatePDFURL(for:)` | 134 | `static func generatePDFURL(for analysis: StockAnalysis?) -> URL` |
| `truncating(to:)` | 252 | `func truncating(to maxChars: Int) -> String` (String extension) |
| `accessibleFinancialText()` | 262 | `func accessibleFinancialText() -> some View` |

---

## 5. DEAD NETWORK MANAGER METHODS (NetworkManager+Sidebar.swift)

These methods in `NetworkManager+Sidebar.swift` are defined but **never called** from any file outside their own definition:

| Method | Line |
|---|---|
| `fetchMarketPulse()` | 61 |
| `fetchMacroAlternatives()` | 103 |
| `fetchInstitutionalFlow()` | 131 |
| `fetchMarketErrorLogs(limit:)` | 207 |
| `fetchEarningsErrorLogs(limit:)` | 258 |

These 5 methods collectively account for ~200 lines of dead async fetch code. The remaining methods in the same file (`fetchMomentum`, `fetchMarketDashboard`, `fetchExtendedMarketDashboard`, `fetchRankedEarningsFeed`, `fetchEarningsCalendar`, `fetchAdvisors`, `fetchIdeasFeed`) ARE called from live code.

---

## 6. MODEL TYPES WITH ONLY SELF-REFERENCE

These Codable structs are defined but **never decoded, instantiated, or referenced outside their own definition file** (except as a property type in a parent response struct in the same file):

| Model | File | Line | Used As |
|---|---|---|---|
| `JournalPattern` | `Models/PortfolioModels.swift` | 81 | Property `patterns` in `TradeJournalStatsResponse` (same file only) |
| `WinLossRatio` | `Models/PortfolioModels.swift` | 75 | Property `winLossRatio` in `TradeJournalStatsResponse` (same file only) |
| `MarketErrorEntry` | `Models/MarketModels.swift` | 304 | Property `errors` in `MarketErrorLogsResponse` (same file only) |
| `MorningSummaryPriorityItem` | `Models/WatchlistModels.swift` | 140 | Property `priorityItems` in `MorningSummaryResponse` (same file only) |
| `AuditorTenure` | `Models/AnalysisModels.swift` | 679 | Decoded in `StockAnalysis` CodingKeys (may be populated by API) |

*Note: These are part of API response hierarchies. They may be populated if their parent response types are ever decoded from the network. However, no code explicitly decodes or uses them individually.*

---

## 7. VIEWS USED ONLY IN THEIR DEFINING FILE (single-file scope)

These sub-views are instantiated within the same file where they're defined (common SwiftUI pattern). Not dead code, but flagged for review — some may represent premature abstraction:

### HomeScreen.swift (16 sub-views)
- `AdvisoryConsensusEmptyCard`, `ADBreathBar`, `PriorityPill`, `NiveshBulletRow`, `SignalBadge`, `MomentumStockRow`, `FundReturnRow`, `MarketMoodGauge`, `IndexCardView`, `MomentumRowView`, `CompactNewsCell`, `NewsDetailSheet`, `MacroGroupView`, `MacroRowView`, `IndexRow`, `HomeLayoutEditorSheet`

### CorrelationMatrixScreen.swift (4 sub-views)
- `DiversificationHero`, `CorrelationHeatmap`, `HeatmapCell`, `SectorConcentrationView`, `SuggestionsView`

### EarningsDashboardView.swift (5 sub-views)
- `VarianceTrackerView`, `VarianceCard`, `PostResultMonitorView`, `EarningsResultCard`, `MiniSparkline`, `EarningsProgressView`, `EarningsCalendarView`, `EarningsFeedView`, `ScreenerView`

### AnalysisScreen.swift (5 sub-views)
- `AnalysisLimitationsCard` **(DEAD)**, `NewsReaderView`, `NewsItemCard`, `NewsSectionView`, `CollapsibleSection`

### ExpertNetworkView.swift (3 sub-views)
- `ExpertProfileCard` **(DEAD)**, `ExpertPostCard`, `MarketIntelligenceCard`, `InsightCard`

### SharedDarkComponents.swift (2 sub-views)
- `SignalBadgePill` **(DEAD)**, `GlowLineChart` **(DEAD)**, `NiveshBrandChip`, `ChangeBadge`, `ScrubTooltipView`, `TimeRangeSelector`

---

## 8. SUMMARY STATISTICS

| Category | Count |
|---|---|
| Dead View structs | 7 (6 never instantiated + 1 empty body) |
| Orphaned files | 1 (`LaunchScreenView.swift`) |
| Dead extension methods | 7 |
| Dead network methods | 5 (~200 lines) |
| Self-referencing models | 5 |
| **Total dead symbols** | **25** |
| Probable dead code lines | **~350 lines** |

---

## 9. RECOMMENDATIONS

1. **Safe to delete:** `LaunchScreenView.swift` — entirely unreferenced.
2. **Safe to delete:** `CountUpNumber`, `MicroTextStrip`, `AnalysisLimitationsCard`, `SignalBadgePill`, `GlowLineChart`, `ExpertProfileCard` — confirmed zero instantiations.
3. **Safe to delete:** `SecurityThread` in `BanknoteDesignSystem.swift` — EmptyView body, never instantiated.
4. **Safe to delete:** 7 dead extension methods in `Utilities/Extensions.swift`.
5. **Safe to delete:** 5 dead `fetch*` methods in `NetworkManager+Sidebar.swift`.
6. **Review before deleting:** 5 self-referencing model types — verify with backend that these API responses are never returned before removing Codable structs.
7. **Consider extracting** the 40+ sub-views used only in their parent file to separate files per AGENTS.md §6.6 (SwiftUI Stack Overflow Prevention). Many of these exceed the 5-line threshold for inline `func -> some View`.
