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

    var currentValue: Double { stock.currentPrice * shares }
    var investedValue: Double { buyPrice * shares }
    var pnl: Double { currentValue - investedValue }
    var pnlPercent: Double { investedValue > 0 ? (pnl / investedValue) * 100 : 0 }

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
    let topKeywords: [String]?
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
