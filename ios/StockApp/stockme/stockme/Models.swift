// Models.swift — umbrella re-export (Candidate 2: domain-sliced)
// See Models/ subdirectory for individual domain files

// This file intentionally re-exports nothing directly.
// Import from Models/ sub-files in your feature files instead:
//   - Models/Common.swift        — Signal, Stock, LoggedInUser, LocalReportManager
//   - Models/AnalysisModels.swift — StockAnalysis, QuickInfo, StockProfileResponse, v2 extreme bundles, etc.
//   - Models/PortfolioModels.swift — PortfolioHolding, TradeJournalEntry, PortfolioChartsResponse, ChartItem
//   - Models/MarketModels.swift   — LiveMarketIndex, MarketPulseResponse, SectorPerformance, InstitutionalFlow, etc.
//   - Models/WatchlistModels.swift — WatchlistItem, SignalWarning, RedFlag, ScreenerResult, MorningSummary, DailyAction
//   - Models/AlertModels.swift    — PriceAlert, EarningsResult, EarningsFeedResponse, PostResultMover, etc.
//   - Models/AdvisoryModels.swift — AdvisoryConsensus, AdvisorInsightRow, AdvisorBiography, IdeasFeed, Harvester
//   - Models/OptionsModels.swift  — OptionsPayoffResponse, OptionsPayoffRequest, OptionLeg, PayoffPoint
//   - Models/UtilityModels.swift  — RiskAnalysis, PricePoint, OHLCVPoint, QuarterlyFinancials, Diagnostics, Brainstorm
