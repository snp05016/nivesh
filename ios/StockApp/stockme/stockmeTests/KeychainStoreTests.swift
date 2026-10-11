import XCTest
@testable import stockme

/// CMON-23: the session (bearer token included) lives in the Keychain, never
/// in plaintext UserDefaults. Needs the app test host for keychain access.
@MainActor
final class KeychainStoreTests: XCTestCase {

    private var key: String { AuthManager.storageKey }
    private var savedKeychain: Data?
    private var savedDefaults: Data?

    override func setUp() {
        super.setUp()
        savedKeychain = KeychainStore.get(key)
        savedDefaults = UserDefaults.standard.data(forKey: key)
        KeychainStore.delete(key)
        UserDefaults.standard.removeObject(forKey: key)
    }

    override func tearDown() {
        KeychainStore.delete(key)
        UserDefaults.standard.removeObject(forKey: key)
        if let savedKeychain { try? KeychainStore.set(savedKeychain, for: key) }
        if let savedDefaults { UserDefaults.standard.set(savedDefaults, forKey: key) }
        super.tearDown()
    }

    func testRoundTrip() throws {
        let data = Data("secret".utf8)
        try KeychainStore.set(data, for: key)
        XCTAssertEqual(KeychainStore.get(key), data)
        try KeychainStore.set(Data("rotated".utf8), for: key)
        XCTAssertEqual(KeychainStore.get(key), Data("rotated".utf8))
        KeychainStore.delete(key)
        XCTAssertNil(KeychainStore.get(key))
    }

    func testLegacyMigrationMovesTokenOutOfUserDefaults() throws {
        let legacy = Data(#"{"user_id":42,"username":"u","display_name":"U","access_token":"tok"}"#.utf8)
        UserDefaults.standard.set(legacy, forKey: key)

        let user = try XCTUnwrap(AuthManager.loadPersistedUser())

        XCTAssertEqual(user.userId, 42)
        XCTAssertEqual(user.token, "tok")
        XCTAssertNil(UserDefaults.standard.data(forKey: key))
        XCTAssertEqual(KeychainStore.get(key), legacy)
        XCTAssertEqual(AuthManager.loadPersistedUser()?.userId, 42)
    }
}
