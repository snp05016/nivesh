import SwiftUI
import UserNotifications
import Combine
/// Global manager for the v2 analysis engine — polls the backend job API so every
/// screen can show live analysis progress without any connection-tied lifetime.
/// Injected as ``.environmentObject()`` at the app root (stockmeApp.swift).
@MainActor
final class AnalysisEngineManager: ObservableObject {
    static let shared = AnalysisEngineManager()

    @Published var isRunning: Bool = false
    @Published var activeJobId: String? = nil
    @Published var ticker: String? = nil
    @Published var scanType: String? = nil
    @Published var status: String? = nil       // RUNNING / SUCCEEDED / FAILED / etc.
    @Published var stage: String? = nil
    @Published var progressPct: Double = 0
    @Published var checkpoints: [CheckpointEvent] = []
    @Published var error: String? = nil
    @Published var result: StockAnalysis? = nil  // full result when SUCCEEDED

    /// The job AnalysisScreen polls itself. The watcher skips its own polls for it and takes
    /// the screen's updates via screenPolled(_:), so one job has one poll channel (PERF-22).
    var screenOwnedJobId: String? = nil

    private var pollTask: Task<Void, Never>? = nil
    private var lastTerminalNotified: String? = nil

    private var currentUserId: Int? {
        AuthManager.loadPersistedUser()?.userId
    }

    private init() {
        // IOSCORE-14: the next account must not see this one's job, progress or result.
        NotificationCenter.default.addObserver(forName: AuthManager.didLogout, object: nil, queue: .main) { [weak self] _ in
            Task { @MainActor in self?.reset() }
        }
    }

    /// Stops the watcher and clears every published field (logout).
    func reset() {
        stopWatching()
        isRunning = false
        activeJobId = nil; ticker = nil; scanType = nil
        status = nil; stage = nil; error = nil; result = nil
        progressPct = 0
        checkpoints = []
        screenOwnedJobId = nil
        lastTerminalNotified = nil
    }

    static let terminalStatuses: Set<String> = ["SUCCEEDED", "FAILED", "TIMEOUT", "CANCELLED"]

    /// The watcher polls only while the server reports a job in flight; no job means stop.
    static func shouldKeepPolling(_ job: JobStatus?) -> Bool {
        guard let job else { return false }
        return job.status == "RUNNING" || job.status == "QUEUED"
    }

    // MARK: - Start watching

    /// One GET /analyze/active check (on launch / foreground). A running job is then
    /// followed via GET /analyze/job/{id} until it ends; with no job nothing polls.
    /// jobStarted() restarts it when this device starts a job.
    func startWatching() {
        stopWatching()
        guard let uid = currentUserId else { return }
        pollTask = Task {
            var jobId: String? = nil
            var failures = 0
            var screenFollowed = false
            while !Task.isCancelled {
                if let jid = jobId, jid == screenOwnedJobId {
                    screenFollowed = true
                    try? await Task.sleep(nanoseconds: AnalysisViewModel.pollDelay(consecutiveFailures: 0))
                    continue
                }
                // The screen followed this job to its end before handing it back.
                if screenFollowed, let jid = jobId, activeJobId == jid, !isRunning { return }
                do {
                    let job: JobStatus?
                    if let jid = jobId {
                        job = try await NetworkManager.shared.pollJob(jobId: jid, userId: uid)
                    } else {
                        job = try await NetworkManager.shared.getActiveJob(userId: uid)
                    }
                    if Task.isCancelled { return }
                    failures = 0
                    apply(job)
                    guard Self.shouldKeepPolling(job) else { return }
                    jobId = job?.jobId
                } catch {
                    if Task.isCancelled { return }
                    failures += 1
                    // Lost/foreign job, undecodable payload or a dead connection: stop and
                    // re-check on the next foreground instead of polling forever.
                    let lost = AnalysisViewModel.pollOutcome(for: error) != .retry
                    if lost || error is DecodingError || failures >= AnalysisViewModel.maxPollFailures {
                        isRunning = false
                        return
                    }
                }
                try? await Task.sleep(nanoseconds: AnalysisViewModel.pollDelay(consecutiveFailures: failures))
            }
        }
    }

    /// Called when this device starts (or attaches to) a job.
    func jobStarted() {
        startWatching()
    }

    func stopWatching() {
        pollTask?.cancel(); pollTask = nil
    }

    /// A status AnalysisScreen polled for the job it owns.
    func screenPolled(_ job: JobStatus) {
        guard job.jobId == screenOwnedJobId else { return }
        apply(job)
    }

    /// AnalysisScreen stopped polling `jobId`; the watcher follows it again if it still runs.
    func releaseScreenJob(_ jobId: String) {
        if screenOwnedJobId == jobId { screenOwnedJobId = nil }
    }

    private func apply(_ job: JobStatus?) {
        guard let job else {
            isRunning = false; activeJobId = nil; ticker = nil
            return
        }
        activeJobId = job.jobId
        ticker = job.ticker
        scanType = job.scanType
        status = job.status
        stage = job.stage
        progressPct = Double(job.progressPct ?? 0)
        if let cps = job.checkpoints { checkpoints = Array(cps.suffix(8)) }
        error = job.error
        result = job.result  // GET /analyze/job/{id} carries the full result once SUCCEEDED
        isRunning = Self.shouldKeepPolling(job)
        // Fire a local notification once per terminal transition.
        if Self.terminalStatuses.contains(job.status), lastTerminalNotified != job.jobId {
            lastTerminalNotified = job.jobId
            fireLocalNotification(job: job)
        }
    }

    // MARK: - Cancel

    func cancelActiveJob() {
        guard let jid = activeJobId else { return }
        // The watcher sees CANCELLED on its next poll and stops; the next job restarts it.
        Task {
            try? await NetworkManager.shared.cancelJob(jobId: jid, userId: currentUserId)
            await MainActor.run {
                isRunning = false; status = "CANCELLED"
            }
        }
    }

    // MARK: - Notification

    private func fireLocalNotification(job: JobStatus) {
        let title: String
        let body: String
        switch job.status {
        case "SUCCEEDED":
            title = "Analysis Complete"
            body = "\(job.ticker) report is ready — tap to view."
        case "FAILED":
            title = "Analysis Failed"
            body = job.error ?? "\(job.ticker) analysis did not complete."
        case "TIMEOUT":
            title = "Analysis Timed Out"
            body = "\(job.ticker) took too long. Try again."
        default: return
        }
        // Routed through NotificationManager so the master switch, quiet hours and
        // sound apply. NotificationManager.didReceive routes a tap to the stock's hub.
        NotificationManager.shared.scheduleLocal(
            title: title, body: body,
            identifier: "job-\(job.jobId)-\(job.status)",
            userInfo: ["ticker": job.ticker]
        )
    }
}
