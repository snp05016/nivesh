import XCTest
@testable import stockme

final class QuickInfoHoldingsDecodingTests: XCTestCase {

    func testInstitutionalTotalWithoutFiiDiiSplit() throws {
        // GET /quick-info after CMKT-08: Yahoo's institutional total, no invented FII/DII split.
        let json = """
        {"ticker": "RELIANCE", "promoter_holding_pct": 50.0, "institutional_holding_pct": 44.0,
         "fii_holding_pct": null, "dii_holding_pct": null, "debt_to_equity": 0.37}
        """.data(using: .utf8)!

        let info = try JSONDecoder().decode(QuickInfo.self, from: json)

        XCTAssertEqual(info.institutionalHoldingPct, 44.0)
        XCTAssertEqual(info.institutionalTotalPct, 44.0)
        XCTAssertFalse(info.hasFiiDiiSplit)
        XCTAssertEqual(info.debtToEquity, 0.37)
    }

    func testOlderPayloadFallsBackToFiiPlusDii() throws {
        let json = """
        {"ticker": "TCS", "fii_holding_pct": 12.5, "dii_holding_pct": 7.5}
        """.data(using: .utf8)!

        let info = try JSONDecoder().decode(QuickInfo.self, from: json)

        XCTAssertNil(info.institutionalHoldingPct)
        XCTAssertEqual(info.institutionalTotalPct, 20.0)
        XCTAssertTrue(info.hasFiiDiiSplit)
    }
}
