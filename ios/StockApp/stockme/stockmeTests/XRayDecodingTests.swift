import XCTest
@testable import stockme

@MainActor
final class XRayDecodingTests: XCTestCase {

    private let base = """
    "as_of": "2026-10-11T09:00:00Z", "total_value_inr": 1234567.0,
    "unpriced": [{"ticker": "XYZ", "name": "XYZ Ltd"}],
    "allocation": [{"key": "stocks", "label": "Stocks", "value_inr": 700000.0, "pct": 56.7}],
    "amcs": [{"name": "HDFC Mutual Fund", "value_inr": 250000.0, "pct": 46.9}],
    "top_holdings": [{"ticker": "INFY", "name": "Infosys Ltd", "asset_class": "EQ", "value_inr": 380000.0, "pct": 30.8}],
    "concentration": {"largest_ticker": "INFY", "largest_pct": 30.8, "top5_pct": 71.2},
    "facts": [{"code": "largest_holding_share", "text": "Your largest holding, INFY, is 31% of your portfolio."}]
    """

    private func xray(plans: String, drag: String) throws -> XRayResponse {
        let json = "{\(base), \"plans\": \(plans), \"commission_drag\": \(drag)}"
        return try JSONDecoder().decode(XRayResponse.self, from: Data(json.utf8))
    }

    func testDecodesWithNullDragAndNullPlans() throws {
        let x = try xray(plans: "null", drag: "null")

        XCTAssertNil(x.plans)
        XCTAssertNil(x.commissionDrag)
        XCTAssertEqual(x.allocation.first?.key, "stocks")
        XCTAssertEqual(x.unpriced.first?.name, "XYZ Ltd")
        XCTAssertEqual(x.concentration.top5Pct, 71.2)
        XCTAssertEqual(x.facts.first?.text, "Your largest holding, INFY, is 31% of your portfolio.")
        XCTAssertFalse(x.isEmpty)
    }

    func testDecodesAvailableCommissionDragAndPlans() throws {
        let drag = """
        {"available": true, "as_of": "2026-09-30", "total_annual_cost_inr": 8450.0, "uncovered_regular_funds": 1,
         "funds": [{"isin": "INF846K01DP8", "name": "Axis Bluechip", "value_inr": 100000.0, "regular_ter_pct": 1.6,
                    "direct_ter_pct": 1.0, "gap_pp": 0.6, "annual_cost_inr": 600.0},
                   {"isin": "INF109K01Z48", "name": "ICICI Fund", "value_inr": 500000.0, "regular_ter_pct": 2.1,
                    "direct_ter_pct": 1.0, "gap_pp": 1.1, "annual_cost_inr": 5500.0}],
         "source": "AMC expense-ratio disclosures", "source_url": "https://www.amfiindia.com/ter-of-mf-schemes"}
        """
        let x = try xray(plans: #"{"direct_pct": 38.0, "regular_pct": 62.0, "unknown_pct": 0.0}"#, drag: drag)

        XCTAssertEqual(x.plans?.regularPct, 62.0)
        let d = try XCTUnwrap(x.commissionDrag)
        XCTAssertTrue(d.available)
        XCTAssertEqual(d.funds?.count, 2)
        XCTAssertEqual(XRayCopy.dragBody(d),
                       "Published expense ratios of your regular-plan funds are 0.6-1.1 points higher than the same funds' direct plans. On your current value that's about Rs 8,450 a year.")
        XCTAssertEqual(XRayCopy.dragFootnote(d),
                       "Regular plans include a distributor commission in their expense ratio. Moving between plans counts as a redemption for tax. Expense ratios as of 30 Sep 2026.")
        XCTAssertNotNil(SafeURL.web(d.sourceUrl))
    }

    func testUnavailableDragHasNoCopy() throws {
        let x = try xray(plans: "null", drag: #"{"available": false, "reason": "ter_data_stale"}"#)

        let d = try XCTUnwrap(x.commissionDrag)
        XCTAssertFalse(d.available)
        XCTAssertEqual(d.reason, "ter_data_stale")
        XCTAssertNil(XRayCopy.dragBody(d))
    }

    func testEmptyPortfolioIsEmpty() throws {
        let json = """
        {"as_of": "2026-10-11T09:00:00Z", "total_value_inr": 0.0, "unpriced": [], "allocation": [], "amcs": [],
         "plans": null, "top_holdings": [], "concentration": {"largest_ticker": null, "largest_pct": 0.0, "top5_pct": 0.0},
         "facts": [], "commission_drag": null}
        """
        let x = try JSONDecoder().decode(XRayResponse.self, from: Data(json.utf8))
        XCTAssertTrue(x.isEmpty)
        XCTAssertNil(x.concentration.largestTicker)
    }

    private let replayJSON = """
    {"scenario": {"id": "covid_2020", "label": "COVID crash", "start": "2020-02-19", "end": "2020-03-23"},
     "nifty_return_pct": -37.4, "portfolio_return_pct": -33.2, "portfolio_change_inr": -412000.0, "covered_value_inr": 1240000.0,
     "holdings": [{"ticker": "INFY", "name": "Infosys Ltd", "value_inr": 380000.0, "return_pct": -25.1}],
     "not_included": [{"ticker": "NEWCO", "name": "New Co", "value_inr": 20000.0, "reason": "listed_after_window"},
                      {"ticker": "INF179K01VC4", "name": "HDFC Flexi Cap", "value_inr": 50000.0, "reason": "mutual_fund"},
                      {"ticker": "ZZZ", "name": "Zed", "value_inr": null, "reason": "unpriced"}],
     "notes": ["This replays how today's holdings moved in that window. It is not a forecast."]}
    """

    func testReplayDecodesNotIncludedReasons() throws {
        let r = try JSONDecoder().decode(CrisisReplayResponse.self, from: Data(replayJSON.utf8))

        XCTAssertEqual(r.holdings.first?.returnPct, -25.1)
        XCTAssertEqual(r.notIncluded.map(\.reason), ["listed_after_window", "mutual_fund", "unpriced"])
        XCTAssertNil(r.notIncluded[2].valueInr)
        XCTAssertEqual(XRayCopy.notIncludedReason("mutual_fund"), "Mutual funds aren't included.")
        XCTAssertEqual(XRayCopy.replayTitle(r), "COVID crash replay (19 Feb - 23 Mar 2020)")
        XCTAssertEqual(XRayCopy.replaySummary(r),
                       "If your current stocks moved as they did then, they'd be worth Rs 4.12 lakh less (-33%). The Nifty 50 fell 37% in the same period.")
    }

    func testReplaySummaryWordsPositiveMoves() throws {
        let json = replayJSON
            .replacingOccurrences(of: "-37.4", with: "5.2")
            .replacingOccurrences(of: "-33.2", with: "4.1")
            .replacingOccurrences(of: "-412000.0", with: "41200.0")
        let r = try JSONDecoder().decode(CrisisReplayResponse.self, from: Data(json.utf8))

        XCTAssertEqual(XRayCopy.replaySummary(r),
                       "If your current stocks moved as they did then, they'd be worth Rs 41,200 more (+4%). The Nifty 50 rose 5% in the same period.")
    }

    func testRupeesUseIndianScale() {
        XCTAssertEqual(XRayCopy.rupees(950), "Rs 950")
        XCTAssertEqual(XRayCopy.rupees(8450), "Rs 8,450")
        XCTAssertEqual(XRayCopy.rupees(41200), "Rs 41,200")
        XCTAssertEqual(XRayCopy.rupees(-412000), "Rs 4.12 lakh")
        XCTAssertEqual(XRayCopy.rupees(12_000_000), "Rs 1.20 crore")
    }

    func testViewModelLoadsReplayOnlyWhenEnabled() async throws {
        let x = try xray(plans: "null", drag: "null")
        let r = try JSONDecoder().decode(CrisisReplayResponse.self, from: Data(replayJSON.utf8))
        var replayCalls = 0

        let off = PortfolioXRayViewModel(fetchXRay: { x }, fetchReplay: { replayCalls += 1; return r }, replayEnabled: { false })
        await off.load()
        XCTAssertEqual(off.state, .loaded)
        XCTAssertNil(off.replay)
        XCTAssertEqual(replayCalls, 0)

        let on = PortfolioXRayViewModel(fetchXRay: { x }, fetchReplay: { replayCalls += 1; return r }, replayEnabled: { true })
        await on.load()
        XCTAssertNotNil(on.replay)

        let failing = PortfolioXRayViewModel(fetchXRay: { x }, fetchReplay: { throw NetworkError.connectionFailed }, replayEnabled: { true })
        await failing.load()
        XCTAssertEqual(failing.state, .loaded, "a replay failure hides only that card")
        XCTAssertNil(failing.replay)
    }

    func testViewModelStates() async throws {
        let empty = try JSONDecoder().decode(XRayResponse.self, from: Data("""
        {"as_of": "2026-10-11T09:00:00Z", "total_value_inr": 0.0, "unpriced": [], "allocation": [], "amcs": [], "plans": null,
         "top_holdings": [], "concentration": {"largest_ticker": null, "largest_pct": 0.0, "top5_pct": 0.0}, "facts": [], "commission_drag": null}
        """.utf8))
        let model = PortfolioXRayViewModel(fetchXRay: { empty }, fetchReplay: { throw NetworkError.connectionFailed }, replayEnabled: { false })
        await model.load()
        XCTAssertEqual(model.state, .empty)

        let offline = PortfolioXRayViewModel(
            fetchXRay: { throw NetworkError.fetchFailed(endpoint: "/x", status: -1, body: "") },
            fetchReplay: { throw NetworkError.connectionFailed }, replayEnabled: { false })
        await offline.load()
        XCTAssertEqual(offline.state, .offline)

        let failed = PortfolioXRayViewModel(
            fetchXRay: { throw NetworkError.fetchFailed(endpoint: "/x", status: 500, body: "") },
            fetchReplay: { throw NetworkError.connectionFailed }, replayEnabled: { false })
        await failed.load()
        if case .failed = failed.state {} else { XCTFail("expected failed") }
    }
}
