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
}
