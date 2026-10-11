import SwiftUI
import Combine

/// One analysis run as the user asked for it, kept so Retry replays the same tier and settings.
struct AnalysisRequest: Equatable {
    let ticker: String
    let deepScan: Bool
    let scanType: String
    let language: String?
    let debateRounds: Int?

    /// Maps the Settings picker values to the request fields: English is the server default (nil).
    static func from(ticker: String, scanType: String, deepScan: Bool, languageSetting: String, roundsSetting: String) -> AnalysisRequest {
        AnalysisRequest(ticker: ticker, deepScan: deepScan, scanType: scanType,
                        language: languageSetting == "English" ? nil : languageSetting,
                        debateRounds: Int(roundsSetting))
    }
}

@MainActor
class AnalysisViewModel: ObservableObject {
    @Published var analysis: StockAnalysis? = nil
    @Published var quickInfo: QuickInfo? = nil
    @Published var isLoading = false
    @Published var errorInfo: AnalysisErrorInfo? = nil
    @Published var quarterlyFinancials: [QuarterlyFinancial] = []
    @Published var promoterHistory: [PromoterHistoryPoint] = []
    @Published var niftyPrices: [NiftyPricePoint] = []
    @Published var macroStrip: MacroStrip? = nil
    @Published var earningsEvents: [EarningsEvent] = []
    @Published var analystRatings: AnalystRatingsResponse? = nil
    @Published var macroImpacts: [MacroImpactItem] = []

    // v2 engine — job polling
    @Published var jobId: String? = nil
    @Published var jobStatus: JobStatus? = nil
    @Published var engineCheckpoints: [CheckpointEvent] = []

    private var analysisTask: Task<Void, Never>?
    private var pollJobTask: Task<Void, Never>?
    /// Set by an explicit Cancel; a superseding fetchAnalysis call resets it.
    private var cancelRequested = false
    /// The most recent run, replayed by retryLast() so a failed Extreme scan is not retried as Standard.
    @Published private(set) var lastRequest: AnalysisRequest?

    /// What AnalysisScreen does on appear when it was NOT launched from the
    /// action hub (holding rows, Home, Search, Earnings push it directly).
    enum AutoStart: Equatable { case idle, showCached, promptCached, fetch }

    /// Never starts a paid job just because the screen appeared: without a
    /// saved report the screen goes idle and waits for an explicit "Run analysis".
    static func autoStart(forceCached: Bool, hasCached: Bool, autoRegenerateStale: Bool, cachedIsStale: Bool) -> AutoStart {
        guard hasCached else { return .idle }
        if forceCached { return .showCached }
        if autoRegenerateStale && cachedIsStale { return .fetch }  // explicit opt-in setting
        return .promptCached
    }

    /// How to treat the POST /analyze response.
    enum StartOutcome: Equatable { case cached, attach(String), conflict(String), unexpected }

    static func classify(_ start: StartJobResponse, ticker: String) -> StartOutcome {
        if start.analysis != nil { return .cached }
        if let jid = start.jobId, start.status == "QUEUED" || start.status == "RUNNING" { return .attach(jid) }
        if start.errorCode == "ALREADY_RUNNING" {
            // The 409 is keyed on user + scan type, not ticker: only attach to a
            // job for this same ticker, never show another stock's result here.
            if let jid = start.jobId, start.ticker?.uppercased() == ticker.uppercased() { return .attach(jid) }
            return .conflict(start.ticker ?? "another stock")
        }
        return .unexpected
    }

    // MARK: - Job polling

    /// Per-run values the poll loop needs to store results and build errors.
    private struct PollContext {
        let jobId: String
        let userId: Int?
        let ticker: String
        let scanType: String
        let quickInfoElapsed: Double
        let useMock: Bool
        let deepScan: Bool
        let reportManager: LocalReportManager
        let started: Date
    }

    private var pollFailures = 0

    /// What a failed job poll means for the loop.
    enum PollOutcome: Equatable { case retry, terminal(String) }

    static let jobLostMessage = "This analysis is no longer available. Start a new one."
    static let maxPollFailures = 8
    static let maxPollDuration: TimeInterval = 30 * 60

    /// 401/403/404/422 mean the job is gone or not this user's: polling again cannot succeed.
    /// Network errors and 5xx are transient and retried with backoff.
    static func pollOutcome(for error: Error) -> PollOutcome {
        switch error as? NetworkError {
        case .serverError(let code, _)? where [401, 403, 404, 422].contains(code):
            return .terminal(jobLostMessage)
        case .unauthorized?:
            return .terminal(jobLostMessage)
        default:
            return .retry
        }
    }

    /// Delay before the next poll: 2 s, doubling per consecutive failure, capped at 15 s.
    static func pollDelay(consecutiveFailures: Int) -> UInt64 {
        let seconds: UInt64 = consecutiveFailures >= 3 ? 15 : 2 << UInt64(max(consecutiveFailures, 0))
        return seconds * 1_000_000_000
    }

    /// One poll of the running job. Returns the delay before the next poll, or nil to stop.
    private func pollOnce(_ ctx: PollContext) async -> UInt64? {
        guard jobId == ctx.jobId else { return nil }
        let raw: [String: Any]
        do {
            raw = try await NetworkManager.shared.pollJobRaw(jobId: ctx.jobId, userId: ctx.userId)
        } catch {
            if Task.isCancelled { return nil }
            pollFailures += 1
            if case .terminal(let message) = Self.pollOutcome(for: error) {
                endPolling(ctx, message: message)
                return nil
            }
            if pollFailures >= Self.maxPollFailures {
                endPolling(ctx, message: "Lost contact with the analysis server. Check your connection and try again.")
                return nil
            }
            return Self.pollDelay(consecutiveFailures: pollFailures)
        }
        if Task.isCancelled { return nil }
        pollFailures = 0

        let polledStatus = raw["status"] as? String ?? ""
        let polledStage  = raw["stage"] as? String
        let polledPct    = raw["progress_pct"] as? Int
        let polledCheckpoints: [CheckpointEvent]? = (raw["checkpoints"] as? [[String: Any]])?.compactMap { cp in
            guard let stage = cp["stage"] as? String,
                  let agent = cp["agent"] as? String,
                  let msg = cp["message"] as? String else { return nil }
            return CheckpointEvent(ts: cp["ts"] as? String ?? "", stage: stage, agent: agent, message: msg, state: cp["state"] as? String ?? "running")
        }
        let polledError  = raw["error"] as? String

        let polled = JobStatus(
            jobId: ctx.jobId, userId: ctx.userId, ticker: ctx.ticker,
            scanType: ctx.scanType, status: polledStatus,
            stage: polledStage, progressPct: polledPct,
            checkpoints: polledCheckpoints, tokensUsed: nil, error: polledError, result: nil
        )
        jobStatus = polled
        // One poll channel per job: the engine watcher takes this status instead of polling (PERF-22).
        AnalysisEngineManager.shared.screenPolled(polled)
        if let cps = polledCheckpoints { engineCheckpoints = cps }
        // A SUCCEEDED result is decoded asynchronously below; isLoading stays true until it is
        // assigned, or the idle state (with a live Run button) flashes in between (PERF-24).
        if !(polledStatus == "SUCCEEDED" && raw["result"] != nil) {
            isLoading = polledStatus != "SUCCEEDED" && polledStatus != "FAILED" && polledStatus != "TIMEOUT" && polledStatus != "CANCELLED"
        }

        if polledStatus == "SUCCEEDED" {
            // Try StockAnalysis decode
            if let resultData = raw["result"] {
                do {
                    let jsonData = try JSONSerialization.data(withJSONObject: resultData)
                    // The full result is 100-300 KB: decode it off the main thread (PERF-24).
                    let decoded = try await NetworkManager.decodeOffMain(StockAnalysis.self, from: jsonData)
                    guard !Task.isCancelled, jobId == ctx.jobId else { return nil }
                    analysis = decoded
                    ctx.reportManager.saveReport(decoded)
                    isLoading = false
                } catch {
                    print("[AnalysisScreen] StockAnalysis decode failed: \(error)")
                    // Show error with raw signal info so user sees something
                    let sigRaw = (resultData as? [String: Any])?["signal"] as? String ?? "?"
                    errorInfo = AnalysisErrorInfo(
                        diagnostic: nil,
                        rawError: "Decode failed but analysis complete. Signal: \(sigRaw)",
                        httpStatusCode: 200, responseBody: "", responseHeaders: "",
                        requestUrl: "/analyze/job/\(ctx.jobId)", elapsedSeconds: 0,
                        quickInfoElapsed: ctx.quickInfoElapsed, isRetryable: false,
                        isMockMode: ctx.useMock, isDeepScan: ctx.deepScan)
                    isLoading = false
                }
            } else {
                isLoading = false
            }
        } else if ["FAILED", "TIMEOUT", "CANCELLED"].contains(polledStatus) {
            errorInfo = AnalysisErrorInfo(
                diagnostic: nil, rawError: polledError ?? "analysis \(polledStatus)",
                httpStatusCode: 0, responseBody: "", responseHeaders: "",
                requestUrl: "/analyze/job/\(ctx.jobId)", elapsedSeconds: 0,
                quickInfoElapsed: ctx.quickInfoElapsed, isRetryable: true,
                isMockMode: ctx.useMock, isDeepScan: ctx.deepScan)
            isLoading = false
        }

        switch polledStatus {
        case "QUEUED", "RUNNING":
            if Date().timeIntervalSince(ctx.started) > Self.maxPollDuration {
                endPolling(ctx, message: "The analysis is taking longer than expected. Check your saved reports later.")
                return nil
            }
            return Self.pollDelay(consecutiveFailures: 0)
        case "SUCCEEDED", "FAILED", "TIMEOUT", "CANCELLED":
            return nil
        default:
            endPolling(ctx, message: "Unexpected response from server")
            return nil
        }
    }

    private func endPolling(_ ctx: PollContext, message: String) {
        errorInfo = AnalysisErrorInfo(
            diagnostic: nil, rawError: message,
            httpStatusCode: 0, responseBody: "", responseHeaders: "",
            requestUrl: "/analyze/job/\(ctx.jobId)", elapsedSeconds: 0,
            quickInfoElapsed: ctx.quickInfoElapsed, isRetryable: true,
            isMockMode: ctx.useMock, isDeepScan: ctx.deepScan)
        isLoading = false
    }

    /// Price/header data for the idle state only; no analysis job.
    func loadQuickInfo(ticker: String) {
        Task { quickInfo = await NetworkManager.shared.quickInfo(ticker: ticker) }
    }

    func fetchAnalysis(ticker: String, userId: Int?, useMock: Bool, reportManager: LocalReportManager, deepScan: Bool = false, scanType: String = "standard", language: String? = nil, debateRounds: Int? = nil) {
        analysisTask?.cancel()
        pollJobTask?.cancel()
        // Set synchronously so the Run button disappears before a second tap can land.
        isLoading = true
        jobId = nil  // a stale id from a previous run would pin isLoading = true below
        cancelRequested = false
        lastRequest = AnalysisRequest(ticker: ticker, deepScan: deepScan, scanType: scanType, language: language, debateRounds: debateRounds)

        analysisTask = Task {
            // A Cancel that lands before this body runs must not turn the spinner back on.
            guard !Task.isCancelled else { return }
            isLoading = true
            errorInfo = nil
            engineCheckpoints = []

            let parallelStart = Date()
            // POST /analyze goes out alongside the supplementary loads, and its response is
            // handled before awaiting them: jobId must be known as soon as the job exists so
            // Cancel can reach the server job instead of leaving it to spend credits.
            async let startResponse = NetworkManager.shared.startAnalysisJob(
                ticker: ticker, exchange: "NSE", userId: userId, deepScan: deepScan, scanType: scanType,
                language: language, debateRounds: debateRounds)
            async let impacts = Self.loadMacroImpacts(userId: userId)
            async let qi = NetworkManager.shared.quickInfo(ticker: ticker)
            async let qfr = NetworkManager.shared.getQuarterlyFinancialsResponse(ticker: ticker)
            async let nifty = NetworkManager.shared.getNiftyHistory(days: 365)
            async let macro = NetworkManager.shared.getMacroStrip()
            async let earnings = NetworkManager.shared.getEarningsCalendar()
            async let ratings = NetworkManager.shared.getAnalystRatings(ticker: ticker)

            // ── v2 engine: start background job, then poll ──
            var cachedResult: StockAnalysis? = nil
            do {
                let start = try await startResponse
                let quickInfoElapsed = Date().timeIntervalSince(parallelStart)
                let outcome = Self.classify(start, ticker: ticker)

                if Task.isCancelled {
                    // Cancel landed after the server answered but before jobId was set, so
                    // cancelAnalysis() could not cancel the job the server just created.
                    if cancelRequested, case .attach(let jid) = outcome {
                        Task { try? await NetworkManager.shared.cancelJob(jobId: jid, userId: nil) }
                    }
                    return
                }

                switch outcome {
                case .cached:
                    cachedResult = start.analysis  // shown once the supplementary data is in
                case .attach(let attachJobId):
                    // This screen polls the job; the engine watcher only learns about it (PERF-22).
                    AnalysisEngineManager.shared.screenOwnedJobId = attachJobId
                    AnalysisEngineManager.shared.jobStarted()
                    jobId = attachJobId
                    pollFailures = 0
                    let ctx = PollContext(jobId: attachJobId, userId: userId, ticker: ticker, scanType: scanType,
                                          quickInfoElapsed: quickInfoElapsed, useMock: useMock, deepScan: deepScan,
                                          reportManager: reportManager, started: Date())
                    pollJobTask = Task { [weak self] in
                        // self is held only for one poll, so leaving the screen releases the
                        // view model and ends the loop (the server job keeps running).
                        while !Task.isCancelled {
                            guard let delay = await self?.pollOnce(ctx) else { break }
                            try? await Task.sleep(nanoseconds: delay)
                        }
                        // Leaving, cancelling or finishing hands the job back to the watcher.
                        AnalysisEngineManager.shared.releaseScreenJob(ctx.jobId)
                    }
                case .conflict(let otherTicker):
                    errorInfo = AnalysisErrorInfo(
                        diagnostic: nil,
                        rawError: "An analysis for \(otherTicker) is already running. Wait for it to finish, then try again.",
                        httpStatusCode: 409, responseBody: start.errorDetail ?? "", responseHeaders: "",
                        requestUrl: NetworkManager.shared.baseURL + "/analyze", elapsedSeconds: 0,
                        quickInfoElapsed: quickInfoElapsed, isRetryable: true,
                        isMockMode: useMock, isDeepScan: deepScan)
                case .unexpected:
                    errorInfo = AnalysisErrorInfo(
                        diagnostic: nil, rawError: "Unexpected response from server",
                        httpStatusCode: 0, responseBody: "", responseHeaders: "",
                        requestUrl: NetworkManager.shared.baseURL + "/analyze", elapsedSeconds: 0,
                        quickInfoElapsed: quickInfoElapsed, isRetryable: true,
                        isMockMode: useMock, isDeepScan: deepScan)
                }
            } catch {
                if Task.isCancelled { return }
                let quickInfoElapsed = Date().timeIntervalSince(parallelStart)
                if let networkError = error as? NetworkError,
                   let info = networkError.diagnosticInfo {
                    self.errorInfo = AnalysisErrorInfo(
                        diagnostic: info.diagnostic, rawError: info.rawError,
                        httpStatusCode: info.httpStatusCode, responseBody: info.responseBody,
                        responseHeaders: info.responseHeaders, requestUrl: info.requestUrl,
                        elapsedSeconds: info.elapsedSeconds, quickInfoElapsed: quickInfoElapsed,
                        isRetryable: info.isRetryable, isMockMode: info.isMockMode, isDeepScan: info.isDeepScan)
                } else {
                    self.errorInfo = AnalysisErrorInfo(
                        diagnostic: nil, rawError: error.localizedDescription,
                        httpStatusCode: 0, responseBody: "", responseHeaders: "",
                        requestUrl: NetworkManager.shared.baseURL + "/analyze",
                        elapsedSeconds: 0, quickInfoElapsed: quickInfoElapsed,
                        isRetryable: true, isMockMode: useMock, isDeepScan: deepScan)
                }
            }

            quickInfo = await qi
            let qfResult = await qfr
            quarterlyFinancials = qfResult?.quarters ?? []
            promoterHistory = qfResult?.promoterHistory ?? []
            niftyPrices = await nifty
            macroStrip = await macro
            earningsEvents = await earnings
            self.analystRatings = await ratings
            self.macroImpacts = await impacts

            if Task.isCancelled { return }
            if let cached = cachedResult {
                analysis = cached
                reportManager.saveReport(cached)
            }

            // v2 engine: isLoading stays true until the poll loop sets analysis/errorInfo
            if jobId == nil, !Task.isCancelled { isLoading = false }
        }
    }

    private static func loadMacroImpacts(userId: Int?) async -> [MacroImpactItem] {
        guard let uid = userId else { return [] }
        return (try? await NetworkManager.shared.fetchMacroImpact(userId: uid))?.impacts ?? []
    }

    /// Re-runs the last request with the same tier, language and debate rounds.
    func retryLast(userId: Int?, useMock: Bool, reportManager: LocalReportManager) {
        guard let r = lastRequest else { return }
        fetchAnalysis(ticker: r.ticker, userId: userId, useMock: useMock, reportManager: reportManager,
                      deepScan: r.deepScan, scanType: r.scanType, language: r.language, debateRounds: r.debateRounds)
    }

    /// Returns the screen to idle at once (no error), whether or not the job had started.
    func cancelAnalysis() {
        cancelRequested = true
        let jid = jobId
        analysisTask?.cancel()
        pollJobTask?.cancel()
        isLoading = false
        jobId = nil
        jobStatus = nil
        // v2 engine: the job runs server-side, so cancel it there too (fire-and-forget).
        if let jid {
            Task { try? await NetworkManager.shared.cancelJob(jobId: jid, userId: nil) }
        }
    }
}

struct AnalysisScreen: View {
    let ticker: String
    var forceCached: Bool = false
    /// When set (from StockActionHubView), bypasses the legacy "Cached Report
    /// Found" alert and launches the report directly in the chosen mode.
    var launchMode: AnalysisLaunchMode? = nil
    var userNote: String? = nil
    var purchaseDateStr: String? = nil
    var portfolioHolding: PortfolioHolding? = nil

    @Environment(\.dismiss) var dismiss
    @EnvironmentObject var authManager: AuthManager
    @EnvironmentObject var reportManager: LocalReportManager
    @StateObject private var viewModel = AnalysisViewModel()
    @State private var showingRegenerateAlert = false
    @State private var showSetAlertSheet = false
    @State private var activeTab = 0
    @AppStorage("useMockAI") private var useMockAI = false
    @AppStorage("defaultDeepScan") private var defaultDeepScan: Bool = false
    @AppStorage("analysisLastTab") private var savedLastTab: Int = 0
    @AppStorage("nivesh_defaultChartRange") private var defaultChartRange: String = "1M"
    @AppStorage("nivesh_showGovernanceFirst") private var showGovernanceFirst: Bool = false
    @AppStorage("nivesh_analysisLanguage") private var analysisLanguage: String = "English"
    @AppStorage("nivesh_debateRounds") private var debateRoundsStr: String = "1"
    @AppStorage("nivesh_autoRegenerateStale") private var autoRegenerateStale: Bool = false
    @State private var deepScanEnabled: Bool = false
    @State private var isAnalyzing = false
    // Extreme result: 0 = AI report, 1 = full stock profile (embedded verbatim).
    @State private var extremeViewMode = 0

    @Environment(\.scenePhase) private var scenePhase
    @State private var livePrice: Double? = nil
    @State private var pricePollingTask: Task<Void, Never>? = nil
    @State private var pricePollPausedInBackground = false
    @State private var previousAnalysis: StockAnalysis? = nil

    // Immersive hero chart (1y price history, fetched once on appear)
    @State private var heroPrices: [Double] = []
    @State private var heroDates: [Date] = []
    @State private var heroLoading = false
    @State private var heroPeriod = ""
    
    // Retained copy of analysis to prevent EXC_BAD_ACCESS from view model dealloc
    @State private var retainedAnalysis: StockAnalysis? = nil

    private static var todayString: String { WireDate.dayKey(Date()) }

    private static let deepScanDisabledTickers: Set<String> = [
        "NIFTY", "SENSEX", "BANKNIFTY", "NIFTYBANK", "INDIAVIX",
    ]

    private let tabs = ["OVERVIEW", "ANALYSIS", "CHARTS", "FUNDAMENTS", "NEWS"]

    private var parsedPurchaseDate: Date? {
        guard let s = purchaseDateStr else { return nil }
        // New rows are "yyyy-MM-dd"; older rows were stored as "dd-MMM-yyyy".
        return WireDate.day(s) ?? WireDate.ddMMMyyyy.date(from: s)
    }

    var body: some View {
            ZStack {
                Theme.canvas.ignoresSafeArea()
                
                if let analysis = retainedAnalysis {
                    renderFullAnalysis(analysis)
                } else if viewModel.isLoading {
                    renderLoadingState()
                } else if let errorInfo = viewModel.errorInfo {
                    renderErrorState(errorInfo)
                } else {
                    AnalysisIdleStateView(
                        ticker: ticker,
                        exchange: portfolioHolding?.stock.exchange ?? "NSE",
                        quickInfo: viewModel.quickInfo,
                        isRunning: viewModel.isLoading,
                        onRun: {
                            HapticManager.impact(.medium)
                            runDefaultAnalysis()
                        },
                        onViewSaved: previousAnalysis.map { saved -> () -> Void in { viewModel.analysis = saved } }
                    )
                }
            }
            // App-owned back button that also restores the edge-swipe pop gesture.
            .banknoteBackButton { dismiss() }
            .toolbar {
            ToolbarItem(placement: .principal) {
                // Screen C — inline ticker title
                Text(ticker)
                    .font(.headline.weight(.bold))
                    .foregroundStyle(Theme.inkPrimary)
            }
            ToolbarItem(placement: .navigationBarTrailing) {
                HStack(spacing: Theme.Spacing.medium) {
                    // Stock profile quick-access while analysis is running
                    NavigationLink(value: StockProfileDest(ticker: ticker, exchange: portfolioHolding?.stock.exchange ?? "NSE")) {
                        Image(systemName: "doc.text.magnifyingglass")
                            .foregroundStyle(Theme.securityGold)
                    }
                    .buttonStyle(EKPressStyle())
                    // Screen C — price + ChangeBadge inline on the right
                    if let info = viewModel.quickInfo {
                        Text(IndianFormatter.price(livePrice ?? info.price))
                        .lineLimit(1)
                        .minimumScaleFactor(0.6)
                            .font(Theme.serialNumberFont(size: 13, relativeTo: .footnote))
                            .foregroundStyle(Theme.inkPrimary)
                        if let pct = info.changePercent {
                            ChangeBadge(value: pct)
                        }
                    }
                    Button {
                        HapticManager.selection()
                        shareAsImage()
                    } label: {
                        Image(systemName: "square.and.arrow.up")
                            .foregroundStyle(viewModel.analysis != nil ? Theme.inkPrimary : Theme.inkSecondary.opacity(0.3))
                    }
                    .disabled(viewModel.analysis == nil)
                    .accessibilityLabel("Share as Image")
                }
            }
        }
        .navigationBarTitleDisplayMode(.inline)
        .toolbarBackground(Theme.canvas, for: .navigationBar)
        .toolbarBackground(.visible, for: .navigationBar)
        .onAppear {
            activeTab = showGovernanceFirst ? 3 : savedLastTab
            deepScanEnabled = defaultDeepScan
            if heroPeriod.isEmpty {
                heroPeriod = ["1M": "1mo", "3M": "3mo", "6M": "6mo", "1Y": "1y"][defaultChartRange] ?? "1y"
            }
            if viewModel.analysis == nil && !viewModel.isLoading {
                if let cached = reportManager.getReport(for: ticker) {
                    previousAnalysis = cached
                }

                if let mode = launchMode {
                    // Hub-driven launch: act directly, no alert.
                    switch mode {
                    case .cached:
                        // Show highest-priority cache (extreme > deep > standard)
                        if let cached = previousAnalysis { viewModel.analysis = cached }
                        else { startRun(scanType: "standard", deepScan: false) }
                    case .standard:
                        startRun(scanType: "standard", deepScan: false)
                    case .regenerate:
                        regenerateAtCachedTier(previousAnalysis)
                    case .deepScan:
                        startRun(scanType: "deep", deepScan: !deepScanForbidden)
                    case .extremeScan:
                        startRun(scanType: "extreme", deepScan: !deepScanForbidden)
                    }
                } else {
                    switch AnalysisViewModel.autoStart(
                        forceCached: forceCached,
                        hasCached: previousAnalysis != nil,
                        autoRegenerateStale: autoRegenerateStale,
                        cachedIsStale: previousAnalysis?.analysisDate != Self.todayString
                    ) {
                    case .showCached:
                        viewModel.analysis = previousAnalysis
                    case .fetch:
                        runDefaultAnalysis()
                    case .promptCached:
                        showingRegenerateAlert = true
                        // Dismissing the dialog leaves the idle view, which shows the price.
                        viewModel.loadQuickInfo(ticker: ticker)
                    case .idle:
                        // No saved report: show the idle state and wait for "Run analysis".
                        viewModel.loadQuickInfo(ticker: ticker)
                    }
                }
            }
            startPricePolling()
            fetchHeroHistory(period: heroPeriod)
        }
        .onChange(of: activeTab) { _, val in savedLastTab = val }
        // No price polling while the app is in the background (PERF-22).
        .onChange(of: scenePhase) { _, phase in
            if phase == .background, pricePollingTask != nil {
                pricePollingTask?.cancel(); pricePollingTask = nil
                pricePollPausedInBackground = true
            } else if phase == .active, pricePollPausedInBackground {
                pricePollPausedInBackground = false
                startPricePolling()
            }
        }
        .onReceive(viewModel.$analysis) { newValue in
            retainedAnalysis = newValue
        }
        .onDisappear {
            // v2 engine: analysis runs server-side — do NOT cancel the job poll here. Pushing the
            // stock profile also fires onDisappear and nothing would restart it; the poll holds
            // the view model weakly and ends by itself once the screen is popped.
            pricePollingTask?.cancel()
            pricePollingTask = nil
        }
        .banknoteDialog(
            "Cached Report Found",
            isPresented: $showingRegenerateAlert,
            message: "A report for \(ticker) was recently generated. Generating a new one takes time and credits. Do you want to view the existing report or generate a new one?",
            buttons: [
                .init("View Cached") {
                    if let cached = reportManager.getReport(for: ticker) {
                        viewModel.analysis = cached
                    }
                },
                .init("Regenerate") {
                    regenerateAtCachedTier(reportManager.getReport(for: ticker))
                },
                .cancel()
            ]
        ) {
            // Fix 3.16: Disable Deep Scan for indices and newly listed tickers
            Toggle("Deep Scan (PKScreener + FinBERT)", isOn: $deepScanEnabled)
                .font(Theme.engravedSerif(size: 13, weight: .regular))
                .tint(Theme.securityGold)
                .foregroundStyle(Theme.inkSecondary)
                .disabled(Self.deepScanDisabledTickers.contains(ticker.uppercased()))
                .opacity(Self.deepScanDisabledTickers.contains(ticker.uppercased()) ? 0.4 : 1.0)
        }
    }

    /// Default (non-hub) analysis run: user's deep-scan, language and debate settings.
    private func runDefaultAnalysis() {
        guard !viewModel.isLoading else { return }
        startRun(scanType: "standard", deepScan: deepScanEnabled)
    }

    private var deepScanForbidden: Bool { Self.deepScanDisabledTickers.contains(ticker.uppercased()) }

    /// Every run goes through here so the language and debate-round settings always reach the request.
    private func startRun(scanType: String, deepScan: Bool) {
        let r = AnalysisRequest.from(ticker: ticker, scanType: scanType, deepScan: deepScan,
                                     languageSetting: analysisLanguage, roundsSetting: debateRoundsStr)
        viewModel.fetchAnalysis(ticker: r.ticker, userId: authManager.currentUser?.userId, useMock: useMockAI,
                                reportManager: reportManager, deepScan: r.deepScan, scanType: r.scanType,
                                language: r.language, debateRounds: r.debateRounds)
    }

    /// Regenerate keeps the cached report's tier instead of silently downgrading it to Standard.
    private func regenerateAtCachedTier(_ cached: StockAnalysis?) {
        switch cached?.cachedScanType ?? cached?.analysisTier ?? "standard" {
        case "extreme": startRun(scanType: "extreme", deepScan: !deepScanForbidden)
        case "deep": startRun(scanType: "deep", deepScan: !deepScanForbidden)
        default: startRun(scanType: "standard", deepScan: deepScanEnabled && !deepScanForbidden)
        }
    }

    // MARK: - Immersive hero chart

    private func fetchHeroHistory(period: String = "1y") {
        heroLoading = true
        Task {
            let hist = await NetworkManager.shared.fetchStockHistory(ticker: ticker, exchange: "NSE", period: period)
            await MainActor.run {
                if let hist = hist, !hist.prices.isEmpty {
                    heroPrices = hist.prices.map(\.close)
                    heroDates = hist.prices.map(\.parsedDate)
                }
                heroLoading = false
            }
        }
    }

    // MARK: - Live price polling

    private func startPricePolling() {
        pricePollingTask?.cancel()
        let exchange = "NSE"
        pricePollingTask = Task {
            while !Task.isCancelled {
                // The server caches quick-info for 15 min, so a 30 s poll mostly re-downloaded
                // identical data (PERF-22).
                try? await Task.sleep(nanoseconds: 300_000_000_000) // 5 min
                guard !Task.isCancelled else { return }
                if let info = await NetworkManager.shared.quickInfo(ticker: ticker, exchange: exchange) {
                    livePrice = info.price
                }
            }
        }
    }

    // MARK: - Share as Image

    private func shareAsImage() {
        guard let analysis = viewModel.analysis else { return }
        
        let viewToRender = ZStack {
            Theme.canvas.ignoresSafeArea()
            DenominationBackground(denomination: .hundred)
            BanknoteWatermark(text: "CONFIDENTIAL", size: 100, opacity: 0.018, alignment: .center)
            
            VStack(spacing: Theme.Spacing.sectionGap) {
                AnalysisCoreSections(analysis: analysis, previousAnalysis: previousAnalysis, ticker: ticker, livePrice: livePrice, viewModel: viewModel)
                if analysis.analysisTier == "extreme" {
                    AnalysisExtremeSections(analysis: analysis, previousAnalysis: previousAnalysis, viewModel: viewModel)
                }
            }
            .padding(.horizontal, Theme.screenPadding)
            .padding(.top, Theme.Spacing.standard)
            .padding(.bottom, Theme.Spacing.large)
        }
        .frame(width: UIScreen.main.bounds.width)
        
        let renderer = ImageRenderer(content: viewToRender)
        renderer.scale = UIScreen.main.scale
        
        if let uiImage = renderer.uiImage {
            let avc = UIActivityViewController(activityItems: [uiImage], applicationActivities: nil)
            if let windowScene = UIApplication.shared.connectedScenes.first as? UIWindowScene,
               let rootVC = windowScene.windows.first(where: { $0.isKeyWindow })?.rootViewController {
                avc.popoverPresentationController?.sourceView = rootVC.view
                avc.popoverPresentationController?.sourceRect = CGRect(x: UIScreen.main.bounds.midX, y: UIScreen.main.bounds.midY, width: 0, height: 0)
                rootVC.present(avc, animated: true)
            }
        }
    }

    // MARK: - Loading State

    private func renderLoadingState() -> some View {
        AnalysisLoadingStateView(
            viewModel: viewModel,
            ticker: ticker,
            userId: authManager.currentUser?.userId,
            onCancel: {
                HapticManager.impact(.rigid)
                viewModel.cancelAnalysis()
            }
        )
    }

    // MARK: - Full Analysis

    private func renderFullAnalysis(_ analysis: StockAnalysis) -> some View {
        AnalysisFullView(
            analysis: analysis,
            previousAnalysis: previousAnalysis,
            ticker: ticker,
            livePrice: livePrice,
            viewModel: viewModel,
            extremeViewMode: $extremeViewMode,
            heroPrices: heroPrices,
            heroDates: heroDates,
            heroLoading: heroLoading,
            heroPeriod: $heroPeriod,
            onPeriodChange: { period in fetchHeroHistory(period: period) }
        )
    }

    // MARK: - Error State

    private func renderErrorState(_ info: AnalysisErrorInfo) -> some View {
        AnalysisErrorStateView(
            info: info,
            quickInfo: viewModel.quickInfo,
            onRetry: {
                HapticManager.impact(.medium)
                // Replays the failed request (same tier, language, rounds); falls back to a default run.
                if viewModel.lastRequest != nil {
                    viewModel.retryLast(userId: authManager.currentUser?.userId, useMock: useMockAI, reportManager: reportManager)
                } else {
                    runDefaultAnalysis()
                }
            }
        )
    }
}

// MARK: - Macro Impact Banner

private struct MacroImpactBanner: View {
    let impacts: [MacroImpactItem]

    var body: some View {
        ScrollView(.horizontal) {
            HStack(spacing: Theme.Spacing.medium) {
                ForEach(impacts) { item in
                    MacroImpactChip(item: item)
                }
            }
            .padding(.horizontal, Theme.screenPadding)
        }
        .scrollIndicators(.hidden)
    }
}

private struct MacroImpactChip: View {
    let item: MacroImpactItem

    var chipColor: Color {
        switch item.direction ?? "neutral" {
        case "positive": return Theme.signalEmerald
        case "negative": return Theme.signalRuby
        default: return Theme.canvasDeep
        }
    }

    var directionArrow: String {
        switch item.direction ?? "neutral" {
        case "positive": return "↑"
        case "negative": return "↓"
        default: return "→"
        }
    }

    var shortImpact: String {
        let words = (item.impactStatement ?? "").split(separator: " ")
        return words.prefix(6).joined(separator: " ")
    }

    var textColor: Color {
        switch item.direction ?? "neutral" {
        case "positive", "negative": return .white
        default: return .primary
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
            HStack(spacing: Theme.Spacing.xSmall) {
                Text(item.ticker)
                    .font(Theme.monoTabular(size: 11, relativeTo: .caption2).weight(.bold))
                Text(directionArrow)
                    .font(.caption2)
            }
            .foregroundStyle(textColor)
            Text(shortImpact)
                .font(Theme.engravedSerif(size: 11, relativeTo: .caption2))
                .foregroundStyle(textColor.opacity(0.85))
                .lineLimit(1)
        }
        .padding(.horizontal, Theme.Spacing.medium)
        .padding(.vertical, Theme.Spacing.tight)
        .background(chipColor.opacity(0.8))
        .cornerRadius(Theme.CornerRadius.tight)
    }
}

// MARK: - Macro Chip

private struct MacroChip: View {
    let label: String
    let value: String
    let color: Color
    var body: some View {
        VStack(spacing: Theme.Spacing.xSmall) {
            Text(label)
                .font(Theme.officialStampFont(size: 7))
                .foregroundStyle(Theme.inkTertiary)
            Text(value)
                .font(Theme.serialNumberFont(size: 11))
                .foregroundStyle(color)
                .lineLimit(1)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, Theme.Spacing.medium)
    }
}

// MARK: - Analysis Metric Cell (Screen C 3-col grid)

struct AnalysisMetricCell: View {
    let label: String
    let term: String
    let value: String

    var body: some View {
        VStack(spacing: Theme.Spacing.xSmall) {
            Text(label)
                .font(Theme.officialStampFont(size: 8)).tracking(1.2)
                .foregroundStyle(Theme.inkTertiary)
                .explainableTerm(term)
            Text(value)
                .font(Theme.serialNumberFont(size: 14, relativeTo: .footnote).weight(.bold))
                .foregroundStyle(Theme.inkPrimary)
                .lineLimit(1).minimumScaleFactor(0.7)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, Theme.Spacing.standard)
        .padding(.horizontal, Theme.Spacing.small)
        .banknoteCard()
    }
}

// MARK: - Key Factor Card

private struct KeyFactorCard: View {
    let icon: String
    let title: String
    let hindiTitle: String
    let text: String
    let color: Color
    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            HStack(spacing: Theme.Spacing.medium) {
                Image(systemName: icon)
                    .font(.subheadline)
                    .foregroundStyle(color)
                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text(hindiTitle)
                        .font(Theme.hindiFont(size: 9))
                        .foregroundStyle(Theme.inkTertiary)
                    Text(title)
                        .font(Theme.officialStampFont(size: 9))
                        .foregroundStyle(Theme.inkPrimary)
                }
            }
            GuillocheDivider()
            Text(text)
                .font(.subheadline.weight(.medium))
                .foregroundStyle(Theme.inkSecondary)
                .lineSpacing(4)
        }
        .padding(Theme.Spacing.card)
        .background(color.opacity(0.04))
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
        .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium).stroke(color.opacity(0.2), lineWidth: 0.8))
    }
}

// MARK: - Perforation Bar (dotted confidence indicator)

private struct PerforationBar: View {
    let percent: Int

    var body: some View {
        HStack(spacing: Theme.Spacing.xSmall) {
            ForEach(0..<20, id: \.self) { i in
                let threshold = Double(i + 1) / 20.0 * 100.0
                Circle()
                    .fill(Double(percent) >= threshold ? Theme.securityGold : Theme.inkSecondary.opacity(0.15))
                    .frame(width: 6, height: 6)
            }
        }
    }
}

// MARK: - News Item Card

struct NewsItemCard: View {
    let item: NewsItem
    let onTap: () -> Void

    var body: some View {
        Button {
            HapticManager.impact(.light)
            onTap()
        } label: {
            HStack(spacing: Theme.Spacing.card) {
                if let urlStr = item.imageUrl, let url = URL(string: urlStr) {
                    AsyncImage(url: url) { image in
                        image.resizable().aspectRatio(contentMode: .fill)
                    } placeholder: {
                        Rectangle().fill(Theme.inkSecondary.opacity(0.1))
                    }
                    .frame(width: UIScreen.main.bounds.width * 0.20, height: UIScreen.main.bounds.width * 0.20)
                    .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
                }

                VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                    Text(item.title)
                        .font(Theme.engravedSerif(size: 15, weight: .bold))
                        .foregroundStyle(Theme.inkPrimary)
                        .lineLimit(3)
                        .multilineTextAlignment(.leading)

                    HStack {
                        Text(item.publisher.uppercased())
                            .font(Theme.officialStampFont(size: 8))
                        Spacer()
                        Image(systemName: "chevron.right")
                            .font(.caption2)
                    }
                    .foregroundStyle(Theme.inkSecondary)
                }
            }
            .padding(Theme.Spacing.standard)
            .banknoteCard()
        }
        .buttonStyle(.plain)
    }
}

// MARK: - News Section (extracted per AGENTS.md §6.6 — owns single hoisted cover)

struct NewsSectionView: View {
    let news: [NewsItem]
    @State private var selectedNews: NewsItem?

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            GuillocheDivider()
            HStack {
                Text("RECENT NEWS")
                    .font(Theme.officialStampFont(size: 9))
                    .tracking(1.5)
                    .foregroundStyle(Theme.inkSecondary)
                Spacer()
                Text("\(news.count) articles")
                    .font(Theme.microLabel(size: 9))
                    .foregroundStyle(Theme.inkTertiary)
            }
            ForEach(news.prefix(5)) { item in
                NewsItemCard(item: item) { selectedNews = item }
            }
        }
        .fullScreenCover(item: $selectedNews) { item in
            NewsReaderView(item: item)
        }
    }
}

// MARK: - Horizon Note Card

private struct HorizonNoteCard: View {
    let label: String
    let target: Double
    let upside: Double
    var isFeatured: Bool = false

    var body: some View {
        GeometryReader { geo in
            VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                Text(label.uppercased())
                    .font(Theme.officialStampFont(size: 8))
                    .foregroundStyle(Theme.inkSecondary)

                Text(target.inrFormatted)
                    .font(Theme.serialNumberFont(size: 18))
                    .foregroundStyle(Theme.inkPrimary)

                HStack(spacing: Theme.Spacing.small) {
                    Image(systemName: upside >= 0 ? "arrow.up.right" : "arrow.down.right")
                    Text("\(upside.percentFormatted)")
                }
                .font(Theme.serialNumberFont(size: 11))
                .foregroundStyle(upside >= 0 ? Theme.bullGreen : Theme.bearRed)
            }
            .padding(Theme.Spacing.card)
            .frame(width: geo.size.width * 0.33)
            .banknoteCard()
        }
        .overlay(
            VStack {
                if isFeatured {
                    Rectangle().fill(Theme.securityGold).frame(height: 2)
                    Spacer()
                }
            }
        )
    }
}

// MARK: - Analysis Note Section (bull/bear/risk)

private struct AnalysisNoteSection: View {
    let title: String
    let items: [String]
    let color: Color

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            Text(title.uppercased())
                .font(Theme.officialStampFont(size: 9))
                .foregroundStyle(Theme.inkPrimary)

            VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                ForEach(items, id: \.self) { item in
                    HStack(alignment: .top, spacing: Theme.Spacing.standard) {
                        Rectangle()
                            .fill(color.opacity(0.5))
                            .frame(width: 2, height: 14)
                            .padding(.top, Theme.Spacing.small)
                        Text(item)
                            .font(.subheadline.weight(.medium))
                            .foregroundStyle(Theme.inkSecondary)
                            .lineSpacing(4)
                    }
                }
            }
        }
        .padding(Theme.Spacing.large)
        .banknoteCard()
        .overlay(
            HStack(spacing: Theme.Spacing.none) {
                Rectangle()
                    .fill(color.opacity(0.25))
                    .frame(width: 2)
                Spacer()
            }
            .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
        )
    }
}

// MARK: - Stat Note Cell

private struct StatNoteCell: View {
    let label: String
    let value: String
    @State private var showGlossary = false

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
            HStack(spacing: Theme.Spacing.small) {
                Text(label)
                    .font(Theme.officialStampFont(size: 8))
                    .foregroundStyle(Theme.inkSecondary)
                Image(systemName: "questionmark.circle")
                    .font(.caption2)
                    .foregroundStyle(Theme.inkTertiary.opacity(0.6))
            }
            Text(value)
                .font(Theme.serialNumberFont(size: 16))
                .foregroundStyle(Theme.inkPrimary)
        }
        .padding(Theme.Spacing.card)
        .frame(maxWidth: .infinity, alignment: .leading)
        .banknoteCard()
        .onLongPressGesture(minimumDuration: 0.4) {
            HapticManager.impact(.medium)
            showGlossary = true
        }
        .sheet(isPresented: $showGlossary) {
            GlossarySheet(term: label)
        }
    }
}

// MARK: - Confidence Card

private struct ConfidenceCard: View {
    let percent: Int

    private var label: String {
        switch percent {
        case 80...100: return "High Confidence"
        case 60..<80:  return "Moderate Confidence"
        case 40..<60:  return "Uncertain"
        default:       return "Low Confidence"
        }
    }
    private var color: Color {
        switch percent {
        case 70...100: return Theme.bullGreen
        case 50..<70:  return Theme.holdAmber
        default:       return Theme.bearRed
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            HStack {
                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text("CONFIDENCE SCORE")
                        .font(Theme.officialStampFont(size: 8)).foregroundStyle(Theme.inkSecondary)
                        .explainableTerm("Confidence Score")
                    Text(label)
                        .font(Theme.engravedSerif(size: 15, weight: .bold)).foregroundStyle(color)
                }
                Spacer()
                Text("\(percent)%")
                    .font(Theme.serialNumberFont(size: 22)).foregroundStyle(color)
            }
            PerforationBar(percent: percent)
            if percent < 50 {
                HStack(spacing: Theme.Spacing.tight) {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .font(.caption2).foregroundStyle(Theme.holdAmber)
                    Text("Uncertainty is high. Cross-check before acting.")
                        .font(.caption.weight(.medium)).foregroundStyle(Theme.holdAmber)
                }
            }
        }
        .padding(Theme.Spacing.screen).banknoteCard()
    }
}

// MARK: - Trend Bar (for promoter history)

private struct TrendBar: View {
    let label: String
    let value: Double
    let color: Color
    var body: some View {
        VStack(spacing: Theme.Spacing.xSmall) {
            Text(String(format: "%.1f%%", value))
                .font(.caption2.weight(.medium)).foregroundStyle(color)
            GeometryReader { geo in
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                    .fill(color.opacity(0.25))
                    .frame(width: geo.size.width)
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                    .fill(color)
                    .frame(width: geo.size.width * min(value / 80.0, 1.0))
            }
            .frame(height: 6)
            Text(label).font(.caption2).foregroundStyle(Theme.inkTertiary)
        }
        .frame(maxWidth: .infinity)
    }
}

// MARK: - Valuation Badge

private struct ValuationBadge: View {
    let peVsAvg: PeVsAvg

    private var isAbove: Bool { peVsAvg.pctVsAvg > 0 }
    private var absPct: Double { abs(peVsAvg.pctVsAvg) }
    private var badgeColor: Color { isAbove ? Theme.bearRed : Theme.bullGreen }

    var body: some View {
        HStack(spacing: Theme.Spacing.standard) {
            Image(systemName: isAbove ? "arrow.up.circle.fill" : "arrow.down.circle.fill")
                .foregroundStyle(badgeColor)
                .font(.body)
            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text("VALUATION VS HISTORY")
                    .font(Theme.officialStampFont(size: 8))
                    .foregroundStyle(Theme.inkSecondary)
                Text("Trading \(String(format: "%.0f", absPct))% \(isAbove ? "above" : "below") 3Y avg valuation")
                    .font(Theme.serialNumberFont(size: 12))
                    .foregroundStyle(badgeColor)
            }
            Spacer()
            VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
                Text("NOW").font(Theme.officialStampFont(size: 7)).foregroundStyle(Theme.inkTertiary)
                Text(String(format: "%.1f", peVsAvg.currentPe)).font(Theme.serialNumberFont(size: 13)).foregroundStyle(Theme.inkPrimary)
                Text("AVG").font(Theme.officialStampFont(size: 7)).foregroundStyle(Theme.inkTertiary)
                Text(String(format: "%.1f", peVsAvg.avgPe3y)).font(Theme.serialNumberFont(size: 11)).foregroundStyle(Theme.inkSecondary)
            }
        }
        .padding(Theme.Spacing.standard)
        .background(badgeColor.opacity(0.07))
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
        .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium).stroke(badgeColor.opacity(0.35), lineWidth: 1))
    }
}

// MARK: - Glossary Sheet

private let glossaryDefinitions: [String: String] = [
    "P/E RATIO": "Price-to-Earnings. How much you pay for ₹1 of company profit. P/E of 20 means you pay ₹20 for every ₹1 earned. Lower can mean cheaper; very high can mean overpriced.",
    "D/E RATIO": "Debt-to-Equity. How much the company borrowed vs what it owns. A D/E of 1 means equal debt and equity. High D/E (above 2) means heavy borrowing — risky if profits fall.",
    "PROMOTER": "The founders or controlling family who own a stake in the company. High promoter holding (above 50%) means they believe in the business. Falling promoter holding is a warning sign.",
    "INSTITUTION": "Foreign Institutional Investors (FIIs) — large global funds. When FIIs increase holding, they're betting the company will grow. Their exits can cause short-term price drops.",
    "DII": "Domestic Institutional Investors — Indian mutual funds and insurance companies. DII buying usually means Indian experts see long-term value.",
    "RSI": "Relative Strength Index (0–100). Above 70: stock is overbought (may pull back). Below 30: oversold (may bounce). Between 30–70: normal range.",
    "CONFIDENCE SCORE": "How certain the AI analysis system is about its signal. Above 70 is reliable. Below 50 means the data is mixed and you should be more cautious.",
    "52W HIGH": "The highest price this stock traded at in the last 52 weeks. Being near the 52W high means the stock is doing well, but there is less room to run before it becomes expensive.",
    "52W LOW": "The lowest price in the last 52 weeks. Being near the 52W low can be a buying opportunity if the business is still strong — but also a sign of trouble if fundamentals weakened.",
    "UPSIDE": "How much the price could go up to reach the target. 30% upside means the AI expects the stock to rise 30% from today's price over the stated time period.",
]

private struct GlossarySheet: View {
    let term: String
    @Environment(\.dismiss) var dismiss

    var body: some View {
        NavigationStack {
            ZStack {
                Theme.canvasDeep.ignoresSafeArea()
                VStack(alignment: .leading, spacing: Theme.Spacing.screen) {
                    Text(term)
                        .font(Theme.engravedSerif(size: 22, weight: .bold))
                        .foregroundStyle(Theme.inkPrimary)
                    GuillocheDivider()
                    Text(glossaryDefinitions[term] ?? "No definition available for this term.")
                        .font(.body.weight(.medium))
                        .foregroundStyle(Theme.inkSecondary)
                        .lineSpacing(6)
                    Spacer()
                }
                .padding(Theme.Spacing.sectionGap)
            }
            .navigationTitle("शब्दावली / Glossary")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }.foregroundStyle(Theme.securityGold).buttonStyle(EKPressStyle())
                }
            }
        }
    }
}

struct AnalysisLimitationsCard: View {
    let disclaimer: String
    @State private var expanded = false
    @AppStorage("analysisLimitationsShownBefore") private var shownBefore = false

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Button(action: {
                HapticManager.selection()
                withAnimation(.easeInOut(duration: 0.25)) { expanded.toggle() }
            }) {
                HStack {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundStyle(Theme.securityGold)
                    Text("HOW TO READ THIS ANALYSIS")
                        .font(Theme.officialStampFont(size: 9)).foregroundStyle(Theme.inkPrimary)
                    Spacer()
                    Image(systemName: expanded ? "chevron.up" : "chevron.down")
                        .font(.caption2).foregroundStyle(Theme.inkTertiary)
                }
            }
            .buttonStyle(.plain)

            if expanded || !shownBefore {
                VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
                    Text("⚠️ AI cannot predict black swan events. Geopolitical shocks — wars, sanctions, pandemics — are outside this model's scope. These have caused real losses for investors in the past.")
                        .font(Theme.serialNumberFont(size: 10)).foregroundStyle(Theme.bearRed.opacity(0.9))

                    Text("This analysis weights Indian market factors: promoter behaviour, FII/DII flows, retail sentiment, and news momentum. It is not a substitute for your own judgment.")
                        .font(Theme.serialNumberFont(size: 10)).foregroundStyle(Theme.inkSecondary)

                    Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)

                    Text(disclaimer)
                        .font(Theme.serialNumberFont(size: 9)).foregroundStyle(Theme.inkTertiary)
                }
                .onAppear { shownBefore = true }
            }
        }
        .padding(Theme.Spacing.card).banknoteCard()
    }
}

// MARK: - News Reader View

struct NewsReaderView: View {
    let item: NewsItem
    @Environment(\.dismiss) var dismiss

    var body: some View {
            NavigationStack {
                ScrollView {
                    VStack(alignment: .leading, spacing: Theme.Spacing.screen) {
                        // Hero Image (proportional height — no GeometryReader per AGENTS.md §2.5/§6.6)
                        if let urlStr = item.imageUrl, let url = URL(string: urlStr) {
                            AsyncImage(url: url) { image in
                                image.resizable().aspectRatio(contentMode: .fill)
                            } placeholder: {
                                Rectangle().fill(Theme.inkSecondary.opacity(0.1))
                            }
                            .frame(height: UIScreen.main.bounds.height * 0.28)
                            .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.card))
                            .padding(.horizontal, Theme.screenPadding)
                        }

                    VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                        Text(item.title)
                            .font(Theme.engravedSerif(size: 24, weight: .bold))
                            .foregroundStyle(Theme.inkPrimary)
                            .lineSpacing(4)

                        HStack {
                            Text(item.publisher.uppercased())
                                .font(Theme.officialStampFont(size: 10))
                                .foregroundStyle(Theme.securityGold)
                            
                            if let time = item.publishTime {
                                Text("•")
                                Text(Date(timeIntervalSince1970: TimeInterval(time)), style: .date)
                            }
                        }
                        .font(Theme.serialNumberFont(size: 11))
                        .foregroundStyle(Theme.inkTertiary)

                        GuillocheDivider()

                        if let summary = item.summary, !summary.isEmpty {
                            Text(summary)
                                .font(Theme.engravedSerif(size: 17, weight: .medium, relativeTo: .headline))
                                .foregroundStyle(Theme.inkSecondary)
                                .lineSpacing(8)
                        } else {
                            Text("Summary not available. Please read the full story for more details.")
                                .italic()
                                .font(Theme.serialNumberFont(size: 14))
                                .foregroundStyle(Theme.inkTertiary)
                        }

                        Group {
                            if let url = URL(string: item.link) {
                                Link(destination: url) {
                                    HStack {
                                        Text("READ FULL STORY ON \(item.publisher.uppercased())")
                                        Image(systemName: "arrow.up.right")
                                    }
                                    .font(Theme.officialStampFont(size: 11))
                                    .foregroundStyle(Theme.canvas)
                                    .padding(.vertical, Theme.Spacing.standard)
                                    .frame(maxWidth: .infinity)
                                    .background(Theme.inkPrimary)
                                    .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
                                }
                            } else {
                                HStack {
                                    Text("READ FULL STORY ON \(item.publisher.uppercased())")
                                    Image(systemName: "link.badge.plus")
                                }
                                .font(Theme.officialStampFont(size: 11))
                                .foregroundStyle(Theme.canvas.opacity(0.5))
                                .padding(.vertical, Theme.Spacing.standard)
                                .frame(maxWidth: .infinity)
                                .background(Theme.inkPrimary.opacity(0.5))
                                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
                            }
                        }
                        .padding(.top, Theme.Spacing.screen)
                    }
                    .padding(.horizontal, Theme.screenPadding)

                    Spacer(minLength: 40)
                }
            }
            .background(Theme.canvasDeep)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button { HapticManager.selection();  dismiss() } label: {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundStyle(Theme.inkTertiary)
                            .font(Theme.engravedSerif(size: 24))
                    }
                    .accessibilityLabel("Close")
                }
            }
        }
    }
}

// MARK: - Diagnostic Error Helpers

struct TraceRow: View {
    let label: String
    let value: String

    var body: some View {
        let colW = UIScreen.main.bounds.width - 2 * Theme.screenPadding
        return HStack(alignment: .top, spacing: Theme.Spacing.medium) {
            Text(label)
                .font(Theme.serialNumberFont(size: 10))
                .foregroundStyle(Theme.inkTertiary)
                .frame(width: colW * 0.25, alignment: .leading)
            Text(value)
                .font(Theme.serialNumberFont(size: 10))
                .foregroundStyle(Theme.inkSecondary)
                .lineSpacing(3)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

struct CollapsibleSection<Content: View>: View {
    let header: String
    @ViewBuilder let content: () -> Content
    @State private var expanded = false

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            Button(action: {
                HapticManager.selection()
                withAnimation(.easeInOut(duration: 0.2)) { expanded.toggle() }
            }) {
                HStack(spacing: Theme.Spacing.tight) {
                    Image(systemName: expanded ? "chevron.down" : "chevron.right")
                        .font(.caption2.weight(.bold))
                        .foregroundStyle(Theme.securityGold)
                    Text(header)
                        .font(Theme.serialNumberFont(size: 10))
                        .foregroundStyle(Theme.inkSecondary)
                    Spacer()
                }
            }
            .buttonStyle(.plain)

            if expanded {
                VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                    content()
                }
                .padding(.leading, Theme.Spacing.card)
                .padding(.vertical, Theme.Spacing.medium)
                .background(Theme.canvasDeep.opacity(0.5))
                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.tight))
            }
        }
    }
}
// Item 14: MagnificationGesture added in StockCharts.swift
