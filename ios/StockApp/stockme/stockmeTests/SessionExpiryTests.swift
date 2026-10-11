import XCTest
@testable import stockme

/// IOSCORE-05: a 401 on any authenticated request signs the user out once, with
/// session-expired copy, instead of leaving Home/Portfolio/Alerts silently empty.
@MainActor
final class SessionExpiryTests: XCTestCase {

    private var savedKeychain: Data?
    private var savedToken: String?

    override func setUp() {
        super.setUp()
        StubURLProtocol.reset()
        savedKeychain = KeychainStore.get(AuthManager.storageKey)
        savedToken = NetworkManager.shared.authToken
        KeychainStore.delete(AuthManager.storageKey)
        // No bearer, so logout() never sends a real device-unregister request.
        NetworkManager.shared.authToken = nil
    }

    override func tearDown() {
        StubURLProtocol.reset()
        KeychainStore.delete(AuthManager.storageKey)
        if let savedKeychain { try? KeychainStore.set(savedKeychain, for: AuthManager.storageKey) }
        NetworkManager.shared.authToken = savedToken
        super.tearDown()
    }

    private func stubbedSession(status: Int) -> AuthAwareSession {
        StubURLProtocol.handler = { req in
            (HTTPURLResponse(url: req.url!, statusCode: status, httpVersion: nil, headerFields: nil)!, Data("{}".utf8))
        }
        return AuthAwareSession(base: URLSession(configuration: StubURLProtocol.configuration()))
    }

    private func request(bearer: String?) -> URLRequest {
        var req = URLRequest(url: URL(string: "https://example.test/portfolio/1")!)
        if let bearer { req.setValue(bearer, forHTTPHeaderField: "Authorization") }
        return req
    }

    func testAuthorized401PostsSessionExpired() async throws {
        let session = stubbedSession(status: 401)
        let posted = expectation(forNotification: .niveshSessionExpired, object: nil) { note in
            note.object as? String == "Bearer expired.tok"
        }

        _ = try await session.data(for: request(bearer: "Bearer expired.tok"))

        await fulfillment(of: [posted], timeout: 1)
    }

    func testUnauthenticated401DoesNotPost() async throws {
        // Login has no Authorization header: its 401 means wrong credentials.
        let session = stubbedSession(status: 401)
        let posted = expectation(forNotification: .niveshSessionExpired, object: nil)
        posted.isInverted = true

        _ = try await session.data(for: request(bearer: nil))

        await fulfillment(of: [posted], timeout: 0.3)
    }

    func testSuccessDoesNotPost() async throws {
        let session = stubbedSession(status: 200)
        let posted = expectation(forNotification: .niveshSessionExpired, object: nil)
        posted.isInverted = true

        _ = try await session.data(for: request(bearer: "Bearer good.tok"))

        await fulfillment(of: [posted], timeout: 0.3)
    }

    func testPortfolio401ThrowsUnauthorized() async {
        let nm = NetworkManager.shared
        let savedSession = nm.session
        defer { nm.session = savedSession }
        nm.session = stubbedSession(status: 401)

        do {
            _ = try await nm.getPortfolio(userId: 1)
            XCTFail("expected unauthorized")
        } catch NetworkError.unauthorized {
        } catch {
            XCTFail("expected unauthorized, got \(error)")
        }
    }

    func testSessionExpiredLogsOutOnceForCurrentTokenOnly() async throws {
        let auth = AuthManager()
        auth.currentUser = LoggedInUser(userId: 7, username: "u", displayName: "U", token: "tok")

        // A 401 for a token that is no longer current is ignored.
        auth.handleSessionExpired(bearer: "Bearer old.tok")
        XCTAssertNotNil(auth.currentUser)

        NotificationCenter.default.post(name: .niveshSessionExpired, object: "Bearer tok")
        for _ in 0..<50 where auth.currentUser != nil {
            try await Task.sleep(nanoseconds: 20_000_000)
        }
        XCTAssertNil(auth.currentUser)
        XCTAssertEqual(auth.loginError, NetworkError.unauthorized.errorDescription)
        XCTAssertNotEqual(auth.loginError, NetworkError.invalidCredentials.errorDescription)

        // A second 401 after sign-out does nothing.
        auth.loginError = nil
        auth.handleSessionExpired(bearer: "Bearer tok")
        XCTAssertNil(auth.loginError)
    }
}
