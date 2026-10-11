// Models/WatchlistModels.swift
// Domain: Watchlist items, signal warnings, red flags, screener, morning summary, daily action

import SwiftUI

// MARK: - Watchlist

struct WatchlistItem: Codable, Identifiable {
    var id: String { ticker }
    let ticker: String
    let companyName: String
    let exchange: String
    let currentPrice: Double
    /// "live" | "unavailable"; when unavailable, currentPrice is a 0.0 placeholder.
    let priceStatus: String?
    let dayChangePct: Double
    let lastSignal: String?
    let lastSignalDate: String?
    let asmGsmStatus: String?

    enum CodingKeys: String, CodingKey {
        case ticker, exchange
        case companyName = "company_name"
        case currentPrice = "current_price"
        case priceStatus = "price_status"
        case dayChangePct = "day_change_pct"
        case lastSignal = "last_signal"
        case lastSignalDate = "last_signal_date"
        case asmGsmStatus = "asm_gsm_status"
    }
}

struct WatchlistEvent: Codable {
    let eventType: String?
    let eventDate: String?
    let daysUntil: Int?

    enum CodingKeys: String, CodingKey {
        case eventType = "event_type"
        case eventDate = "event_date"
        case daysUntil = "days_until"
    }
}

// MARK: - Signal Warnings

struct SignalWarning: Codable, Identifiable {
    var id: String { ticker }
    let ticker: String
    let currentSignal: String
    let previousSignal: String?
    let signalFlipped: Bool
    let confidenceDropped: Bool
    let isBearish: Bool
    let analysisDate: String

    enum CodingKeys: String, CodingKey {
        case ticker
        case currentSignal = "current_signal"
        case previousSignal = "previous_signal"
        case signalFlipped = "signal_flipped"
        case confidenceDropped = "confidence_dropped"
        case isBearish = "is_bearish"
        case analysisDate = "analysis_date"
    }
}

struct SignalWarningsResponse: Codable {
    let warnings: [SignalWarning]
}

// MARK: - Red Flags

struct RedFlag: Codable, Identifiable {
    var id: String { ticker + flagType }
    let ticker: String
    let severity: String
    let flagType: String
    let detail: String

    enum CodingKeys: String, CodingKey {
        case ticker, severity, detail
        case flagType = "flag_type"
    }
}

struct RedFlagsResponse: Codable {
    let flags: [RedFlag]
    let summary: String?
    let totalFlags: Int
    let critical: Int
    let warnings: Int
    let watches: Int

    enum CodingKeys: String, CodingKey {
        case flags, summary
        case totalFlags = "total_flags"
        case critical, warnings, watches
    }
}

// MARK: - Screener

struct ScreenerResult: Codable, Identifiable {
    var id: String { ticker }
    let ticker: String
    let companyName: String?
    let signal: String?
    let confidencePct: Int?
    let reason: String?
    let fScore: Int?
    let peRatio: Double?
    let profitGrowthPct: Double?
    let rsi: Double?
    let pcr: Double?
    let currentPrice: Double?
    let changePercent: Double?
    let sparkline: [Double]?

    enum CodingKeys: String, CodingKey {
        case ticker, signal, reason, sparkline
        case companyName = "company_name"
        case confidencePct = "confidence_pct"
        case fScore = "f_score"
        case peRatio = "pe_ratio"
        case profitGrowthPct = "profit_growth_pct"
        case rsi = "rsi"
        case pcr = "pcr"
        case currentPrice = "current_price"
        case changePercent = "change_percent"
    }
}

struct ScreenerBookmark: Codable, Identifiable {
    var id: String { presetKey }
    let presetKey: String
    let displayName: String
    let savedAt: String
}

// MARK: - Morning Summary

struct MorningSummaryPriorityItem: Codable, Identifiable {
    var id: String { "\(ticker)|\(type)" }
    let priority: Int
    let type: String
    let ticker: String
    let message: String
}

struct MorningSummaryResponse: Codable {
    let summary: String
    let movers: [String]
    let mood: String
    let generatedAt: String
    let priorityItems: [MorningSummaryPriorityItem]?

    enum CodingKeys: String, CodingKey {
        case summary, movers, mood
        case generatedAt = "generated_at"
        case priorityItems = "priority_items"
    }
}

// MARK: - Daily Action

struct DailyActionResponse: Codable {
    let action: String
    let urgency: String  // "high" | "medium" | "low"
}
