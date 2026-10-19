import Foundation
import Combine
import os

/// Server-side feature flags (backend core/feature_flags.py, spec_money 2.1).
/// Keys mirror the backend registry; unknown or never-fetched keys read `defaultValue`.
nonisolated enum FeatureKey: String, CaseIterable {
    case moneyHoldingDetail = "money_holding_detail"
    case moneyXirrCard = "money_xirr_card"
    case moneyJournalScoring = "money_journal_scoring"
    case moneyCasImport = "money_cas_import"
    case moneyXray = "money_xray"
    case moneyCommissionDrag = "money_commission_drag"
    case moneyTaxReport = "money_tax_report"
    case moneyCrisisReplay = "money_crisis_replay"
    // Habit cluster (spec_habit 0.2).
    case notifPrefsV2 = "notif_prefs_v2"
    case todayBrief = "today_brief"
    case eventRadar = "event_radar"
    case watchlistV2 = "watchlist_v2"
    case widgetSnapshot = "widget_snapshot"

    /// Value before the first successful fetch: off (fail closed), except the
    /// widget_snapshot kill switch, which is on unless the server says off.
    var defaultValue: Bool { self == .widgetSnapshot }
}

/// Flags fetched from GET /api/v1/features and cached in UserDefaults, so a cold
/// launch shows the last known surfaces before the network answers.
/// Views: `@ObservedObject private var flags = FeatureFlags.shared`, then `flags.isOn(.moneyXray)`.
@MainActor
final class FeatureFlags: ObservableObject {
    static let shared = FeatureFlags()

    nonisolated static let cacheKey = "featureFlags.v1"
    static let refreshInterval: TimeInterval = 600

    @Published private(set) var values: [String: Bool]

    private let defaults: UserDefaults
    private let fetch: () async throws -> [String: Bool]
    private let now: () -> Date
    private var lastSuccess: Date?
    private var inFlight = false  // launch .task and the first .active both call refresh()
    private static let log = Logger(subsystem: Bundle.main.bundleIdentifier ?? "stockme", category: "FeatureFlags")

    init(defaults: UserDefaults = .standard,
         fetch: @escaping () async throws -> [String: Bool] = { try await NetworkManager.shared.fetchFeatureFlags().flags },
         now: @escaping () -> Date = Date.init) {
        self.defaults = defaults
        self.fetch = fetch
        self.now = now
        self.values = defaults.data(forKey: Self.cacheKey).flatMap(Self.decode) ?? [:]
    }

    func isOn(_ key: FeatureKey) -> Bool { values[key.rawValue] ?? key.defaultValue }

    /// Last cached value, for callers off the main actor (e.g. WidgetSnapshotStore).
    nonisolated static func cachedIsOn(_ key: FeatureKey, defaults: UserDefaults = .standard) -> Bool {
        defaults.data(forKey: cacheKey).flatMap(decode)?[key.rawValue] ?? key.defaultValue
    }

    /// Fetches the flags unless the last success is under `refreshInterval` old.
    /// Failure keeps the current values (and the cache) and is only logged.
    func refresh(force: Bool = false) async {
        if inFlight { return }
        if !force, let last = lastSuccess, now().timeIntervalSince(last) < Self.refreshInterval { return }
        inFlight = true
        defer { inFlight = false }
        do {
            let fresh = try await fetch()
            values = fresh
            lastSuccess = now()
            if let data = try? JSONEncoder().encode(["flags": fresh]) {
                defaults.set(data, forKey: Self.cacheKey)
            }
        } catch {
            Self.log.error("feature flag refresh failed: \(error.localizedDescription, privacy: .public)")
        }
    }

    /// Decodes a `{"flags": {key: Bool}}` payload (the API body and the cache share it).
    /// Any non-Bool value fails the whole payload -> nil.
    nonisolated static func decode(_ data: Data) -> [String: Bool]? {
        try? JSONDecoder().decode(FeatureFlagsResponse.self, from: data).flags
    }
}
