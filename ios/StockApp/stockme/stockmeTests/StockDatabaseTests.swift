import XCTest
@testable import stockme

/// ARCH-10: the stock list is decoded from the bundled nse_bse_symbols.json
/// (a byte copy of backend/data/nse_bse_symbols.json), not a Swift literal.
@MainActor
final class StockDatabaseTests: XCTestCase {

    func testBundledUniverseLoads() {
        XCTAssertGreaterThan(StockDatabase.all.count, 3000)
    }

    func testSearchFindsTickerOnlyInSharedJSON() {
        let hit = StockDatabase.search("ALKYL").first { $0.ticker == "ALKYLAMINE" }
        XCTAssertNotNil(hit)
        XCTAssertEqual(hit?.sector, "Chemicals")
        XCTAssertEqual(hit?.exchange, "NSE")
    }
}
