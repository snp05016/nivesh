import Foundation

// MARK: - ResearchReport contract `research.v1` (spec 6.1-6.2)
//
// Mirrors ml-engine/research/contract.py and the fixtures in
// docs/research/contract/fixtures/. Decoded with `NetworkManager.researchDecoder()`
// (a plain JSONDecoder), so every property maps its snake_case JSON key through an
// explicit CodingKeys enum.
//
// Decoding is lenient: everything is optional except `schemaVersion`, `symbol` and
// `asOf`, and every string enum falls back to `.unknown`, so additive v1 changes on
// the server never break a shipped build. Dates stay as the server's ISO strings.
//
// Every number is shown through the server's `display` string; the app never formats
// or recomputes a figure. Deliberately not decoded: the reserved per-horizon cohort
// block (no v1 UI, D9), the universe-membership block and the per-check Piotroski
// list (the screen shows only the tier text and "x of y available checks").

/// A server string enum that decodes any unrecognised value to `.unknown`.
protocol ResearchStringEnum: RawRepresentable, Codable, Equatable where RawValue == String {
    static var unknown: Self { get }
}

extension ResearchStringEnum {
    init(from decoder: Decoder) throws {
        let raw = (try? decoder.singleValueContainer().decode(String.self)) ?? ""
        self = Self(rawValue: raw) ?? .unknown
    }
}

// MARK: - 6.1 Fact

enum ResearchUnit: String, ResearchStringEnum {
    case inr, pct, pp, prob, pctl, ratio, x, count, sessions, unknown
    case inrCrore = "inr_cr"
}

enum ResearchFactStatus: String, ResearchStringEnum {
    case ok, stale, unavailable, unknown
}

enum ResearchSource: String, ResearchStringEnum {
    case yfinance, computed, model, unknown
    case nseBhavcopy = "nse_bhavcopy"
}

enum ResearchReasonCode: String, ResearchStringEnum {
    case sourceUnavailable = "source_unavailable"
    case staleSource = "stale_source"
    case insufficientHistory = "insufficient_history"
    case dataQualityFlag = "data_quality_flag"
    case notApplicableFinancials = "not_applicable_financials"
    case sourceNotIntegrated = "source_not_integrated"
    case notInUniverse = "not_in_universe"
    case backtestFailed = "backtest_failed"
    case policyHidden = "policy_hidden"
    case unknown
}

/// One computed figure. `display` is the server-formatted string shown verbatim;
/// it is nil exactly when `value` is nil (status `unavailable`, with a `reason`).
struct ResearchFact: Codable {
    let id: String?
    let label: String?
    let value: Double?
    let unit: ResearchUnit?
    let decimals: Int?
    let signed: Bool?
    let display: String?
    let status: ResearchFactStatus?
    let reason: ResearchReasonCode?
    let source: ResearchSource?
    let asOf: String?
    let method: String?

    enum CodingKeys: String, CodingKey {
        case id, label, value, unit, decimals, signed, display, status, reason, source, method
        case asOf = "as_of"
    }
}

// MARK: - 6.2 Report

enum ResearchOrigin: String, ResearchStringEnum {
    case nightly, unknown
    case onDemand = "on_demand"
}

enum ResearchReportStatus: String, ResearchStringEnum {
    case ok, degraded, unknown
}

struct ResearchReport: Codable {
    let schemaVersion: String
    let reportId: String?
    let engineVersion: String?
    let origin: ResearchOrigin?
    let status: ResearchReportStatus?
    let degradedReasons: [String]?
    let symbol: String
    let exchange: String?
    let isin: String?
    let companyName: String?
    let sector: String?
    let asOf: ResearchAsOf
    let snapshot: ResearchSnapshot?
    /// 21 then 63 trading days.
    let outlooks: [ResearchOutlook]?
    let factorProfile: ResearchFactorProfile?
    let risk: ResearchRisk?
    let fundamentals: ResearchFundamentals?
    let modelCard: ResearchModelCard?
    let provenance: ResearchProvenance?
    let pipeline: [ResearchPipelineStage]?
    // Backend-owned blocks: nil in raw ml-engine output.
    let staleness: ResearchStaleness?
    let narrative: ResearchNarrative?
    let liveTrackRecord: ResearchLiveTrackRecord?
    let compliance: ResearchCompliance?

    enum CodingKeys: String, CodingKey {
        case origin, status, symbol, exchange, isin, sector, snapshot, outlooks, risk, fundamentals
        case provenance, pipeline, staleness, narrative, compliance
        case schemaVersion = "schema_version"
        case reportId = "report_id"
        case engineVersion = "engine_version"
        case degradedReasons = "degraded_reasons"
        case companyName = "company_name"
        case asOf = "as_of"
        case factorProfile = "factor_profile"
        case modelCard = "model_card"
        case liveTrackRecord = "live_track_record"
    }
}

struct ResearchAsOf: Codable {
    /// Market session the report describes, "YYYY-MM-DD".
    let marketDate: String
    let computedAt: String?

    enum CodingKeys: String, CodingKey {
        case marketDate = "market_date"
        case computedAt = "computed_at"
    }
}

struct ResearchSnapshot: Codable {
    let benchmarkId: String?
    let lastClose: ResearchFact?
    let dayChangePct: ResearchFact?
    let r1mPct: ResearchFact?
    let r3mPct: ResearchFact?
    let r6mPct: ResearchFact?
    let r12mPct: ResearchFact?
    let nifty50R12mPct: ResearchFact?
    let excess12mVsNifty50Pp: ResearchFact?
    let high52w: ResearchFact?
    let low52w: ResearchFact?
    let pctBelow52wHigh: ResearchFact?
    let medianTurnover63dCr: ResearchFact?
    let marketCapCr: ResearchFact?

    enum CodingKeys: String, CodingKey {
        case benchmarkId = "benchmark_id"
        case lastClose = "last_close"
        case dayChangePct = "day_change_pct"
        case r1mPct = "r_1m_pct"
        case r3mPct = "r_3m_pct"
        case r6mPct = "r_6m_pct"
        case r12mPct = "r_12m_pct"
        case nifty50R12mPct = "nifty50_r_12m_pct"
        case excess12mVsNifty50Pp = "excess_12m_vs_nifty50_pp"
        case high52w = "high_52w"
        case low52w = "low_52w"
        case pctBelow52wHigh = "pct_below_52w_high"
        case medianTurnover63dCr = "median_turnover_63d_cr"
        case marketCapCr = "market_cap_cr"
    }
}

// MARK: Outlooks

enum ResearchEvidenceTier: String, ResearchStringEnum {
    case validatedEdge = "validated_edge"
    case weakEvidence = "weak_evidence"
    case noReliableEdge = "no_reliable_edge"
    case outOfUniverse = "out_of_universe"
    case unavailable
    case unknown
}

/// What testing found at one horizon. Shown as the server `tierText` and `event`
/// only; v1 never shows a stock-level number here.
struct ResearchOutlook: Codable {
    let horizonDays: Int?
    let horizonLabel: String?
    let event: String?
    let evidenceTier: ResearchEvidenceTier?
    /// e.g. "gate_failed:G1", "not_in_universe", "snapshot_expired".
    let reasonCodes: [String]?
    /// Backend-owned (tx-2 text for the served tier).
    let tierText: String?
    let procedureId: String?
    let modelId: String?
    /// Backend-owned ledger row id.
    let predictionId: Int?

    enum CodingKeys: String, CodingKey {
        case event
        case horizonDays = "horizon_days"
        case horizonLabel = "horizon_label"
        case evidenceTier = "evidence_tier"
        case reasonCodes = "reason_codes"
        case tierText = "tier_text"
        case procedureId = "procedure_id"
        case modelId = "model_id"
        case predictionId = "prediction_id"
    }
}

// MARK: Factor profile

enum ResearchFactorFamilyID: String, ResearchStringEnum {
    case momentum, reversal, risk, liquidity, trend, unknown
}

struct ResearchFactorProfile: Codable {
    let universeId: String?
    /// Five families in fixed display order.
    let families: [ResearchFactorFamily]?

    enum CodingKeys: String, CodingKey {
        case families
        case universeId = "universe_id"
    }
}

struct ResearchFactorFamily: Codable {
    let family: ResearchFactorFamilyID?
    /// Includes the "(higher = ...)" meaning.
    let label: String?
    let pctl: ResearchFact?
    let metrics: [ResearchFactorMetric]?
}

struct ResearchFactorMetric: Codable {
    let featureId: String?
    let label: String?
    let value: ResearchFact?
    let pctl: ResearchFact?

    enum CodingKeys: String, CodingKey {
        case label, value, pctl
        case featureId = "feature_id"
    }
}

// MARK: Risk

enum ResearchVaRStatus: String, ResearchStringEnum {
    case ok, unavailable, unknown
    case backtestFailed = "backtest_failed"
}

enum ResearchVaRMethod: String, ResearchStringEnum {
    case historical500d = "historical_500d"
    case fhsEwma = "fhs_ewma"
    case unknown
}

struct ResearchRisk: Codable {
    let volEwmaAnnPct: ResearchFact?
    let vol63dAnnPct: ResearchFact?
    let vol252dAnnPct: ResearchFact?
    let volPctl: ResearchFact?
    let beta: ResearchBeta?
    let varStatus: ResearchVaRStatus?
    /// Present only when `varStatus == .ok` (only methods that passed their backtest).
    let var1d: [ResearchVaRRow]?
    let drawdown: ResearchDrawdown?
    let drawdownSeries: ResearchDrawdownSeries?
    /// Descriptive historical ranges, 21 then 63; not a forecast.
    let returnRanges: [ResearchReturnRange]?

    enum CodingKeys: String, CodingKey {
        case beta, drawdown
        case volEwmaAnnPct = "vol_ewma_ann_pct"
        case vol63dAnnPct = "vol_63d_ann_pct"
        case vol252dAnnPct = "vol_252d_ann_pct"
        case volPctl = "vol_pctl"
        case varStatus = "var_status"
        case var1d = "var_1d"
        case drawdownSeries = "drawdown_series"
        case returnRanges = "return_ranges"
    }
}

struct ResearchBeta: Codable {
    let benchmarkId: String?
    let method: String?
    let raw: ResearchFact?
    let se: ResearchFact?
    let blumeAdjusted: ResearchFact?

    enum CodingKeys: String, CodingKey {
        case method, raw, se
        case benchmarkId = "benchmark_id"
        case blumeAdjusted = "blume_adjusted"
    }
}

struct ResearchVaRRow: Codable {
    /// 0.95 or 0.99.
    let level: Double?
    let method: ResearchVaRMethod?
    let varPct: ResearchFact?
    let cvarPct: ResearchFact?
    let backtest: ResearchVaRBacktest?

    enum CodingKeys: String, CodingKey {
        case level, method, backtest
        case varPct = "var_pct"
        case cvarPct = "cvar_pct"
    }
}

struct ResearchVaRBacktest: Codable {
    let windowDays: Int?
    let exceptions: Int?
    let expected: Double?
    let kupiecP: Double?
    let christoffersenP: Double?

    enum CodingKeys: String, CodingKey {
        case exceptions, expected
        case windowDays = "window_days"
        case kupiecP = "kupiec_p"
        case christoffersenP = "christoffersen_p"
    }
}

struct ResearchDrawdown: Codable {
    let max1y: ResearchFact?
    let max3y: ResearchFact?
    let max5y: ResearchFact?
    let current: ResearchFact?
    let daysSincePeak: ResearchFact?
    let ulcer1y: ResearchFact?

    enum CodingKeys: String, CodingKey {
        case max1y = "max_1y_pct"
        case max3y = "max_3y_pct"
        case max5y = "max_5y_pct"
        case current = "current_pct"
        case daysSincePeak = "days_since_peak"
        case ulcer1y = "ulcer_1y"
    }
}

struct ResearchDrawdownSeries: Codable {
    /// "W" (weekly).
    let freq: String?
    /// "pct".
    let unit: String?
    /// At most 160 weekly points.
    let points: [ResearchDrawdownPoint]?
}

/// One `[date, pct]` pair of the drawdown series, encoded as a two-element JSON array.
struct ResearchDrawdownPoint: Codable {
    /// "YYYY-MM-DD".
    let date: String
    /// Distance below the running peak, in percent (0 or negative).
    let pct: Double

    init(date: String, pct: Double) {
        self.date = date
        self.pct = pct
    }

    init(from decoder: Decoder) throws {
        var container = try decoder.unkeyedContainer()
        date = try container.decode(String.self)
        pct = try container.decode(Double.self)
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.unkeyedContainer()
        try container.encode(date)
        try container.encode(pct)
    }
}

/// The 10th-90th percentile of the stock's own past h-session returns (D11).
struct ResearchReturnRange: Codable {
    let horizonDays: Int?
    let low: ResearchFact?
    let high: ResearchFact?
    let windowSessions: Int?
    /// Server sentence ending "This is not a forecast."; nil when unavailable.
    let text: String?
    let method: String?

    enum CodingKeys: String, CodingKey {
        case text, method
        case horizonDays = "horizon_days"
        case low = "low_pct"
        case high = "high_pct"
        case windowSessions = "window_sessions"
    }
}

// MARK: Fundamentals (display only, Yahoo Finance, not point-in-time)

enum ResearchStatementBasis: String, ResearchStringEnum {
    // "unknown" is also a real contract value.
    case consolidated, standalone, unknown
}

struct ResearchFundamentals: Codable {
    let status: ResearchFactStatus?
    let reason: ResearchReasonCode?
    let source: String?
    let fetchedAt: String?
    let fiscalPeriodEnd: String?
    let pointInTime: Bool?
    let statementBasis: ResearchStatementBasis?
    let isFinancial: Bool?
    let valuation: ResearchValuation?
    let quality: ResearchQuality?
    let piotroski: ResearchPiotroski?
    let altmanZEm: ResearchScoreValue?
    let beneishM: ResearchScoreValue?

    enum CodingKeys: String, CodingKey {
        case status, reason, source, valuation, quality, piotroski
        case fetchedAt = "fetched_at"
        case fiscalPeriodEnd = "fiscal_period_end"
        case pointInTime = "point_in_time"
        case statementBasis = "statement_basis"
        case isFinancial = "is_financial"
        case altmanZEm = "altman_z_em"
        case beneishM = "beneish_m"
    }
}

struct ResearchValuation: Codable {
    let peTtm: ResearchFact?
    let pb: ResearchFact?
    let evEbitda: ResearchFact?
    let dividendYieldPct: ResearchFact?
    let peSectorPctl: ResearchFact?

    enum CodingKeys: String, CodingKey {
        case pb
        case peTtm = "pe_ttm"
        case evEbitda = "ev_ebitda"
        case dividendYieldPct = "dividend_yield_pct"
        case peSectorPctl = "pe_sector_pctl"
    }
}

struct ResearchQuality: Codable {
    let roePct: ResearchFact?
    let operatingMarginPct: ResearchFact?
    let debtToEquity: ResearchFact?
    let cfoToPat: ResearchFact?

    enum CodingKeys: String, CodingKey {
        case roePct = "roe_pct"
        case operatingMarginPct = "operating_margin_pct"
        case debtToEquity = "debt_to_equity"
        case cfoToPat = "cfo_to_pat"
    }
}

/// Shown as "{fScore} of {maxPossible} available checks"; no grade.
struct ResearchPiotroski: Codable {
    let fScore: ResearchFact?
    let maxPossible: ResearchFact?

    enum CodingKeys: String, CodingKey {
        case fScore = "f_score"
        case maxPossible = "max_possible"
    }
}

/// Altman Z''-score (emerging markets) or Beneish M-score: the value only.
/// `applicable == false` for banks, NBFCs and insurers.
struct ResearchScoreValue: Codable {
    let applicable: Bool?
    let value: ResearchFact?
}

// MARK: Model card, provenance, pipeline

enum ResearchUniverseQuality: String, ResearchStringEnum {
    case pit, unknown
    case survivorshipBiased = "survivorship_biased"
}

/// Summary model card; the statistical checks behind it are admin-only.
struct ResearchModelCard: Codable {
    let procedureId: String?
    let featureVersion: String?
    let universeId: String?
    let universeQuality: ResearchUniverseQuality?
    /// What the model ranks (the label it was trained on), in plain words.
    let labelDefinition: String?
    let dataPeriod: String?
    let trainedThrough: String?
    let manifestSha256: String?
    let limitations: [String]?
    let horizons: [ResearchModelCardHorizon]?

    enum CodingKeys: String, CodingKey {
        case limitations, horizons
        case procedureId = "procedure_id"
        case featureVersion = "feature_version"
        case universeId = "universe_id"
        case universeQuality = "universe_quality"
        case labelDefinition = "label_definition"
        case dataPeriod = "data_period"
        case trainedThrough = "trained_through"
        case manifestSha256 = "manifest_sha256"
    }
}

struct ResearchModelCardHorizon: Codable {
    let horizonDays: Int?
    /// Backend-owned served tier text.
    let tierText: String?

    enum CodingKeys: String, CodingKey {
        case horizonDays = "horizon_days"
        case tierText = "tier_text"
    }
}

enum ResearchSourceHealth: String, ResearchStringEnum {
    case ok, fallback, failed, unknown
}

struct ResearchProvenance: Codable {
    let engineVersion: String?
    let gitSha: String?
    let dataSnapshotId: String?
    let dataSha256: String?
    let featureVersion: String?
    let costModelVersion: String?
    let configSha256: String?
    let sources: [ResearchSourceStatus]?

    enum CodingKeys: String, CodingKey {
        case sources
        case engineVersion = "engine_version"
        case gitSha = "git_sha"
        case dataSnapshotId = "data_snapshot_id"
        case dataSha256 = "data_sha256"
        case featureVersion = "feature_version"
        case costModelVersion = "cost_model_version"
        case configSha256 = "config_sha256"
    }
}

struct ResearchSourceStatus: Codable {
    let id: ResearchSource?
    let lastSuccess: String?
    let status: ResearchSourceHealth?
    let note: String?

    enum CodingKeys: String, CodingKey {
        case id, status, note
        case lastSuccess = "last_success"
    }
}

enum ResearchPipelineStageName: String, ResearchStringEnum {
    case prices, universe, features, scores, risk, fundamentals, assemble, unknown
}

enum ResearchPipelineStatus: String, ResearchStringEnum {
    case ok, degraded, failed, skipped, unknown
}

struct ResearchPipelineStage: Codable {
    let stage: ResearchPipelineStageName?
    let status: ResearchPipelineStatus?
    let detail: String?
}

// MARK: Backend-owned blocks

enum ResearchStalenessState: String, ResearchStringEnum {
    case fresh, stale, expired, unknown
}

struct ResearchStaleness: Codable {
    let sessionsOld: Int?
    let state: ResearchStalenessState?

    enum CodingKeys: String, CodingKey {
        case state
        case sessionsOld = "sessions_old"
    }
}

enum ResearchNarrativeStatus: String, ResearchStringEnum {
    case template, unknown
    case llmValidated = "llm_validated"
}

enum ResearchNarrativeSectionID: String, ResearchStringEnum {
    case risk, fundamentals, unknown
    case factorProfile = "factor_profile"
}

/// Prose built only from computed facts (validated LLM text or a fixed template).
/// Render through `stripEmoji`.
struct ResearchNarrative: Codable {
    let status: ResearchNarrativeStatus?
    let language: String?
    let summary: String?
    let sections: [ResearchNarrativeSection]?
    let promptVersion: String?
    let validatorVersion: String?
    let attempts: Int?
    let factsHash: String?

    enum CodingKeys: String, CodingKey {
        case status, language, summary, sections, attempts
        case promptVersion = "prompt_version"
        case validatorVersion = "validator_version"
        case factsHash = "facts_hash"
    }
}

struct ResearchNarrativeSection: Codable {
    let id: ResearchNarrativeSectionID?
    let text: String?
}

enum ResearchLiveState: String, ResearchStringEnum {
    case collecting, ok, unknown
    case underReview = "under_review"
}

/// Live-ledger states only; never rates or IC.
struct ResearchLiveTrackRecord: Codable {
    let visible: Bool?
    let horizons: [ResearchLiveHorizon]?
}

struct ResearchLiveHorizon: Codable {
    let horizonDays: Int?
    let state: ResearchLiveState?
    let since: String?
    let maturedDates: Int?
    let independentPeriods: Int?
    let minPeriodsRequired: Int?

    enum CodingKeys: String, CodingKey {
        case state, since
        case horizonDays = "horizon_days"
        case maturedDates = "matured_dates"
        case independentPeriods = "independent_periods"
        case minPeriodsRequired = "min_periods_required"
    }
}

enum ResearchOutlookDisplay: String, ResearchStringEnum {
    case tierOnly = "tier_only"
    case cohortFrequency = "cohort_frequency"
    case unknown
}

struct ResearchCompliance: Codable {
    let mode: String?
    let disclaimerId: String?
    /// Always shown in the footer.
    let disclaimerText: String?
    /// Always shown in the footer.
    let aiDisclosure: String?
    let outlookDisplay: ResearchOutlookDisplay?
    let trackRecordVisible: Bool?
    let lexiconVersion: String?

    enum CodingKeys: String, CodingKey {
        case mode
        case disclaimerId = "disclaimer_id"
        case disclaimerText = "disclaimer_text"
        case aiDisclosure = "ai_disclosure"
        case outlookDisplay = "outlook_display"
        case trackRecordVisible = "track_record_visible"
        case lexiconVersion = "lexicon_version"
    }
}
