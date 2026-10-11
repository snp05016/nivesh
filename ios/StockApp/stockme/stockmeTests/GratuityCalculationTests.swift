import XCTest
@testable import stockme

/// Code on Social Security, 2020 gratuity eligibility: 5 years for regular
/// employees, 1 year (pro-rata) for fixed-term employees, ₹20 L ceiling.
final class GratuityCalculationTests: XCTestCase {

    func testRegularEmployeeThreeYearsIneligible() {
        let r = GratuityCalculationResult.computeLocally(lastDrawnSalary: 50_000, yearsOfService: 3)
        XCTAssertFalse(r.isEligible)
        XCTAssertEqual(r.payableGratuity, 0, accuracy: 0.01)
    }

    func testFixedTermThreeYearsPaysProRata() {
        let r = GratuityCalculationResult.computeLocally(lastDrawnSalary: 50_000, yearsOfService: 3, isFixedTerm: true)
        XCTAssertTrue(r.isEligible)
        XCTAssertEqual(r.payableGratuity, 86_538.46, accuracy: 0.01)
    }

    func testFixedTermUnderOneYearIneligible() {
        let none = GratuityCalculationResult.computeLocally(lastDrawnSalary: 50_000, yearsOfService: 0, isFixedTerm: true)
        XCTAssertFalse(none.isEligible)
        XCTAssertEqual(none.payableGratuity, 0, accuracy: 0.01)
        let elevenMonths = GratuityCalculationResult.computeLocally(lastDrawnSalary: 50_000, yearsOfService: 0, months: 11, isFixedTerm: true)
        XCTAssertFalse(elevenMonths.isEligible)
    }

    func testTenYearsRegular() {
        let r = GratuityCalculationResult.computeLocally(lastDrawnSalary: 50_000, yearsOfService: 10)
        XCTAssertEqual(r.payableGratuity, 2_88_461.54, accuracy: 0.01)
    }

    func testFortyYearsCappedAtCeiling() {
        let r = GratuityCalculationResult.computeLocally(lastDrawnSalary: 5_00_000, yearsOfService: 40)
        XCTAssertTrue(r.isCapped)
        XCTAssertEqual(r.payableGratuity, 20_00_000, accuracy: 0.01)
    }
}
