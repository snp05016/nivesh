import XCTest
@testable import stockme

/// UX-14: transport failures must never be reported as wrong credentials.
@MainActor
final class AuthErrorMessageTests: XCTestCase {

    func testOfflineIsNotBlamedOnPassword() {
        let msg = AuthManager.message(for: URLError(.notConnectedToInternet), registering: false)
        XCTAssertTrue(msg.lowercased().contains("internet"))
        XCTAssertFalse(msg.lowercased().contains("password"))
    }

    func testTimeoutIsNotBlamedOnPassword() {
        let msg = AuthManager.message(for: URLError(.timedOut), registering: false)
        XCTAssertFalse(msg.lowercased().contains("password"))
    }

    func testRateLimitHasNoRawJSON() {
        let msg = AuthManager.message(for: NetworkError.serverError(429, nil), registering: false)
        XCTAssertTrue(msg.contains("Too many"))
        XCTAssertFalse(msg.contains("{"))
    }

    func testInvalidCredentialsCopy() {
        XCTAssertEqual(NetworkError.invalidCredentials.errorDescription, "Incorrect username or password.")
        XCTAssertEqual(AuthManager.message(for: NetworkError.invalidCredentials, registering: false),
                       "Incorrect username or password.")
    }

    func testRegisterPasswordPolicyDetailPassesThrough() {
        let detail = NetworkError.serverDetail(from: Data(#"{"detail":"Password must be at least 8 characters."}"#.utf8))
        let msg = AuthManager.message(for: NetworkError.serverError(400, detail), registering: true)
        XCTAssertEqual(msg, "Password must be at least 8 characters.")
    }

    func testUnknownErrorIsGeneric() {
        struct Boom: Error {}
        let msg = AuthManager.message(for: Boom(), registering: false)
        XCTAssertFalse(msg.lowercased().contains("password"))
    }
}
