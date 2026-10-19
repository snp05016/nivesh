import XCTest
@testable import stockme

final class MutualFundDecodingTests: XCTestCase {
    
    func testMutualFundLegacyDataDecoding() throws {
        // The backend `MutualFundResponse` normalizes the legacy `fund_name` and `amc` DB columns
        // into `scheme_name` and `amc_name` respectively.
        // This test ensures that the Swift `MutualFundDTO` correctly decodes this normalized JSON.
        let json = """
        {
            "id": 1,
            "scheme_name": "Axis Bluechip Fund",
            "amc_name": "Axis Mutual Fund",
            "category": "Equity",
            "nav": 45.67
        }
        """.data(using: .utf8)!
        
        let decoder = JSONDecoder()
        let fund = try decoder.decode(MutualFundDTO.self, from: json)
        
        XCTAssertEqual(fund.id, 1)
        XCTAssertEqual(fund.fundName, "Axis Bluechip Fund")
        XCTAssertEqual(fund.amc, "Axis Mutual Fund")
        XCTAssertEqual(fund.category, "Equity")
        XCTAssertEqual(fund.nav, 45.67)
    }

    func testMutualFundFullPayloadDecoding() throws {
        // Test with the full modern payload including all the new fields
        let json = """
        {
            "id": 2,
            "scheme_name": "SBI Small Cap Fund",
            "amc_name": "SBI Mutual Fund",
            "category": "Equity",
            "sub_category": "Small Cap",
            "nav": 120.50,
            "nav_date": "2023-10-01",
            "aum_cr": 25000.0,
            "expense_ratio": 0.75,
            "returns_1y": 15.5,
            "returns_3y": 20.1,
            "returns_5y": 18.2,
            "risk_level": "Very High",
            "fund_manager": "R Srinivasan",
            "is_direct_plan": true,
            "is_growth_plan": true
        }
        """.data(using: .utf8)!
        
        let decoder = JSONDecoder()
        let fund = try decoder.decode(MutualFundDTO.self, from: json)
        
        XCTAssertEqual(fund.id, 2)
        XCTAssertEqual(fund.fundName, "SBI Small Cap Fund")
        XCTAssertEqual(fund.amc, "SBI Mutual Fund")
        XCTAssertEqual(fund.subCategory, "Small Cap")
        XCTAssertEqual(fund.nav, 120.50)
        XCTAssertEqual(fund.aumCr, 25000.0)
        XCTAssertEqual(fund.expenseRatio, 0.75)
        XCTAssertEqual(fund.returns1y, 15.5)
        XCTAssertEqual(fund.isDirectPlan, true)
    }

    func testIsSampleDecodes() throws {
        // CMON-13: the backend flags its seeded catalog `is_sample` so the UI
        // can label it; absent on older payloads.
        let sample = try JSONDecoder().decode(MutualFundDTO.self, from: """
        {"id": 3, "scheme_name": "Sample Fund", "amc_name": "AMC", "category": "Equity", "is_sample": true}
        """.data(using: .utf8)!)
        XCTAssertEqual(sample.isSample, true)

        let legacy = try JSONDecoder().decode(MutualFundDTO.self, from: """
        {"id": 4, "scheme_name": "Old Fund", "amc_name": "AMC", "category": "Equity"}
        """.data(using: .utf8)!)
        XCTAssertNil(legacy.isSample)
    }

    func testNAVRangesWithinBackendLimit() {
        // Backend nav-history accepts days 1...365 (le=365); a range beyond that
        // would silently show a shorter window under a longer label.
        for range in MutualFundNAVRange.allCases {
            XCTAssertTrue((1...365).contains(range.approxDays), "\(range.rawValue) requests \(range.approxDays) days")
        }
    }

    func testAMFIFieldsDecode() throws {
        let fund = try JSONDecoder().decode(MutualFundDTO.self, from: """
        {"id": 5, "scheme_name": "Alpha Large Cap Fund - Direct Plan - Growth", "amc_name": "Alpha Mutual Fund",
         "category": "Equity", "sub_category": "Large Cap Fund", "nav": 123.4567, "nav_date": "2026-10-09",
         "scheme_type": "open", "nav_source": "amfi", "is_active": true,
         "isin_growth": "INF000A01011", "isin_reinvest": "INF000A01029", "history_start": "2026-10-01",
         "returns_1y": null, "is_direct_plan": true, "is_growth_plan": true}
        """.data(using: .utf8)!)
        XCTAssertEqual(fund.schemeType, "open")
        XCTAssertEqual(fund.navSource, "amfi")
        XCTAssertEqual(fund.isActive, true)
        XCTAssertEqual(fund.isinGrowth, "INF000A01011")
        XCTAssertEqual(fund.isinReinvest, "INF000A01029")
        XCTAssertEqual(fund.historyStart, "2026-10-01")
        XCTAssertNil(fund.returns1y)
        XCTAssertTrue(fund.isAMFISourced)
        XCTAssertEqual(fund.navPreciseDisplay, "₹123.4567")
    }

    func testLegacyPayloadLeavesAMFIFieldsNil() throws {
        let fund = try JSONDecoder().decode(MutualFundDTO.self, from: """
        {"id": 6, "scheme_name": "Old Fund", "amc_name": "AMC", "category": "Equity"}
        """.data(using: .utf8)!)
        XCTAssertNil(fund.schemeType)
        XCTAssertNil(fund.navSource)
        XCTAssertNil(fund.isinGrowth)
        XCTAssertNil(fund.historyStart)
        XCTAssertFalse(fund.isAMFISourced)
    }

    func testFiltersDecode() throws {
        let filters = try JSONDecoder().decode(MutualFundFilters.self, from: """
        {"categories": {"Equity": ["Large Cap Fund", "ELSS"], "Debt": []}, "amcs": ["Alpha Mutual Fund", "L&T Mutual Fund"]}
        """.data(using: .utf8)!)
        XCTAssertEqual(filters.sortedCategories, ["Debt", "Equity"])
        XCTAssertEqual(filters.categories["Equity"], ["Large Cap Fund", "ELSS"])
        XCTAssertEqual(filters.amcs.count, 2)
    }
}
