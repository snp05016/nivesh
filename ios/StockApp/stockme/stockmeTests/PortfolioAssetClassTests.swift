import XCTest
@testable import stockme

/// Money: GET /portfolio rows carry asset_class; fund rows are requested only by the Portfolio screen.
@MainActor
final class PortfolioAssetClassTests: XCTestCase {

    private var savedToken: String?
    private var savedSession: AuthAwareSession?

    override func setUp() {
        super.setUp()
        StubURLProtocol.reset()
        savedToken = NetworkManager.shared.authToken
        savedSession = NetworkManager.shared.session
        NetworkManager.shared.authToken = nil
    }

    override func tearDown() {
        StubURLProtocol.reset()
        NetworkManager.shared.authToken = savedToken
        if let savedSession { NetworkManager.shared.session = savedSession }
        super.tearDown()
    }

    private func stubPortfolio(_ json: String) {
        StubURLProtocol.handler = { req in
            (HTTPURLResponse(url: req.url!, statusCode: 200, httpVersion: nil, headerFields: nil)!, Data(json.utf8))
        }
        NetworkManager.shared.session = AuthAwareSession(base: URLSession(configuration: StubURLProtocol.configuration()))
    }

    private let payload = """
    {"holdings": [
      {"ticker": "INFY", "company_name": "Infosys Ltd", "shares": 10, "buy_price": 1400, "current_price": 1500,
       "price_status": "live", "day_change_pct": 1.0, "asset_class": "EQ"},
      {"ticker": "INF179K01VC4", "company_name": "HDFC Flexi Cap Fund", "shares": 100, "buy_price": 40, "current_price": 50,
       "price_status": "nav", "day_change_pct": 0.0, "asset_class": "MF"},
      {"ticker": "TCS", "company_name": "TCS Ltd", "shares": 1, "buy_price": 3000, "current_price": 3100, "price_status": "live"}
    ]}
    """

    func testAssetClassMapsAndDefaultsToEquity() async throws {
        stubPortfolio(payload)

        let holdings = try await NetworkManager.shared.getPortfolio(userId: 1, includeFunds: true)

        XCTAssertEqual(holdings.map(\.assetClass), ["EQ", "MF", "EQ"])
        XCTAssertEqual(holdings.map(\.isMutualFund), [false, true, false])
        XCTAssertEqual(holdings[1].priceStatus, "nav")
    }

    func testFundsHeaderSentOnlyWhenRequested() async throws {
        stubPortfolio(payload)

        _ = try await NetworkManager.shared.getPortfolio(userId: 1)
        _ = try await NetworkManager.shared.getPortfolio(userId: 1, includeFunds: true)

        let sent = StubURLProtocol.requests.map { $0.value(forHTTPHeaderField: "X-Client-Features") }
        XCTAssertEqual(sent.count, 2)
        XCTAssertNil(sent[0])
        XCTAssertEqual(sent[1], "asset_class")
    }

    func testWidgetSnapshotExcludesFunds() async throws {
        guard let defaults = UserDefaults(suiteName: WidgetSnapshotStore.suite) else {
            throw XCTSkip("App Group defaults unavailable in this test host")
        }
        stubPortfolio(payload)

        _ = try await NetworkManager.shared.getPortfolio(userId: 1, includeFunds: true)

        // INFY 10 x 1500 + TCS 1 x 3100; the 100 x 50 fund is not counted.
        XCTAssertEqual(defaults.double(forKey: "w_portfolio_value"), 18_100, accuracy: 0.01)
    }
}
