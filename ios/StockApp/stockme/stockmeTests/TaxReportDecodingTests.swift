import XCTest
@testable import stockme

@MainActor
final class TaxReportDecodingTests: XCTestCase {

    private let reportJSON = """
    {"fy": "2025-26", "rules_version": "in-cg-2026.1", "as_of": "2026-10-12",
     "summary": {"stcg": {"pre_2024_07_23": 0.0, "post_2024_07_23": 1965.0},
                 "ltcg": {"pre_2024_07_23": 0.0, "post_2024_07_23": 20000.0},
                 "ltcg_exemption_limit_inr": 125000.0, "ltcg_above_exemption_inr": 0.0,
                 "rows": 2, "not_computed": 1, "needs_review": 1},
     "rows": [
       {"term": "STCG", "section": "111A", "rate_period": "post_2024_07_23", "symbol": "INFY", "name": "Infosys Ltd",
        "quantity": 10.0, "acquired_on": "2025-05-10", "sold_on": "2025-12-01", "sale_value_inr": 12000.0,
        "cost_of_acquisition_inr": 10020.0, "fmv_per_unit": null, "fmv_total_inr": null, "cost_used_inr": 10020.0,
        "transfer_expenses_inr": 15.0, "gain_inr": 1965.0, "needs_review": false, "review_reasons": []},
       {"term": "LTCG", "section": "112A", "rate_period": "post_2024_07_23", "symbol": "ITC", "name": "ITC Ltd",
        "quantity": 100.0, "acquired_on": "2017-06-01", "sold_on": "2025-09-01", "sale_value_inr": 100000.0,
        "cost_of_acquisition_inr": 50000.0, "fmv_per_unit": 800.0, "fmv_total_inr": 80000.0, "cost_used_inr": 80000.0,
        "transfer_expenses_inr": 0.0, "gain_inr": 20000.0, "needs_review": true, "review_reasons": ["fmv_nse_high"]}
     ],
     "not_computed": [{"symbol": "HDFCBANK", "sold_on": "2025-12-01", "quantity": 10.0, "reason": "acquisition_date_uncertain"}],
     "scope_note": "Listed shares only. Mutual funds are not covered yet.",
     "disclaimer": "Informational working from your Nivesh transactions. Not tax advice."}
    """

    func testDecodesTheContractWithNullFMVFields() throws {
        let r = try JSONDecoder().decode(CapitalGainsReport.self, from: Data(reportJSON.utf8))

        XCTAssertEqual(r.fy, "2025-26")
        XCTAssertEqual(r.summary.stcg.post, 1965.0)
        XCTAssertEqual(r.summary.ltcgExemptionLimitInr, 125000.0)
        XCTAssertNil(r.rows[0].fmvPerUnit)
        XCTAssertNil(r.rows[0].fmvTotalInr)
        XCTAssertEqual(r.rows[1].fmvPerUnit, 800.0)
        XCTAssertTrue(r.rows[1].isLongTerm)
        XCTAssertEqual(r.rows[1].reviewReasons, ["fmv_nse_high"])
        XCTAssertEqual(r.notComputed.first?.reason, "acquisition_date_uncertain")
        XCTAssertEqual(r.scopeNote, "Listed shares only. Mutual funds are not covered yet.")
    }

    func testDecodesEmptyRows() throws {
        let json = """
        {"fy": "2024-25", "rules_version": "in-cg-2026.1", "as_of": "2026-10-12",
         "summary": {"stcg": {"pre_2024_07_23": 0.0, "post_2024_07_23": 0.0}, "ltcg": {"pre_2024_07_23": 0.0, "post_2024_07_23": 0.0},
                     "ltcg_exemption_limit_inr": 125000.0, "ltcg_above_exemption_inr": 0.0, "rows": 0, "not_computed": 0, "needs_review": 0},
         "rows": [], "not_computed": [], "scope_note": "x", "disclaimer": "y"}
        """
        let r = try JSONDecoder().decode(CapitalGainsReport.self, from: Data(json.utf8))
        XCTAssertTrue(r.rows.isEmpty)
        XCTAssertTrue(r.notComputed.isEmpty)
        XCTAssertEqual(TaxCopy.empty(fy: r.fy), "No sales recorded in FY 2024-25.")
    }

    func testEveryReasonCodeHasText() {
        let codes = ["acquisition_date_uncertain", "etf_category_unverified", "fmv_unavailable", "fmv_nse_high",
                     "corporate_action_review", "possible_intraday", "user_entered_date", "stt_on_acquisition_unverified"]
        for code in codes {
            XCTAssertNotNil(TaxReason.all[code], code)
            XCTAssertNotEqual(TaxReason.userText(code), "Needs review", code)
        }
        XCTAssertEqual(TaxReason.userText("acquisition_date_uncertain"), "Purchase date unknown (edited holding or no date entered)")
        XCTAssertEqual(TaxReason.userText("possible_intraday"), "Bought and sold the same day: may be business income")
        XCTAssertEqual(TaxReason.userText("something_new"), "Needs review")
    }

    func testSummaryLabels() {
        XCTAssertEqual(TaxCopy.shortTermLabel(rate: 20), "Short-term gains (20%)")
        XCTAssertEqual(TaxCopy.longTermLabel(rate: "12.5", limit: 125000), "Long-term gains (12.5% above Rs 1.25 lakh)")
        XCTAssertEqual(TaxCopy.signedRupees(-1965), "-Rs 1,965")
        XCTAssertEqual(TaxCopy.signedRupees(20000), "Rs 20,000")
    }

    private func istDate(_ y: Int, _ m: Int, _ d: Int) -> Date {
        var c = Calendar(identifier: .gregorian)
        c.timeZone = TimeZone(identifier: "Asia/Kolkata")!
        return c.date(from: DateComponents(year: y, month: m, day: d, hour: 12))!
    }

    func testDefaultFinancialYear() {
        XCTAssertEqual(TaxFY.defaultFY(istDate(2026, 7, 15)), "2025-26", "1 Apr to 31 Jul shows the previous FY")
        XCTAssertEqual(TaxFY.defaultFY(istDate(2026, 9, 15)), "2026-27")
        XCTAssertEqual(TaxFY.defaultFY(istDate(2026, 4, 1)), "2025-26")
        XCTAssertEqual(TaxFY.defaultFY(istDate(2026, 7, 31)), "2025-26")
        XCTAssertEqual(TaxFY.defaultFY(istDate(2026, 8, 1)), "2026-27")
        XCTAssertEqual(TaxFY.defaultFY(istDate(2027, 2, 10)), "2026-27", "Jan to Mar belongs to the FY that began the previous April")
    }

    func testFinancialYearOptionsGoBackTo2018() {
        let options = TaxFY.options(istDate(2026, 9, 15))
        XCTAssertEqual(options.first, "2026-27")
        XCTAssertEqual(options.last, "2018-19")
        XCTAssertEqual(options.count, 9)
        XCTAssertEqual(TaxFY.label(2099), "2099-00")
    }

    func testViewModelStatesAndCSV() async throws {
        let report = try JSONDecoder().decode(CapitalGainsReport.self, from: Data(reportJSON.utf8))
        let temp = FileManager.default.temporaryDirectory.appendingPathComponent("tax-vm-test-\(UUID().uuidString).csv")
        try Data("fy\n".utf8).write(to: temp)
        let model = TaxReportViewModel(now: istDate(2026, 9, 15), fetch: { _ in report }, download: { _ in temp })

        await model.load()
        XCTAssertEqual(model.state, .loaded)

        await model.prepareCSV()
        XCTAssertEqual(model.csvURL, temp)
        XCTAssertTrue(FileManager.default.fileExists(atPath: temp.path))

        model.discardCSV()
        XCTAssertNil(model.csvURL)
        XCTAssertFalse(FileManager.default.fileExists(atPath: temp.path), "the temporary CSV is deleted")
    }

    func testViewModelEmptyAndOffline() async throws {
        let empty = try JSONDecoder().decode(CapitalGainsReport.self, from: Data("""
        {"fy": "2025-26", "rules_version": "in-cg-2026.1", "as_of": "2026-10-12",
         "summary": {"stcg": {"pre_2024_07_23": 0.0, "post_2024_07_23": 0.0}, "ltcg": {"pre_2024_07_23": 0.0, "post_2024_07_23": 0.0},
                     "ltcg_exemption_limit_inr": 125000.0, "ltcg_above_exemption_inr": 0.0, "rows": 0, "not_computed": 0, "needs_review": 0},
         "rows": [], "not_computed": [], "scope_note": "x", "disclaimer": "y"}
        """.utf8))
        let model = TaxReportViewModel(fetch: { _ in empty }, download: { _ in throw NetworkError.connectionFailed })
        await model.load()
        XCTAssertEqual(model.state, .empty)

        let offline = TaxReportViewModel(fetch: { _ in throw NetworkError.fetchFailed(endpoint: "/x", status: -1, body: "") },
                                         download: { _ in throw NetworkError.connectionFailed })
        await offline.load()
        XCTAssertEqual(offline.state, .offline)
    }
}
