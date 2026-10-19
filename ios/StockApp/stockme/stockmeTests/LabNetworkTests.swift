import XCTest
@testable import stockme

/// Lab network calls hit the contract's paths and methods under /api/v1/research-lab,
/// send snake_case bodies, and map 422 / 404 to user copy.
@MainActor
final class LabNetworkTests: XCTestCase {

    private var savedSession: AuthAwareSession?
    private var savedServerURL: String?
    private static let baseURL = "https://golden.test"
    private static let prefix = "/api/v1/research-lab"

    override func setUp() {
        super.setUp()
        StubURLProtocol.reset()
        let nm = NetworkManager.shared
        savedSession = nm.session
        savedServerURL = UserDefaults.standard.string(forKey: NetworkManager.serverURLKey)
        nm.session = AuthAwareSession(base: URLSession(configuration: StubURLProtocol.configuration()))
        UserDefaults.standard.set(Self.baseURL, forKey: NetworkManager.serverURLKey)
    }

    override func tearDown() {
        if let savedSession { NetworkManager.shared.session = savedSession }
        if let savedServerURL {
            UserDefaults.standard.set(savedServerURL, forKey: NetworkManager.serverURLKey)
        } else {
            UserDefaults.standard.removeObject(forKey: NetworkManager.serverURLKey)
        }
        StubURLProtocol.reset()
        super.tearDown()
    }

    private struct UnexpectedRoute: Error { let route: String }

    /// Serves `"METHOD /path"` (path without the Lab prefix) with `body` and `status`.
    private func serve(_ routes: [String: (Int, String)]) {
        let prefix = Self.prefix
        StubURLProtocol.handler = { req in
            let path = (req.url?.path ?? "").replacingOccurrences(of: prefix, with: "")
            let route = "\(req.httpMethod ?? "GET") \(path)"
            guard let hit = routes[route], let url = req.url else { throw UnexpectedRoute(route: route) }
            let response = HTTPURLResponse(url: url, statusCode: hit.0, httpVersion: nil,
                                           headerFields: ["Content-Type": "application/json"])!
            return (response, Data(hit.1.utf8))
        }
    }

    private func lastBody() throws -> [String: Any] {
        let body = try XCTUnwrap(StubURLProtocol.requests.last?.httpBody, "request has no body")
        return try XCTUnwrap(try JSONSerialization.jsonObject(with: body) as? [String: Any])
    }

    func testScenariosAndSessionsAreGETs() async throws {
        serve(["GET /scenarios": (200, #"{"version": 1, "scenarios": [{"id": "s1", "title": "T", "briefing": "b"}]}"#),
               "GET /sessions": (200, #"[{"id": 1, "title": "A"}]"#)])
        let catalog = try await NetworkManager.shared.labScenarios()
        XCTAssertEqual(catalog.scenarios?.first?.id, "s1")
        let sessions = try await NetworkManager.shared.labSessions()
        XCTAssertEqual(sessions.items.first?.id, "1")
        XCTAssertEqual(StubURLProtocol.requests.map { $0.url?.path ?? "" },
                       ["\(Self.prefix)/scenarios", "\(Self.prefix)/sessions"])
    }

    func testCreateSessionPostsConfig() async throws {
        serve(["POST /sessions": (200, #"{"id": "abc", "state": {"clock": "2020-02-03", "finished": false}}"#)])
        let config = LabSimConfig(start: "2020-02-03", end: "2020-06-30", universe: ["SBIN", "TCS"], capital: 1_000_000, hideIdentity: true)
        let s = try await NetworkManager.shared.labCreateSession(title: "T", scenarioId: "covid", config: config)
        XCTAssertEqual(s.id?.value, "abc")
        let body = try lastBody()
        XCTAssertEqual(body["scenario_id"] as? String, "covid")
        let cfg = try XCTUnwrap(body["config"] as? [String: Any])
        XCTAssertEqual(cfg["universe"] as? [String], ["SBIN", "TCS"])
        XCTAssertEqual(cfg["hide_identity"] as? Bool, true)
    }

    func testPostActionSendsActionAndClientId() async throws {
        serve(["POST /sessions/s1/actions": (200, #"{"id": "s1", "state": {"clock": "2020-02-10", "day_index": 5}}"#)])
        let s = try await NetworkManager.shared.labPostAction(sessionId: "s1", action: .advance(days: 5), clientActionId: "c-1")
        XCTAssertEqual(s?.state?.dayIndex, 5)
        let body = try lastBody()
        XCTAssertEqual(body["client_action_id"] as? String, "c-1")
        let action = try XCTUnwrap(body["action"] as? [String: Any])
        XCTAssertEqual(action["type"] as? String, "advance")
        XCTAssertEqual(action["days"] as? Int, 5)
    }

    func testPostActionAcknowledgementWithoutStateReturnsNil() async throws {
        serve(["POST /sessions/s1/actions": (200, #"{"ok": true, "action_index": 4}"#)])
        let s = try await NetworkManager.shared.labPostAction(sessionId: "s1", action: .cancel(orderId: "o2"), clientActionId: "c-2")
        XCTAssertNil(s)
    }

    func testRejectedActionSurfacesServerReason() async {
        serve(["POST /sessions/s1/actions": (422, #"{"detail": "action 3: not enough cash"}"#)])
        do {
            _ = try await NetworkManager.shared.labPostAction(sessionId: "s1", action: .advance(days: 1), clientActionId: "c")
            XCTFail("expected a 422")
        } catch {
            XCTAssertEqual(LabErrors.message(error), "action 3: not enough cash")
        }
    }

    func testDisabledFlagMapsToDisabledCopy() async {
        serve(["GET /scenarios": (404, #"{"detail": "Not Found"}"#)])
        do {
            _ = try await NetworkManager.shared.labScenarios()
            XCTFail("expected a 404")
        } catch {
            XCTAssertEqual(LabErrors.message(error), LabErrors.disabled)
        }
    }

    func testHistoryAutopsyAndMentorPaths() async throws {
        serve(["POST /sessions/s1/history": (200, #"{"symbol": "SBIN", "asof": "2020-03-02", "bars": [{"d": "2020-03-02", "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 10}]}"#),
               "GET /sessions/s1/autopsy": (200, #"{"clock": "2020-03-02", "trades": []}"#),
               "POST /sessions/s1/mentor": (200, #"{"answer": "a", "grounded_on": {}, "mode": "llm", "disclaimer": "d"}"#)])
        let h = try await NetworkManager.shared.labHistory(sessionId: "s1", symbol: "SBIN", bars: 60)
        XCTAssertEqual(h.bars?.first?.c, 1.5)
        XCTAssertEqual(try lastBody()["bars"] as? Int, 60)

        _ = try await NetworkManager.shared.labAutopsy(sessionId: "s1", orderId: "o3")
        XCTAssertEqual(StubURLProtocol.requests.last?.url?.query, "order_id=o3")

        let reply = try await NetworkManager.shared.labMentor(sessionId: "s1", question: "Why?", orderId: nil)
        XCTAssertEqual(reply.modeKind, .llm)
        let body = try lastBody()
        XCTAssertEqual(body["question"] as? String, "Why?")
        XCTAssertNil(body["order_id"])
    }

    func testResearchEndpoints() async throws {
        serve(["GET /research/templates": (200, #"{"templates": [{"id": "momentum_12_1", "score": "mom_12_1", "horizon": 20, "program": "p"}]}"#),
               "POST /research/compile": (200, #"{"ok": false, "error": "unknown field", "line": 2, "col": 7}"#),
               "POST /research/translate": (200, #"{"spec": {"program": "x = 1", "score": "x", "horizon": 5}, "explanation": "e", "missing_data": [], "mode": "rules"}"#),
               "POST /research/experiments": (200, #"{"id": 9, "report": {"status": "insufficient_data", "verdict": {"label": "insufficient_data"}}}"#),
               "GET /research/experiments": (200, #"{"items": [{"id": 9}], "total": 1}"#)])
        let t = try await NetworkManager.shared.labTemplates()
        XCTAssertEqual(t.templates?.first?.horizon, 20)
        let c = try await NetworkManager.shared.labCompile(program: "x = nope")
        XCTAssertEqual(c.ok, false)
        XCTAssertEqual(c.line, 2)
        XCTAssertEqual(try lastBody()["program"] as? String, "x = nope")
        let tr = try await NetworkManager.shared.labTranslate(question: "q")
        XCTAssertEqual(tr.spec?.score, "x")
        let run = try await NetworkManager.shared.labRunExperiment(spec: ["program": "x = 1", "score": "x", "horizon": 5])
        XCTAssertEqual(run.id?.value, "9")
        XCTAssertEqual(run.report.verdict?.kind, .insufficientData)
        XCTAssertNil(try lastBody()["trials_so_far"], "the server fills trials_so_far from the ledger")
        let ledger = try await NetworkManager.shared.labExperiments()
        XCTAssertEqual(ledger.total, 1)
    }

    func testSchoolAndEventEndpoints() async throws {
        serve(["GET /school/curriculum": (200, #"{"tracks": ["foundation"], "lessons": [{"id": "f-1", "track": "foundation"}]}"#),
               "GET /school/lessons/f-1": (200, #"{"id": "f-1", "body": [], "quiz": []}"#),
               "POST /school/lessons/f-1/grade": (200, #"{"score": 1, "passed": true, "per_question": []}"#),
               "GET /school/next": (200, #"{"lessons": []}"#),
               "POST /events/timeline": (200, #"{"bars": [], "items": [], "note": "n"}"#)])
        _ = try await NetworkManager.shared.labCurriculum()
        _ = try await NetworkManager.shared.labLesson(id: "f-1")
        let g = try await NetworkManager.shared.labGrade(lessonId: "f-1", answers: [2, 0])
        XCTAssertEqual(g.passed, true)
        XCTAssertEqual(try lastBody()["answers"] as? [Int], [2, 0])
        _ = try await NetworkManager.shared.labNextLessons()
        let ev = try await NetworkManager.shared.labEventTimeline(symbol: "RELIANCE", start: "2020-01-01", end: "2020-06-30")
        XCTAssertEqual(ev.note, "n")
        let body = try lastBody()
        XCTAssertEqual(body["symbol"] as? String, "RELIANCE")
        XCTAssertEqual(body["end"] as? String, "2020-06-30")
    }
}
