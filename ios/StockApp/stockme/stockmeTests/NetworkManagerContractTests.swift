import XCTest
@testable import stockme

/// IOSCORE-27: endpoints that used to hand-roll their requests now go through the
/// shared pipeline: Bearer + correlation id attached, non-2xx surfaced as typed
/// errors, and a paid fallback only on a genuine cache miss.
@MainActor
final class NetworkManagerContractTests: XCTestCase {

    private var savedToken: String?
    private var savedSession: AuthAwareSession?

    override func setUp() {
        super.setUp()
        StubURLProtocol.reset()
        let nm = NetworkManager.shared
        savedToken = nm.authToken
        savedSession = nm.session
        nm.session = AuthAwareSession(base: URLSession(configuration: StubURLProtocol.configuration()))
    }

    override func tearDown() {
        let nm = NetworkManager.shared
        nm.authToken = savedToken
        if let savedSession { nm.session = savedSession }
        StubURLProtocol.reset()
        super.tearDown()
    }

    private func stub(_ status: Int, _ body: String = "{}", contentType: String = "application/json") {
        StubURLProtocol.handler = { req in
            (HTTPURLResponse(url: req.url!, statusCode: status, httpVersion: nil,
                             headerFields: ["Content-Type": contentType])!, Data(body.utf8))
        }
    }

    /// Requests to `path`; the host app may use the same session meanwhile.
    private func requests(to path: String) -> [URLRequest] {
        StubURLProtocol.requests.filter { ($0.url?.path ?? "").contains(path) }
    }

    private func assertFetchFailed(_ error: Error, status: Int, file: StaticString = #filePath, line: UInt = #line) {
        guard case NetworkError.fetchFailed(_, let got, _) = error else {
            return XCTFail("expected fetchFailed(\(status)), got \(error)", file: file, line: line)
        }
        XCTAssertEqual(got, status, file: file, line: line)
    }

    func testFetchDecodeAttachesBearerAndCorrelationId() async throws {
        NetworkManager.shared.authToken = "a.b.c"
        stub(200, "[]")

        _ = try await NetworkManager.shared.fetchHarvesterSources()

        let req = try XCTUnwrap(requests(to: "/harvester/sources").first)
        XCTAssertEqual(req.value(forHTTPHeaderField: "Authorization"), "Bearer a.b.c")
        XCTAssertTrue((req.value(forHTTPHeaderField: "X-Correlation-ID") ?? "").hasPrefix("nivesh_ios_"))
    }

    func testMarketFetchCarriesBearerAndCorrelationId() async throws {
        NetworkManager.shared.authToken = "a.b.c"
        stub(503)

        _ = try? await NetworkManager.shared.getMarketIndices()

        let req = try XCTUnwrap(requests(to: "/market-indices").first)
        XCTAssertEqual(req.value(forHTTPHeaderField: "Authorization"), "Bearer a.b.c")
        XCTAssertTrue((req.value(forHTTPHeaderField: "X-Correlation-ID") ?? "").hasPrefix("nivesh_ios_"))
    }

    func testHarvesterFeedChecksStatus() async {
        NetworkManager.shared.authToken = nil
        stub(503, #"{"detail":"down"}"#)

        do {
            _ = try await NetworkManager.shared.fetchHarvesterFeed()
            XCTFail("a 503 error body must not decode as an empty feed")
        } catch {
            assertFetchFailed(error, status: 503)
        }
    }

    func test401MapsToUnauthorized() async {
        // No bearer, so the 401 does not sign the host app out.
        NetworkManager.shared.authToken = nil
        stub(401)

        do {
            _ = try await NetworkManager.shared.fetchGovernanceCards(ticker: "TCS")
            XCTFail("expected unauthorized")
        } catch NetworkError.unauthorized {
        } catch {
            XCTFail("expected unauthorized, got \(error)")
        }
    }

    func testExportPDFRejectsJSONErrorBody() async {
        NetworkManager.shared.authToken = nil
        stub(500, #"{"detail":"boom"}"#)

        do {
            _ = try await NetworkManager.shared.exportPortfolioPDF(userId: 1)
            XCTFail("a JSON error body must not be shared as a PDF")
        } catch NetworkError.serverError(let code, _) {
            XCTAssertEqual(code, 500)
        } catch {
            XCTFail("expected serverError(500), got \(error)")
        }
    }

    func testYouTubeSummaryDoesNotPostOnServerError() async {
        NetworkManager.shared.authToken = nil
        stub(500)

        do {
            _ = try await NetworkManager.shared.fetchYouTubeSummary(videoId: "abc123")
            XCTFail("expected an error")
        } catch {}

        let calls = requests(to: "/youtube/summary")
        XCTAssertEqual(calls.count, 1, "a 5xx on the cached GET must not trigger the paid POST")
        XCTAssertEqual(calls.first?.httpMethod, "GET")
    }

    func testYouTubeSummaryPostsOnCacheMiss() async {
        NetworkManager.shared.authToken = nil
        StubURLProtocol.handler = { req in
            let status = req.httpMethod == "POST" ? 200 : 404
            return (HTTPURLResponse(url: req.url!, statusCode: status, httpVersion: nil, headerFields: nil)!, Data("{}".utf8))
        }

        _ = try? await NetworkManager.shared.fetchYouTubeSummary(videoId: "abc123")

        let calls = requests(to: "/youtube/summary")
        XCTAssertEqual(calls.map(\.httpMethod), ["GET", "POST"])
    }

    func testBrainstormNon2xxThrows() async {
        NetworkManager.shared.authToken = "a.b.c"
        stub(500)

        do {
            _ = try await NetworkManager.shared.brainstorm(topic: "EV", riskTolerance: "low")
            XCTFail("expected serverError")
        } catch NetworkError.serverError(let code, _) {
            XCTAssertEqual(code, 500)
        } catch {
            XCTFail("expected serverError(500), got \(error)")
        }
        XCTAssertEqual(requests(to: "/brainstorm").first?.value(forHTTPHeaderField: "Authorization"), "Bearer a.b.c")
    }

    func testSidebarFetchReturnsNilOnServerError() async {
        NetworkManager.shared.authToken = "a.b.c"
        stub(503)

        let result = await NetworkManager.shared.fetchMomentum()

        XCTAssertNil(result)
        let req = requests(to: "/market/momentum").first
        XCTAssertEqual(req?.value(forHTTPHeaderField: "Authorization"), "Bearer a.b.c")
    }

    func testHomeFeedEncodesAmpersandTicker() async throws {
        NetworkManager.shared.authToken = "a.b.c"
        stub(503)

        _ = try? await HomeFeedService.shared.fetchFeed(userId: 7, ticker: "M&M")

        let req = try XCTUnwrap(requests(to: "/home-feed").first)
        XCTAssertEqual(req.value(forHTTPHeaderField: "Authorization"), "Bearer a.b.c")
        let items = URLComponents(url: try XCTUnwrap(req.url), resolvingAgainstBaseURL: false)?.queryItems ?? []
        XCTAssertEqual(items.first { $0.name == "ticker" }?.value, "M&M")
        XCTAssertEqual(items.first { $0.name == "user_id" }?.value, "7")
        XCTAssertEqual(items.count, 2)
    }
}
