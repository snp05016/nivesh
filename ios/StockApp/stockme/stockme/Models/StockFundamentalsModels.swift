// Models/StockFundamentalsModels.swift
// Domain: Financial statements, shareholding patterns, corporate actions, valuation, risk signals

import Foundation

// MARK: - Financial Statements

struct FinancialStatementResponse: Codable {
    let ticker: String
    let periodType: String
    let consolidation: String
    let periods: [FinancialPeriod]
    let lineItems: [FinancialLineItem]
    let availablePeriods: [String]

    enum CodingKeys: String, CodingKey {
        case ticker, consolidation, periods
        case periodType = "period_type"
        case lineItems = "line_items"
        case availablePeriods = "available_periods"
    }
}

struct FinancialPeriod: Codable, Identifiable {
    var id: String { label }
    let label: String
    let endDate: String
    let isBank: Bool

    enum CodingKeys: String, CodingKey {
        case label
        case endDate = "end_date"
        case isBank = "is_bank"
    }
}

struct FinancialLineItem: Codable, Identifiable {
    var id: String { label }
    let label: String
    let group: String
    let values: [String: Double]
    let qoqChangePct: [String: Double]
    let yoyChangePct: [String: Double]
    let isPercentage: Bool
    let bankSpecific: Bool

    enum CodingKeys: String, CodingKey {
        case label, group, values
        case qoqChangePct = "qoq_change_pct"
        case yoyChangePct = "yoy_change_pct"
        case isPercentage = "is_percentage"
        case bankSpecific = "bank_specific"
    }
}

// MARK: - Shareholding Patterns

struct ShareholdingResponse: Codable {
    let ticker: String
    let latestQuarter: String
    let availableQuarters: [String]
    let categories: [ShareholderCategory]
    let topHolders: [TopHolder]
    let promoterPledgePct: Double?
    let promoterPledgeQoqChange: Double?
    let holdingTrend: [ShareholdingQuarter]

    enum CodingKeys: String, CodingKey {
        case ticker, categories
        case latestQuarter = "latest_quarter"
        case availableQuarters = "available_quarters"
        case topHolders = "top_holders"
        case promoterPledgePct = "promoter_pledge_pct"
        case promoterPledgeQoqChange = "promoter_pledge_qoq_change"
        case holdingTrend = "holding_trend"
    }
}

struct ShareholderCategory: Codable, Identifiable {
    var id: String { name }
    let name: String
    let warning: String?
    let currentPct: Double
    let qoqChangeBps: Double?
    let yoyChangeBps: Double?

    enum CodingKeys: String, CodingKey {
        case name, warning
        case currentPct = "current_pct"
        case qoqChangeBps = "qoq_change_bps"
        case yoyChangeBps = "yoy_change_bps"
    }
}

struct TopHolder: Codable, Identifiable {
    var id: String { name }
    let name: String
    let category: String
    let sharesCrores: Double
    let holdingPct: Double
    let qoqChangeBps: Double?

    enum CodingKeys: String, CodingKey {
        case name, category
        case sharesCrores = "shares_crores"
        case holdingPct = "holding_pct"
        case qoqChangeBps = "qoq_change_bps"
    }
}

struct ShareholdingQuarter: Codable, Identifiable {
    var id: String { quarter }
    let quarter: String
    let promoterPct: Double
    let fiiPct: Double
    let diiPct: Double
    let publicPct: Double
    let othersPct: Double

    enum CodingKeys: String, CodingKey {
        case quarter
        case promoterPct = "promoter_pct"
        case fiiPct = "fii_pct"
        case diiPct = "dii_pct"
        case publicPct = "public_pct"
        case othersPct = "others_pct"
    }
}

// MARK: - Corporate Actions

struct CorporateAction: Codable, Identifiable {
    var id: UUID = UUID()
    let type: String
    let announcementDate: String
    let exDate: String
    let recordDate: String
    let details: String
    let amount: Double?
    let ratio: String?

    enum CodingKeys: String, CodingKey {
        case id, type, details, amount, ratio
        case announcementDate = "announcement_date"
        case exDate = "ex_date"
        case recordDate = "record_date"
    }
}

struct CorporateActionsResponse: Codable {
    let ticker: String
    let actions: [CorporateAction]
    let upcoming: [CorporateAction]
    let dividendYieldTtm: Double?
    let dividendPayoutRatio: Double?

    enum CodingKeys: String, CodingKey {
        case ticker, actions, upcoming
        case dividendYieldTtm = "dividend_yield_ttm"
        case dividendPayoutRatio = "dividend_payout_ratio"
    }
}

// MARK: - Valuation

struct ValuationSnapshot: Codable {
    let ticker: String
    let peCurrent: Double?
    let pe5yrAvg: Double?
    let peSectorAvg: Double?
    let pe5yrHigh: Double?
    let pe5yrLow: Double?
    let pbCurrent: Double?
    let pb5yrAvg: Double?
    let evEbitda: Double?
    let marketCapCrores: Double
    let enterpriseValueCrores: Double?
    let dividendYield: Double?
    let earningsYield: Double?
    let pegRatio: Double?

    enum CodingKeys: String, CodingKey {
        case ticker
        case peCurrent = "pe_current"
        case pe5yrAvg = "pe_5yr_avg"
        case peSectorAvg = "pe_sector_avg"
        case pe5yrHigh = "pe_5yr_high"
        case pe5yrLow = "pe_5yr_low"
        case pbCurrent = "pb_current"
        case pb5yrAvg = "pb_5yr_avg"
        case evEbitda = "ev_ebitda"
        case marketCapCrores = "market_cap_crores"
        case enterpriseValueCrores = "enterprise_value_crores"
        case dividendYield = "dividend_yield"
        case earningsYield = "earnings_yield"
        case pegRatio = "peg_ratio"
    }
}

struct ValuationResponse: Codable {
    let ticker: String
    let snapshot: ValuationSnapshot
    let peBandData: [[String: AnyCodable]]?
    let peerComparison: [PeerValuation]

    enum CodingKeys: String, CodingKey {
        case ticker, snapshot
        case peBandData = "pe_band_data"
        case peerComparison = "peer_comparison"
    }
}

struct PeerValuation: Codable, Identifiable {
    var id: String { ticker }
    let ticker: String
    let pe: Double?
    let pb: Double?
    let evEbitda: Double?
    let roce: Double?
    let roe: Double?

    enum CodingKeys: String, CodingKey {
        case ticker, pe, pb, roce, roe
        case evEbitda = "ev_ebitda"
    }
}

// MARK: - Risk Signals

struct RiskSignal: Codable, Identifiable {
    var id: UUID = UUID()
    let type: String
    let severity: String
    let title: String
    let description: String
    let detectedAt: String?
    let metricValue: Double?
    let threshold: Double?

    enum CodingKeys: String, CodingKey {
        case id, type, severity, title, description, threshold
        case detectedAt = "detected_at"
        case metricValue = "metric_value"
    }
}

struct RiskSignalsResponse: Codable {
    let ticker: String
    let overallRiskScore: Double
    let signals: [RiskSignal]
    let governanceScore: Double?
    let pledgeRisk: String?
    let fiiTrend: String?
    let debtConcern: String?

    enum CodingKeys: String, CodingKey {
        case ticker, signals
        case overallRiskScore = "overall_risk_score"
        case governanceScore = "governance_score"
        case pledgeRisk = "pledge_risk"
        case fiiTrend = "fii_trend"
        case debtConcern = "debt_concern"
    }
}
