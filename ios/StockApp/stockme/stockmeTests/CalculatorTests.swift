import XCTest
@testable import stockme

/// Fixed vectors for the local money math. Expected values were computed
/// independently from the textbook formulas (and, for SIP, match
/// backend/services/mutual_fund_calculators.py:calculate_sip_returns).
final class CalculatorTests: XCTestCase {

    // MARK: - EMI (reducing balance)

    func testEMIStandardVector() {
        let r = EMICalculationResult.computeLocally(principal: 10_00_000, annualRatePct: 9.5, tenureMonths: 60)
        XCTAssertEqual(r.monthlyEMI, 21_001.86, accuracy: 0.01)
        XCTAssertEqual(r.totalPayment, 12_60_111.68, accuracy: 0.01)
        XCTAssertEqual(r.totalInterest, 2_60_111.68, accuracy: 0.01)
    }

    func testEMIZeroRate() {
        let r = EMICalculationResult.computeLocally(principal: 1_20_000, annualRatePct: 0, tenureMonths: 12)
        XCTAssertEqual(r.monthlyEMI, 10_000, accuracy: 0.01)
        XCTAssertEqual(r.totalInterest, 0, accuracy: 0.01)
    }

    // MARK: - Gratuity (15/26 rule, 5-year eligibility, statutory cap)

    func testGratuityIneligibleUnder5() {
        let r = GratuityCalculationResult.computeLocally(lastDrawnSalary: 50_000, yearsOfService: 3)
        XCTAssertFalse(r.isEligible)
        XCTAssertEqual(r.payableGratuity, 0, accuracy: 0.01)
    }

    func testGratuity5And10Years() {
        let five = GratuityCalculationResult.computeLocally(lastDrawnSalary: 50_000, yearsOfService: 5)
        XCTAssertTrue(five.isEligible)
        XCTAssertEqual(five.payableGratuity, 1_44_230.77, accuracy: 0.01)

        let ten = GratuityCalculationResult.computeLocally(lastDrawnSalary: 50_000, yearsOfService: 10)
        XCTAssertTrue(ten.isEligible)
        XCTAssertFalse(ten.isCapped)
        XCTAssertEqual(ten.payableGratuity, 2_88_461.54, accuracy: 0.01)
    }

    func testGratuityCap() {
        let r = GratuityCalculationResult.computeLocally(lastDrawnSalary: 10_00_000, yearsOfService: 45)
        XCTAssertTrue(r.isCapped)
        XCTAssertEqual(r.payableGratuity, GratuityCalculationResult.statutoryCeiling, accuracy: 0.01)
        XCTAssertEqual(r.payableGratuity, 20_00_000, accuracy: 0.01)
        XCTAssertEqual(r.uncappedGratuity, 2_59_61_538.46, accuracy: 0.01)
    }

    // MARK: - SIP (annuity-due)

    func testSIPVector() {
        let r = SIPCalculationResult.computeLocally(monthlyAmount: 5_000, annualReturnPct: 12, years: 10)
        XCTAssertEqual(r.investedAmount, 6_00_000, accuracy: 0.01)
        XCTAssertEqual(r.totalValue, 11_61_695.38, accuracy: 0.01)
        XCTAssertEqual(r.estimatedReturns, 5_61_695.38, accuracy: 0.01)
    }
}
