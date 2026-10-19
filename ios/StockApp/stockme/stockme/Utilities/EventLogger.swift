import Foundation

/// The analytics events the server accepts (backend services/events_service.py EVENT_SCHEMA).
/// Props are enumerated values only: never put tickers, holdings, amounts or free text in props.
enum AppEvent: String {
    case appOpen = "app_open"
    case search = "search"
    case stockView = "stock_view"
    case reportView = "report_view"
    case reportCompute = "report_compute"
    case alertCreate = "alert_create"
    case importStart = "import_start"
    case importDone = "import_done"
    case paywallView = "paywall_view"
    case purchase = "purchase"
}

/// One buffered event; `ts` is ISO-8601 UTC.
nonisolated struct QueuedEvent: Codable, Equatable {
    let name: String
    let props: [String: String]
    let ts: String
}

/// POST /api/v1/events reply. `reason` is nil, "disabled" or "no_consent".
nonisolated struct EventsAck: Decodable, Equatable {
    let accepted: Int
    let rejected: Int
    let reason: String?
}

/// In-memory buffer for first-party usage events (I47). Runs only while the server flag
/// `analytics` and the caller's `analytics_consented` are on and a session token exists;
/// otherwise nothing is recorded. Flushes at 20 events, on background, in batches of at most 50.
@MainActor
final class EventLogger {
    static let shared = EventLogger()

    static let maxBuffer = 200
    static let flushThreshold = 20
    static let maxBatch = 50

    private(set) var buffer: [QueuedEvent] = []
    /// The flush scheduled by `log`, so tests can await it.
    private(set) var pendingFlush: Task<Void, Never>?

    private let isEnabled: @MainActor () -> Bool
    private let send: ([QueuedEvent]) async throws -> EventsAck
    private let refreshFlags: () async -> Void
    private let now: () -> Date
    private var flushing = false
    private var droppedWhileFlushing = 0

    init(isEnabled: @escaping @MainActor () -> Bool = {
            RemoteFlags.shared.isOn(RemoteFlags.analyticsKey)
                && RemoteFlags.shared.isOn(RemoteFlags.analyticsConsentedKey)
                && NetworkManager.shared.authToken != nil
         },
         send: @escaping ([QueuedEvent]) async throws -> EventsAck = { try await NetworkManager.shared.postEvents($0) },
         refreshFlags: @escaping () async -> Void = { await RemoteFlags.shared.refresh(force: true) },
         now: @escaping () -> Date = Date.init) {
        self.isEnabled = isEnabled
        self.send = send
        self.refreshFlags = refreshFlags
        self.now = now
    }

    func log(_ event: AppEvent, _ props: [String: String] = [:]) {
        guard isEnabled() else { return }
        buffer.append(QueuedEvent(name: event.rawValue, props: props, ts: Self.isoString(now())))
        if buffer.count > Self.maxBuffer {
            let extra = buffer.count - Self.maxBuffer
            buffer.removeFirst(extra)
            if flushing { droppedWhileFlushing += extra }
        }
        if buffer.count >= Self.flushThreshold && !flushing {
            pendingFlush = Task { await flush() }
        }
    }

    /// Sends the first batch. No-op while a flush runs or when the buffer is empty. Disabled
    /// (consent withdrawn, logged out) clears the buffer without sending; an error keeps the events.
    func flush() async {
        guard !flushing, !buffer.isEmpty else { return }
        guard isEnabled() else {
            buffer.removeAll()
            return
        }
        flushing = true
        droppedWhileFlushing = 0
        let batch = Array(buffer.prefix(Self.maxBatch))
        var cleared = false
        do {
            let ack = try await send(batch)
            if ack.reason == "no_consent" || ack.reason == "disabled" {
                buffer.removeAll()
                cleared = true
            } else {
                buffer.removeFirst(min(max(batch.count - droppedWhileFlushing, 0), buffer.count))
            }
        } catch {
            // Keep the events for the next flush.
        }
        flushing = false
        if cleared {
            await refreshFlags()
        } else if buffer.count >= Self.flushThreshold, isEnabled() {
            pendingFlush = Task { await flush() }
        }
    }

    /// Bucket for `search` results: "0", "1-5" or "6+".
    static func searchBucket(_ count: Int) -> String {
        if count <= 0 { return "0" }
        return count <= 5 ? "1-5" : "6+"
    }

    private static func isoString(_ date: Date) -> String {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime]
        return formatter.string(from: date)
    }
}
