// Models/PortfolioModels.swift
// Domain: Portfolio holdings, trade journal, portfolio charts, valuation

import SwiftUI

// MARK: - Portfolio Holdings

struct PortfolioHolding: Codable, Identifiable {
    var id: String { stock.ticker }
    let stock: Stock
    let shares: Double
    let buyPrice: Double
    let purchaseDate: String?
    let notes: String?
    let targetPrice: Double?
    /// "live" | "stale" | "unavailable" from GET /portfolio (set by NetworkManager, not decoded).
    var priceStatus: String = "live"
    var priceAsOf: String? = nil

    /// False when the server had no quote: the holding is valued at cost, never at ₹0.
    var priceAvailable: Bool { priceStatus != "unavailable" }
    var currentValue: Double { priceAvailable ? stock.currentPrice * shares : investedValue }
    var investedValue: Double { buyPrice * shares }
    var pnl: Double { currentValue - investedValue }
    var pnlPercent: Double { investedValue > 0 ? (pnl / investedValue) * 100 : 0 }
    /// Today's P&L = shares x (price - prevClose). changePercent is relative to the
    /// previous close (backend day_change_pct), so it must not be applied to today's price.
    var dayPnL: Double {
        let p = stock.changePercent
        guard priceAvailable, p > -100 else { return 0 }
        return currentValue * p / (100 + p)
    }

    enum CodingKeys: String, CodingKey {
        case stock, shares, buyPrice = "buy_price", notes
        case purchaseDate = "purchase_date"
        case targetPrice = "target_price"
    }
}

// MARK: - Trade Journal

struct TradeJournalEntry: Codable, Identifiable {
    let id: Int
    let ticker: String
    let companyName: String?
    let action: String
    let priceAtTime: Double?
    let reasonText: String?
    let outcomeText: String?
    let mood: String?
    let createdAt: String?

    enum CodingKeys: String, CodingKey {
        case id, ticker, action, mood
        case companyName = "company_name"
        case priceAtTime = "price_at_time"
        case reasonText = "reason_text"
        case outcomeText = "outcome_text"
        case createdAt = "created_at"
    }
}

struct TradeJournalResponse: Codable {
    let entries: [TradeJournalEntry]
    let total: Int
}

struct TradeJournalStatsResponse: Codable {
    let totalEntries: Int
    let mostJournalledTicker: String?
    let winLossRatio: WinLossRatio?
    let topKeywords: [KeywordCount]?
    let actionBreakdown: [String: Int]?
    let patterns: [JournalPattern]?

    enum CodingKeys: String, CodingKey {
        case totalEntries = "total_entries"
        case mostJournalledTicker = "most_journalled_ticker"
        case winLossRatio = "win_loss_ratio"
        case topKeywords = "top_keywords"
        case actionBreakdown = "action_breakdown"
        case patterns
    }
}

struct KeywordCount: Codable, Equatable {
    let word: String
    let count: Int
}

struct WinLossRatio: Codable {
    let wins: Int
    let losses: Int
    let ratio: Double?
}

struct JournalPattern: Codable {
    let pattern: String
}

// MARK: - Portfolio Charts

struct ChartItem: Codable, Identifiable {
    var id: String { filename }
    let filename: String
    let title: String
    let description: String
    let url: String
}

struct PortfolioChartsResponse: Codable {
    let charts: [ChartItem]
    let count: Int
}
