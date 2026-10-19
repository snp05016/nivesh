import XCTest
@testable import stockme

/// IOSCORE-14: logout leaves no per-account preferences or analysis-engine state
/// for the next user on the same phone. Needs the app test host (Keychain).
@MainActor
final class LogoutCleanupTests: XCTestCase {

    private let apnsKey = "apns_device_token"
    private var savedKeychain: Data?
    private var savedToken: String?
    private var savedAPNs: String?
    private var savedReports: Data?

    override func setUp() {
        super.setUp()
        savedKeychain = KeychainStore.get(AuthManager.storageKey)
        savedToken = NetworkManager.shared.authToken
        savedAPNs = UserDefaults.standard.string(forKey: apnsKey)
        // logout() also makes the host app's LocalReportManager wipe the real file.
        savedReports = try? Data(contentsOf: LocalReportManager.defaultFileURL)
        KeychainStore.delete(AuthManager.storageKey)
        // No bearer, so logout() never sends a real device-unregister request.
        NetworkManager.shared.authToken = nil
    }

    override func tearDown() {
        KeychainStore.delete(AuthManager.storageKey)
        if let savedKeychain { try? KeychainStore.set(savedKeychain, for: AuthManager.storageKey) }
        NetworkManager.shared.authToken = savedToken
        UserDefaults.standard.set(savedAPNs, forKey: apnsKey)
        if let savedReports { try? savedReports.write(to: LocalReportManager.defaultFileURL) }
        super.tearDown()
    }

    func testLogoutClearsUserScopedDefaults() {
        for key in AuthManager.userScopedKeys { UserDefaults.standard.set("previous user", forKey: key) }
        UserDefaults.standard.set("device-token", forKey: apnsKey)

        AuthManager().logout()

        for key in AuthManager.userScopedKeys {
            XCTAssertNil(UserDefaults.standard.object(forKey: key), key)
        }
        // Device-scoped: kept so the next account can bind it without a relaunch.
        XCTAssertEqual(UserDefaults.standard.string(forKey: apnsKey), "device-token")
    }

    func testLogoutResetsAnalysisEngine() async throws {
        let engine = AnalysisEngineManager.shared
        engine.isRunning = true
        engine.activeJobId = "job-1"
        engine.ticker = "TCS"
        engine.status = "RUNNING"
        engine.progressPct = 40

        AuthManager().logout()
        for _ in 0..<50 where engine.activeJobId != nil {
            try await Task.sleep(nanoseconds: 20_000_000)
        }

        XCTAssertFalse(engine.isRunning)
        XCTAssertNil(engine.activeJobId)
        XCTAssertNil(engine.ticker)
        XCTAssertNil(engine.status)
        XCTAssertNil(engine.result)
        XCTAssertEqual(engine.progressPct, 0)
    }
}
