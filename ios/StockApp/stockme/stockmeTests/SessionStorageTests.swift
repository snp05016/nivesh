import XCTest
@testable import stockme

/// FINSEC-06: logout leaves no session, profile PII or saved reports behind for
/// the next account on the same phone. Needs the app test host (Keychain, Documents).
@MainActor
final class SessionStorageTests: XCTestCase {

    private let reportsURL = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        .appendingPathComponent("saved_reports.json")
    private var savedKeychain: Data?
    private var savedToken: String?
    private var savedReports: Data?

    override func setUp() {
        super.setUp()
        savedKeychain = KeychainStore.get(AuthManager.storageKey)
        savedToken = NetworkManager.shared.authToken
        savedReports = try? Data(contentsOf: reportsURL)
        KeychainStore.delete(AuthManager.storageKey)
        // No bearer, so logout() never sends a real device-unregister request.
        NetworkManager.shared.authToken = nil
    }

    override func tearDown() {
        KeychainStore.delete(AuthManager.storageKey)
        if let savedKeychain { try? KeychainStore.set(savedKeychain, for: AuthManager.storageKey) }
        NetworkManager.shared.authToken = savedToken
        if let savedReports { try? savedReports.write(to: reportsURL) }
        super.tearDown()
    }

    func testLogoutLeavesNoTokenOrProfileBehind() throws {
        let legacy = Data(#"{"user_id":42,"username":"u","display_name":"U","access_token":"tok.secret"}"#.utf8)
        UserDefaults.standard.set(legacy, forKey: AuthManager.storageKey)
        UserDefaults.standard.set("a@example.com", forKey: "nivesh_profileEmail")
        UserDefaults.standard.set("9999999999", forKey: "nivesh_profilePhone")
        // Mark the disclaimer as recorded so init sends no consent request.
        let disclaimerKey = "nivesh_disclaimerRecordedVersion_42"
        UserDefaults.standard.set(PolicyVersion.current, forKey: disclaimerKey)
        defer { UserDefaults.standard.removeObject(forKey: disclaimerKey) }

        let auth = AuthManager()   // migrates the plaintext session into the Keychain
        XCTAssertEqual(auth.currentUser?.token, "tok.secret")
        XCTAssertNil(UserDefaults.standard.data(forKey: AuthManager.storageKey))

        NetworkManager.shared.authToken = nil   // no device-unregister request with the fake token
        auth.logout()

        XCTAssertNil(auth.currentUser)
        XCTAssertNil(KeychainStore.get(AuthManager.storageKey))
        let defaults = UserDefaults.standard.dictionaryRepresentation()
        XCTAssertFalse(defaults.keys.contains { $0.hasPrefix("nivesh_user") })
        XCTAssertNil(defaults["nivesh_profileEmail"])
        XCTAssertNil(defaults["nivesh_profilePhone"])
        XCTAssertFalse(defaults.values.contains { ($0 as? String)?.contains("tok.secret") == true })
    }

    func testLogoutWipesSavedReportsOnDisk() async throws {
        try Data("stale".utf8).write(to: reportsURL)   // undecodable: the manager loads nothing
        let reports = LocalReportManager()

        NotificationCenter.default.post(name: AuthManager.didLogout, object: nil)
        for _ in 0..<50 where (try? String(contentsOf: reportsURL, encoding: .utf8)) != "[]" {
            try await Task.sleep(nanoseconds: 20_000_000)
        }

        XCTAssertTrue(reports.savedReports.isEmpty)
        XCTAssertEqual(try String(contentsOf: reportsURL, encoding: .utf8), "[]")
        XCTAssertTrue(LocalReportManager().savedReports.isEmpty)
    }
}
