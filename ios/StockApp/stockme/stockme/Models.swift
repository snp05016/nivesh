import SwiftUI

struct Stock: Codable, Identifiable {
    var id: String { ticker }
    let ticker: String
    let companyName: String
    let exchange: String // NSE or BSE
    var currentPrice: Double
    var changePercent: Double
    var signal: Signal?
    // var lastAnalysis: AnalysisReport? // Added during analysis
}

enum Signal: String, Codable {
    case bullish = "BULLISH"
    case cautiously_bullish = "CAUTIOUSLY BULLISH"
    case neutral = "NEUTRAL"
    case hold = "HOLD"
    case cautiously_bearish = "CAUTIOUSLY BEARISH"
    case bearish = "BEARISH"

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        let raw = (try? container.decode(String.self))?.uppercased().trimmingCharacters(in: .whitespaces) ?? ""
        switch raw {
        case "BULLISH", "BUY", "STRONG BUY", "STRONG_BUY":
            self = .bullish
        case "CAUTIOUSLY BULLISH", "CAUTIOUS_BULLISH":
            self = .cautiously_bullish
        case "NEUTRAL":
            self = .neutral
        case "HOLD":
            self = .hold
        case "CAUTIOUSLY BEARISH", "CAUTIOUS_BEARISH":
            self = .cautiously_bearish
        case "BEARISH", "SELL", "AVOID", "STRONG SELL", "STRONG_SELL":
            self = .bearish
        default:
            self = .neutral // never crash on unknown signal
        }
    }

    var color: Color {
        switch self {
        case .bullish: return Theme.signalEmerald
        case .cautiously_bullish: return Theme.signalEmerald.opacity(0.7)
        case .neutral, .hold: return Theme.securityGold
        case .cautiously_bearish: return Theme.signalRuby.opacity(0.7)
        case .bearish: return Theme.signalRuby
        }
    }

    var label: String { self.rawValue }

    var shortLabel: String {
        switch self {
        case .bullish: return "BULL"
        case .cautiously_bullish: return "C.BULL"
        case .neutral: return "NEUT"
        case .hold: return "HOLD"
        case .cautiously_bearish: return "C.BEAR"
        case .bearish: return "BEAR"
        }
    }
}

struct StockAnalysis: Codable {
    let ticker: String
    let companyName: String
    let exchange: String?
    let analysisDate: String
    let signal: Signal
    let confidencePercent: Int
    let currentPriceInr: Double
    let targetPrices: TargetPrices
    let upsideDownsidePct: UpsideDownsidePct
    let bullCase: [String]
    let bearCase: [String]
    let keyRisks: [String]
    let keyFactors: KeyFactors
    let fundamentalsSnapshot: FundamentalsSnapshot
    let whatToWatch: [String]
    let disclaimer: String
    let recentNews: [NewsItem]?
    let patterns: [String]?
    let confidenceRationale: String?
    let signalChanged: Bool?
    let previousSignal: String?
    var advisorMatrix: [AdvisorInsightRow] = []
    let pricePerformance: PricePerformance?
    // v2 extreme bundles — optional, present only for scan_type=="extreme"
    let analysisTier: String?
    let factorScores: FactorScores?
    let piotroski: PiotroskiData?
    let financialTrends: FinancialTrends?
    let ownershipTrends: OwnershipTrends?
    let peerComparison: [PeerRow]?
    let scenarios: ScenarioBundle?
    let valuationBands: ValuationBands?
    let extendedThesis: ExtendedThesis?
    let nicheInsights: [String]?
    let governanceFlags: [GovernanceFlag]?
    // Backend-computed staleness (set by get_analysis_for_date / get_last_analysis_any_type)
    let stalenessLabel: String?
    let stalenessScore: Int?
    let stalenessUrgency: String?
    let stalenessHours: Double?
    let stalenessReason: String?
    let cachedScanType: String?

    enum CodingKeys: String, CodingKey {
        case ticker, signal, exchange, patterns
        case companyName = "company_name"
        case analysisDate = "analysis_date"
        case confidencePercent = "confidence_pct"
        case currentPriceInr = "current_price_inr"
        case targetPrices = "target_prices"
        case upsideDownsidePct = "upside_downside_pct"
        case bullCase = "bull_case"
        case bearCase = "bear_case"
        case keyRisks = "key_risks"
        case keyFactors = "key_factors"
        case fundamentalsSnapshot = "fundamentals_snapshot"
        case whatToWatch = "what_to_watch"
        case disclaimer
        case recentNews = "recent_news"
        case confidenceRationale = "confidence_rationale"
        case signalChanged = "signal_changed"
        case previousSignal = "previous_signal"
        case advisorMatrix = "advisor_matrix"
        case pricePerformance = "price_performance"
        case analysisTier = "analysis_tier"
        case factorScores = "factor_scores"
        case piotroski
        case financialTrends = "financial_trends"
        case ownershipTrends = "ownership_trends"
        case peerComparison = "peer_comparison"
        case scenarios
        case valuationBands = "valuation_bands"
        case extendedThesis = "extended_thesis"
        case nicheInsights = "niche_insights"
        case governanceFlags = "governance_flags"
        case stalenessLabel = "_staleness_label"
        case stalenessScore = "_staleness_score"
        case stalenessUrgency = "_staleness_urgency"
        case stalenessHours = "_staleness_hours"
        case stalenessReason = "_staleness_reason"
        case cachedScanType = "_cached_scan_type"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        ticker               = try c.decode(String.self,               forKey: .ticker)
        companyName          = try c.decode(String.self,               forKey: .companyName)
        exchange             = try c.decodeIfPresent(String.self,      forKey: .exchange)
        analysisDate         = try c.decode(String.self,               forKey: .analysisDate)
        signal               = try c.decode(Signal.self,               forKey: .signal)
        confidencePercent    = try c.decode(Int.self,                  forKey: .confidencePercent)
        currentPriceInr      = try c.decode(Double.self,               forKey: .currentPriceInr)
        targetPrices         = try c.decode(TargetPrices.self,         forKey: .targetPrices)
        upsideDownsidePct    = try c.decode(UpsideDownsidePct.self,    forKey: .upsideDownsidePct)
        bullCase             = try c.decode([String].self,             forKey: .bullCase)
        bearCase             = try c.decode([String].self,             forKey: .bearCase)
        keyRisks             = try c.decode([String].self,             forKey: .keyRisks)
        keyFactors           = try c.decode(KeyFactors.self,           forKey: .keyFactors)
        fundamentalsSnapshot = try c.decode(FundamentalsSnapshot.self, forKey: .fundamentalsSnapshot)
        whatToWatch          = try c.decode([String].self,             forKey: .whatToWatch)
        disclaimer           = try c.decode(String.self,               forKey: .disclaimer)
        recentNews           = try c.decodeIfPresent([NewsItem].self,          forKey: .recentNews)
        patterns             = try c.decodeIfPresent([String].self,            forKey: .patterns)
        confidenceRationale  = try c.decodeIfPresent(String.self,             forKey: .confidenceRationale)
        signalChanged        = try c.decodeIfPresent(Bool.self,               forKey: .signalChanged)
        previousSignal       = try c.decodeIfPresent(String.self,             forKey: .previousSignal)
        advisorMatrix        = (try? c.decodeIfPresent([AdvisorInsightRow].self, forKey: .advisorMatrix)) ?? []
        pricePerformance     = try c.decodeIfPresent(PricePerformance.self,   forKey: .pricePerformance)
        // v2 extreme bundles — decodeIfPresent so standard analyses keep working
        analysisTier         = try c.decodeIfPresent(String.self,            forKey: .analysisTier)
        factorScores         = try c.decodeIfPresent(FactorScores.self,      forKey: .factorScores)
        piotroski            = try c.decodeIfPresent(PiotroskiData.self,     forKey: .piotroski)
        financialTrends      = try c.decodeIfPresent(FinancialTrends.self,   forKey: .financialTrends)
        ownershipTrends      = try c.decodeIfPresent(OwnershipTrends.self,   forKey: .ownershipTrends)
        peerComparison       = try c.decodeIfPresent([PeerRow].self,          forKey: .peerComparison)
        scenarios            = try c.decodeIfPresent(ScenarioBundle.self,     forKey: .scenarios)
        valuationBands       = try c.decodeIfPresent(ValuationBands.self,    forKey: .valuationBands)
        extendedThesis       = try c.decodeIfPresent(ExtendedThesis.self,    forKey: .extendedThesis)
        nicheInsights        = try c.decodeIfPresent([String].self,           forKey: .nicheInsights)
        governanceFlags      = try c.decodeIfPresent([GovernanceFlag].self,   forKey: .governanceFlags)
        stalenessLabel       = try c.decodeIfPresent(String.self,             forKey: .stalenessLabel)
        stalenessScore       = try c.decodeIfPresent(Int.self,                forKey: .stalenessScore)
        stalenessUrgency     = try c.decodeIfPresent(String.self,             forKey: .stalenessUrgency)
        stalenessHours       = try c.decodeIfPresent(Double.self,             forKey: .stalenessHours)
        stalenessReason      = try c.decodeIfPresent(String.self,             forKey: .stalenessReason)
        cachedScanType       = try c.decodeIfPresent(String.self,             forKey: .cachedScanType)
    }
}

// MARK: - v2 Engine — Job Status

struct JobStatus: Codable {
    let jobId: String
    let userId: Int?
    let ticker: String
    let scanType: String?
    let status: String          // QUEUED | RUNNING | SUCCEEDED | FAILED | CANCELLED | TIMEOUT
    let stage: String?
    let progressPct: Int?
    let checkpoints: [CheckpointEvent]?
    let tokensUsed: Int?
    let error: String?
    let result: StockAnalysis?  // present only when SUCCEEDED (full_json)

    enum CodingKeys: String, CodingKey {
        case jobId = "job_id"; case userId = "user_id"; case ticker; case scanType = "scan_type"
        case status; case stage; case progressPct = "progress_pct"
        case checkpoints; case tokensUsed = "tokens_used"; case error; case result
    }
}

struct CheckpointEvent: Codable, Identifiable {
    var id: String { "\(ts)_\(stage)" }
    let ts: String
    let stage: String
    let agent: String
    let message: String
    let state: String       // running | ok | error
}

// MARK: - v2 Engine — Extreme Bundle Models

struct FactorScores: Codable {
    let value, quality, momentum, growth, lowVolatility: Int?
    enum CodingKeys: String, CodingKey {
        case value, quality, momentum, growth
        case lowVolatility = "low_volatility"
    }
}

struct ScenarioPoint: Codable {
    let price3m, price12m, price36m: Double?
    let probabilityPct: Int?
    let narrative: String?
    enum CodingKeys: String, CodingKey {
        case price3m = "price_3m"; case price12m = "price_12m"; case price36m = "price_36m"
        case probabilityPct = "probability_pct"; case narrative
    }
}

struct ScenarioBundle: Codable {
    let bull, base, bear: ScenarioPoint?
}

struct ValuationBands: Codable {
    let currentPrice, fairValue, bullValue, bearValue: Double?
    let method: String?
    let peBand: PEBand?
    enum CodingKeys: String, CodingKey {
        case currentPrice = "current_price"; case fairValue = "fair_value"
        case bullValue = "bull_value"; case bearValue = "bear_value"
        case method; case peBand = "pe_band"
    }
}

struct PEBand: Codable {
    let low, mid, high: Double?
}

struct ExtendedThesis: Codable {
    let bullDeepDive, bearDeepDive, managementQuality, competitiveMoat, sectorPositioning: String?
    enum CodingKeys: String, CodingKey {
        case bullDeepDive = "bull_deep_dive"; case bearDeepDive = "bear_deep_dive"
        case managementQuality = "management_quality"; case competitiveMoat = "competitive_moat"
        case sectorPositioning = "sector_positioning"
    }
}

struct GovernanceFlag: Codable, Identifiable {
    var id: String { flag ?? UUID().uuidString }
    let flag: String?
    let severity: String?
    let detail: String?
}

struct FinancialTrends: Codable {
    let years: [String]?
    let revenueCr: [Double?]?
    let netProfitCr: [Double?]?
    let netMarginPct: [Double?]?
    enum CodingKeys: String, CodingKey {
        case years; case revenueCr = "revenue_cr"; case netProfitCr = "net_profit_cr"
        case netMarginPct = "net_margin_pct"
    }
}

struct OwnershipTrends: Codable {
    let dates: [String]?
    let promoterPledgedPct: [Double]?
    enum CodingKeys: String, CodingKey {
        case dates; case promoterPledgedPct = "promoter_pledged_pct"
    }
}

struct PeerRow: Codable, Identifiable {
    var id: String { ticker ?? UUID().uuidString }
    let ticker: String?
    let name: String?
    let pe: Double?
    let roePct: Double?
    let revGrowthPct: Double?
    let debtToEquity: Double?
    let marketcapCr: Double?
    enum CodingKeys: String, CodingKey {
        case ticker, name, pe; case roePct = "roe_pct"; case revGrowthPct = "rev_growth_pct"
        case debtToEquity = "debt_to_equity"; case marketcapCr = "marketcap_cr"
    }
}

// MARK: - v2 Engine — Job request/response wrappers

struct StartJobRequest: Encodable {
    let ticker, exchange: String
    let userId: Int?
    let scanType: String
    enum CodingKeys: String, CodingKey {
        case ticker, exchange; case userId = "user_id"; case scanType = "scan_type"
    }
}

struct StartJobResponse: Codable {
    let jobId: String?; let status: String?; let ticker: String?
    var analysis: StockAnalysis?

    enum CodingKeys: String, CodingKey {
        case jobId = "job_id"; case status; case ticker
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        jobId = try c.decodeIfPresent(String.self, forKey: .jobId)
        status = try c.decodeIfPresent(String.self, forKey: .status)
        ticker = try c.decodeIfPresent(String.self, forKey: .ticker)
        // If the response is a cache hit, it IS a StockAnalysis — try decoding it directly
        if jobId == nil {
            analysis = try? StockAnalysis(from: decoder)
        } else {
            analysis = nil
        }
    }

    func encode(to encoder: Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encodeIfPresent(jobId, forKey: .jobId)
        try c.encodeIfPresent(status, forKey: .status)
        try c.encodeIfPresent(ticker, forKey: .ticker)
    }
}

struct TargetPrices: Codable {
    let shortTerm3m: Double
    let mediumTerm12m: Double
    let longTerm36m: Double

    enum CodingKeys: String, CodingKey {
        case shortTerm3m = "short_term_3m"
        case mediumTerm12m = "medium_term_12m"
        case longTerm36m = "long_term_36m"
    }
}

struct UpsideDownsidePct: Codable {
    let shortTerm: Double
    let mediumTerm: Double
    let longTerm: Double

    enum CodingKeys: String, CodingKey {
        case shortTerm = "short_term"
        case mediumTerm = "medium_term"
        case longTerm = "long_term"
    }
}

struct KeyFactors: Codable {
    let managementQuality: String
    let geopoliticalContext: String
    let promoterFiiDiiActivity: String
    let turnaroundStory: String
    let fundamentalsSummary: String
    let globalMacroImpact: String
    let newsSentiment: String
    let indianMarketSentiment: String?

    enum CodingKeys: String, CodingKey {
        case managementQuality = "management_quality"
        case geopoliticalContext = "geopolitical_context"
        case promoterFiiDiiActivity = "promoter_fii_dii_activity"
        case turnaroundStory = "turnaround_story"
        case fundamentalsSummary = "fundamentals_summary"
        case globalMacroImpact = "global_macro_impact"
        case newsSentiment = "news_sentiment"
        case indianMarketSentiment = "indian_market_sentiment"
    }
}

struct PromoterHistoryPoint: Codable, Identifiable {
    var id: String { period }
    let period: String
    let promoter: Double
    let fii: Double
    let dii: Double
}

struct QuarterlyFinancialsResponse: Codable {
    let quarters: [QuarterlyFinancial]
    let promoterHistory: [PromoterHistoryPoint]
    enum CodingKeys: String, CodingKey {
        case quarters
        case promoterHistory = "promoter_history"
    }
}

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

struct FundamentalsSnapshot: Codable {
    let peRatio: Double?
    let debtToEquity: Double?
    let promoterHoldingPct: Double?
    let fiiHoldingPct: Double?
    let diiHoldingPct: Double?
    let revenueTtmCrores: Double?
    let ebitdaMarginPct: Double?
    let patTtmCrores: Double?
    let roePct: Double?
    let rocePct: Double?
    let marketCapCrores: Double?

    enum CodingKeys: String, CodingKey {
        case peRatio = "pe_ratio"
        case debtToEquity = "debt_to_equity"
        case promoterHoldingPct = "promoter_holding_pct"
        case fiiHoldingPct = "fii_holding_pct"
        case diiHoldingPct = "dii_holding_pct"
        case revenueTtmCrores = "revenue_ttm_crores"
        case ebitdaMarginPct = "ebitda_margin_pct"
        case patTtmCrores = "pat_ttm_crores"
        case roePct = "roe_pct"
        case rocePct = "roce_pct"
        case marketCapCrores = "market_cap_crores"
    }
}

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

struct PricePoint: Codable, Identifiable {
    var id: String { date }
    let date: String
    let close: Double
    let volume: Double?

    var parsedDate: Date {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        return f.date(from: date) ?? Date()
    }
}

struct NiftyPricePoint: Codable, Identifiable {
    var id: String { date }
    let date: String
    let close: Double

    var parsedDate: Date {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        return f.date(from: date) ?? Date()
    }
}

struct OHLCVPoint: Codable, Identifiable {
    var id: String { date }
    let date: String
    let open: Double
    let high: Double
    let low: Double
    let close: Double
    let volume: Double

    var parsedDate: Date {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        return f.date(from: date) ?? Date()
    }
}

struct StockHistoryResponse: Codable {
    let ticker: String
    let exchange: String
    let period: String
    let prices: [OHLCVPoint]
}

struct PiotroskiData: Codable {
    let ticker: String?
    let fScore: Int?
    let maxPossible: Int?
    let grade: String?
    let confidence: String?
    let checks: [String: String]?

    enum CodingKeys: String, CodingKey {
        case ticker
        case fScore = "f_score"
        case maxPossible = "max_possible"
        case grade, confidence, checks
    }
}

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

struct PeVsAvg: Codable {
    let currentPe: Double
    let avgPe3y: Double
    let pctVsAvg: Double

    enum CodingKeys: String, CodingKey {
        case currentPe = "current_pe"
        case avgPe3y = "avg_pe_3y"
        case pctVsAvg = "pct_vs_avg"
    }
}

struct QuickInfo: Codable {
    let ticker: String
    let price: Double?
    let change: Double?
    let changePercent: Double?
    let signal: Signal?
    let sector: String?
    let industry: String?
    let description: String?
    let officers: [String]?
    let website: String?
    let recentNews: [NewsItem]?
    let sparkline30d: [Double]?
    let week52High: Double?
    let week52Low: Double?
    let peRatio: Double?
    let debtToEquity: Double?
    let promoterHoldingPct: Double?
    let fiiHoldingPct: Double?
    let diiHoldingPct: Double?
    let ebitdaMarginPct: Double?
    let roePct: Double?
    let rocePct: Double?
    let volume: Int?
    let avgVolume: Int?
    let priceHistory90d: [PricePoint]?
    let peVsAvg: PeVsAvg?
    let asmGsmStatus: String?
    let promoterPledgedPct: Double?
    let governanceScore: Int?
    let governanceRedFlags: [String]?

    enum CodingKeys: String, CodingKey {
        case ticker, signal
        case price = "current_price"
        case change = "day_change_abs"
        case changePercent = "day_change_pct"
        case sector, industry, description, officers, website
        case recentNews = "recent_news"
        case sparkline30d = "sparkline_30d"
        case week52High = "week_52_high"
        case week52Low = "week_52_low"
        case peRatio = "pe_ratio"
        case debtToEquity = "debt_to_equity"
        case promoterHoldingPct = "promoter_holding_pct"
        case fiiHoldingPct = "fii_holding_pct"
        case diiHoldingPct = "dii_holding_pct"
        case ebitdaMarginPct = "ebitda_margin_pct"
        case roePct = "roe_pct"
        case rocePct = "roce_pct"
        case volume, avgVolume = "avg_volume"
        case priceHistory90d = "price_history_90d"
        case peVsAvg = "pe_vs_avg"
        case asmGsmStatus = "asm_gsm_status"
        case promoterPledgedPct = "promoter_pledged_pct"
        case governanceScore = "governance_score"
        case governanceRedFlags = "governance_red_flags"
    }
}

// MARK: - Unified StockProfile Response

struct PriceHistoryBlock: Codable {
    let prices: [OHLCVPoint]
    let source: String?
    let error: String?
}

struct QuarterlyFinancialsBlock: Codable {
    let quarters: [QuarterlyFinancial]
    let promoterHistory: [PromoterHistoryPoint]?
    let error: String?

    enum CodingKeys: String, CodingKey {
        case quarters, error
        case promoterHistory = "promoter_history"
    }
}

struct StockProfileResponse: Codable {
    let ticker: String
    let exchange: String
    let companyName: String
    let currentPrice: Double
    let dayChangePct: Double
    let peRatio: Double?
    let sector: String?
    let promoterHoldingPct: Double?
    let fiiHoldingPct: Double?
    let diiHoldingPct: Double?
    let roePct: Double?
    let rocePct: Double?
    let ebitdaMarginPct: Double?
    let debtToEquity: Double?
    let week52High: Double?
    let week52Low: Double?
    let marketCapCrores: Double?
    let description: String?
    let priceHistory: PriceHistoryBlock?
    let quarterlyFinancials: QuarterlyFinancialsBlock?
    let errors: [String]?

    enum CodingKeys: String, CodingKey {
        case ticker, exchange, sector, description, errors
        case companyName = "company_name"
        case currentPrice = "current_price"
        case dayChangePct = "day_change_pct"
        case peRatio = "pe_ratio"
        case promoterHoldingPct = "promoter_holding_pct"
        case fiiHoldingPct = "fii_holding_pct"
        case diiHoldingPct = "dii_holding_pct"
        case roePct = "roe_pct"
        case rocePct = "roce_pct"
        case ebitdaMarginPct = "ebitda_margin_pct"
        case debtToEquity = "debt_to_equity"
        case week52High = "week_52_high"
        case week52Low = "week_52_low"
        case marketCapCrores = "market_cap_crores"
        case priceHistory = "price_history"
        case quarterlyFinancials = "quarterly_financials"
    }
}

struct PricePerformance: Codable {
    let change3mPct: Double?
    let change6mPct: Double?
    let change12mPct: Double?

    enum CodingKeys: String, CodingKey {
        case change3mPct  = "change_3m_pct"
        case change6mPct  = "change_6m_pct"
        case change12mPct = "change_12m_pct"
    }
}

struct NewsItem: Codable, Identifiable {
    var id: String { link }
    let title: String
    let publisher: String
    let link: String
    let publishTime: Int?
    let summary: String?
    let imageUrl: String?

    enum CodingKeys: String, CodingKey {
        case title, publisher, link, summary
        case publishTime = "publish_time"
        case imageUrl = "image_url"
    }
}

struct LoggedInUser: Codable {
    let userId: Int
    let username: String
    let displayName: String
    let token: String

    enum CodingKeys: String, CodingKey {
        case userId = "user_id"
        case username
        case displayName = "display_name"
        case token = "access_token"
    }
}

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

struct WatchlistItem: Codable, Identifiable {
    var id: String { ticker }
    let ticker: String
    let companyName: String
    let exchange: String
    let currentPrice: Double
    let dayChangePct: Double
    let lastSignal: String?
    let lastSignalDate: String?
    let asmGsmStatus: String?

    enum CodingKeys: String, CodingKey {
        case ticker, exchange
        case companyName = "company_name"
        case currentPrice = "current_price"
        case dayChangePct = "day_change_pct"
        case lastSignal = "last_signal"
        case lastSignalDate = "last_signal_date"
        case asmGsmStatus = "asm_gsm_status"
    }
}

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

import Combine

@MainActor
class LocalReportManager: ObservableObject {
    @Published var savedReports: [StockAnalysis] = []

    private let fileURL: URL = {
        let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        return docs.appendingPathComponent("saved_reports.json")
    }()

    init() {
        loadReports()
    }

    func loadReports() {
        guard let data = try? Data(contentsOf: fileURL) else { return }
        if let decoded = try? JSONDecoder().decode([StockAnalysis].self, from: data) {
            self.savedReports = decoded.sorted { $0.analysisDate > $1.analysisDate }
        }
    }

    func saveReport(_ report: StockAnalysis) {
        // Remove existing report for same ticker if it exists, to update it
        savedReports.removeAll { $0.ticker == report.ticker }
        savedReports.insert(report, at: 0)
        
        if let encoded = try? JSONEncoder().encode(savedReports) {
            try? encoded.write(to: fileURL)
        }
    }
    
    func deleteReport(ticker: String) {
        savedReports.removeAll { $0.ticker == ticker }
        if let encoded = try? JSONEncoder().encode(savedReports) {
            try? encoded.write(to: fileURL)
        }
    }

    func getReport(for ticker: String) -> StockAnalysis? {
        return savedReports.first { $0.ticker == ticker }
    }
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

// MARK: - Diagnostic Error Payload (unified telemetry contract)

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

    var suggestedActionText: String {
        guard let action = diagnostic?.suggestedAction else { return "RETRY" }
        switch action {
        case "WAIT": return "Please wait and try again shortly."
        case "RETRY": return "Tap 'Retry' below to attempt the analysis again."
        case "CHECK_CONFIG": return "Check your API keys and server configuration."
        case "CONTACT_SUPPORT": return "Please contact support with the diagnostic info below."
        default: return action
        }
    }
}

// MARK: - Sector Performance

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

// MARK: - Watchlist enrichment

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

// MARK: - Daily Action

struct DailyActionResponse: Codable {
    let action: String
    let urgency: String  // "high" | "medium" | "low"
}

// MARK: - Sidebar Market Intelligence Models

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

// MARK: - Advisor Intelligence Models

struct AdvisoryConsensusResponse: Codable {
    let generatedAt: String
    let windowDays: Int
    let sectorSignals: [SectorSignal]
    let trendingTickers: [TrendingTicker]
    let totalVideosProcessed: Int
    let lastHarvestAt: String?

    enum CodingKeys: String, CodingKey {
        case generatedAt = "generated_at"
        case windowDays = "window_days"
        case sectorSignals = "sector_signals"
        case trendingTickers = "trending_tickers"
        case totalVideosProcessed = "total_videos_processed"
        case lastHarvestAt = "last_harvest_at"
    }
}

struct SectorSignal: Codable, Identifiable {
    var id: String { theme }
    let theme: String
    let bullishCount: Int
    let bearishCount: Int
    let neutralCount: Int
    let topAdvisors: [String]

    enum CodingKeys: String, CodingKey {
        case theme
        case bullishCount = "bullish_count"
        case bearishCount = "bearish_count"
        case neutralCount = "neutral_count"
        case topAdvisors = "top_advisors"
    }
}

struct TrendingTicker: Codable, Identifiable {
    var id: String { ticker }
    let ticker: String
    let companyName: String
    let mentionCount: Int
    let dominantStance: String
    let totalViewCount: Int
    let advisors: [String]

    enum CodingKeys: String, CodingKey {
        case ticker, advisors
        case companyName = "company_name"
        case mentionCount = "mention_count"
        case dominantStance = "dominant_stance"
        case totalViewCount = "total_view_count"
    }
}

struct AdvisorInsightRow: Codable, Identifiable {
    var id: String { videoUrl }
    let advisorName: String
    let stance: String
    let confidence: String
    let catalystSummary: String
    let videoTitle: String
    let videoUrl: String
    let publishedAt: String
    let transcriptSource: String

    enum CodingKeys: String, CodingKey {
        case stance, confidence
        case advisorName = "advisor_name"
        case catalystSummary = "catalyst_summary"
        case videoTitle = "video_title"
        case videoUrl = "video_url"
        case publishedAt = "published_at"
        case transcriptSource = "transcript_source"
    }
}

// MARK: - Earnings Dashboard Models (Sections 1–5)

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
    var parsedResultDate: Date {
        let f = DateFormatter(); f.dateFormat = "yyyy-MM-dd"
        return f.date(from: resultDate) ?? Date()
    }
    var parsedReportedAt: Date? {
        guard let s = reportedAt else { return nil }
        let f = ISO8601DateFormatter()
        return f.date(from: s)
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

// MARK: - Pre-IPO / Unlisted Shares Models (Section 6)

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

struct OTCAdvisory: Identifiable {
    let id: String
    let companyName: String
    let entryPrice: Double
    let targetPrice: Double
    let stopLoss: Double
    let rationale: String
    let isPremium: Bool
}

// MARK: - Expert Network Models (Section 7)

struct MarketExpert: Identifiable {
    let id: String
    let name: String
    let sebiRegId: String?
    let yearsExperience: Int
    let strategy: String          // e.g. "Harmonic Trading Strategy"
    let focusTags: [String]       // e.g. ["Charts", "Currency", "Gold"]
    let postCount: Int
    let isVerified: Bool
    let bio: String
}

struct ExpertPost: Identifiable {
    let id: String
    let expertId: String
    let expertName: String
    let content: String           // unhedged plain-english analysis
    let ticker: String?
    let chartImageUrl: String?
    let publishedAt: Date
    let likeCount: Int
    let isPremium: Bool
    var isLiked: Bool = false
    var isBookmarked: Bool = false
}

// MARK: - Screener Bookmark

struct ScreenerBookmark: Codable, Identifiable {
    var id: String { presetKey }
    let presetKey: String
    let displayName: String
    let savedAt: String
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

// MARK: - Ideas Workspace Models

struct AdvisorBiography: Codable, Identifiable {
    let id: Int
    let advisorName: String
    let sebiRegNumber: String
    let experienceYears: Int
    let analyticalFramework: String?
    let fullBiographyText: String
    let createdAt: String?
    enum CodingKeys: String, CodingKey {
        case id
        case advisorName = "advisor_name"
        case sebiRegNumber = "sebi_reg_number"
        case experienceYears = "experience_years"
        case analyticalFramework = "analytical_framework"
        case fullBiographyText = "full_biography_text"
        case createdAt = "created_at"
    }
}

struct AdvisorsResponse: Codable {
    let advisors: [AdvisorBiography]
    let count: Int
    let fetchedAt: String
    enum CodingKeys: String, CodingKey {
        case advisors, count
        case fetchedAt = "fetched_at"
    }
}

struct TextAdvisoryInsight: Codable, Identifiable {
    let id: Int
    let advisorName: String?
    let timestamp: String?
    let contentText: String
    let targetTicker: String?
    let extractedSentiment: String?
    enum CodingKeys: String, CodingKey {
        case id
        case advisorName = "advisor_name"
        case timestamp
        case contentText = "content_text"
        case targetTicker = "target_ticker"
        case extractedSentiment = "extracted_sentiment"
    }
}

struct IdeasFeedResponse: Codable {
    let insights: [TextAdvisoryInsight]
    let count: Int
    let fetchedAt: String
    enum CodingKeys: String, CodingKey {
        case insights, count
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

// MARK: - Macro Context Models (Stock Profile)

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

// MARK: - Harvester (Market Intelligence) models — port 8001 microservice

struct HarvestedCard: Codable, Identifiable {
    let id: Int
    let sourceType: String
    let sourceName: String
    let sourceUrl: String
    let originalAuthor: String?
    let publishedAt: String?
    let title: String
    let reformattedSummary: String?
    let keyTakeaways: [String]?
    let tickers: [String]?
    let sentiment: String?
    let credibilityScore: Int
    let cardType: String
    let expertCredential: String?
    let createdAt: String?

    enum CodingKeys: String, CodingKey {
        case id
        case sourceType = "source_type"
        case sourceName = "source_name"
        case sourceUrl = "source_url"
        case originalAuthor = "original_author"
        case publishedAt = "published_at"
        case title
        case reformattedSummary = "reformatted_summary"
        case keyTakeaways = "key_takeaways"
        case tickers
        case sentiment
        case credibilityScore = "credibility_score"
        case cardType = "card_type"
        case expertCredential = "expert_credential"
        case createdAt = "created_at"
    }
}

struct HarvesterFeedResponse: Codable {
    let cards: [HarvestedCard]
    let total: Int
    let sources: [String]
}

struct HarvesterSourceStatus: Codable, Identifiable {
    var id: String { sourceName }
    let sourceName: String
    let lastSuccess: String?
    let lastFailure: String?
    let itemsScraped: Int
    let isHealthy: Bool
    let errorMessage: String?

    enum CodingKeys: String, CodingKey {
        case sourceName = "source_name"
        case lastSuccess = "last_success"
        case lastFailure = "last_failure"
        case itemsScraped = "items_scraped"
        case isHealthy = "is_healthy"
        case errorMessage = "error_message"
    }
}


struct BrainstormResponse: Codable {
    let ideas: [BrainstormIdea]
}

struct BrainstormIdea: Codable, Identifiable {
    var id: String { ticker ?? title }
    let title: String
    let description: String
    let ticker: String?
}

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

// MARK: - Options Strategy Builder Models

struct OptionLeg: Codable {
    let type: String            // CALL or PUT
    let position: String        // LONG or SHORT
    let strike: Double
    let premium: Double

    enum CodingKeys: String, CodingKey {
        case type, position, strike, premium
    }
}

struct PayoffPoint: Codable, Identifiable {
    var id: Double { underlyingPrice }
    let underlyingPrice: Double
    let pnl: Double

    enum CodingKeys: String, CodingKey {
        case underlyingPrice = "underlying_price"
        case pnl
    }
}

struct OptionsPayoffResponse: Codable {
    let spotPrice: Double
    let payoffVector: [PayoffPoint]
    let maxProfit: Double?
    let maxProfitUnlimited: Bool
    let maxProfitFormatted: String
    let maxLoss: Double?
    let maxLossUnlimited: Bool
    let maxLossFormatted: String
    let breakevens: [Double]
    let netPremium: Double
    let netPremiumFormatted: String
    let numLegs: Int
    let strategyType: String

    enum CodingKeys: String, CodingKey {
        case spotPrice = "spot_price"
        case payoffVector = "payoff_vector"
        case maxProfit = "max_profit"
        case maxProfitUnlimited = "max_profit_unlimited"
        case maxProfitFormatted = "max_profit_formatted"
        case maxLoss = "max_loss"
        case maxLossUnlimited = "max_loss_unlimited"
        case maxLossFormatted = "max_loss_formatted"
        case breakevens
        case netPremium = "net_premium"
        case netPremiumFormatted = "net_premium_formatted"
        case numLegs = "num_legs"
        case strategyType = "strategy_type"
    }
}

struct OptionsPayoffRequest: Codable {
    let spotPrice: Double
    let legs: [OptionLeg]

    enum CodingKeys: String, CodingKey {
        case spotPrice = "spot_price"
        case legs
    }
}
