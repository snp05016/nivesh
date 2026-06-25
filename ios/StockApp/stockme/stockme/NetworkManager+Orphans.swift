import Foundation
import Combine

// MARK: - Orphaned Endpoint Coverage
// Backend endpoints that lacked iOS API methods — now wired.

extension NetworkManager {

    // ── Health ────────────────────────────────────────────────────────
    func checkHealthLite() async throws -> HealthStatus {
        try await _fetchDecode("/health", as: HealthStatus.self)
    }

    // ── Cache & Admin ─────────────────────────────────────────────────
    func fetchCacheStatus(ticker: String) async throws -> CacheStatus {
        try await _fetchDecode("/analyze/cache-status/\(ticker.uppercased())", as: CacheStatus.self)
    }
    func invalidateCache(ticker: String, scanType: String = "all") async throws {
        let _: [String: Any] = try await _fetchDecode("/analyze/cache/\(ticker.uppercased())/invalidate?scan_type=\(scanType)")
    }
    func fetchAnalysisSlots() async throws -> SlotsInfo {
        try await _fetchDecode("/analyze/slots", as: SlotsInfo.self, auth: true)
    }
    func releaseAnalysisSlots(userId: Int? = nil) async throws {
        var path = "/analyze/slots"
        if let uid = userId { path += "?user_id=\(uid)" }
        let _: [String: Any] = try await _fetchDecode(path)
    }
    func submitBatchAnalysis(tickers: [String], userId: Int) async throws -> BatchResult {
        try await _fetchDecode("/batch", method: "POST",
            body: ["tickers": tickers, "user_id": userId], as: BatchResult.self)
    }
    func fetchBatchStatus(batchId: String) async throws -> BatchResult {
        try await _fetchDecode("/analyze/batch/\(batchId)", as: BatchResult.self)
    }

    // ── Portfolio Additions ───────────────────────────────────────────
    func fetchPortfolioHistory(userId: Int, days: Int = 30) async throws -> [PortfolioHistoryEntry] {
        try await _fetchDecode("/portfolio/history/\(userId)?days=\(days)", as: [PortfolioHistoryEntry].self)
    }
    func fetchBenchmark(userId: Int) async throws -> BenchmarkData {
        try await _fetchDecode("/portfolio/benchmark?user_id=\(userId)", as: BenchmarkData.self, auth: true)
    }
    func fetchNetWorthLedger(userId: Int) async throws -> [NetWorthEntry] {
        try await _fetchDecode("/api/v1/market/net-worth-ledger/\(userId)", as: [NetWorthEntry].self, auth: true)
    }
    func fetchAttribution(userId: Int) async throws -> AttributionData {
        try await _fetchDecode("/attribution/\(userId)", as: AttributionData.self, auth: true)
    }
    func fetchSignalAccuracy() async throws -> SignalAccuracy {
        try await _fetchDecode("/signal-accuracy", as: SignalAccuracy.self)
    }
    func calculateSIP(monthlyAmount: Double, expectedReturnPct: Double, years: Int, stepUpPct: Double = 0) async throws -> SIPResult {
        try await _fetchDecode("/portfolio/sip-calculator", method: "POST",
            body: ["monthly_amount": monthlyAmount, "expected_return_pct": expectedReturnPct, "years": years, "step_up_pct": stepUpPct], as: SIPResult.self)
    }
    func exportPortfolioPDF(userId: Int) async throws -> URL {
        let urlStr = "\(baseURL)/portfolio/export/pdf/\(userId)"
        guard let url = URL(string: urlStr) else { throw NetworkError.invalidURL }
        var req = URLRequest(url: url)
        if let token = authToken { req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }
        let (tempURL, _) = try await URLSession.shared.download(for: req)
        return tempURL
    }

    // ── Market Data Additions ─────────────────────────────────────────
    func fetchDividends(ticker: String, exchange: String = "NSE") async throws -> DividendData {
        try await _fetchDecode("/dividends/\(ticker.uppercased())?exchange=\(exchange)", as: DividendData.self)
    }
    func fetchMFNAV(schemeCode: String) async throws -> MFNAVData {
        try await _fetchDecode("/mf/\(schemeCode)", as: MFNAVData.self)
    }
    func fetchBlockDeals(ticker: String) async throws -> [BlockDealEntry] {
        try await _fetchDecode("/block-deals/\(ticker.uppercased())", as: [BlockDealEntry].self)
    }
    func fetchFIIDIIFlow(limit: Int = 30) async throws -> [FIIDIIEntry] {
        try await _fetchDecode("/fii-dii-flow?limit=\(limit)", as: [FIIDIIEntry].self)
    }
    func fetchIPOCalendar() async throws -> [IPOEntry] {
        try await _fetchDecode("/ipo-calendar", as: [IPOEntry].self)
    }
    func fetchSectorWeekly() async throws -> SectorWeekly {
        try await _fetchDecode("/sector-weekly", as: SectorWeekly.self)
    }
    func fetchInstitutionalLeaderboard() async throws -> [InstitutionalLeader] {
        try await _fetchDecode("/api/v1/market/institutional-leaderboard", as: [InstitutionalLeader].self)
    }
    func fetchSentimentTrend(ticker: String, days: Int = 30) async throws -> SentimentTrend {
        try await _fetchDecode("/market/sentiment-trend/\(ticker.uppercased())?days=\(days)", as: SentimentTrend.self)
    }
    func fetchMarketScreener(preset: String = "52w_breakout") async throws -> [ScreenerResult] {
        try await _fetchDecode("/market/screener?preset=\(preset)", as: [ScreenerResult].self)
    }
    func fetchOptionsChain(ticker: String, currentPrice: Double = 0) async throws -> OptionsChain {
        try await _fetchDecode("/api/v1/options/chain/\(ticker.uppercased())?current_price=\(currentPrice)", as: OptionsChain.self)
    }

    // ── Earnings Additions ────────────────────────────────────────────
    func fetchEarningsSyncRatio() async throws -> EarningsSyncData {
        try await _fetchDecode("/api/v1/earnings/sync-ratio", as: EarningsSyncData.self)
    }
    func fetchEarningsYoYAggregate() async throws -> EarningsYoYData {
        try await _fetchDecode("/api/v1/earnings/yoy-aggregate", as: EarningsYoYData.self)
    }
    func fetchMyEarningsAlerts(userId: Int) async throws -> [EarningsAlert] {
        try await _fetchDecode("/api/v1/earnings/alerts?user_id=\(userId)", as: [EarningsAlert].self)
    }
    func deleteEarningsAlert(alertId: Int) async throws {
        let _: EmptyResponse = try await _fetchDecode("/api/v1/earnings/alerts/\(alertId)", method: "DELETE",
            body: [:], as: EmptyResponse.self, auth: true)
    }
    func fetchEarningsSurpriseHistory(ticker: String) async throws -> [SurpriseHistoryEntry] {
        try await _fetchDecode("/api/v1/earnings/surprise-history/\(ticker.uppercased())", as: [SurpriseHistoryEntry].self)
    }

    // ── Predictions & QuantLab ────────────────────────────────────────
    func fetchPredictionsPerformance() async throws -> PredictionsPerformance {
        try await _fetchDecode("/api/v1/predictions/performance", as: PredictionsPerformance.self, auth: true)
    }
    func fetchCalibrationHealth() async throws -> CalibrationHealth {
        try await _fetchDecode("/api/v1/predictions/calibration/health", as: CalibrationHealth.self, auth: true)
    }
    func fetchFusionWeightRecommendations() async throws -> FusionWeights {
        try await _fetchDecode("/api/v1/predictions/fusion-weight-recommendations", as: FusionWeights.self, auth: true)
    }

    // ── Harvester Additions ───────────────────────────────────────────
    func searchHarvester(query: String, limit: Int = 30) async throws -> [HarvesterCard] {
        try await _fetchDecode("/harvester/search?q=\(query.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? query)&limit=\(limit)", as: [HarvesterCard].self)
    }
    func triggerScrape(source: String, limit: Int = 20) async throws -> ScrapeResult {
        try await _fetchDecode("/harvester/trigger/scrape?source=\(source)&limit=\(limit)", method: "POST", body: [:], as: ScrapeResult.self, auth: true)
    }
    func fetchHarvesterStats() async throws -> HarvesterStats {
        try await _fetchDecode("/harvester/stats", as: HarvesterStats.self, auth: true)
    }

    // ── Dashboard Additions ───────────────────────────────────────────
    func fetchAIEngineJobs(mode: String = "running", ticker: String? = nil, limit: Int = 20) async throws -> [AIEngineJob] {
        var path = "/api/v1/dashboard/ai-engine?mode=\(mode)&limit=\(limit)"
        if let t = ticker { path += "&ticker=\(t.uppercased())" }
        return try await _fetchDecode(path, as: [AIEngineJob].self, auth: true)
    }
    func fetchAIEngineJobDetail(jobId: String) async throws -> AIEngineJob {
        try await _fetchDecode("/api/v1/dashboard/ai-engine/\(jobId)", as: AIEngineJob.self, auth: true)
    }

    // ── Stress Test Additions ─────────────────────────────────────────
    func fetchStressTestProgress(jobId: String) async throws -> StressTestProgress {
        try await _fetchDecode("/api/v1/portfolio/stress-test/\(jobId)/progress", as: StressTestProgress.self)
    }
    func fetchStressTestJobs() async throws -> [StressTestJob] {
        try await _fetchDecode("/api/v1/dashboard/stress-test-jobs", as: [StressTestJob].self, auth: true)
    }

    // ── Token Stats (admin) ───────────────────────────────────────────
    func fetchTokenStats() async throws -> TokenStats {
        try await _fetchDecode("/token-stats", as: TokenStats.self, auth: true)
    }
}


// MARK: - Response Models for Orphaned Endpoints

struct HealthStatus: Codable { let status: String }
struct CacheStatus: Codable {
    let ticker: String?
    let scan_type: String?
    let cached: Bool?
    let stale: Bool?
    let staleness_score: Int?
    let cache_date: String?
}
struct SlotsInfo: Codable { let total: Int?; let used: Int?; let available: Int? }
struct BatchResult: Codable { let batch_id: String?; let status: String?; let results: [BatchAnalysisResult]? }
struct BatchAnalysisResult: Codable { let ticker: String?; let status: String? }
struct PortfolioHistoryEntry: Codable, Identifiable {
    var id: String { "\(date ?? "")_\(ticker ?? "")" }
    let ticker: String?; let date: String?; let value: Double?; let change_pct: Double?
}
struct BenchmarkData: Codable {
    let portfolio_cagr: Double?; let benchmark_cagr: Double?; let alpha: Double?
    let tracking_error: Double?; let information_ratio: Double?
}
struct NetWorthEntry: Codable, Identifiable {
    var id: String { date ?? UUID().uuidString }
    let date: String?; let net_worth: Double?; let change_pct: Double?
}
struct AttributionData: Codable {
    let sector_attribution: [AttributionItem]?; let stock_attribution: [AttributionItem]?
}
struct AttributionItem: Codable, Identifiable {
    var id: String { name ?? UUID().uuidString }
    let name: String?; let contribution: Double?
}
struct SignalAccuracy: Codable {
    let overall_accuracy: Double?; let by_signal: [SignalAccuracyItem]?
}
struct SignalAccuracyItem: Codable, Identifiable {
    var id: String { signal ?? UUID().uuidString }
    let signal: String?; let accuracy: Double?; let count: Int?
}
struct SIPResult: Codable {
    let total_investment: Double?; let maturity_value: Double?; let total_gain: Double?
    let yearly_breakdown: [SIPYearRow]?
}
struct SIPYearRow: Codable, Identifiable { var id: String { "\(year ?? 0)" }; let year: Int?; let invested: Double?; let value: Double? }
struct DividendData: Codable { let ticker: String?; let next_ex_date: String?; let dividends: [DividendEntry]? }
struct DividendEntry: Codable, Identifiable { var id: String { date ?? "" }; let date: String?; let amount: Double?; let yield_pct: Double? }
struct MFNAVData: Codable { let scheme_code: String?; let nav: Double?; let date: String? }
struct BlockDealEntry: Codable, Identifiable { var id: String { "\(date ?? "")_\(quantity ?? 0)" }; let date: String?; let quantity: Int?; let price: Double?; let type: String? }
struct FIIDIIEntry: Codable, Identifiable { var id: String { date ?? UUID().uuidString }; let date: String?; let fii_net: Double?; let dii_net: Double? }
struct IPOEntry: Codable, Identifiable { var id: String { name ?? UUID().uuidString }; let name: String?; let open_date: String?; let close_date: String?; let price_band: String? }
struct SectorWeekly: Codable { let sectors: [SectorWeeklyItem]? }
struct SectorWeeklyItem: Codable, Identifiable { var id: String { sector ?? UUID().uuidString }; let sector: String?; let change_pct: Double? }
struct InstitutionalLeader: Codable, Identifiable { var id: String { ticker ?? UUID().uuidString }; let ticker: String?; let fii_holding_pct: Double?; let dii_holding_pct: Double?; let change_qoq: Double? }
struct SentimentTrend: Codable { let ticker: String?; let sentiment_scores: [SentimentPoint]? }
struct SentimentPoint: Codable, Identifiable { var id: String { date ?? UUID().uuidString }; let date: String?; let score: Double? }
struct ScreenerResult: Codable, Identifiable { var id: String { ticker ?? UUID().uuidString }; let ticker: String?; let company: String?; let score: Double? }
struct OptionsChain: Codable { let ticker: String?; let spot_price: Double?; let calls: [OptionContract]?; let puts: [OptionContract]? }
struct OptionContract: Codable, Identifiable { var id: String { "\(strike ?? 0)_\(expiry ?? "")" }; let strike: Double?; let expiry: String?; let premium: Double?; let oi: Int? }
struct EarningsSyncData: Codable { let sync_ratio: Double?; let total_estimates: Int?; let total_actuals: Int? }
struct EarningsYoYData: Codable { let revenue_growth: Double?; let profit_growth: Double?; let sectors: [YoYSector]? }
struct YoYSector: Codable, Identifiable { var id: String { sector ?? UUID().uuidString }; let sector: String?; let growth: Double? }
struct EarningsAlert: Codable, Identifiable { var id: Int?; let ticker: String?; let earnings_date: String?; let user_id: Int? }
struct SurpriseHistoryEntry: Codable, Identifiable { var id: String { date ?? UUID().uuidString }; let date: String?; let estimated_eps: Double?; let actual_eps: Double?; let surprise_pct: Double? }
struct PredictionsPerformance: Codable {
    let total_predictions: Int?
    let by_horizon: [String: HorizonPerf]?
    let confidence_buckets: [BucketPerf]?
    let by_scan_type: [GroupPerf]?
    let by_sector: [GroupPerf]?
    let by_regime: [GroupPerf]?
    let by_ml_engine_mode: [GroupPerf]?
    let by_recommendation: [GroupPerf]?
}
struct HorizonPerf: Codable { let matured_count: Int?; let hit_rate: Double?; let avg_return: Double?; let avg_brier_score: Double? }
struct BucketPerf: Codable { let bucket_label: String?; let count: Int?; let hit_rate_30d: Double?; let avg_return_30d: Double?; let avg_brier_score_30d: Double? }
struct GroupPerf: Codable { let group_key: String?; let count: Int?; let hit_rate_30d: Double?; let avg_return_30d: Double?; let avg_brier_score_30d: Double? }
struct CalibrationHealth: Codable { let status: String?; let brier_score: Double?; let reliability_diagram: [ReliabilityPoint]? }
struct ReliabilityPoint: Codable { let bin: String?; let predicted: Double?; let actual: Double? }
struct FusionWeights: Codable { let recommended_weights: [String: Double]? }
struct HarvesterCard: Codable, Identifiable { var id: String { url ?? UUID().uuidString }; let title: String?; let url: String?; let source: String?; let ticker: String? }
struct ScrapeResult: Codable { let status: String?; let cards_added: Int? }
struct HarvesterStats: Codable { let total_cards: Int?; let by_source: [String: Int]?; let last_run: String? }
struct AIEngineJob: Codable, Identifiable { var id: String { job_id ?? UUID().uuidString }; let job_id: String?; let ticker: String?; let status: String?; let progress_pct: Int?; let stage: String? }
struct StressTestProgress: Codable { let progress_pct: Int?; let stage: String?; let status: String? }
struct StressTestJob: Codable, Identifiable { var id: String { job_id ?? UUID().uuidString }; let job_id: String?; let portfolio_id: String?; let status: String?; let scenarios: [String]? }
struct TokenStats: Codable { let total_tokens: Int?; let today_tokens: Int?; let cost_estimate: Double? }
struct EmptyResponse: Codable {}
