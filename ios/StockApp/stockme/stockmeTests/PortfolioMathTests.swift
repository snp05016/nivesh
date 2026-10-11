import XCTest
@testable import stockme

/// IOSCORE-24: the DAILY tile is shares x (price - prevClose), not price x pct.
@MainActor
final class PortfolioMathTests: XCTestCase {

    private func holding(price: Double, changePercent: Double, status: String = "live") -> PortfolioHolding {
        let stock = Stock(ticker: "INFY", companyName: "Infosys", exchange: "NSE",
                          currentPrice: price, changePercent: changePercent, signal: nil)
        return PortfolioHolding(stock: stock, shares: 10, buyPrice: 90, purchaseDate: nil,
                                notes: nil, targetPrice: nil, priceStatus: status)
    }

    func testDayPnLUsesPreviousClose() {
        XCTAssertEqual(holding(price: 105, changePercent: 5).dayPnL, 50, accuracy: 1e-9) // not 52.5
        XCTAssertEqual(holding(price: 95, changePercent: -5).dayPnL, -50, accuracy: 1e-9)
        XCTAssertEqual(holding(price: 100, changePercent: 0).dayPnL, 0, accuracy: 1e-9)
    }

    func testDayPnLIsZeroWithoutAQuote() {
        XCTAssertEqual(holding(price: 0, changePercent: 3, status: "unavailable").dayPnL, 0)
    }
}
