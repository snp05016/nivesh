import XCTest
@testable import stockme

final class ResultsDigestTests: XCTestCase {

    private func decode(_ json: String) throws -> ResultsDigest {
        try JSONDecoder().decode(ResultsDigest.self, from: Data(json.utf8))
    }

    func testFullPayloadDecodes() throws {
        let digest = try decode("""
        {"symbol":"INFY","period_end":"2026-09-30","period_label":"Quarter ended 30 Sep 2026",
         "filing_url":"https://nsearchives.nseindia.com/corporate/INFY.pdf","filing_title":"Results",
         "announced_at":"2026-10-16T12:00:00","numbers_status":"ok","revenue_inr":412000000000.0,
         "revenue_yoy_pct":8.24,"net_profit_inr":65000000000.0,"net_profit_yoy_pct":-3.1,"eps":15.7,
         "eps_yoy_pct":null,"numbers_source_text":"Figures from Yahoo Finance quarterly statements."}
        """)
        XCTAssertEqual(digest.symbol, "INFY")
        XCTAssertEqual(digest.periodLabel, "Quarter ended 30 Sep 2026")
        XCTAssertEqual(digest.revenueInr, 412_000_000_000)
        XCTAssertNil(digest.epsYoyPct)
        XCTAssertFalse(digest.isPending)
        XCTAssertFalse(digest.isUnavailable)
        XCTAssertNotNil(digest.filingURL)
    }

    func testPendingAndUnavailablePayloadsDecode() throws {
        let pending = try decode("""
        {"symbol":"TCS","period_end":"2026-09-30","period_label":"Quarter ended 30 Sep 2026","filing_url":null,
         "filing_title":null,"announced_at":null,"numbers_status":"pending","revenue_inr":null,"revenue_yoy_pct":null,
         "net_profit_inr":null,"net_profit_yoy_pct":null,"eps":null,"eps_yoy_pct":null,
         "numbers_source_text":"Figures are still being collected from our data source. See the company's filing."}
        """)
        XCTAssertTrue(pending.isPending)
        XCTAssertNil(pending.filingURL)

        let unavailable = try decode("""
        {"symbol":"TCS","period_end":"2026-09-30","period_label":"Quarter ended 30 Sep 2026","filing_url":"http://insecure.example/x",
         "numbers_status":"unavailable","numbers_source_text":"Figures aren't available from our data source. See the company's filing."}
        """)
        XCTAssertTrue(unavailable.isUnavailable)
        XCTAssertNil(unavailable.revenueInr)
        XCTAssertNil(unavailable.filingURL, "only https filing links are shown")
    }

    func testYoyText() {
        XCTAssertEqual(ResultsDigest.yoyText(8.24), "+8.2% YoY")
        XCTAssertTrue(ResultsDigest.yoyText(-3.1).contains("\u{2212}"))
        XCTAssertEqual(ResultsDigest.yoyText(-3.1), "\u{2212}3.1% YoY")
        XCTAssertEqual(ResultsDigest.yoyText(nil), "—")
        XCTAssertEqual(ResultsDigest.yoyText(0), "+0.0% YoY")
    }

    func testEpsText() {
        XCTAssertEqual(ResultsDigest.epsText(5.5), "₹5.50")
        XCTAssertEqual(ResultsDigest.epsText(nil), "—")
    }

    func testHideRule() {
        let noDigest = NetworkError.fetchFailed(endpoint: "x", status: 404, body: #"{"detail":{"code":"NO_DIGEST"}}"#)
        let disabled = NetworkError.fetchFailed(
            endpoint: "x", status: 404, body: #"{"detail":{"code":"FEATURE_DISABLED","feature":"data_results_digest"}}"#)
        let server = NetworkError.fetchFailed(endpoint: "x", status: 500, body: "NO_DIGEST")
        XCTAssertTrue(ResultsDigest.shouldHide(noDigest))
        XCTAssertTrue(ResultsDigest.shouldHide(disabled))
        XCTAssertFalse(ResultsDigest.shouldHide(server))
        XCTAssertFalse(ResultsDigest.shouldHide(NetworkError.invalidResponse))
    }
}
