import XCTest
@testable import stockme

/// C1 golden path, iOS half (docs/release/GOLDEN_PATH.md). Drives the real
/// NetworkManager methods over the response fixtures recorded from the hermetic
/// backend run (docs/contract/golden) and checks the request bodies the app sends
/// against requests.json, which backend/tests/test_golden_path.py posts too. A
/// renamed backend field fails pytest; a renamed Swift key fails here.
@MainActor
final class GoldenPathContractTests: XCTestCase {

    private var savedSession: AuthAwareSession?
    private var savedToken: String?
    private var savedServerURL: String?

    private static let baseURL = "https://golden.test"

    override func setUp() {
        super.setUp()
        StubURLProtocol.reset()
        let nm = NetworkManager.shared
        savedSession = nm.session
        savedToken = nm.authToken
        savedServerURL = UserDefaults.standard.string(forKey: NetworkManager.serverURLKey)
        nm.session = AuthAwareSession(base: URLSession(configuration: StubURLProtocol.configuration()))
        UserDefaults.standard.set(Self.baseURL, forKey: NetworkManager.serverURLKey)
    }

    override func tearDown() {
        let nm = NetworkManager.shared
        if let savedSession { nm.session = savedSession }
        nm.authToken = savedToken
        if let savedServerURL {
            UserDefaults.standard.set(savedServerURL, forKey: NetworkManager.serverURLKey)
        } else {
            UserDefaults.standard.removeObject(forKey: NetworkManager.serverURLKey)
        }
        StubURLProtocol.reset()
        super.tearDown()
    }

    // MARK: - Fixtures

    /// The repository root, reached from this file: the test directory is four
    /// levels below it (ios/StockApp/stockme/stockmeTests).
    private static let repoRoot = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent()   // stockmeTests
        .deletingLastPathComponent()   // stockme
        .deletingLastPathComponent()   // StockApp
        .deletingLastPathComponent()   // ios
        .deletingLastPathComponent()   // repository root

    private func golden(_ name: String) throws -> Data {
        try Data(contentsOf: Self.repoRoot.appendingPathComponent("docs/contract/golden/\(name).json"))
    }

    private func goldenObject(_ name: String) throws -> [String: Any] {
        try XCTUnwrap(try JSONSerialization.jsonObject(with: golden(name)) as? [String: Any], name)
    }

    /// requests.json[`key`]: the request body the backend half posts for that step.
    private func requestFixture(_ key: String) throws -> [String: Any] {
        try XCTUnwrap(try goldenObject("requests")[key] as? [String: Any], "requests.json has no \(key)")
    }

    // MARK: - Stub

    private struct UnexpectedRoute: Error { let route: String }

    /// Serves only `routes` ("METHOD /path" -> body, 200); anything else throws, so
    /// no request from this test (or the host app meanwhile) reaches the network.
    private func serve(_ routes: [String: Data]) {
        StubURLProtocol.handler = { req in
            let route = "\(req.httpMethod ?? "GET") \(req.url?.path ?? "")"
            guard let body = routes[route], let url = req.url else { throw UnexpectedRoute(route: route) }
            let response = HTTPURLResponse(url: url, statusCode: 200, httpVersion: nil,
                                           headerFields: ["Content-Type": "application/json"])!
            return (response, body)
        }
    }

    private func recorded(_ method: String, _ path: String) throws -> URLRequest {
        try XCTUnwrap(StubURLProtocol.requests.first { $0.httpMethod == method && $0.url?.path == path },
                      "no \(method) \(path) was sent")
    }

    private func bodyKeys(_ request: URLRequest) throws -> Set<String> {
        let body = try XCTUnwrap(request.httpBody, "request has no body")
        let object = try XCTUnwrap(try JSONSerialization.jsonObject(with: body) as? [String: Any])
        return Set(object.keys)
    }

    // MARK: - 1. Sign in

    func testLoginDecodesGoldenResponse() async throws {
        let login = try goldenObject("login")
        let creds = try requestFixture("login")
        serve(["POST /login": try golden("login")])

        let user = try await NetworkManager.shared.login(
            username: try XCTUnwrap(creds["username"] as? String),
            password: try XCTUnwrap(creds["password"] as? String))

        XCTAssertEqual(user.userId, try XCTUnwrap(login["user_id"] as? Int))
        XCTAssertEqual(user.token, try XCTUnwrap(login["access_token"] as? String))
        XCTAssertEqual(try bodyKeys(try recorded("POST", "/login")), Set(creds.keys))
    }

    // MARK: - 2. Add a holding

    func testAddHoldingSendsBackendFields() async throws {
        let token = try XCTUnwrap(try goldenObject("login")["access_token"] as? String)
        let req = try requestFixture("add_holding")
        NetworkManager.shared.authToken = token
        // POST /portfolio is the same backend handler as /portfolio/add (routers/portfolio.py).
        serve(["POST /portfolio": Data(#"{"success":true}"#.utf8),
               "POST /portfolio/add": Data(#"{"success":true}"#.utf8)])

        try await NetworkManager.shared.addHolding(
            userId: try XCTUnwrap(req["user_id"] as? Int),
            ticker: try XCTUnwrap(req["ticker"] as? String),
            companyName: try XCTUnwrap(req["company_name"] as? String),
            shares: try XCTUnwrap(req["shares"] as? Double),
            buyPrice: try XCTUnwrap(req["buy_price"] as? Double),
            purchaseDate: try XCTUnwrap(WireDate.dayFormatter.date(from: try XCTUnwrap(req["purchase_date"] as? String))),
            notes: req["notes"] as? String ?? "",
            targetPrice: nil,
            transactionType: req["transaction_type"] as? String ?? "BUY")

        let sent = try XCTUnwrap(StubURLProtocol.requests.first {
            $0.httpMethod == "POST" && ["/portfolio", "/portfolio/add"].contains($0.url?.path ?? "")
        }, "no add-holding request was sent")
        let keys = try bodyKeys(sent)
        XCTAssertTrue(keys.isSubset(of: Set(req.keys)), "keys the backend does not accept: \(keys.subtracting(req.keys))")
        for key in ["user_id", "ticker", "company_name", "shares", "buy_price"] {
            XCTAssertTrue(keys.contains(key), "missing \(key)")
        }
        XCTAssertEqual(sent.value(forHTTPHeaderField: "Authorization"), "Bearer \(token)")
    }

    // MARK: - 3. Priced P&L

    func testPortfolioDecodesGoldenResponse() async throws {
        let portfolio = try goldenObject("portfolio")
        let userId = try XCTUnwrap(try goldenObject("login")["user_id"] as? Int)
        let fixtureHoldings = try XCTUnwrap(portfolio["holdings"] as? [[String: Any]])
        let expected = try XCTUnwrap(fixtureHoldings.first)
        NetworkManager.shared.authToken = try XCTUnwrap(try goldenObject("login")["access_token"] as? String)
        serve(["GET /portfolio/\(userId)": try golden("portfolio")])

        let holdings = try await NetworkManager.shared.getPortfolio(userId: userId)

        XCTAssertEqual(holdings.count, fixtureHoldings.count)
        let h = try XCTUnwrap(holdings.first)
        XCTAssertEqual(h.stock.ticker, try XCTUnwrap(expected["ticker"] as? String))
        XCTAssertEqual(h.stock.ticker, "TCS")
        // A nil current_price would fall back to buy_price, so equality catches it.
        XCTAssertEqual(h.stock.currentPrice, try XCTUnwrap(expected["current_price"] as? Double), accuracy: 0.001)
        XCTAssertEqual(h.priceStatus, try XCTUnwrap(expected["price_status"] as? String))
        XCTAssertEqual(h.priceAsOf, try XCTUnwrap(expected["price_as_of"] as? String))
        XCTAssertEqual(h.buyPrice, try XCTUnwrap(expected["buy_price"] as? Double), accuracy: 0.001)
        XCTAssertEqual(h.shares, try XCTUnwrap(expected["shares"] as? Double), accuracy: 0.001)
        XCTAssertEqual(h.pnl, try XCTUnwrap(expected["pnl_inr"] as? Double), accuracy: 0.01)
    }

    // MARK: - 4. Stock report

    func testResearchReportFetch() async throws {
        let report = try Data(contentsOf: Self.repoRoot
            .appendingPathComponent("docs/research/contract/fixtures/validated_cohort.json"))
        NetworkManager.shared.authToken = try XCTUnwrap(try goldenObject("login")["access_token"] as? String)
        serve(["GET /api/v1/research/stocks/TCS": report])

        let result = try await NetworkManager.shared.fetchResearchReport(symbol: "TCS")

        guard case .report(let r) = result else { return XCTFail("expected a report, got \(result)") }
        XCTAssertEqual(r.schemaVersion, "research.v1")
    }

    // MARK: - 5. Price alert

    func testAlertAddAndList() async throws {
        let added = try goldenObject("add_alert")
        let req = try requestFixture("add_alert")
        let userId = try XCTUnwrap(req["user_id"] as? Int)
        let listed = try XCTUnwrap(try goldenObject("alerts")["alerts"] as? [[String: Any]])
        let expected = try XCTUnwrap(listed.first)
        NetworkManager.shared.authToken = try XCTUnwrap(try goldenObject("login")["access_token"] as? String)
        serve(["POST /alerts/add": try golden("add_alert"),
               "GET /alerts/\(userId)": try golden("alerts")])

        let alertId = try await NetworkManager.shared.addAlert(
            userId: userId,
            ticker: try XCTUnwrap(req["ticker"] as? String),
            targetPrice: try XCTUnwrap(req["target_price"] as? Double),
            direction: try XCTUnwrap(req["direction"] as? String),
            companyName: try XCTUnwrap(req["company_name"] as? String))
        let alerts = try await NetworkManager.shared.getAlerts(userId: userId)

        XCTAssertEqual(alertId, try XCTUnwrap(added["alert_id"] as? Int))
        XCTAssertEqual(try bodyKeys(try recorded("POST", "/alerts/add")), Set(req.keys))
        XCTAssertEqual(alerts.count, listed.count)
        let a = try XCTUnwrap(alerts.first)
        XCTAssertEqual(a.ticker, try XCTUnwrap(expected["ticker"] as? String))
        XCTAssertEqual(a.ticker, "TCS")
        XCTAssertEqual(a.targetPrice, try XCTUnwrap(expected["target_price"] as? Double), accuracy: 0.001)
        XCTAssertEqual(a.direction, try XCTUnwrap(expected["direction"] as? String))
    }

    // MARK: - 6. Push registration

    func testDeviceRegistrationBody() async throws {
        let req = try requestFixture("device_register")
        NetworkManager.shared.authToken = try XCTUnwrap(try goldenObject("login")["access_token"] as? String)
        serve(["POST /api/v1/notifications/register": Data(#"{"success":true}"#.utf8)])

        try await NetworkManager.shared.registerDeviceToken(token: try XCTUnwrap(req["device_token"] as? String))

        XCTAssertEqual(try bodyKeys(try recorded("POST", "/api/v1/notifications/register")), Set(req.keys))
    }

    // MARK: - 7. Tap through to the stock

    func testInboxItemRoutesToReport() async throws {
        let inbox = try XCTUnwrap(try JSONSerialization.jsonObject(with: golden("inbox")) as? [[String: Any]])
        let expectedURL = try XCTUnwrap(inbox.first?["action_url"] as? String)
        NetworkManager.shared.authToken = try XCTUnwrap(try goldenObject("login")["access_token"] as? String)
        serve(["GET /api/v1/notifications": try golden("inbox")])

        let items = try await NetworkManager.shared.fetchNotifications()

        let actionUrl = try XCTUnwrap(items.first?.actionUrl, "first inbox item has no action_url")
        XCTAssertEqual(actionUrl, expectedURL)
        XCTAssertEqual(DeepLink.ticker(from: try XCTUnwrap(URL(string: actionUrl))), "TCS")
    }
}
