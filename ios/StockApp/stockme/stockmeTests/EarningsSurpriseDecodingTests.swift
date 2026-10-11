import XCTest
@testable import stockme

final class EarningsSurpriseDecodingTests: XCTestCase {

    func testCalendarDayReadsBackendResultDate() throws {
        // Shape of GET /api/v1/earnings/calendar items (market_service._earnings_result_from_row):
        // the date arrives as result_date, and eps is trailing EPS, not an estimate (CMKT-10).
        let json = """
        {
            "date": "2026-10-10",
            "count": 1,
            "results": [{
                "ticker": "TCS",
                "company_name": "Tata",
                "result_date": "2026-10-10",
                "quarter": "Upcoming",
                "eps": 120.5,
                "sparkline": [],
                "price_change_7d_pct": null
            }]
        }
        """.data(using: .utf8)!

        let response = try JSONDecoder().decode(EarningsCalendarResponse.self, from: json)

        XCTAssertEqual(response.count, 1)
        let day = try XCTUnwrap(response.results.first)
        XCTAssertEqual(day.ticker, "TCS")
        XCTAssertEqual(day.announcement_date, "2026-10-10")
        XCTAssertEqual(day.id, "TCS2026-10-10")
        XCTAssertNil(day.price_change_7d_pct)
    }
}
