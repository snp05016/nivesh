import Foundation
import Combine

@MainActor
class AuthManager: ObservableObject {
    @Published var currentUser: LoggedInUser? = nil
    @Published var isLoggingIn = false
    @Published var loginError: String? = nil

    /// Keychain account (and legacy UserDefaults key) for the persisted session.
    static let storageKey = "nivesh_user_v1"
    private let disclaimerRecordedKey = "nivesh_disclaimerRecordedVersion"

    init() {
        if let user = Self.loadPersistedUser() {
            currentUser = user
            NetworkManager.shared.authToken = user.token
            recordDisclaimerIfNeeded()
        }
    }

    /// The persisted session, read from the Keychain. Installs that stored it
    /// (bearer token included) in plaintext UserDefaults are migrated on first
    /// read; the legacy copy is removed only once the Keychain write succeeds.
    static func loadPersistedUser() -> LoggedInUser? {
        if let data = KeychainStore.get(storageKey) {
            return try? JSONDecoder().decode(LoggedInUser.self, from: data)
        }
        guard let legacy = UserDefaults.standard.data(forKey: storageKey),
              let user = try? JSONDecoder().decode(LoggedInUser.self, from: legacy) else { return nil }
        if (try? KeychainStore.set(legacy, for: storageKey)) != nil {
            UserDefaults.standard.removeObject(forKey: storageKey)
        }
        return user
    }

    private func persist(_ user: LoggedInUser) {
        guard let data = try? JSONEncoder().encode(user) else { return }
        try? KeychainStore.set(data, for: Self.storageKey)
    }

    var isLoggedIn: Bool { currentUser != nil }

    func login(username: String, password: String) async {
        isLoggingIn = true
        loginError = nil
        do {
            let user = try await NetworkManager.shared.login(username: username, password: password)
            currentUser = user
            NetworkManager.shared.authToken = user.token
            persist(user)
            recordDisclaimerIfNeeded()
        } catch {
            loginError = Self.message(for: error, registering: false)
        }
        isLoggingIn = false
    }
    
    func register(username: String, password: String, displayName: String, ageConfirmed: Bool) async {
        isLoggingIn = true
        loginError = nil
        do {
            // The registration form only enables this after the policy and 18+ boxes are ticked.
            let user = try await NetworkManager.shared.register(username: username, password: password, displayName: displayName, acceptedPolicyVersion: PolicyVersion.current, ageConfirmed: ageConfirmed)
            currentUser = user
            NetworkManager.shared.authToken = user.token
            persist(user)
            recordDisclaimerIfNeeded()
        } catch {
            loginError = Self.message(for: error, registering: true)
        }
        isLoggingIn = false
    }

    /// FINSEC-09: the disclaimer is accepted before sign-in (device-local
    /// @AppStorage), so record it server-side once per policy version as soon
    /// as there is an account to bind it to. Retried on the next sign-in or
    /// launch if the request fails.
    private func recordDisclaimerIfNeeded() {
        guard let userId = currentUser?.userId,
              UserDefaults.standard.bool(forKey: "hasAcceptedDisclaimer") else { return }
        let recordedKey = "\(disclaimerRecordedKey)_\(userId)"
        guard UserDefaults.standard.string(forKey: recordedKey) != PolicyVersion.current else { return }
        Task {
            guard (try? await NetworkManager.shared.grantConsent(type: "disclaimer", granted: true)) != nil else { return }
            UserDefaults.standard.set(PolicyVersion.current, forKey: recordedKey)
        }
    }

    /// User-facing copy for a login/register failure. Only a 401 from /login
    /// (`NetworkError.invalidCredentials`) ever blames the credentials; transport
    /// failures (offline, timeout, TLS) get connectivity copy instead.
    static func message(for error: Error, registering: Bool) -> String {
        let generic = "Something went wrong. Please try again."
        if let networkError = error as? NetworkError {
            return networkError.errorDescription ?? generic
        }
        if let urlError = error as? URLError {
            switch urlError.code {
            case .notConnectedToInternet, .networkConnectionLost, .dataNotAllowed:
                return "No internet connection. Check your connection and try again."
            case .timedOut:
                return "The server took too long to respond. Please try again."
            case .cannotFindHost, .cannotConnectToHost, .secureConnectionFailed, .dnsLookupFailed:
                return "Can't reach Nivesh right now. Please try again shortly."
            default:
                return generic
            }
        }
        if error is DecodingError {
            return registering ? "Your account may have been created. Try signing in." : generic
        }
        return generic
    }

    func logout() {
        // Fix 3.30: Destructive cleanup — cancel network session and clear state
        URLSession.shared.invalidateAndCancel()
        // GH-695: NetworkManager's default config caches to URLCache.shared (Cache.db);
        // wipe holdings/watchlist responses so they don't outlive the session.
        URLCache.shared.removeAllCachedResponses()
        currentUser = nil
        NetworkManager.shared.authToken = nil
        KeychainStore.delete(Self.storageKey)
        UserDefaults.standard.removeObject(forKey: Self.storageKey)
        UserDefaults.standard.removeObject(forKey: "nivesh_cached_portfolio_v1")
        UserDefaults.standard.removeObject(forKey: "nivesh_last_refresh_v1")
        WidgetSnapshotStore.clear()
    }
}
