// Models/UtilityModels.swift
// Domain: Diagnostic, telemetry, crash reporting, price history, quarterly financials, risk, brainstorming, timeframe conflicts

import SwiftUI

// MARK: - Price & History Points

struct PricePoint: Codable, Identifiable, WireDated {
    var id: String { date }
    let date: String
    let close: Double
    let volume: Double?
    /// Parsed once at decode; `.distantPast` when `date` is unparseable.
    let parsedDate: Date

    enum CodingKeys: String, CodingKey { case date, close, volume }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        date = try c.decode(String.self, forKey: .date)
        close = try c.decode(Double.self, forKey: .close)
        volume = try c.decodeIfPresent(Double.self, forKey: .volume)
        parsedDate = WireDate.day(date) ?? .distantPast
    }
}

struct NiftyPricePoint: Codable, Identifiable, WireDated {
    var id: String { date }
    let date: String
    let close: Double
    /// Parsed once at decode; `.distantPast` when `date` is unparseable.
    let parsedDate: Date

    enum CodingKeys: String, CodingKey { case date, close }

    init(date: String, close: Double) {
        self.date = date
        self.close = close
        parsedDate = WireDate.day(date) ?? .distantPast
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        self.init(date: try c.decode(String.self, forKey: .date),
                  close: try c.decode(Double.self, forKey: .close))
    }
}

struct OHLCVPoint: Codable, Identifiable, WireDated {
    var id: String { date }
    let date: String
    let open: Double
    let high: Double
    let low: Double
    let close: Double
    let volume: Double
    /// Parsed once at decode; `.distantPast` when `date` is unparseable.
    let parsedDate: Date

    enum CodingKeys: String, CodingKey { case date, open, high, low, close, volume }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        date = try c.decode(String.self, forKey: .date)
        open = try c.decode(Double.self, forKey: .open)
        high = try c.decode(Double.self, forKey: .high)
        low = try c.decode(Double.self, forKey: .low)
        close = try c.decode(Double.self, forKey: .close)
        volume = try c.decode(Double.self, forKey: .volume)
        parsedDate = WireDate.day(date) ?? .distantPast
    }
}

struct StockHistoryResponse: Codable {
    let ticker: String
    let exchange: String
    let period: String
    let prices: [OHLCVPoint]

    enum CodingKeys: String, CodingKey { case ticker, exchange, period, prices }

    /// Every construction path (decode, bare-array fallback, unified profile) drops undated rows.
    init(ticker: String, exchange: String, period: String, prices: [OHLCVPoint]) {
        self.ticker = ticker
        self.exchange = exchange
        self.period = period
        self.prices = prices.droppingUndated
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        self.init(ticker: try c.decode(String.self, forKey: .ticker),
                  exchange: try c.decode(String.self, forKey: .exchange),
                  period: try c.decode(String.self, forKey: .period),
                  prices: try c.decode([OHLCVPoint].self, forKey: .prices))
    }
}

// MARK: - Quarterly Financials

struct QuarterlyFinancial: Codable, Identifiable {
    var id: String { label }
    let label: String
    let revenue: Double
    let netProfit: Double
    enum CodingKeys: String, CodingKey {
        case label, revenue
        case netProfit = "net_profit"
    }
}

struct QuarterlyFinancialsResponse: Codable {
    let quarters: [QuarterlyFinancial]
    let promoterHistory: [PromoterHistoryPoint]
    enum CodingKeys: String, CodingKey {
        case quarters
        case promoterHistory = "promoter_history"
    }
}

struct PromoterHistoryPoint: Codable, Identifiable {
    var id: String { period }
    let period: String
    let promoter: Double
    let fii: Double
    let dii: Double
}

// MARK: - Risk Analysis

struct RiskAnalysis: Codable {
    let portfolioBeta: Double?
    let riskScore: Int?
    let riskScoreLabel: String?
    let sectorConcentration: [SectorConcentration]?
    let concentrationRisks: [ConcentrationWarning]?
    let highestCorrelationPair: CorrelationPair?
    let riskSummary: String?
    let totalPortfolioValue: Double?
    let holdingsCount: Int?

    enum CodingKeys: String, CodingKey {
        case portfolioBeta = "portfolio_beta"
        case riskScore = "risk_score"
        case riskScoreLabel = "risk_score_label"
        case sectorConcentration = "sector_concentration"
        case concentrationRisks = "concentration_risks"
        case highestCorrelationPair = "highest_correlation_pair"
        case riskSummary = "risk_summary"
        case totalPortfolioValue = "total_portfolio_value"
        case holdingsCount = "holdings_count"
    }
}

struct SectorConcentration: Codable, Identifiable {
    var id: String { sector }
    let sector: String
    let pct: Double
    let value: Double?
}

struct ConcentrationWarning: Codable, Identifiable {
    var id: String { ticker }
    let ticker: String
    let companyName: String?
    let pctOfPortfolio: Double

    enum CodingKeys: String, CodingKey {
        case ticker
        case companyName = "company_name"
        case pctOfPortfolio = "pct_of_portfolio"
    }
}

struct CorrelationPair: Codable {
    let tickerA: String
    let tickerB: String
    let correlation: Double

    enum CodingKeys: String, CodingKey {
        case tickerA = "ticker_a"
        case tickerB = "ticker_b"
        case correlation
    }
}

// MARK: - Timeframe Conflicts

struct TimeframeConflict: Codable, Identifiable {
    var id: String { ticker }
    let ticker: String
    let companyName: String?
    let shortTermPct: Double?
    let longTermPct: Double?
    let conflictType: String?
    let actionHint: String?
    let signal: String?
    let analysisDate: String?

    enum CodingKeys: String, CodingKey {
        case ticker, signal
        case companyName = "company_name"
        case shortTermPct = "short_upside_pct"
        case longTermPct = "long_upside_pct"
        case conflictType = "conflict_type"
        case actionHint = "explanation"
        case analysisDate = "analysis_date"
    }
}

struct TimeframeConflictsResponse: Codable {
    let conflicts: [TimeframeConflict]
    let conflictCount: Int

    enum CodingKeys: String, CodingKey {
        case conflicts
        case conflictCount = "conflict_count"
    }
}

// MARK: - Brainstorm

struct BrainstormResponse: Codable {
    let ideas: [BrainstormIdea]
}

struct BrainstormIdea: Codable, Identifiable {
    var id: String { ticker ?? title }
    let title: String
    let description: String
    let ticker: String?
}

// MARK: - Crash Reporting

struct CrashReport: Codable, Identifiable {
    let id: String
    let timestamp: String
    let type: CrashType
    let signalNumber: Int?
    let signalName: String?
    let exceptionName: String?
    let exceptionReason: String?
    let stackTrace: String
    let viewPath: String?
    let swiftFile: String?
    let approxLine: String?
    let device: String
    let osVersion: String
    let appVersion: String
    let buildNumber: String
    let classification: String
}

enum CrashType: String, Codable {
    case signal
    case exception
}

// MARK: - Analysis Error Diagnostics

struct DiagnosticError: Codable {
    let error: Bool
    let errorCode: String
    let errorTitle: String
    let errorDetail: String
    let errorType: String
    let phaseFailed: String?
    let ticker: String?
    let timestamp: String?
    let suggestedAction: String?
    let diagnosticInfo: String?
    let httpStatus: Int?

    enum CodingKeys: String, CodingKey {
        case error, ticker, timestamp
        case errorCode = "error_code"
        case errorTitle = "error_title"
        case errorDetail = "error_detail"
        case errorType = "error_type"
        case phaseFailed = "phase_failed"
        case suggestedAction = "suggested_action"
        case diagnosticInfo = "diagnostic_info"
        case httpStatus = "http_status"
    }
}

struct DiagnosticErrorPayload: Codable {
    let errorUuid: String
    let correlationId: String
    let timestamp: String
    let subsystem: String
    let classification: String
    let context: DiagnosticContext?
    let telemetry: DiagnosticTelemetry?
    let exception: DiagnosticException?
    let automatedRecoveryAction: String?

    enum CodingKeys: String, CodingKey {
        case errorUuid = "error_uuid"
        case correlationId = "correlation_id"
        case timestamp
        case subsystem
        case classification
        case context
        case telemetry
        case exception
        case automatedRecoveryAction = "automated_recovery_action"
    }
}

struct DiagnosticContext: Codable {
    let targetTicker: String?
    let marketHoursState: String?
    let activeDataProvider: String?

    enum CodingKeys: String, CodingKey {
        case targetTicker = "target_ticker"
        case marketHoursState = "market_hours_state"
        case activeDataProvider = "active_data_provider"
    }
}

struct DiagnosticTelemetry: Codable {
    let httpMethod: String?
    let requestRoute: String?
    let iosSwiftFile: String?
    let failingNodeContract: String?

    enum CodingKeys: String, CodingKey {
        case httpMethod = "http_method"
        case requestRoute = "request_route"
        case iosSwiftFile = "ios_swift_file"
        case failingNodeContract = "failing_node_contract"
    }
}

struct DiagnosticException: Codable {
    let type: String?
    let message: String?
    let cleanedTraceback: [String]?

    enum CodingKeys: String, CodingKey {
        case type
        case message
        case cleanedTraceback = "cleaned_traceback"
    }
}

struct AnalysisErrorInfo {
    let diagnostic: DiagnosticError?
    let rawError: String
    let httpStatusCode: Int
    let responseBody: String
    let responseHeaders: String
    let requestUrl: String
    let elapsedSeconds: Double
    let quickInfoElapsed: Double?
    let isRetryable: Bool
    let isMockMode: Bool
    let isDeepScan: Bool

    var isRateLimit: Bool { diagnostic?.errorType == "rate_limit" }
    var isServerError: Bool { diagnostic?.errorType == "server" }
    var isAIFailure: Bool { diagnostic?.errorType == "ai_generation" }
    var isConnectionError: Bool { diagnostic?.errorType == "connection" }

    var iconName: String {
        if isRateLimit { return "hand.raised.slash.fill" }
        if isServerError { return "xmark.shield.fill" }
        if isAIFailure { return "brain.head.profile" }
        if isConnectionError { return "wifi.slash" }
        return "exclamationmark.triangle.fill"
    }

    var badgeText: String {
        if isRateLimit { return "RATE LIMITED" }
        if isServerError { return "SERVER ERROR" }
        if isAIFailure { return "AI FAILURE" }
        if isConnectionError { return "CONNECTION LOST" }
        return "PROCESS ERROR"
    }

    var displayTitle: String {
        diagnostic?.errorTitle ?? "Analysis Failed"
    }

    var displayDetail: String {
        diagnostic?.errorDetail ?? rawError
    }

    /// Plain-language description of the failure. No URLs, status codes or raw bodies.
    var userMessage: String {
        if isRateLimit { return "Too many analysis requests right now." }
        if isConnectionError { return "Couldn't reach Nivesh. Check your internet connection." }
        if isAIFailure { return "The AI analysis couldn't be completed this time." }
        if isServerError { return "Nivesh is having trouble right now." }
        return "The analysis couldn't be completed."
    }

    var suggestedActionText: String {
        switch diagnostic?.suggestedAction {
        case "WAIT": return "Please wait a minute and try again."
        case "CHECK_CONFIG", "CONTACT_SUPPORT":
            return "The analysis service is temporarily unavailable. Please try again later."
        default: return "Tap Retry to run the analysis again."
        }
    }
}
