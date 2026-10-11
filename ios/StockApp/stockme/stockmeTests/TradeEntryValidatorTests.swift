import XCTest
@testable import stockme

@MainActor
final class TradeEntryValidatorTests: XCTestCase {
    private let now = Date()

    private func validate(hasStock: Bool = true, type: String = "BUY", shares: Double = 10,
                          price: Double = 100, date: Date? = nil, heldShares: Double? = nil) -> String? {
        TradeEntryValidator.validate(hasStock: hasStock, type: type, shares: shares, price: price,
                                     date: date ?? now, heldShares: heldShares, now: now)
    }

    func testFutureDateIsRejected() {
        let future = Calendar.current.date(byAdding: .day, value: 2, to: now)!
        XCTAssertEqual(validate(date: future), "Trade date can't be in the future.")
    }

    func testTodayPasses() {
        XCTAssertNil(validate(date: now))
    }

    func testPastDatePasses() {
        let past = DateComponents(calendar: .current, year: 2021, month: 6, day: 1).date!
        XCTAssertNil(validate(date: past))
    }

    func testSellAboveHoldingIsRejected() {
        XCTAssertEqual(validate(type: "SELL", shares: 10, heldShares: 5), "You hold only 5 shares.")
    }

    func testSellWithoutHoldingIsRejected() {
        XCTAssertEqual(validate(type: "SELL", shares: 5, heldShares: nil), "You don't hold this stock.")
    }

    func testSellEqualToHoldingPasses() {
        XCTAssertNil(validate(type: "SELL", shares: 5, heldShares: 5))
    }

    func testBuyWithoutHoldingPasses() {
        XCTAssertNil(validate(type: "BUY", heldShares: nil))
    }

    func testZeroSharesIsRejected() {
        XCTAssertEqual(validate(shares: 0), "Enter the number of shares.")
    }

    func testZeroPriceIsRejected() {
        XCTAssertEqual(validate(price: 0), "Enter the price per share.")
    }

    func testMissingStockIsRejectedFirst() {
        XCTAssertEqual(validate(hasStock: false, shares: 0), "Select a stock first.")
    }
}
