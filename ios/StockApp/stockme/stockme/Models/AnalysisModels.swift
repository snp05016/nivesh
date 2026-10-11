// Models/AnalysisModels.swift
// Domain: Stock analysis (core AI pipeline output), v2 extreme bundles, job orchestration, QuickInfo, StockProfile, fundamentals

import SwiftUI

// MARK: - Stock Analysis (Core AI Output)

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
    // New calibration engine fields
    let confidenceCalibration: ConfidenceCalibration?
    let targetPriceBounds: TargetPriceBounds?
    let historicalAnalogues: HistoricalAnalogues?
    let marketMicrostructure: MarketMicrostructure?
    let sectorMomentum: SectorMomentum?
    let auditorTenure: AuditorTenure?
    // Backend-computed staleness (set by get_analysis_for_date / get_last_analysis_any_type)
    let stalenessLabel: String?
    let stalenessScore: Int?
    let stalenessUrgency: String?
    let stalenessHours: Double?
    let stalenessReason: String?
    let cachedScanType: String?
    // ML Hybrid Pipeline — quant engine fields
    let marketRegime: String?
    let calibratedConfidence: Double?
    let confidenceMathBreakdown: [String: Double]?
    let conformalTargetUpper3m: Double?
    let conformalTargetLower3m: Double?
    let quantitativeDrivers: [String: Double]?
    let tailRiskFlags: [String: Bool]?

    // MARK: - Computed Helpers

    /// Prefer calibrated confidence from quant engine; fall back to legacy confidencePct.
    /// Clamped to [0.0, 1.0] to guard against stale cached rows predating schema bounds.
    var displayConfidence: Double {
        if let cc = calibratedConfidence {
            return max(0.0, min(1.0, cc))
        }
        return Double(confidencePercent) / 100.0
    }

    var hasQuantData: Bool {
        return calibratedConfidence != nil && quantitativeDrivers != nil
    }

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
        case confidenceCalibration = "confidence_calibration"
        case targetPriceBounds = "target_price_bounds"
        case historicalAnalogues = "historical_analogues"
        case marketMicrostructure = "market_microstructure"
        case sectorMomentum = "sector_momentum"
        case auditorTenure = "auditor_tenure"
        case stalenessLabel = "_staleness_label"
        case stalenessScore = "_staleness_score"
        case stalenessUrgency = "_staleness_urgency"
        case stalenessHours = "_staleness_hours"
        case stalenessReason = "_staleness_reason"
        case cachedScanType = "_cached_scan_type"
        case marketRegime = "market_regime"
        case calibratedConfidence = "calibrated_confidence"
        case confidenceMathBreakdown = "confidence_math_breakdown"
        case conformalTargetUpper3m = "conformal_target_upper_3m"
        case conformalTargetLower3m = "conformal_target_lower_3m"
        case quantitativeDrivers = "quantitative_drivers"
        case tailRiskFlags = "tail_risk_flags"
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
        confidenceCalibration = try c.decodeIfPresent(ConfidenceCalibration.self, forKey: .confidenceCalibration)
        targetPriceBounds     = try c.decodeIfPresent(TargetPriceBounds.self, forKey: .targetPriceBounds)
        historicalAnalogues   = try c.decodeIfPresent(HistoricalAnalogues.self, forKey: .historicalAnalogues)
        marketMicrostructure  = try c.decodeIfPresent(MarketMicrostructure.self, forKey: .marketMicrostructure)
        sectorMomentum        = try c.decodeIfPresent(SectorMomentum.self, forKey: .sectorMomentum)
        auditorTenure         = try c.decodeIfPresent(AuditorTenure.self, forKey: .auditorTenure)
        stalenessLabel       = try c.decodeIfPresent(String.self,             forKey: .stalenessLabel)
        stalenessScore       = try c.decodeIfPresent(Int.self,                forKey: .stalenessScore)
        stalenessUrgency     = try c.decodeIfPresent(String.self,             forKey: .stalenessUrgency)
        stalenessHours       = try c.decodeIfPresent(Double.self,             forKey: .stalenessHours)
        stalenessReason      = try c.decodeIfPresent(String.self,             forKey: .stalenessReason)
        cachedScanType          = try c.decodeIfPresent(String.self,                forKey: .cachedScanType)
        marketRegime            = try c.decodeIfPresent(String.self,                forKey: .marketRegime)
        calibratedConfidence    = try c.decodeIfPresent(Double.self,                forKey: .calibratedConfidence)
        confidenceMathBreakdown = try c.decodeIfPresent([String: Double].self,       forKey: .confidenceMathBreakdown)
        conformalTargetUpper3m  = try c.decodeIfPresent(Double.self,                forKey: .conformalTargetUpper3m)
        conformalTargetLower3m  = try c.decodeIfPresent(Double.self,                forKey: .conformalTargetLower3m)
        quantitativeDrivers     = try c.decodeIfPresent([String: Double].self,       forKey: .quantitativeDrivers)
        tailRiskFlags           = try c.decodeIfPresent([String: Bool].self,        forKey: .tailRiskFlags)
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

// MARK: - v2 Engine — Job request/response wrappers

struct StartJobRequest: Encodable {
    let ticker, exchange: String
    let userId: Int?
    let deepScan: Bool
    let scanType: String
    var language: String? = nil
    var debateRounds: Int? = nil
    var riskTolerance: String? = nil
    enum CodingKeys: String, CodingKey {
        case ticker, exchange
        case userId = "user_id"
        case deepScan = "deep_scan"
        case scanType = "scan_type"
        case language
        case debateRounds = "debate_rounds"
        case riskTolerance = "risk_tolerance"
    }
}

struct StartJobResponse: Codable {
    let jobId: String?; let status: String?; let ticker: String?
    /// Set on error bodies, e.g. the 409 `ALREADY_RUNNING` payload (which has no `status`).
    let errorCode: String?; let errorDetail: String?
    var analysis: StockAnalysis?

    enum CodingKeys: String, CodingKey {
        case jobId = "job_id"; case status; case ticker
        case errorCode = "error_code"; case errorDetail = "error_detail"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        jobId = try c.decodeIfPresent(String.self, forKey: .jobId)
        status = try c.decodeIfPresent(String.self, forKey: .status)
        ticker = try c.decodeIfPresent(String.self, forKey: .ticker)
        errorCode = try c.decodeIfPresent(String.self, forKey: .errorCode)
        errorDetail = try c.decodeIfPresent(String.self, forKey: .errorDetail)
        // A cache hit IS a StockAnalysis. Decode it strictly: schema drift must
        // surface as an error, not as a silent nil that leaves the screen blank.
        if jobId == nil && errorCode == nil {
            analysis = try StockAnalysis(from: decoder)
        } else {
            analysis = nil
        }
    }

    func encode(to encoder: Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encodeIfPresent(jobId, forKey: .jobId)
        try c.encodeIfPresent(status, forKey: .status)
        try c.encodeIfPresent(ticker, forKey: .ticker)
        try c.encodeIfPresent(errorCode, forKey: .errorCode)
        try c.encodeIfPresent(errorDetail, forKey: .errorDetail)
    }
}

// MARK: - Target Prices & Upside/Downside

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

// MARK: - Key Factors

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

// MARK: - Fundamentals Snapshot

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

// MARK: - Price Performance

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

// MARK: - News Item

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

// MARK: - QuickInfo

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

// MARK: - Piotroski Data

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

// MARK: — New Calibration Engine Fields (BETTER_AI_ANALYSIS_PROMPT)

struct ConfidenceCalibration: Codable {
    let rawLlmConfidence: Int?
    let signalAgreementRatio: Double?
    let regimeState: String?
    let regimeMultiplier: Double?
    let calibrationNote: String?
    enum CodingKeys: String, CodingKey {
        case rawLlmConfidence = "raw_llm_confidence"
        case signalAgreementRatio = "signal_agreement_ratio"
        case regimeState = "regime_state"
        case regimeMultiplier = "regime_multiplier"
        case calibrationNote = "calibration_note"
    }
}

struct TargetPriceBound: Codable {
    let lower: Double?
    let mid: Double?
    let upper: Double?
    let coveragePct: Int?
    enum CodingKeys: String, CodingKey {
        case lower, mid, upper
        case coveragePct = "coverage_pct"
    }
}

struct TargetPriceBounds: Codable {
    let shortTerm3m: TargetPriceBound?
    let mediumTerm12m: TargetPriceBound?
    let longTerm36m: TargetPriceBound?
    enum CodingKeys: String, CodingKey {
        case shortTerm3m = "short_term_3m"
        case mediumTerm12m = "medium_term_12m"
        case longTerm36m = "long_term_36m"
    }
}

struct HistoricalAnalogues: Codable {
    let kFound: Int?
    let historicalWinRatePct: Double?
    let avgReturnOnWinsPct: Double?
    let analogueSummary: String?
    enum CodingKeys: String, CodingKey {
        case kFound = "k_found"
        case historicalWinRatePct = "historical_win_rate_pct"
        case avgReturnOnWinsPct = "avg_return_on_wins_pct"
        case analogueSummary = "analogue_summary"
    }
}

struct MarketMicrostructure: Codable {
    let deliveryPct: Double?
    let deliverySignal: String?
    let oiPcr: Double?
    let volumePcr: Double?
    let dealerRegime: String?
    let minskyanFlag: Bool?
    let minskyanScore: Double?
    enum CodingKeys: String, CodingKey {
        case deliveryPct = "delivery_pct"
        case deliverySignal = "delivery_signal"
        case oiPcr = "oi_pcr"
        case volumePcr = "volume_pcr"
        case dealerRegime = "dealer_regime"
        case minskyanFlag = "minskyan_flag"
        case minskyanScore = "minskyan_score"
    }
}

struct SectorMomentum: Codable {
    let rrgQuadrant: String?
    let rsRatio: Double?
    let rsMomentum: Double?
    enum CodingKeys: String, CodingKey {
        case rrgQuadrant = "rrg_quadrant"
        case rsRatio = "rs_ratio"
        case rsMomentum = "rs_momentum"
    }
}

struct AuditorTenure: Codable {
    let auditorName: String?
    let tenureYears: Int?
    let isBig4: Bool?
    enum CodingKeys: String, CodingKey {
        case auditorName = "auditor_name"
        case tenureYears = "tenure_years"
        case isBig4 = "is_big4"
    }
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
