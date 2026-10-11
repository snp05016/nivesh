// Models/AlertModels.swift
// Domain: Price alerts, earnings calendar/results, post-result movers, earnings errors

import SwiftUI

// MARK: - Price Alerts

struct PriceAlert: Codable, Identifiable {
    let id: Int
    let ticker: String
    let companyName: String
    let targetPrice: Double
    let direction: String  // "above" or "below"
    let currentPrice: Double?
    let distancePct: Double?
    let triggered: Bool
    let createdAt: String

    enum CodingKeys: String, CodingKey {
        case id, ticker, direction, triggered
        case companyName = "company_name"
        case targetPrice = "target_price"
        case currentPrice = "current_price"
        case distancePct = "distance_pct"
        case createdAt = "created_at"
    }

    var isAbove: Bool { direction == "above" }
}

struct AlertsResponse: Codable {
    let alerts: [PriceAlert]
}

struct AlertCheckResponse: Codable {
    let newlyTriggered: [TriggeredAlert]
    enum CodingKeys: String, CodingKey { case newlyTriggered = "newly_triggered" }
}

struct TriggeredAlert: Codable {
    let id: Int
    let ticker: String
    let targetPrice: Double
    let direction: String
    let currentPrice: Double
    enum CodingKeys: String, CodingKey {
        case id, ticker, direction
        case targetPrice = "target_price"
        case currentPrice = "current_price"
    }
}

// MARK: - Earnings Dashboard (Sections 1–5)

struct EarningsResult: Codable, Identifiable {
    var id: String { ticker + quarter }
    let ticker: String
    let companyName: String
    let quarter: String          // e.g. "Q4FY26"
    let resultDate: String       // "yyyy-MM-dd"
    let marketCap: String        // "large_cap" | "mid_cap" | "small_cap" | "nifty50"
    let revenue: Double          // in Crores
    let revenuePrev: Double      // same period last year
    let netProfit: Double        // in Crores
    let netProfitPrev: Double
    let grossProfit: Double?
    let grossProfitPrev: Double?
    let eps: Double?
    let epsPrev: Double?
    let ltp: Double
    let changePercent: Double
    let isConsolidated: Bool
    let reportedAt: String?      // ISO timestamp
    // Server-computed growth metrics (provided by ranked feed endpoint)
    let revenueGrowthPctServer: Double?
    let netProfitGrowthPctServer: Double?
    // Calendar sparkline data
    let sparkline: [Double]?
    let priceChange7dPct: Double?

    enum CodingKeys: String, CodingKey {
        case ticker, quarter, revenue, ltp, sparkline
        case companyName = "company_name"
        case resultDate = "result_date"
        case marketCap = "market_cap"
        case revenuePrev = "revenue_prev"
        case netProfit = "net_profit"
        case netProfitPrev = "net_profit_prev"
        case grossProfit = "gross_profit"
        case grossProfitPrev = "gross_profit_prev"
        case eps, epsPrev = "eps_prev"
        case changePercent = "change_percent"
        case isConsolidated = "is_consolidated"
        case reportedAt = "reported_at"
        case revenueGrowthPctServer = "revenue_growth_pct"
        case netProfitGrowthPctServer = "net_profit_growth_pct"
        case priceChange7dPct = "price_change_7d_pct"
    }

    /// Prefer server-computed growth, fall back to local calculation
    var revenueGrowthPct: Double {
        revenueGrowthPctServer ?? {
            guard revenuePrev > 0 else { return 0 }
            return ((revenue - revenuePrev) / revenuePrev) * 100
        }()
    }
    var netProfitGrowthPct: Double {
        netProfitGrowthPctServer ?? {
            guard netProfitPrev != 0 else { return 0 }
            return ((netProfit - netProfitPrev) / abs(netProfitPrev)) * 100
        }()
    }
    var netProfitMarginPct: Double {
        guard revenue > 0 else { return 0 }
        return (netProfit / revenue) * 100
    }
    var parsedReportedAt: Date? {
        reportedAt.flatMap(WireDate.parseISO)
    }
}

struct EarningsProgressResponse: Codable {
    let reported: Int
    let total: Int
    let yoyRevenueGrowthPct: Double?
    let yoyNetProfitGrowthPct: Double?
    let fetchedAt: String
    enum CodingKeys: String, CodingKey {
        case reported, total
        case yoyRevenueGrowthPct = "yoy_revenue_growth_pct"
        case yoyNetProfitGrowthPct = "yoy_net_profit_growth_pct"
        case fetchedAt = "fetched_at"
    }
}

struct EarningsCalendarDayResponse: Codable {
    let date: String
    let results: [EarningsCalendarItem]
    let count: Int
    let fetchedAt: String?
    let error: String?
    enum CodingKeys: String, CodingKey {
        case date, results, count
        case fetchedAt = "fetched_at"
        case error
    }
}

/// Calendar item with sparkline price history
struct EarningsCalendarItem: Codable, Identifiable {
    var id: String { "\(ticker)_\(resultDate)" }
    let ticker: String
    let companyName: String
    let quarter: String
    let resultDate: String
    let marketCap: String
    let revenue: Double
    let revenuePrev: Double
    let netProfit: Double
    let netProfitPrev: Double
    let eps: Double?
    let epsPrev: Double?
    let ltp: Double
    let changePercent: Double
    let isConsolidated: Bool
    let reportedAt: String?
    let sparkline: [Double]
    let priceChange7dPct: Double?
    enum CodingKeys: String, CodingKey {
        case ticker, quarter, revenue, eps, ltp, sparkline
        case companyName = "company_name"
        case resultDate = "result_date"
        case marketCap = "market_cap"
        case revenuePrev = "revenue_prev"
        case netProfit = "net_profit"
        case netProfitPrev = "net_profit_prev"
        case epsPrev = "eps_prev"
        case changePercent = "change_percent"
        case isConsolidated = "is_consolidated"
        case reportedAt = "reported_at"
        case priceChange7dPct = "price_change_7d_pct"
    }
}

struct EarningsFeedResponse: Codable {
    let sort: String?
    let latest: [EarningsResult]?
    let bestPerformers: [EarningsResult]?
    let worstPerformers: [EarningsResult]?
    let results: [EarningsResult]     // backward-compatible — always present
    let count: Int?
    let fetchedAt: String?
    let error: String?
    let dataSource: String?           // "database" | "yfinance_fallback" | "empty" (new server only)
    let diagnostic: String?           // human-readable explanation (new server only)
    enum CodingKeys: String, CodingKey {
        case sort, latest, results, count, error
        case bestPerformers = "best_performers"
        case worstPerformers = "worst_performers"
        case fetchedAt = "fetched_at"
        case dataSource = "data_source"
        case diagnostic
    }
}

struct EarningsEstimate: Codable, Identifiable {
    var id: String { ticker }
    let ticker: String
    let companyName: String
    let revenueEstimate: Double?
    let revenueActual: Double?
    let netProfitEstimate: Double?
    let netProfitActual: Double?
    let epsEstimate: Double?
    let epsActual: Double?
    enum CodingKeys: String, CodingKey {
        case ticker
        case companyName = "company_name"
        case revenueEstimate = "revenue_estimate"
        case revenueActual = "revenue_actual"
        case netProfitEstimate = "net_profit_estimate"
        case netProfitActual = "net_profit_actual"
        case epsEstimate = "eps_estimate"
        case epsActual = "eps_actual"
    }
    var revenueSurprisePct: Double? {
        guard let est = revenueEstimate, let act = revenueActual, est != 0 else { return nil }
        return ((act - est) / abs(est)) * 100
    }
    var netProfitSurprisePct: Double? {
        guard let est = netProfitEstimate, let act = netProfitActual, est != 0 else { return nil }
        return ((act - est) / abs(est)) * 100
    }
}

// MARK: - Post-Result Price Action (Section 5)

struct PostResultMover: Codable, Identifiable {
    var id: String { ticker }
    let ticker: String
    let companyName: String
    let resultDate: String
    let ltp: Double
    let changePercent: Double
    let volume: Int?
    enum CodingKeys: String, CodingKey {
        case ticker, ltp, volume
        case companyName = "company_name"
        case resultDate = "result_date"
        case changePercent = "change_percent"
    }
}

struct PostResultMoversResponse: Codable {
    let movers: [PostResultMover]
    let fetchedAt: String
    enum CodingKeys: String, CodingKey {
        case movers
        case fetchedAt = "fetched_at"
    }
}

// MARK: - Earnings Error Telemetry

struct EarningsErrorLogEntry: Codable, Identifiable {
    var id: Int
    let timestamp: String?
    let module: String
    let errorTrace: String
    let failedTicker: String?
    enum CodingKeys: String, CodingKey {
        case id, timestamp, module
        case errorTrace = "error_trace"
        case failedTicker = "failed_ticker"
    }
}

struct EarningsErrorLogsResponse: Codable {
    let errors: [EarningsErrorLogEntry]
    let count: Int
    let fetchedAt: String
    enum CodingKeys: String, CodingKey {
        case errors, count
        case fetchedAt = "fetched_at"
    }
}
