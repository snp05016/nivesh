import XCTest
@testable import stockme

final class BenchmarkDecodingTests: XCTestCase {

    func testDecodesBackendKeys() throws {
        // Shape of GET /portfolio/benchmark (portfolio_service.compute_benchmark + router extras, MATH-V2).
        let json = """
        {
            "portfolio_cagr_pct": 12.3,
            "nifty_cagr_pct": 10.1,
            "alpha_pct": 2.2,
            "return_basis": "annualized_xirr",
            "period_days": 800,
            "earliest_holding_date": "2024-08-02",
            "current_portfolio_value": 250000.0,
            "unpriced_tickers": []
        }
        """.data(using: .utf8)!

        let data = try JSONDecoder().decode(BenchmarkData.self, from: json)

        XCTAssertEqual(data.portfolioReturn, 12.3)
        XCTAssertEqual(data.niftyReturn, 10.1)
        XCTAssertEqual(data.alpha, 2.2)
        XCTAssertEqual(data.periodDays, 800)
        XCTAssertEqual(data.unpricedTickers, [])
        XCTAssertTrue(data.isAnnualized)
    }

    func testNullNiftyLeavesPortfolioReturn() throws {
        // Nifty history present but PME undefined: nifty/alpha null, absolute sub-year return.
        let json = """
        {"portfolio_cagr_pct": -4.5, "nifty_cagr_pct": null, "alpha_pct": null,
         "return_basis": "absolute", "period_days": 90, "unpriced_tickers": ["XYZ"]}
        """.data(using: .utf8)!

        let data = try JSONDecoder().decode(BenchmarkData.self, from: json)

        XCTAssertEqual(data.portfolioReturn, -4.5)
        XCTAssertNil(data.niftyReturn)
        XCTAssertNil(data.alpha)
        XCTAssertFalse(data.isAnnualized)
        XCTAssertEqual(data.unpricedTickers, ["XYZ"])
    }
}
