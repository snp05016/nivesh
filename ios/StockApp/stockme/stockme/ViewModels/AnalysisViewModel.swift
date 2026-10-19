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

/// State for an archived report from the previous engine. New reports come from the
/// Research Engine (`ResearchReportView`); this model no longer starts or polls jobs.
/// The static policies below are still used by `AnalysisEngineManager`'s watcher.
@MainActor
class AnalysisViewModel: ObservableObject {
    @Published var analysis: StockAnalysis? = nil
    @Published var quickInfo: QuickInfo? = nil

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

    // MARK: - Job polling policy (AnalysisEngineManager)

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

    /// Price/header data for the archived view only; no analysis job.
    func loadQuickInfo(ticker: String) {
        Task { quickInfo = await NetworkManager.shared.quickInfo(ticker: ticker) }
    }
}
