import XCTest
@testable import stockme

/// A failed price lookup must never render as a ₹0 value / -100% loss.
/// @MainActor: app types are MainActor-isolated by default (SWIFT_DEFAULT_ACTOR_ISOLATION).
@MainActor
final class PortfolioHoldingPriceStatusTests: XCTestCase {

    private func holding(currentPrice: Double, priceStatus: String) -> PortfolioHolding {
        let stock = Stock(ticker: "INFY", companyName: "Infosys", exchange: "NSE",
                          currentPrice: currentPrice, changePercent: 0, signal: nil)
        return PortfolioHolding(stock: stock, shares: 10, buyPrice: 1500, purchaseDate: nil,
                                notes: nil, targetPrice: nil, priceStatus: priceStatus)
    }

    func testUnavailablePriceIsValuedAtCostNotZero() {
        let h = holding(currentPrice: 0, priceStatus: "unavailable")
        XCTAssertFalse(h.priceAvailable)
        XCTAssertEqual(h.currentValue, h.investedValue)
        XCTAssertEqual(h.pnl, 0)
        XCTAssertEqual(h.pnlPercent, 0) // not -100
    }

    func testLiveHoldingKeepsMarketMath() {
        let h = holding(currentPrice: 1650, priceStatus: "live")
        XCTAssertTrue(h.priceAvailable)
        XCTAssertEqual(h.currentValue, 16500, accuracy: 0.001)
        XCTAssertEqual(h.pnl, 1500, accuracy: 0.001)
        XCTAssertEqual(h.pnlPercent, 10, accuracy: 0.001)
    }

    func testStalePriceStillCountsAsAvailable() {
        XCTAssertTrue(holding(currentPrice: 1600, priceStatus: "stale").priceAvailable)
    }

    func testWatchlistItemDecodesPriceStatus() throws {
        let json = """
        {"ticker": "TCS", "company_name": "Tata Consultancy Services", "exchange": "NSE",
         "current_price": 0.0, "price_status": "unavailable", "day_change_pct": 0.0}
        """.data(using: .utf8)!
        let item = try JSONDecoder().decode(WatchlistItem.self, from: json)
        XCTAssertEqual(item.priceStatus, "unavailable")
    }
}
