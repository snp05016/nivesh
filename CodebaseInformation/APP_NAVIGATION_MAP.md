# Nivesh App Navigation Map

> Last verified: 2026-06-16 from `ContentView.swift` and current Swift screen files.

## Global Surfaces

| Surface | Source | Notes |
|---|---|---|
| Authentication gate | `ContentView.swift`, `LoginScreen.swift` | Shows login when `AuthManager.isLoggedIn` is false |
| Launch overlay | `LaunchSequenceView.swift` | Controlled by `ContentView` launch state |
| Global Copilot | `CopilotScreen.swift` | Applied with `.withCopilot()` on root `ContentView` |
| Tutorial/global overlays | `GlobalOverlayModifier` in `ContentView.swift` | Handles tutorial and app-level overlays |

## Bottom Tab Bar

The app currently uses a 5-tab `TabView` in `ContentView.swift`:

| Index | Tab | Root view | Purpose |
|---|---|---|---|
| 0 | Home | `HomeScreen` | Personalized dashboard, home feed, analysis shortcuts, market summary, configurable sections |
| 1 | Markets | `MarketsView` | Market and quantitative tools hub |
| 2 | Ideas | `ExpertNetworkView` | Expert ideas, advisor feed, videos, consensus cards |
| 3 | News | `NewsMultimediaView` | News and multimedia feed |
| 4 | Portfolio | `PortfolioScreen` | Holdings, allocation, performance, trade journal, charts, portfolio intelligence |

## Markets Tab

`MarketsView` is defined in `ContentView.swift`. It has an overview plus section pages backed by the `MarketSection` enum.

| `MarketSection` case | Screen | Notes |
|---|---|---|
| `earnings` | `EarningsDashboardView` | Earnings calendar/feed, estimates, progress, post-result movers |
| `technical` | `TechnicalMomentumView` | Momentum and technical scan surface |
| `unlisted` | `PreIPOMarketplaceView` | Pre-IPO and unlisted marketplace experience |
| `screener` | `SearchScreen` | Stock discovery and search reuse |
| `alerts` | `AlertsScreen` | Price alerts and watch triggers |
| `strategy` | `StrategyLabScreen` | Backtesting and strategy lab |
| `nl_screener` | `NLScreenerScreen` | Natural language stock screener |
| `correlation` | `CorrelationMatrixScreen` | Portfolio correlation matrix |
| `anomalies` | `MarketAnomalyScreen` | Market anomaly scan |
| `sector_rotation` | `SectorRotationScreen` | Sector rotation view |
| `stress_test` | `StressTestScreen` | Portfolio shock scenarios |
| `earnings_surprise` | `EarningsSurpriseScreen` | Earnings surprise tracking |
| `options_strategy` | `OptionsStrategyScreen` | Multi-leg options payoff visualizer |

## Stock Deep-Dive Flow

Common stock navigation flow:

1. A ticker is selected from search, portfolio, watchlist, home feed, or another market surface.
2. `StockProfileView` shows the high-level profile, price/history context, and related actions.
3. `AnalysisScreen` shows the AI analysis output and supporting sections from `Views/Analysis/`.
4. `CompareScreen` is available for side-by-side stock comparison flows.

## Portfolio Surfaces

`PortfolioScreen` is the main root for holdings. Related screens and components include:

- `TradeJournalScreen` for trade journaling.
- `ValuationCalendarView` for valuation history/timeline.
- Portfolio charts through `NetworkManager.fetchPortfolioCharts`.
- Risk analysis, red flags, macro impact, timeframe conflicts, and advisory consensus through `NetworkManager` methods.

## Support and Settings

| Screen | Purpose |
|---|---|
| `SettingsScreen` | Server URL/theme/settings controls |
| `GlossaryBrowserView`, `TermDefinitionSheet` | Financial term help |
| `QuietHoursView` | Notification quiet hours |
| `SectorBlacklistView` | Sector preferences |
| `CrashLabView` | Diagnostics/testing surface |
| `ReportManagerView` | Local/downloaded report management |
| `AIHowItWorksView` | Explanation of the AI system |
| `FeatureHelpViews.swift` | Feature-specific help views |

## Notes For Copilot Navigation Answers

When guiding a user, prefer exact tab and section names:

- Natural language screener: Markets tab -> NL Screener.
- Sector rotation: Markets tab -> Sector Rotation.
- Portfolio stress test: Markets tab -> Stress Test, or portfolio intelligence surfaces where linked.
- Options payoff: Markets tab -> Options Strategy.
- Trade journal: Portfolio tab -> trade journal area.
- Expert ideas: Ideas tab.
- News: News tab.
- Stock search: Markets tab -> Screener, or global search if the current build exposes it in the header.
