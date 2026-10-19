import Foundation
import os

/// Platform flags from GET /api/v1/flags (backend services/feature_flags.py), plus the per-caller
/// `analytics_consented`. The money-cluster flags live in FeatureFlags (GET /api/v1/features).
/// Unknown or never-fetched keys read off, so new surfaces stay hidden until the server says yes.
/// The last known global flags and `analytics_retention_days` are cached in UserDefaults;
/// `analytics_consented` is user-specific and is never persisted.
@MainActor
final class RemoteFlags: ObservableObject {
    static let shared = RemoteFlags()

    static let cacheKey = "nivesh_remoteFlags_v2"
    static let refreshInterval: TimeInterval = 300
    static let analyticsKey = "analytics"
    static let analyticsConsentedKey = "analytics_consented"

    @Published private(set) var flags: [String: Bool]
    @Published private(set) var analyticsRetentionDays: Int?

    private let defaults: UserDefaults
    private let fetch: () async throws -> ClientFlagsResponse
    private let now: () -> Date
    private var lastSuccess: Date?
    private var inFlight = false
    private var issuedTickets = 0
    private var appliedTicket = 0
    private static let log = Logger(subsystem: Bundle.main.bundleIdentifier ?? "stockme", category: "RemoteFlags")

    nonisolated private struct Cache: Codable {
        var flags: [String: Bool]
        var analyticsRetentionDays: Int?
    }

    init(defaults: UserDefaults = .standard,
         fetch: @escaping () async throws -> ClientFlagsResponse = { try await NetworkManager.shared.fetchClientFlags() },
         now: @escaping () -> Date = Date.init) {
        self.defaults = defaults
        self.fetch = fetch
        self.now = now
        let cached = defaults.data(forKey: Self.cacheKey).flatMap { try? JSONDecoder().decode(Cache.self, from: $0) }
        self.flags = cached?.flags ?? [:]
        self.analyticsRetentionDays = cached?.analyticsRetentionDays
    }

    func isOn(_ key: String) -> Bool { flags[key] ?? false }

    /// Fetches the flags unless the last success is under `refreshInterval` old. A forced refresh
    /// (login change, consent change) always fetches. Failure keeps the current values and the cache.
    func refresh(force: Bool = false) async {
        if inFlight && !force { return }
        if !force, let last = lastSuccess, now().timeIntervalSince(last) < Self.refreshInterval { return }
        inFlight = true
        issuedTickets += 1
        let ticket = issuedTickets
        defer { if ticket == issuedTickets { inFlight = false } }
        do {
            let response = try await fetch()
            guard ticket > appliedTicket else { return }  // a newer request already answered
            appliedTicket = ticket
            flags = response.flags
            if let days = response.analyticsRetentionDays { analyticsRetentionDays = days }
            lastSuccess = now()
            persist()
        } catch {
            Self.log.error("remote flag refresh failed: \(error.localizedDescription, privacy: .public)")
        }
    }

    private func persist() {
        var shared = flags
        shared.removeValue(forKey: Self.analyticsConsentedKey)
        if let data = try? JSONEncoder().encode(Cache(flags: shared, analyticsRetentionDays: analyticsRetentionDays)) {
            defaults.set(data, forKey: Self.cacheKey)
        }
    }
}
