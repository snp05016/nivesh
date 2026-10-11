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

    private var pollTask: Task<Void, Never>? = nil

    private var currentUserId: Int? {
        guard let data = UserDefaults.standard.data(forKey: "nivesh_user_v1"),
              let user = try? JSONDecoder().decode(LoggedInUser.self, from: data) else { return nil }
        return user.userId
    }

    private init() {}

    // MARK: - Start watching

    func startWatching() {
        stopWatching()
        pollTask = Task {
            var lastTerminalNotified: String? = nil
            while !Task.isCancelled {
                guard let uid = currentUserId else {
                    try? await Task.sleep(nanoseconds: 3_000_000_000); continue
                }
                do {
                    if let job = try await NetworkManager.shared.getActiveJob(userId: uid) {
                        activeJobId = job.jobId
                        ticker = job.ticker
                        scanType = job.scanType
                        status = job.status
                        stage = job.stage
                        progressPct = Double(job.progressPct ?? 0)
                        if let cps = job.checkpoints { checkpoints = Array(cps.suffix(8)) }
                        error = job.error
                        isRunning = job.status == "RUNNING" || job.status == "QUEUED"

                        // Fetch full result on terminal states
                        if (job.status == "SUCCEEDED" || job.status == "FAILED" || job.status == "TIMEOUT")
                            && job.result == nil, let jid = activeJobId {
                            let full = try? await NetworkManager.shared.pollJob(jobId: jid, userId: uid)
                            self.result = full?.result
                        } else {
                            self.result = job.result
                        }

                        // Fire local notification once per terminal transition
                        let terminal = ["SUCCEEDED", "FAILED", "TIMEOUT", "CANCELLED"]
                        if terminal.contains(job.status), lastTerminalNotified != job.jobId {
                            lastTerminalNotified = job.jobId
                            fireLocalNotification(job: job)
                            if job.status != "RUNNING" { isRunning = false }
                        }
                    } else {
                        isRunning = false; activeJobId = nil; ticker = nil
                    }

                    if isRunning { try? await Task.sleep(nanoseconds: 2_000_000_000) }
                    else { try? await Task.sleep(nanoseconds: 3_000_000_000) }
                } catch {
                    try? await Task.sleep(nanoseconds: 5_000_000_000)
                }
            }
        }
    }

    func stopWatching() {
        pollTask?.cancel(); pollTask = nil
    }

    // MARK: - Cancel

    func cancelActiveJob() {
        guard let jid = activeJobId else { return }
        // The watcher keeps running: it must pick up the next job after this one.
        Task {
            try? await NetworkManager.shared.cancelJob(jobId: jid, userId: currentUserId)
            await MainActor.run {
                isRunning = false; status = "CANCELLED"
            }
        }
    }

    // MARK: - Notification

    private func fireLocalNotification(job: JobStatus) {
        let content = UNMutableNotificationContent()
        switch job.status {
        case "SUCCEEDED":
            content.title = "Analysis Complete"
            content.body = "\(job.ticker) report is ready — tap to view."
        case "FAILED":
            content.title = "Analysis Failed"
            content.body = job.error ?? "\(job.ticker) analysis did not complete."
        case "TIMEOUT":
            content.title = "Analysis Timed Out"
            content.body = "\(job.ticker) took too long. Try again."
        default: return
        }
        content.sound = .default
        // NotificationManager.didReceive routes a tap on this to the stock's hub.
        content.userInfo = ["ticker": job.ticker]
        let trigger = UNTimeIntervalNotificationTrigger(timeInterval: 1, repeats: false)
        let request = UNNotificationRequest(identifier: "job-\(job.jobId)-\(job.status)",
                                            content: content, trigger: trigger)
        UNUserNotificationCenter.current().add(request)
    }
}
