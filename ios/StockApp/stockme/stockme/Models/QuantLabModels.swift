import Foundation

// MARK: - ML Signal

struct FeatureDriver: Codable {
    let feature: String
    let contribution: Double
    let direction: String

    enum CodingKeys: String, CodingKey {
        case feature, contribution, direction
    }
}

struct MLReliability: Codable {
    let hitRate30d: Double?
    let brierScore30d: Double?
    let calibrationError30d: Double?

    enum CodingKeys: String, CodingKey {
        case hitRate30d = "hit_rate_30d"
        case brierScore30d = "brier_score_30d"
        case calibrationError30d = "calibration_error_30d"
    }
}

struct MLSignalResponse: Codable {
    let symbol: String
    let direction: Int
    let directionLabel: String
    let confidence: Double?
    let confidencePct: Int?
    let modelVersion: String?
    let modelStatus: String?
    let mlEngineMode: String
    let lightgbmLoaded: Bool
    let predictionHorizon: String
    let generatedAt: String
    let featureDrivers: [FeatureDriver]
    let reliability: MLReliability?
    let status: String
    let warning: String?

    enum CodingKeys: String, CodingKey {
        case symbol, direction, confidence, status, warning, reliability
        case directionLabel = "direction_label"
        case confidencePct = "confidence_pct"
        case modelVersion = "model_version"
        case modelStatus = "model_status"
        case mlEngineMode = "ml_engine_mode"
        case lightgbmLoaded = "lightgbm_loaded"
        case predictionHorizon = "prediction_horizon"
        case generatedAt = "generated_at"
        case featureDrivers = "feature_drivers"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        symbol = try container.decode(String.self, forKey: .symbol)
        direction = try container.decode(Int.self, forKey: .direction)
        directionLabel = try container.decode(String.self, forKey: .directionLabel)
        confidence = try container.decodeIfPresent(Double.self, forKey: .confidence)
        confidencePct = try container.decodeIfPresent(Int.self, forKey: .confidencePct)
        modelVersion = try container.decodeIfPresent(String.self, forKey: .modelVersion)
        modelStatus = try container.decodeIfPresent(String.self, forKey: .modelStatus)
        mlEngineMode = try container.decode(String.self, forKey: .mlEngineMode)
        lightgbmLoaded = try container.decodeIfPresent(Bool.self, forKey: .lightgbmLoaded) ?? false
        predictionHorizon = try container.decodeIfPresent(String.self, forKey: .predictionHorizon) ?? "20d"
        generatedAt = try container.decode(String.self, forKey: .generatedAt)
        featureDrivers = try container.decodeIfPresent([FeatureDriver].self, forKey: .featureDrivers) ?? []
        reliability = try container.decodeIfPresent(MLReliability.self, forKey: .reliability)
        status = try container.decode(String.self, forKey: .status)
        warning = try container.decodeIfPresent(String.self, forKey: .warning)
    }
}

// MARK: - Calibration

struct CalibrationBucket: Codable {
    let bucketLabel: String
    let count: Int
    let accuracy: Double?
    let avgBrierScore: Double?
    let avgConfidence: Double?
    let overconfidence: Double?

    enum CodingKeys: String, CodingKey {
        case count, accuracy, overconfidence
        case bucketLabel = "bucket_label"
        case avgBrierScore = "avg_brier_score"
        case avgConfidence = "avg_confidence"
    }
}

struct HorizonHitRate: Codable {
    let horizon: String
    let maturedCount: Int
    let hitRate: Double?

    enum CodingKeys: String, CodingKey {
        case horizon
        case maturedCount = "matured_count"
        case hitRate = "hit_rate"
    }
}

struct GroupCalibration: Codable {
    let groupKey: String
    let count: Int
    let accuracy: Double?
    let avgBrierScore: Double?
    let avgConfidence: Double?
    let calibrationError: Double?

    enum CodingKeys: String, CodingKey {
        case count, accuracy
        case groupKey = "group_key"
        case avgBrierScore = "avg_brier_score"
        case avgConfidence = "avg_confidence"
        case calibrationError = "calibration_error"
    }
}

struct CalibrationResponse: Codable {
    let confidenceBucketAccuracy: [CalibrationBucket]
    let brierScoreByBucket: [CalibrationBucket]
    let overconfidenceByBucket: [CalibrationBucket]
    let calibrationError: Double?
    let expectedCalibrationError: Double?
    let maxCalibrationError: Double?
    let hitRateByHorizon: [HorizonHitRate]
    let calibrationByScanType: [GroupCalibration]
    let calibrationByRegime: [GroupCalibration]
    let calibrationBySector: [GroupCalibration]
    let calibrationByMlEngineMode: [GroupCalibration]
    let calibrationByRecommendation: [GroupCalibration]

    enum CodingKeys: String, CodingKey {
        case confidenceBucketAccuracy = "confidence_bucket_accuracy"
        case brierScoreByBucket = "brier_score_by_bucket"
        case overconfidenceByBucket = "overconfidence_by_bucket"
        case calibrationError = "calibration_error"
        case expectedCalibrationError = "expected_calibration_error"
        case maxCalibrationError = "max_calibration_error"
        case hitRateByHorizon = "hit_rate_by_horizon"
        case calibrationByScanType = "calibration_by_scan_type"
        case calibrationByRegime = "calibration_by_regime"
        case calibrationBySector = "calibration_by_sector"
        case calibrationByMlEngineMode = "calibration_by_ml_engine_mode"
        case calibrationByRecommendation = "calibration_by_recommendation"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        confidenceBucketAccuracy = try container.decodeIfPresent([CalibrationBucket].self, forKey: .confidenceBucketAccuracy) ?? []
        brierScoreByBucket = try container.decodeIfPresent([CalibrationBucket].self, forKey: .brierScoreByBucket) ?? []
        overconfidenceByBucket = try container.decodeIfPresent([CalibrationBucket].self, forKey: .overconfidenceByBucket) ?? []
        calibrationError = try container.decodeIfPresent(Double.self, forKey: .calibrationError)
        expectedCalibrationError = try container.decodeIfPresent(Double.self, forKey: .expectedCalibrationError)
        maxCalibrationError = try container.decodeIfPresent(Double.self, forKey: .maxCalibrationError)
        hitRateByHorizon = try container.decodeIfPresent([HorizonHitRate].self, forKey: .hitRateByHorizon) ?? []
        calibrationByScanType = try container.decodeIfPresent([GroupCalibration].self, forKey: .calibrationByScanType) ?? []
        calibrationByRegime = try container.decodeIfPresent([GroupCalibration].self, forKey: .calibrationByRegime) ?? []
        calibrationBySector = try container.decodeIfPresent([GroupCalibration].self, forKey: .calibrationBySector) ?? []
        calibrationByMlEngineMode = try container.decodeIfPresent([GroupCalibration].self, forKey: .calibrationByMlEngineMode) ?? []
        calibrationByRecommendation = try container.decodeIfPresent([GroupCalibration].self, forKey: .calibrationByRecommendation) ?? []
    }
}

// MARK: - Pillar Attribution

struct PillarAttribution: Codable {
    let pillarName: String
    let correlationWithOutcome: Double?
    let bucketedAccuracy: [CalibrationBucket]
    let avgBrierScore: Double?
    let predictiveLift: Double?
    let missingRate: Double
    let usefulnessRank: Int?

    enum CodingKeys: String, CodingKey {
        case pillarName = "pillar_name"
        case correlationWithOutcome = "correlation_with_outcome"
        case bucketedAccuracy = "bucketed_accuracy"
        case avgBrierScore = "avg_brier_score"
        case predictiveLift = "predictive_lift"
        case missingRate = "missing_rate"
        case usefulnessRank = "usefulness_rank"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        pillarName = try container.decode(String.self, forKey: .pillarName)
        correlationWithOutcome = try container.decodeIfPresent(Double.self, forKey: .correlationWithOutcome)
        bucketedAccuracy = try container.decodeIfPresent([CalibrationBucket].self, forKey: .bucketedAccuracy) ?? []
        avgBrierScore = try container.decodeIfPresent(Double.self, forKey: .avgBrierScore)
        predictiveLift = try container.decodeIfPresent(Double.self, forKey: .predictiveLift)
        missingRate = try container.decodeIfPresent(Double.self, forKey: .missingRate) ?? 0.0
        usefulnessRank = try container.decodeIfPresent(Int.self, forKey: .usefulnessRank)
    }
}

struct PillarAttributionResponse: Codable {
    let pillars: [PillarAttribution]
    let totalPredictions: Int

    enum CodingKeys: String, CodingKey {
        case pillars
        case totalPredictions = "total_predictions"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        pillars = try container.decodeIfPresent([PillarAttribution].self, forKey: .pillars) ?? []
        totalPredictions = try container.decodeIfPresent(Int.self, forKey: .totalPredictions) ?? 0
    }
}

// MARK: - Model Versions

struct ModelVersionStats: Codable {
    let modelVersion: String
    let mlEngineMode: String?
    let totalPredictions: Int
    let hitRate7d: Double?
    let hitRate30d: Double?
    let hitRate90d: Double?
    let averageReturn30d: Double?
    let brierScore30d: Double?
    let calibrationError30d: Double?
    let confidenceAvg: Double?
    let confidenceRealizedAccuracyGap: Double?

    enum CodingKeys: String, CodingKey {
        case modelVersion = "model_version"
        case mlEngineMode = "ml_engine_mode"
        case totalPredictions = "total_predictions"
        case hitRate7d = "hit_rate_7d"
        case hitRate30d = "hit_rate_30d"
        case hitRate90d = "hit_rate_90d"
        case averageReturn30d = "average_return_30d"
        case brierScore30d = "brier_score_30d"
        case calibrationError30d = "calibration_error_30d"
        case confidenceAvg = "confidence_avg"
        case confidenceRealizedAccuracyGap = "confidence_realized_accuracy_gap"
    }
}

struct ModelVersionsResponse: Codable {
    let versions: [ModelVersionStats]
    let totalPredictions: Int

    enum CodingKeys: String, CodingKey {
        case versions
        case totalPredictions = "total_predictions"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        versions = try container.decodeIfPresent([ModelVersionStats].self, forKey: .versions) ?? []
        totalPredictions = try container.decodeIfPresent(Int.self, forKey: .totalPredictions) ?? 0
    }
}

// MARK: - Backtest

struct BacktestParams: Codable {
    let horizon: String = "30d"
    let strategyType: String = "momentum"
    let topK: Int = 10
    let confidenceThreshold: Double = 0.5
    let positionSizing: String = "equal"
    let costPreset: String = "medium"

    enum CodingKeys: String, CodingKey {
        case horizon
        case strategyType = "strategy_type"
        case topK = "top_k"
        case confidenceThreshold = "confidence_threshold"
        case positionSizing = "position_sizing"
        case costPreset = "cost_preset"
    }
}

struct PortfolioMetrics: Codable {
    let grossReturn: Double = 0
    let netReturn: Double = 0
    let cagr: Double = 0
    let sharpe: Double = 0
    let sortino: Double = 0
    let maxDrawdown: Double = 0
    let volatility: Double = 0
    let hitRate: Double = 0
    let averageWin: Double = 0
    let averageLoss: Double = 0
    let profitFactor: Double = 0
    let turnover: Double = 0
    let averageHoldingPeriod: Double? = nil
    let exposure: Double? = nil
    let cashPercentage: Double? = nil
    let sectorConcentration: Double? = nil
    let drawdownDuration: Double? = nil
    let benchmarkExcessReturn: Double = 0

    enum CodingKeys: String, CodingKey {
        case cagr, sharpe, sortino, volatility, turnover, exposure
        case grossReturn = "gross_return"
        case netReturn = "net_return"
        case maxDrawdown = "max_drawdown"
        case hitRate = "hit_rate"
        case averageWin = "average_win"
        case averageLoss = "average_loss"
        case profitFactor = "profit_factor"
        case averageHoldingPeriod = "average_holding_period"
        case cashPercentage = "cash_percentage"
        case sectorConcentration = "sector_concentration"
        case drawdownDuration = "drawdown_duration"
        case benchmarkExcessReturn = "benchmark_excess_return"
    }
}

struct BacktestResult: Codable {
    let params: BacktestParams
    let metrics: PortfolioMetrics
    let benchmarkMetrics: [String: AnyCodableValue]?
    let statisticalSignificance: [String: AnyCodableValue]?

    enum CodingKeys: String, CodingKey {
        case params, metrics
        case benchmarkMetrics = "benchmark_metrics"
        case statisticalSignificance = "statistical_significance"
    }
}

// MARK: - Strategy Sweep

struct SweepIteration: Codable {
    let confidenceThreshold: Double
    let topK: Int
    let holdingPeriod: String
    let positionSizing: String
    let netCagr: Double
    let sharpe: Double
    let maxDrawdown: Double
    let turnover: Double
    let tradeCount: Int

    enum CodingKeys: String, CodingKey {
        case sharpe, turnover
        case confidenceThreshold = "confidence_threshold"
        case topK = "top_k"
        case holdingPeriod = "holding_period"
        case positionSizing = "position_sizing"
        case netCagr = "net_cagr"
        case maxDrawdown = "max_drawdown"
        case tradeCount = "trade_count"
    }
}

struct StrategySweepResponse: Codable {
    let bestCagr: SweepIteration?
    let bestSharpe: SweepIteration?
    let allResults: [SweepIteration]
    let status: String?

    enum CodingKeys: String, CodingKey {
        case status
        case bestCagr = "best_cagr"
        case bestSharpe = "best_sharpe"
        case allResults = "all_results"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        bestCagr = try container.decodeIfPresent(SweepIteration.self, forKey: .bestCagr)
        bestSharpe = try container.decodeIfPresent(SweepIteration.self, forKey: .bestSharpe)
        allResults = try container.decodeIfPresent([SweepIteration].self, forKey: .allResults) ?? []
        status = try container.decodeIfPresent(String.self, forKey: .status)
    }
}

// MARK: - Regime Breakdown

struct RegimePerformance: Codable {
    let regimeName: String
    let sampleSize: Int
    let netCagr: Double?
    let sharpe: Double?
    let maxDrawdown: Double?
    let hitRate: Double?

    enum CodingKeys: String, CodingKey {
        case sharpe
        case regimeName = "regime_name"
        case sampleSize = "sample_size"
        case netCagr = "net_cagr"
        case maxDrawdown = "max_drawdown"
        case hitRate = "hit_rate"
    }
}

struct RegimeBreakdownResponse: Codable {
    let overallMetrics: PortfolioMetrics?
    let regimes: [RegimePerformance]
    let conclusion: String?
    let status: String?

    enum CodingKeys: String, CodingKey {
        case regimes, conclusion, status
        case overallMetrics = "overall_metrics"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        overallMetrics = try container.decodeIfPresent(PortfolioMetrics.self, forKey: .overallMetrics)
        regimes = try container.decodeIfPresent([RegimePerformance].self, forKey: .regimes) ?? []
        conclusion = try container.decodeIfPresent(String.self, forKey: .conclusion)
        status = try container.decodeIfPresent(String.self, forKey: .status)
    }
}

// MARK: - Cost Sensitivity

struct CostPresetResult: Codable {
    let cagr: Double?
    let sharpe: Double?
    let maxDrawdown: Double?
    let netReturn: Double?
    let grossReturn: Double?
    let turnover: Double?
    let error: String?

    enum CodingKeys: String, CodingKey {
        case cagr, sharpe, turnover, error
        case maxDrawdown = "max_drawdown"
        case netReturn = "net_return"
        case grossReturn = "gross_return"
    }
}

struct CostSensitivityResponse: Codable {
    let presets: [String: CostPresetResult]
    let status: String?
    let warning: String?

    enum CodingKeys: String, CodingKey {
        case presets, status, warning
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        presets = try container.decodeIfPresent([String: CostPresetResult].self, forKey: .presets) ?? [:]
        status = try container.decodeIfPresent(String.self, forKey: .status)
        warning = try container.decodeIfPresent(String.self, forKey: .warning)
    }
}

// MARK: - Calibration Health

struct CalibrationHealthResponse: Codable {
    let totalPredictions: Int
    let matured7d: Int
    let matured30d: Int
    let matured90d: Int
    let latestPredictionDate: String?
    let isReadyForCalibration: Bool
    let warnings: [String]

    enum CodingKeys: String, CodingKey {
        case warnings
        case totalPredictions = "total_predictions"
        case matured7d = "matured_7d"
        case matured30d = "matured_30d"
        case matured90d = "matured_90d"
        case latestPredictionDate = "latest_prediction_date"
        case isReadyForCalibration = "is_ready_for_calibration"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        totalPredictions = try container.decodeIfPresent(Int.self, forKey: .totalPredictions) ?? 0
        matured7d = try container.decodeIfPresent(Int.self, forKey: .matured7d) ?? 0
        matured30d = try container.decodeIfPresent(Int.self, forKey: .matured30d) ?? 0
        matured90d = try container.decodeIfPresent(Int.self, forKey: .matured90d) ?? 0
        latestPredictionDate = try container.decodeIfPresent(String.self, forKey: .latestPredictionDate)
        isReadyForCalibration = try container.decodeIfPresent(Bool.self, forKey: .isReadyForCalibration) ?? false
        warnings = try container.decodeIfPresent([String].self, forKey: .warnings) ?? []
    }
}

// MARK: - Fusion Weight Recommendations

struct FusionWeightRecommendationResponse: Codable {
    let recommendedWeights: [String: AnyCodableValue]
    let warnings: [String]
    let applyRecommendation: Bool
    let isConfident: Bool

    enum CodingKeys: String, CodingKey {
        case warnings
        case recommendedWeights = "recommended_weights"
        case applyRecommendation = "apply_recommendation"
        case isConfident = "is_confident"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        recommendedWeights = try container.decodeIfPresent([String: AnyCodableValue].self, forKey: .recommendedWeights) ?? [:]
        warnings = try container.decodeIfPresent([String].self, forKey: .warnings) ?? []
        applyRecommendation = try container.decodeIfPresent(Bool.self, forKey: .applyRecommendation) ?? false
        isConfident = try container.decodeIfPresent(Bool.self, forKey: .isConfident) ?? false
    }
}

// MARK: - AnyCodableValue (for Dict[str, Any] fields)

enum AnyCodableValue: Codable {
    case string(String)
    case int(Int)
    case double(Double)
    case bool(Bool)
    case null

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if container.decodeNil() {
            self = .null
            return
        }
        if let boolVal = try? container.decode(Bool.self) {
            self = .bool(boolVal)
            return
        }
        if let intVal = try? container.decode(Int.self) {
            self = .int(intVal)
            return
        }
        if let doubleVal = try? container.decode(Double.self) {
            self = .double(doubleVal)
            return
        }
        if let stringVal = try? container.decode(String.self) {
            self = .string(stringVal)
            return
        }
        self = .null
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .string(let val): try container.encode(val)
        case .int(let val): try container.encode(val)
        case .double(let val): try container.encode(val)
        case .bool(let val): try container.encode(val)
        case .null: try container.encodeNil()
        }
    }

    var doubleValue: Double? {
        switch self {
        case .double(let val): return val
        case .int(let val): return Double(val)
        default: return nil
        }
    }

    var stringValue: String? {
        switch self {
        case .string(let val): return val
        default: return nil
        }
    }

    var boolValue: Bool? {
        switch self {
        case .bool(let val): return val
        default: return nil
        }
    }
}
