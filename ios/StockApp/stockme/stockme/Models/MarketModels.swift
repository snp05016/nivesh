// Models/MarketModels.swift
// Domain: Market indices, pulse, momentum, screener sectors, institutional flows, macro context, top movers

import SwiftUI

// MARK: - Live Market Indices

struct LiveMarketIndex: Codable, Identifiable {
    var id: String { ticker }
    let name: String
    let ticker: String
    let value: Double
    let changePct: Double
    let changeAbs: Double

    enum CodingKeys: String, CodingKey {
        case name, ticker, value
        case changePct = "change_pct"
        case changeAbs = "change_abs"
    }
}

struct MarketIndicesResponse: Codable {
    let indices: [LiveMarketIndex]
    let fetchedAt: String

    enum CodingKeys: String, CodingKey {
        case indices
        case fetchedAt = "fetched_at"
    }
}

// MARK: - Sidebar Market Pulse

struct SidebarIndex: Codable, Identifiable {
    var id: String { name }
    let name: String
    let value: String
    let changePts: String
    let changePct: String
    let direction: String
    enum CodingKeys: String, CodingKey {
        case name, value
        case changePts = "change_pts"
        case changePct = "change_pct"
        case direction
    }
}

struct MarketPulseResponse: Codable {
    let indices: [SidebarIndex]
    let advances: Int
    let declines: Int
    let unchanged: Int
    let breadthRatio: Double?
    let fetchedAt: String
    enum CodingKeys: String, CodingKey {
        case indices, advances, declines, unchanged
        case breadthRatio = "breadth_ratio"
        case fetchedAt = "fetched_at"
    }
}

// MARK: - Momentum

struct MomentumTicker: Codable, Identifiable {
    var id: String { ticker }
    let ticker: String
    let lastPrice: Double
    let ma20: Double
    let ma50: Double
    let sparkline: [Double]
    let trendDate: String
    let crossover: String
    enum CodingKeys: String, CodingKey {
        case ticker
        case lastPrice = "last_price"
        case ma20, ma50, sparkline
        case trendDate = "trend_date"
        case crossover
    }
}

struct MomentumResponse: Codable {
    let bullish: [MomentumTicker]
    let bearish: [MomentumTicker]
    let fetchedAt: String
    enum CodingKeys: String, CodingKey {
        case bullish, bearish
        case fetchedAt = "fetched_at"
    }
}

// MARK: - Macro Alternatives

struct MacroItem: Codable, Identifiable {
    var id: String { ticker }
    let name: String
    let ticker: String
    let price: Double
    let changePts: Double
    let changePct: Double
    let direction: String
    enum CodingKeys: String, CodingKey {
        case name, ticker, price
        case changePts = "change_pts"
        case changePct = "change_pct"
        case direction
    }
}

struct MacroAlternativesResponse: Codable {
    let items: [MacroItem]
    let fetchedAt: String
    enum CodingKeys: String, CodingKey {
        case items
        case fetchedAt = "fetched_at"
    }
}

// MARK: - Institutional Flows

struct MutualFund: Codable, Identifiable {
    var id: String { name }
    let name: String
    let category: String
    let oneYearReturnPct: Double
    let aumCr: Double?
    enum CodingKeys: String, CodingKey {
        case name, category
        case oneYearReturnPct = "one_year_return_pct"
        case aumCr = "aum_cr"
    }
}

struct InstitutionalFlowResponse: Codable {
    let funds: [MutualFund]
    let fetchedAt: String
    enum CodingKeys: String, CodingKey {
        case funds
        case fetchedAt = "fetched_at"
    }
}

// MARK: - Mutual Fund
// MutualFundDTO now lives in Models/MutualFundModels.swift (richer MF Router
// fields: scheme_code, aum_cr, returns_1y/3y/5y, expense_ratio, risk_level, etc).

// MARK: - Combined Market Dashboard

struct MarketDashboardResponse: Codable {
    let pulse: MarketPulseResponse?
    let momentum: MomentumResponse?
    let macro: MacroAlternativesResponse?
    let institutional: InstitutionalFlowResponse?
    let fetchedAt: String?
    enum CodingKeys: String, CodingKey {
        case pulse, momentum, macro, institutional
        case fetchedAt = "fetched_at"
    }
}

// MARK: - Sector Performance

struct SectorPerformance: Codable, Identifiable {
    var id: String { name }
    let name: String
    let ticker: String
    let value: Double
    let changePct: Double
    let changeAbs: Double

    enum CodingKeys: String, CodingKey {
        case name, ticker, value
        case changePct = "change_pct"
        case changeAbs = "change_abs"
    }
}

// MARK: - Analyst Ratings

struct AnalystRating: Codable, Identifiable {
    var id: String { "\(firm)|\(period)" }
    let firm: String
    let grade: String
    let period: String
}

struct AnalystRatingsResponse: Codable {
    let ratings: [AnalystRating]
    let consensus: String?
    let buy: Int
    let hold: Int
    let sell: Int
}

// MARK: - Macro Impact

struct MacroImpactItem: Codable, Identifiable {
    var id: String { ticker }
    let ticker: String
    let impactStatement: String?
    let direction: String?

    enum CodingKeys: String, CodingKey {
        case ticker
        case impactStatement = "impact_statement"
        case direction
    }
}

struct MacroImpactResponse: Codable {
    let impacts: [MacroImpactItem]
    let macroReadings: MacroReadings?
    let generatedAt: String?

    enum CodingKeys: String, CodingKey {
        case impacts
        case macroReadings = "macro_readings"
        case generatedAt = "generated_at"
    }
}

struct MacroReadings: Codable {
    let brentOilUsd: Double?
    let indiaVix: Double?
    let usdInr: Double?
    let rbiRepoRatePct: Double?

    enum CodingKeys: String, CodingKey {
        case brentOilUsd = "brent_oil_usd"
        case indiaVix = "india_vix"
        case usdInr = "usd_inr"
        case rbiRepoRatePct = "rbi_repo_rate_pct"
    }
}

struct MacroStrip: Codable {
    let usdInr: Double?
    let crudeOilUsd: Double?
    let brentOilUsd: Double?
    let indiaVix: Double?
    let rbiRepoRatePct: Double?
    let rbiStance: String?

    enum CodingKeys: String, CodingKey {
        case usdInr = "usd_inr"
        case crudeOilUsd = "crude_oil_usd"
        case brentOilUsd = "brent_oil_usd"
        case indiaVix = "india_vix"
        case rbiRepoRatePct = "rbi_repo_rate_pct"
        case rbiStance = "rbi_stance"
    }
}

// MARK: - Core Markets Data Contracts (dashboard-pulse extended payload)

struct LiveReportingSync: Codable {
    let declaredCount: Int
    let totalExpected: Int
    let syncRatioPct: Double
    let source: String
    let fetchedAt: String
    enum CodingKeys: String, CodingKey {
        case declaredCount = "declared_count"
        case totalExpected = "total_expected"
        case syncRatioPct = "sync_ratio_pct"
        case source
        case fetchedAt = "fetched_at"
    }
}

struct YoYMarketHealth: Codable {
    let revenueYoYPct: Double
    let netProfitYoYPct: Double
    let companiesReported: Int
    let source: String
    let fetchedAt: String
    enum CodingKeys: String, CodingKey {
        case revenueYoYPct = "revenue_yoy_pct"
        case netProfitYoYPct = "net_profit_yoy_pct"
        case companiesReported = "companies_reported"
        case source
        case fetchedAt = "fetched_at"
    }
}

struct CapIndexGridEntry: Codable, Identifiable {
    var id: String { capBracket }
    let capBracket: String
    let tickerCount: Int
    let avgMarketCapCr: String
    let avgRevenueCr: String
    let avgNetProfitCr: String
    let avgPeRatio: Double?
    let avgRevenueYoYPct: Double?
    enum CodingKeys: String, CodingKey {
        case capBracket = "cap_bracket"
        case tickerCount = "ticker_count"
        case avgMarketCapCr = "avg_market_cap_cr"
        case avgRevenueCr = "avg_revenue_cr"
        case avgNetProfitCr = "avg_net_profit_cr"
        case avgPeRatio = "avg_pe_ratio"
        case avgRevenueYoYPct = "avg_revenue_yoy_pct"
    }
}

struct MarketErrorEntry: Codable, Identifiable {
    var id: Int
    let timestamp: String?
    let component: String
    let errorMessage: String
    let contextTicker: String?
    enum CodingKeys: String, CodingKey {
        case id, timestamp, component
        case errorMessage = "error_message"
        case contextTicker = "context_ticker"
    }
}

struct MarketErrorLogsResponse: Codable {
    let errors: [MarketErrorEntry]
    let count: Int
    let fetchedAt: String
    enum CodingKeys: String, CodingKey {
        case errors, count
        case fetchedAt = "fetched_at"
    }
}

// MARK: - Extended Market Dashboard (with new core markets sections)

struct ExtendedMarketDashboardResponse: Codable {
    let pulse: MarketPulseResponse?
    let momentum: MomentumResponse?
    let liveReportingSync: LiveReportingSync?
    let yoyMarketHealth: YoYMarketHealth?
    let capIndexAggregator: [CapIndexGridEntry]?
    let fetchedAt: String?
    enum CodingKeys: String, CodingKey {
        case pulse, momentum
        case liveReportingSync = "live_reporting_sync"
        case yoyMarketHealth = "yoy_market_health"
        case capIndexAggregator = "cap_index_aggregator"
        case fetchedAt = "fetched_at"
    }
}

// MARK: - Top Movers (Section 9 — Technical Momentum sub-tabs 3/4/5/6)

struct TopMover: Codable, Identifiable {
    var id: String { ticker }
    let ticker: String
    let name: String
    let price: Double
    let changePct: Double
    let changeAbs: Double
    let volume: Int
    let value: Double
    enum CodingKeys: String, CodingKey {
        case ticker, name, price, volume, value
        case changePct = "change_pct"
        case changeAbs = "change_abs"
    }
}

struct TopMoversResponse: Codable {
    let gainers: [TopMover]
    let losers: [TopMover]
    let activeByValue: [TopMover]
    let activeByVolume: [TopMover]
    let fetchedAt: String
    enum CodingKeys: String, CodingKey {
        case gainers, losers
        case activeByValue = "active_by_value"
        case activeByVolume = "active_by_volume"
        case fetchedAt = "fetched_at"
    }
}

// MARK: - Macro Context (Stock Profile)

struct MacroContextData: Codable {
    let ticker: String
    let macroStrip: MacroStrip?
    let fiiDiiTrend: FIIDIITrendData?
    let sectorPerformance: MacroSectorPerf?
    let marketMood: MarketMoodData?
    let stockImpact: [StockMacroImpact]?
    let summary: String?
    let aiSummary: String?
    let aiSentiment: String?

    enum CodingKeys: String, CodingKey {
        case ticker
        case macroStrip = "macro_strip"
        case fiiDiiTrend = "fii_dii_trend"
        case sectorPerformance = "sector_performance"
        case marketMood = "market_mood"
        case stockImpact = "stock_impact"
        case summary
        case aiSummary = "ai_summary"
        case aiSentiment = "ai_sentiment"
    }
}

struct FIIDIITrendData: Codable {
    let fiiNet5dCrores: Double?
    let diiNet5dCrores: Double?
    let bias: String?

    enum CodingKeys: String, CodingKey {
        case fiiNet5dCrores = "fii_net_5d_crores"
        case diiNet5dCrores = "dii_net_5d_crores"
        case bias
    }
}

struct MacroSectorPerf: Codable {
    let name: String?
    let changePct: Double?
    let niftyChangePct: Double?

    enum CodingKeys: String, CodingKey {
        case name
        case changePct = "change_pct"
        case niftyChangePct = "nifty_change_pct"
    }
}

struct MarketMoodData: Codable {
    let zone: String?
    let score: Int?
    let indiaVix: Double?
    let interpretation: String?

    enum CodingKeys: String, CodingKey {
        case zone, score
        case indiaVix = "india_vix"
        case interpretation
    }
}

struct StockMacroImpact: Codable, Identifiable {
    var id: String { factor }
    let factor: String
    let value: String
    let impact: String
    let detail: String
}

// MARK: - Earnings Event

struct EarningsEvent: Codable, Identifiable {
    var id: String { ticker + earningsDate }
    let ticker: String
    let earningsDate: String
    let daysAway: Int
    enum CodingKeys: String, CodingKey {
        case ticker
        case earningsDate = "earnings_date"
        case daysAway = "days_away"
    }
}

// MARK: - Pre-IPO / Unlisted Shares

struct UnlistedCompany: Identifiable {
    let id: String
    let name: String
    let sector: String
    let ltp: Double
    let prevLtp: Double
    let description: String
    let keyMetrics: [String: String]
    var isBookmarked: Bool = false

    var changeAbs: Double { ltp - prevLtp }
    var changePct: Double { prevLtp > 0 ? ((ltp - prevLtp) / prevLtp) * 100 : 0 }
}
