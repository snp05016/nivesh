import Foundation

/// What the Your Data screen and the Home analytics ask need from the network layer.
protocol PrivacyAPI {
    func downloadMyData() async throws -> URL
    func setConsent(type: String, granted: Bool) async throws
    func refreshFlags() async
}

extension NetworkManager: PrivacyAPI {
    func setConsent(type: String, granted: Bool) async throws {
        _ = try await grantConsent(type: type, granted: granted)
    }

    func refreshFlags() async {
        await RemoteFlags.shared.refresh(force: true)
    }
}

/// State of the Your Data screen (I06) and the usage-analytics consent (I47).
@MainActor
final class PrivacyCenterViewModel: ObservableObject {
    enum ExportState: Equatable {
        case idle
        case preparing
        case ready(URL)
        case failed(String)
    }

    static let analyticsConsentType = "product_analytics"

    @Published private(set) var exportState: ExportState = .idle
    @Published private(set) var analyticsOn: Bool
    @Published private(set) var analyticsBusy = false
    @Published private(set) var analyticsError: String?

    private let api: PrivacyAPI

    init(api: PrivacyAPI = NetworkManager.shared,
         analyticsConsented: Bool = RemoteFlags.shared.isOn(RemoteFlags.analyticsConsentedKey)) {
        self.api = api
        self.analyticsOn = analyticsConsented
    }

    func exportData() async {
        exportState = .preparing
        do {
            exportState = .ready(try await api.downloadMyData())
        } catch {
            exportState = .failed(Self.exportMessage(for: error))
        }
    }

    static func exportMessage(for error: Error) -> String {
        if let urlError = error as? URLError,
           urlError.code == .notConnectedToInternet || urlError.code == .networkConnectionLost {
            return "You're offline. Connect and try again."
        }
        if let network = error as? NetworkError, case .serverError(let status, _) = network {
            if status == 429 { return "You've downloaded your data several times today. Try again tomorrow." }
            if status == 404 { return "Data download isn't available right now." }
        }
        return "Couldn't prepare your file. Try again."
    }

    /// Turns usage analytics on or off. Turning it off makes the server erase the recorded events.
    /// The switch moves at once and reverts, with an error, when the server call fails.
    func setAnalytics(_ on: Bool) async -> Bool {
        guard !analyticsBusy else { return false }
        let previous = analyticsOn
        analyticsOn = on
        analyticsBusy = true
        analyticsError = nil
        defer { analyticsBusy = false }
        do {
            try await api.setConsent(type: Self.analyticsConsentType, granted: on)
            await api.refreshFlags()
            return true
        } catch {
            analyticsOn = previous
            analyticsError = "Couldn't update this setting. Try again."
            return false
        }
    }

    /// Follows the server's `analytics_consented` after a flag refresh, unless a toggle is in flight.
    func syncAnalytics(consented: Bool) {
        if !analyticsBusy { analyticsOn = consented }
    }

    static func analyticsCaption(retentionDays: Int?) -> String {
        let kept = retentionDays.map { "Kept for \($0) days." } ?? "Kept for the period set out in our Privacy Policy."
        return "Tells us which screens and features are used. We never record your holdings, stock names or amounts. "
            + kept
            + " You can turn this off at any time; turning it off deletes what was recorded."
    }
}

/// Remembers, per user and device, that the Home analytics ask was answered ("Allow" or "Not now").
enum AnalyticsAskStore {
    private static let keyPrefix = "nivesh_analyticsAsk_v1_"

    static func shouldAsk(userKey: String, defaults: UserDefaults = .standard) -> Bool {
        !defaults.bool(forKey: keyPrefix + userKey)
    }

    static func markAnswered(userKey: String, defaults: UserDefaults = .standard) {
        defaults.set(true, forKey: keyPrefix + userKey)
    }
}
