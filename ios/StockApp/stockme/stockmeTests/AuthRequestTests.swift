import XCTest
@testable import stockme

/// IOSCORE-04: analysis job calls must carry the Bearer token and app-build headers,
/// so the backend can enforce token auth without breaking this build.
final class AuthRequestTests: XCTestCase {

    @MainActor
    func testAuthRequestCarriesBearerAndVersion() {
        let nm = NetworkManager.shared
        let savedToken = nm.authToken
        defer { nm.authToken = savedToken }
        nm.authToken = "a.b.c"

        let req = nm.authRequest(URL(string: "https://x/analyze/active")!)

        XCTAssertEqual(req.value(forHTTPHeaderField: "Authorization"), "Bearer a.b.c")
        XCTAssertFalse((req.value(forHTTPHeaderField: "X-App-Version") ?? "").isEmpty)
        XCTAssertFalse((req.value(forHTTPHeaderField: "X-App-Build") ?? "").isEmpty)
        XCTAssertNotNil(req.value(forHTTPHeaderField: "X-Correlation-ID"))
    }

    @MainActor
    func testAnalysisJobCallsSendBearer() async {
        let nm = NetworkManager.shared
        let savedToken = nm.authToken
        let savedSession = nm.session
        defer { nm.authToken = savedToken; nm.session = savedSession }
        nm.authToken = "a.b.c"
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [CaptureProtocol.self]
        nm.session = AuthAwareSession(base: URLSession(configuration: config))
        CaptureProtocol.reset()

        _ = try? await nm.startAnalysisJob(ticker: "TCS", exchange: "NSE", userId: 7, scanType: "standard")
        _ = try? await nm.pollJob(jobId: "j1", userId: 7)
        _ = try? await nm.pollJobRaw(jobId: "j1", userId: 7)
        _ = try? await nm.cancelJob(jobId: "j1", userId: 7)
        _ = try? await nm.getActiveJob(userId: 7)

        // The host app may poll through the same session meanwhile, so judge every /analyze call.
        let analysisCalls = CaptureProtocol.requests.filter { ($0.url?.path ?? "").contains("/analyze") }
        let paths = analysisCalls.compactMap { $0.url?.path }
        for suffix in ["/analyze", "/analyze/job/j1", "/analyze/j1/cancel", "/analyze/active"] {
            XCTAssertTrue(paths.contains { $0.hasSuffix(suffix) }, "no request captured for \(suffix)")
        }
        for req in analysisCalls {
            let url = req.url?.absoluteString ?? "?"
            XCTAssertEqual(req.value(forHTTPHeaderField: "Authorization"), "Bearer a.b.c", url)
            XCTAssertNotNil(req.value(forHTTPHeaderField: "X-App-Build"), url)
        }
    }
}

/// Answers every request with 200 `{}` and records it, so nothing reaches the network.
private final class CaptureProtocol: URLProtocol {
    private static let lock = NSLock()
    private static var captured: [URLRequest] = []

    static var requests: [URLRequest] {
        lock.lock(); defer { lock.unlock() }
        return captured
    }

    static func reset() {
        lock.lock(); defer { lock.unlock() }
        captured = []
    }

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        Self.lock.lock()
        Self.captured.append(request)
        Self.lock.unlock()
        let response = HTTPURLResponse(url: request.url!, statusCode: 200, httpVersion: nil,
                                       headerFields: ["Content-Type": "application/json"])!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: Data("{}".utf8))
        client?.urlProtocolDidFinishLoading(self)
    }

    override func stopLoading() {}
}
