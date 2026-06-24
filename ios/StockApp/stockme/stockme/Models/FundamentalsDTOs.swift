import Foundation

// MARK: - Financial Metrics
public struct FinancialMetrics: Decodable, Equatable {
    public let period: String
    public let revenue: String?
    public let netIncome: String?
    public let eps: Double?
    public let operatingMargin: Double?
    public let freeCashFlow: String?
    
    enum CodingKeys: String, CodingKey {
        case period
        case revenue
        case netIncome = "net_income"
        case eps
        case operatingMargin = "operating_margin"
        case freeCashFlow = "free_cash_flow"
    }
}

// MARK: - Shareholding
public struct Shareholding: Decodable, Equatable {
    public let quarter: String
    public let promoterPct: Double?
    public let fiiPct: Double?
    public let diiPct: Double?
    public let publicPct: Double?
    public let pledgedPct: Double?
    
    enum CodingKeys: String, CodingKey {
        case quarter
        case promoterPct = "promoter_pct"
        case fiiPct = "fii_pct"
        case diiPct = "dii_pct"
        case publicPct = "public_pct"
        case pledgedPct = "pledged_pct"
    }
}

// MARK: - Corporate Action
public struct CorporateActionDTO: Decodable, Equatable {
    public let exDate: String
    public let recordDate: String?
    public let purpose: String
    public let dividendAmount: Double?
    
    enum CodingKeys: String, CodingKey {
        case exDate = "ex_date"
        case recordDate = "record_date"
        case purpose
        case dividendAmount = "dividend_amount"
    }
}

// MARK: - Valuation Metrics
public struct ValuationMetrics: Decodable, Equatable {
    public let date: String
    public let currentPe: Double?
    public let forwardPe: Double?
    public let pbRatio: Double?
    public let evEbitda: Double?
    public let marketCap: String?
    
    enum CodingKeys: String, CodingKey {
        case date
        case currentPe = "current_pe"
        case forwardPe = "forward_pe"
        case pbRatio = "pb_ratio"
        case evEbitda = "ev_ebitda"
        case marketCap = "market_cap"
    }
}

// MARK: - Risk Signal
public struct RiskSignalDTO: Decodable, Equatable {
    public let date: String
    public let signalType: String
    public let severity: String
    public let description: String
    
    enum CodingKeys: String, CodingKey {
        case date
        case signalType = "signal_type"
        case severity
        case description
    }
}

// MARK: - Fundamentals Response (If fetched together)
public struct FundamentalsResponse: Decodable, Equatable {
    public let ticker: String
    public let financials: [FinancialMetrics]
    public let shareholding: [Shareholding]
    public let corporateActions: [CorporateActionDTO]
    public let valuation: ValuationMetrics?
    public let riskSignals: [RiskSignalDTO]
    
    enum CodingKeys: String, CodingKey {
        case ticker
        case financials
        case shareholding
        case corporateActions = "corporate_actions"
        case valuation
        case riskSignals = "risk_signals"
    }
}
