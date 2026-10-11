import XCTest
@testable import stockme

/// SIP projection is pure local math (no backend round-trip, ARCH-08).
final class SIPCalculatorTests: XCTestCase {

    func testMatchesClosedFormAnnuityDue() {
        let i = 0.01
        let n = 120.0
        let expected = 10_000 * ((pow(1 + i, n) - 1) / i) * (1 + i)
        let r = SIPCalculationResult.computeLocally(monthlyAmount: 10_000, annualReturnPct: 12, years: 10)
        XCTAssertEqual(r.investedAmount, 12_00_000, accuracy: 0.01)
        XCTAssertEqual(r.totalValue, expected, accuracy: 1)
        XCTAssertEqual(r.estimatedReturns, expected - 12_00_000, accuracy: 1)
    }

    func testZeroYearsReturnsZeroInvested() {
        let r = SIPCalculationResult.computeLocally(monthlyAmount: 10_000, annualReturnPct: 12, years: 0)
        XCTAssertEqual(r.investedAmount, 0, accuracy: 0.01)
        XCTAssertEqual(r.totalValue, 0, accuracy: 0.01)
        XCTAssertTrue(r.totalValue.isFinite)
    }
}
