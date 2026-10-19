import XCTest
@testable import stockme

@MainActor
final class EventLoggerTests: XCTestCase {

    private struct Offline: Error {}

    private final class Harness {
        var enabled = true
        var batches: [[QueuedEvent]] = []
        var refreshes = 0
        var ack = EventsAck(accepted: 0, rejected: 0, reason: nil)
        var failSend = false

        func makeLogger() -> EventLogger {
            EventLogger(
                isEnabled: { [unowned self] in self.enabled },
                send: { [unowned self] batch in
                    if self.failSend { throw Offline() }
                    self.batches.append(batch)
                    return EventsAck(accepted: batch.count, rejected: 0, reason: self.ack.reason)
                },
                refreshFlags: { [unowned self] in self.refreshes += 1 },
                now: { Date(timeIntervalSince1970: 1_790_000_000) }
            )
        }
    }

    func testDisabledBuffersNothing() {
        let h = Harness()
        h.enabled = false
        let logger = h.makeLogger()
        logger.log(.stockView)
        XCTAssertTrue(logger.buffer.isEmpty)
    }

    func testTwentyEventsTriggerOneSend() async {
        let h = Harness()
        let logger = h.makeLogger()
        for _ in 0..<19 { logger.log(.stockView) }
        XCTAssertTrue(h.batches.isEmpty)
        logger.log(.stockView)
        await logger.pendingFlush?.value
        XCTAssertEqual(h.batches.count, 1)
        XCTAssertEqual(h.batches[0].count, 20)
        XCTAssertTrue(logger.buffer.isEmpty)
    }

    func testBatchesAreCappedAt50() async {
        let h = Harness()
        let logger = h.makeLogger()
        h.failSend = true  // keep events buffered while we fill past 50
        for _ in 0..<120 { logger.log(.stockView) }
        await logger.pendingFlush?.value
        h.failSend = false
        await logger.flush()
        XCTAssertEqual(h.batches.first?.count, 50)
        XCTAssertTrue(h.batches.allSatisfy { $0.count <= 50 })
    }

    func testBufferIsCappedAt200ByDroppingOldest() async {
        let h = Harness()
        let logger = h.makeLogger()
        h.failSend = true
        for i in 0..<230 { logger.log(.search, ["results": i == 0 ? "0" : "6+"]) }
        await logger.pendingFlush?.value
        XCTAssertEqual(logger.buffer.count, 200)
        XCTAssertFalse(logger.buffer.contains { $0.props["results"] == "0" })  // the oldest is gone
    }

    func testNoConsentAckClearsBufferAndRefreshesFlags() async {
        let h = Harness()
        h.ack = EventsAck(accepted: 0, rejected: 0, reason: "no_consent")
        let logger = h.makeLogger()
        for _ in 0..<5 { logger.log(.stockView) }
        await logger.flush()
        XCTAssertTrue(logger.buffer.isEmpty)
        XCTAssertEqual(h.refreshes, 1)
    }

    func testFlushWhileDisabledClearsWithoutSending() async {
        let h = Harness()
        let logger = h.makeLogger()
        logger.log(.stockView)
        h.enabled = false
        await logger.flush()
        XCTAssertTrue(logger.buffer.isEmpty)
        XCTAssertTrue(h.batches.isEmpty)
    }

    func testSendErrorKeepsEvents() async {
        let h = Harness()
        h.failSend = true
        let logger = h.makeLogger()
        logger.log(.stockView)
        logger.log(.paywallView)
        await logger.flush()
        XCTAssertEqual(logger.buffer.map(\.name), ["stock_view", "paywall_view"])
    }

    func testEventCarriesNameAndPropsAndIsoTimestamp() {
        let h = Harness()
        let logger = h.makeLogger()
        logger.log(.appOpen, ["launch": "cold"])
        XCTAssertEqual(logger.buffer.first?.name, "app_open")
        XCTAssertEqual(logger.buffer.first?.props, ["launch": "cold"])
        XCTAssertEqual(logger.buffer.first?.ts, "2026-09-21T14:13:20Z")
    }

    func testSearchBuckets() {
        XCTAssertEqual(EventLogger.searchBucket(0), "0")
        XCTAssertEqual(EventLogger.searchBucket(1), "1-5")
        XCTAssertEqual(EventLogger.searchBucket(5), "1-5")
        XCTAssertEqual(EventLogger.searchBucket(6), "6+")
        XCTAssertEqual(EventLogger.searchBucket(40), "6+")
    }

    func testAppEventNamesMatchTheServerAllowlist() {
        let names: Set<String> = [
            AppEvent.appOpen, .search, .stockView, .reportView, .reportCompute,
            .alertCreate, .importStart, .importDone, .paywallView, .purchase,
        ].reduce(into: Set<String>()) { $0.insert($1.rawValue) }
        XCTAssertEqual(names, ["app_open", "search", "stock_view", "report_view", "report_compute",
                               "alert_create", "import_start", "import_done", "paywall_view", "purchase"])
    }
}

/// POST /api/v1/events must carry the Bearer token, the app-version header and the documented body.
final class PostEventsRequestTests: XCTestCase {

    @MainActor
    func testPostEventsSendsBearerVersionAndBody() async throws {
        let nm = NetworkManager.shared
        let savedToken = nm.authToken
        let savedSession = nm.session
        defer { nm.authToken = savedToken; nm.session = savedSession }
        nm.authToken = "a.b.c"
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [EventsCaptureProtocol.self]
        nm.session = AuthAwareSession(base: URLSession(configuration: config))
        EventsCaptureProtocol.reset()

        let ack = try await nm.postEvents([QueuedEvent(name: "app_open", props: ["launch": "cold"], ts: "2026-10-11T03:12:00Z")])
        XCTAssertEqual(ack, EventsAck(accepted: 1, rejected: 0, reason: nil))

        let req = try XCTUnwrap(EventsCaptureProtocol.requests.first { $0.url?.path == "/api/v1/events" })
        XCTAssertEqual(req.httpMethod, "POST")
        XCTAssertEqual(req.value(forHTTPHeaderField: "Authorization"), "Bearer a.b.c")
        XCTAssertFalse((req.value(forHTTPHeaderField: "X-App-Version") ?? "").isEmpty)
        XCTAssertEqual(req.value(forHTTPHeaderField: "Content-Type"), "application/json")
        let body = try XCTUnwrap(EventsCaptureProtocol.bodies.first)
        let json = try XCTUnwrap(JSONSerialization.jsonObject(with: body) as? [String: Any])
        XCTAssertEqual(json["platform"] as? String, "ios")
        XCTAssertNotNil(json["app_version"])
        let events = try XCTUnwrap(json["events"] as? [[String: Any]])
        XCTAssertEqual(events.first?["name"] as? String, "app_open")
        XCTAssertEqual((events.first?["props"] as? [String: String]), ["launch": "cold"])
        XCTAssertEqual(events.first?["ts"] as? String, "2026-10-11T03:12:00Z")
    }
}

/// Answers every request with 202 and an events ack, and records the request and its body.
private final class EventsCaptureProtocol: URLProtocol {
    private static let lock = NSLock()
    private static var captured: [URLRequest] = []
    private static var capturedBodies: [Data] = []

    static var requests: [URLRequest] { lock.lock(); defer { lock.unlock() }; return captured }
    static var bodies: [Data] { lock.lock(); defer { lock.unlock() }; return capturedBodies }

    static func reset() {
        lock.lock(); defer { lock.unlock() }
        captured = []
        capturedBodies = []
    }

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        var body = request.httpBody
        if body == nil, let stream = request.httpBodyStream {
            stream.open()
            defer { stream.close() }
            var data = Data()
            var buffer = [UInt8](repeating: 0, count: 4096)
            while stream.hasBytesAvailable {
                let n = stream.read(&buffer, maxLength: buffer.count)
                if n <= 0 { break }
                data.append(buffer, count: n)
            }
            body = data
        }
        Self.lock.lock()
        Self.captured.append(request)
        if let body { Self.capturedBodies.append(body) }
        Self.lock.unlock()
        let response = HTTPURLResponse(url: request.url!, statusCode: 202, httpVersion: nil,
                                       headerFields: ["Content-Type": "application/json"])!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: Data(#"{"accepted":1,"rejected":0,"reason":null}"#.utf8))
        client?.urlProtocolDidFinishLoading(self)
    }

    override func stopLoading() {}
}
