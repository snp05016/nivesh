import XCTest
@testable import stockme

/// Payment of Gratuity Act rules in GratuityCalculationResult.computeLocally:
/// 5-year eligibility (s.4(1)), part-year over 6 months rounded up for covered
/// employers (s.4(2)), 15/30 on completed years when not covered, ₹20 L cap.
final class GratuityCalculatorTests: XCTestCase {

    func testUnderFiveYearsNotEligible() {
        let r = GratuityCalculationResult.computeLocally(lastDrawnSalary: 50_000, yearsOfService: 3, months: 0)
        XCTAssertFalse(r.isEligible)
        XCTAssertEqual(r.payableGratuity, 0, accuracy: 0.01)
    }

    func testFiveYearsExact() {
        let r = GratuityCalculationResult.computeLocally(lastDrawnSalary: 50_000, yearsOfService: 5, months: 0)
        XCTAssertTrue(r.isEligible)
        XCTAssertEqual(r.payableGratuity, 1_44_230.77, accuracy: 0.01)
    }

    func testMoreThanSixMonthsRoundsUpToNextYear() {
        let r = GratuityCalculationResult.computeLocally(lastDrawnSalary: 50_000, yearsOfService: 5, months: 7)
        XCTAssertEqual(r.payableGratuity, 1_73_076.92, accuracy: 0.01)
    }

    func testExactlySixMonthsDoesNotRoundUp() {
        let r = GratuityCalculationResult.computeLocally(lastDrawnSalary: 50_000, yearsOfService: 5, months: 6)
        XCTAssertEqual(r.payableGratuity, 1_44_230.77, accuracy: 0.01)
    }

    func testNotCoveredUsesFifteenOverThirtyOnCompletedYears() {
        let ten = GratuityCalculationResult.computeLocally(lastDrawnSalary: 50_000, yearsOfService: 10, months: 0, coveredByAct: false)
        XCTAssertEqual(ten.payableGratuity, 2_50_000, accuracy: 0.01)
        // Part-year is not rounded up when not covered by the Act.
        let partial = GratuityCalculationResult.computeLocally(lastDrawnSalary: 50_000, yearsOfService: 5, months: 9, coveredByAct: false)
        XCTAssertEqual(partial.payableGratuity, 1_25_000, accuracy: 0.01)
    }

    func testCappedAtStatutoryCeiling() {
        let r = GratuityCalculationResult.computeLocally(lastDrawnSalary: 5_00_000, yearsOfService: 30, months: 0)
        XCTAssertTrue(r.isCapped)
        XCTAssertEqual(r.payableGratuity, 20_00_000, accuracy: 0.01)
    }
}
