import XCTest
@testable import stockme

final class MutualFundQueryTests: XCTestCase {

    private func items(_ query: MutualFundQuery) -> [String: String] {
        Dictionary(uniqueKeysWithValues: query.queryItems.map { ($0.name, $0.value ?? "") })
    }

    func testDefaultItemsAreExactlyPlanOptionLimitOffset() {
        let query = MutualFundQuery()
        XCTAssertEqual(query.queryItems.map { $0.name }, ["plan", "option", "limit", "offset"])
        XCTAssertEqual(items(query), ["plan": "direct", "option": "growth", "limit": "50", "offset": "0"])
    }

    func testAMCWithAmpersandRoundTripsThroughURLComponents() throws {
        var query = MutualFundQuery()
        query.amc = "L&T Mutual Fund"
        query.search = "  large+cap  "
        let url = try XCTUnwrap(query.url(baseURL: "https://example.test"))
        XCTAssertFalse(url.absoluteString.contains("L&T"))
        let comps = try XCTUnwrap(URLComponents(url: url, resolvingAgainstBaseURL: false))
        let decoded = Dictionary(uniqueKeysWithValues: (comps.queryItems ?? []).map { ($0.name, $0.value ?? "") })
        XCTAssertEqual(decoded["amc_name"], "L&T Mutual Fund")
        XCTAssertEqual(decoded["search"], "large+cap")
        XCTAssertEqual(decoded["plan"], "direct")
    }

    func testWhitespaceOnlySearchIsOmitted() {
        var query = MutualFundQuery()
        query.search = "   \n"
        XCTAssertNil(items(query)["search"])
    }

    func testOptionalFiltersAppearOnlyWhenSet() {
        var query = MutualFundQuery()
        query.category = "Equity"
        query.subCategory = "Large Cap Fund"
        query.plan = .all
        query.option = .idcw
        query.offset = 100
        XCTAssertEqual(items(query)["category"], "Equity")
        XCTAssertEqual(items(query)["sub_category"], "Large Cap Fund")
        XCTAssertEqual(items(query)["plan"], "all")
        XCTAssertEqual(items(query)["option"], "idcw")
        XCTAssertEqual(items(query)["offset"], "100")
        XCTAssertNil(items(query)["amc_name"])
    }

    func testFilterLabels() {
        XCTAssertEqual(MutualFundPlanFilter.allCases.map { $0.label }, ["Direct", "Regular", "All plans"])
        XCTAssertEqual(MutualFundOptionFilter.allCases.map { $0.label }, ["Growth", "IDCW", "All options"])
    }

    func testCanLoadMore() {
        XCTAssertTrue(MutualFundQuery.canLoadMore(loaded: 50, total: 120))
        XCTAssertFalse(MutualFundQuery.canLoadMore(loaded: 120, total: 120))
        XCTAssertFalse(MutualFundQuery.canLoadMore(loaded: 50, total: nil))
    }

    func testTotalCountHeaderParsing() throws {
        let url = try XCTUnwrap(URL(string: "https://example.test/api/mutual-funds/"))
        let with = try XCTUnwrap(HTTPURLResponse(url: url, statusCode: 200, httpVersion: nil,
                                                 headerFields: ["X-Total-Count": "1234"]))
        XCTAssertEqual(MutualFundQuery.totalCount(from: with), 1234)
        let without = try XCTUnwrap(HTTPURLResponse(url: url, statusCode: 200, httpVersion: nil, headerFields: [:]))
        XCTAssertNil(MutualFundQuery.totalCount(from: without))
        let junk = try XCTUnwrap(HTTPURLResponse(url: url, statusCode: 200, httpVersion: nil,
                                                 headerFields: ["X-Total-Count": "many"]))
        XCTAssertNil(MutualFundQuery.totalCount(from: junk))
    }

    func testDateText() {
        XCTAssertEqual(MutualFundDateText.short("2026-10-09"), "9 Oct 2026")
        XCTAssertEqual(MutualFundDateText.short("not a date"), "not a date")
    }
}
