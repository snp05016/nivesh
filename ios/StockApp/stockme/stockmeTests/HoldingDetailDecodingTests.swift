import XCTest
@testable import stockme

/// C11 / I30: payloads shaped like backend services/money_holding.py and
/// money_returns.portfolio_benchmark decode, and the card copy matches spec_money 3.2-3.3.
@MainActor
final class HoldingDetailDecodingTests: XCTestCase {

    private func decode<T: Decodable>(_ type: T.Type, _ json: String) throws -> T {
        try JSONDecoder().decode(type, from: Data(json.utf8))
    }

    private func detail(returns: String, assetClass: String = "EQ", reportAvailable: Bool = true,
                        priceStatus: String = "live") -> String {
        """
        {"ticker":"INFY","name":"Infosys Ltd","asset_class":"\(assetClass)",
         "position":{"quantity":12.0,"avg_cost":1450.25,"invested_inr":17403.0,"price":1520.1,"price_status":"\(priceStatus)","price_as_of":"2026-10-09T10:15:00Z","value_inr":18241.2,"pnl_inr":838.2,"pnl_pct":4.82},
         "returns":\(returns),
         "transactions":[{"id":41,"type":"BUY","quantity":10.0,"price":1400.0,"fees":20.0,"date":"2024-02-01","imported":false,"notes":null}],
         "dividends":{"total_inr":340.0,"count":2},"notes":"","target_price":null,
         "journal":[{"id":5,"action":"BUY","created_at":"2024-01-30","reason_excerpt":"Q3 margins..."}],
         "stock_report_available":\(reportAvailable)}
        """
    }

    func testSpecExampleDecodes() throws {
        let d = try decode(HoldingDetailResponse.self, detail(returns: """
        {"basis":"annualized_xirr","value_pct":11.3,"nifty_same_flows_pct":9.1,"nifty_available":true,"since":"2024-02-01","period_days":983,"approximate_start":true,"start_reason":"user_entered_date","unavailable_reason":null,"benchmark_label":"Nifty 50 price index (excludes dividends)"}
        """))
        XCTAssertEqual(d.ticker, "INFY")
        XCTAssertEqual(d.name, "Infosys Ltd")
        XCTAssertTrue(d.isEquity)
        XCTAssertEqual(d.position.quantity, 12)
        XCTAssertEqual(d.position.avgCost, 1450.25, accuracy: 0.001)
        XCTAssertEqual(d.position.priceStatus, "live")
        XCTAssertEqual(d.position.pnlPct ?? 0, 4.82, accuracy: 0.001)
        XCTAssertEqual(d.returns.periodDays, 983)
        XCTAssertEqual(d.transactions.first?.id, 41)
        XCTAssertEqual(d.transactions.first?.fees, 20)
        XCTAssertFalse(d.transactions.first?.imported ?? true)
        XCTAssertNil(d.transactions.first?.notes)
        XCTAssertEqual(d.dividends?.count, 2)
        XCTAssertEqual(d.dividends?.totalInr, 340)
        XCTAssertNil(d.targetPrice)
        XCTAssertEqual(d.journal.first?.reasonExcerpt, "Q3 margins...")
        XCTAssertTrue(d.stockReportAvailable)

        let copy = try XCTUnwrap(MoneyReturnCopy.holding(d.returns))
        XCTAssertEqual(copy.headline, "Your return (XIRR): 11.3%")
        XCTAssertEqual(copy.nifty, "Same rupees in the Nifty 50: 9.1% a year")
        XCTAssertEqual(copy.notes, ["Start date is the purchase date you entered.",
                                    "Nifty 50 price index (excludes dividends)"])
        XCTAssertEqual(MoneyReturnCopy.holding(d.returns, masked: true)?.headline, "Your return (XIRR): ••••")
    }

    func testNullReturnFieldsDecodeAsUnavailable() throws {
        let d = try decode(HoldingDetailResponse.self, detail(returns: """
        {"basis":"unavailable","value_pct":null,"nifty_same_flows_pct":null,"nifty_available":false,"since":null,"period_days":null,"approximate_start":false,"start_reason":null,"unavailable_reason":"start_date_unknown","benchmark_label":"Nifty 50 price index (excludes dividends)"}
        """))
        XCTAssertNil(d.returns.valuePct)
        XCTAssertNil(d.returns.since)
        XCTAssertNil(d.returns.startReason)
        XCTAssertEqual(MoneyReturnCopy.holding(d.returns),
                       ReturnCopy(headline: "Return unavailable: add this holding's purchase date to see it."))

        // No reason and no figure: nothing to say, the card is hidden.
        let silent = try decode(HoldingReturns.self, """
        {"basis":"unavailable","value_pct":null,"nifty_same_flows_pct":null,"nifty_available":false,"since":"2026-01-02","period_days":null,"approximate_start":false,"start_reason":null,"unavailable_reason":null,"benchmark_label":"x"}
        """)
        XCTAssertNil(MoneyReturnCopy.holding(silent))
    }

    func testSinceEditAbsoluteReturn() throws {
        let r = try decode(HoldingReturns.self, """
        {"basis":"absolute","value_pct":4.1,"nifty_same_flows_pct":2.0,"nifty_available":true,"since":"2026-06-03","period_days":128,"approximate_start":true,"start_reason":"since_edit","unavailable_reason":null,"benchmark_label":"Nifty 50 price index (excludes dividends)"}
        """)
        let copy = try XCTUnwrap(MoneyReturnCopy.holding(r))
        XCTAssertEqual(copy.headline, "Return since you edited this holding on 3 Jun 2026: +4.1%")
        XCTAssertEqual(copy.nifty, "Nifty 50, same cash flows: +2.0%")
        XCTAssertEqual(copy.notes, ["Not annualised: under 12 months.", "Nifty 50 price index (excludes dividends)"])
    }

    func testAbsoluteReturnWithoutNifty() throws {
        let r = try decode(HoldingReturns.self, """
        {"basis":"absolute","value_pct":6.1,"nifty_same_flows_pct":null,"nifty_available":false,"since":"2026-03-01","period_days":200,"approximate_start":false,"start_reason":null,"unavailable_reason":null,"benchmark_label":"Nifty 50 price index (excludes dividends)"}
        """)
        XCTAssertEqual(MoneyReturnCopy.holding(r),
                       ReturnCopy(headline: "Return since 1 Mar 2026: +6.1% (under 12 months, not annualised)"))
    }

    func testMutualFundHoldingHasNoStockReport() throws {
        let d = try decode(HoldingDetailResponse.self, detail(returns: """
        {"basis":"unavailable","value_pct":null,"nifty_same_flows_pct":null,"nifty_available":false,"since":null,"period_days":null,"approximate_start":false,"start_reason":null,"unavailable_reason":"imported_without_history","benchmark_label":"Nifty 50 price index (excludes dividends)"}
        """, assetClass: "MF", reportAvailable: false, priceStatus: "nav"))
        XCTAssertEqual(d.assetClass, "MF")
        XCTAssertFalse(d.isEquity)
        XCTAssertFalse(d.stockReportAvailable)
        XCTAssertEqual(d.position.priceStatus, "nav")
        XCTAssertEqual(MoneyReturnCopy.holding(d.returns)?.headline,
                       "Return unavailable: imported as a balance without purchase history.")
    }

    func testBenchmarkBodyWithExclusionsAndCoverage() throws {
        let b = try decode(PortfolioReturnDTO.self, """
        {"portfolio_cagr_pct":14.2,"nifty_cagr_pct":11.8,"alpha_pct":2.4,"return_basis":"annualized_xirr","period_days":990,
         "portfolio_cagr":14.2,"benchmark_cagr":11.8,"alpha":2.4,"tracking_error":null,"information_ratio":null,
         "earliest_holding_date":"2024-02-01","current_portfolio_value":250000.0,"unpriced_tickers":["TCS"],
         "excluded_tickers":[{"ticker":"INFY","reason":"start_date_unknown"},{"ticker":"TCS","reason":"price_unavailable"}],
         "benchmark_label":"Nifty 50 price index (excludes dividends)","approximate_start":true,"coverage_pct":82.0,
         "funds_excluded":true,"unavailable_reason":null,"nifty_available":true}
        """)
        XCTAssertEqual(b.excludedTickers, [.init(ticker: "INFY", reason: "start_date_unknown"),
                                           .init(ticker: "TCS", reason: "price_unavailable")])
        XCTAssertEqual(b.coveragePct, 82)
        XCTAssertEqual(b.unpricedTickers, ["TCS"])
        XCTAssertNil(b.unavailableReason)

        let copy = MoneyReturnCopy.portfolio(b)
        XCTAssertEqual(copy.headline, "Your yearly return (XIRR): 14.2%")
        XCTAssertEqual(copy.nifty, "Same rupees in the Nifty 50: 11.8% a year")
        XCTAssertEqual(copy.notes, [
            "Nifty 50 price index, excludes dividends. Since 1 Feb 2024.",
            "Covers holdings worth 82% of your stocks.",
            "Not included: INFY (purchase date unknown), TCS (no current price)",
            "Some start dates are approximate.",
            "Mutual funds aren't included yet.",
        ])
    }

    func testBenchmarkUnavailableAndNiftyDown() throws {
        let unavailable = try decode(PortfolioReturnDTO.self, """
        {"portfolio_cagr_pct":null,"nifty_cagr_pct":null,"return_basis":"unavailable","period_days":null,
         "earliest_holding_date":null,"unpriced_tickers":[],"excluded_tickers":[{"ticker":"INFY","reason":"start_date_unknown"}],
         "benchmark_label":"Nifty 50 price index (excludes dividends)","approximate_start":false,"coverage_pct":40.0,
         "funds_excluded":false,"unavailable_reason":"insufficient_history","nifty_available":false}
        """)
        XCTAssertEqual(unavailable.unavailableReason, "insufficient_history")
        let copy = MoneyReturnCopy.portfolio(unavailable)
        XCTAssertEqual(copy.headline, "Add purchase dates to your holdings to see your yearly return.")
        XCTAssertNil(copy.nifty)
        XCTAssertEqual(copy.notes, ["Not included: INFY (purchase date unknown)"])

        // Under a year, Nifty fetch failed (200, nifty_available false): no Nifty line.
        let short = try decode(PortfolioReturnDTO.self, """
        {"portfolio_cagr_pct":6.1,"nifty_cagr_pct":null,"return_basis":"absolute","period_days":200,
         "earliest_holding_date":"2026-03-01","coverage_pct":100.0,"nifty_available":false}
        """)
        let shortCopy = MoneyReturnCopy.portfolio(short)
        XCTAssertEqual(shortCopy.headline, "Your return since 1 Mar 2026: +6.1%")
        XCTAssertNil(shortCopy.nifty)
        XCTAssertEqual(shortCopy.notes, ["Not annualised: under 12 months."])

        // An older server sends only the MATH-04 keys.
        let legacy = try decode(PortfolioReturnDTO.self, """
        {"portfolio_cagr_pct":-3.25,"nifty_cagr_pct":1.0,"return_basis":"absolute","period_days":90}
        """)
        XCTAssertEqual(MoneyReturnCopy.portfolio(legacy).headline, "Your return: -3.3%")
        XCTAssertEqual(MoneyReturnCopy.portfolio(legacy).nifty, "Nifty 50, same cash flows: +1.0%")
    }

    func testErrorStates() {
        XCTAssertEqual(HoldingDetailViewModel.state(for: NetworkError.fetchFailed(
            endpoint: "/api/v1/me/holdings/INFY", status: 404, body: #"{"detail":{"code":"NOT_HELD"}}"#)), .notHeld)
        XCTAssertEqual(HoldingDetailViewModel.state(for: NetworkError.fetchFailed(
            endpoint: "/api/v1/me/holdings/INFY", status: -1, body: "Network error")), .offline)
        let flagOff = NetworkError.fetchFailed(endpoint: "/api/v1/me/holdings/INFY", status: 404,
                                               body: #"{"detail":{"code":"FEATURE_DISABLED","message":"off"}}"#)
        XCTAssertTrue(HoldingDetailViewModel.isFeatureDisabled(flagOff))
        if case .failed = HoldingDetailViewModel.state(for: flagOff) {} else { XCTFail("flag off is not 'not held'") }
        if case .failed = HoldingDetailViewModel.state(for: NetworkError.unauthorized) {} else { XCTFail("401 should fail") }
    }

    func testLoadKeepsLastGoodDetailWhenOffline() async throws {
        let body = detail(returns: """
        {"basis":"unavailable","value_pct":null,"nifty_same_flows_pct":null,"nifty_available":false,"since":null,"period_days":null,"approximate_start":false,"start_reason":null,"unavailable_reason":"price_unavailable","benchmark_label":"x"}
        """)
        var offline = false
        let model = HoldingDetailViewModel(ticker: "INFY", fetch: { _ in
            if offline { throw NetworkError.fetchFailed(endpoint: "/x", status: -1, body: "") }
            return try JSONDecoder().decode(HoldingDetailResponse.self, from: Data(body.utf8))
        })
        await model.load()
        XCTAssertEqual(model.state, .loaded)
        offline = true
        await model.load()
        XCTAssertEqual(model.state, .offline)
        XCTAssertEqual(model.detail?.ticker, "INFY")
    }
}
