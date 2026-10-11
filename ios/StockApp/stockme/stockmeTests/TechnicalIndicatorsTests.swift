import XCTest
@testable import stockme

/// IOSCORE-37: a flat series is neutral (50), not overbought, and both RSI charts share one helper.
@MainActor
final class TechnicalIndicatorsTests: XCTestCase {

    func testFlatSeriesIs50() {
        let rsi = TechnicalIndicators.rsi(closes: Array(repeating: 100, count: 20))
        XCTAssertEqual(rsi.count, 20 - 15)
        XCTAssertTrue(rsi.allSatisfy { $0 == 50 }, "\(rsi)")
    }

    func testMonotonicUpIs100() {
        let rsi = TechnicalIndicators.rsi(closes: (0..<20).map { 100 + Double($0) })
        XCTAssertFalse(rsi.isEmpty)
        XCTAssertTrue(rsi.allSatisfy { $0 == 100 }, "\(rsi)")
    }

    func testMonotonicDownIs0() {
        let rsi = TechnicalIndicators.rsi(closes: (0..<20).map { 100 - Double($0) })
        XCTAssertFalse(rsi.isEmpty)
        XCTAssertTrue(rsi.allSatisfy { $0 == 0 }, "\(rsi)")
    }

    func testTooShortIsEmpty() {
        XCTAssertTrue(TechnicalIndicators.rsi(closes: Array(repeating: 1, count: 15)).isEmpty)
    }

    /// Period 2, closes 10, 11, 10, 12: changes +1, -1, +2.
    /// Seed avgGain = avgLoss = 0.5; next step gain = (0.5 + 2) / 2 = 1.25, loss = 0.25.
    /// RSI = 100 - 100 / (1 + 5) = 83.333...
    func testKnownWilderValue() {
        let rsi = TechnicalIndicators.rsi(closes: [10, 11, 10, 12], period: 2)
        XCTAssertEqual(rsi.count, 1)
        XCTAssertEqual(rsi[0], 100 - 100 / 6.0, accuracy: 1e-6)
    }
}
