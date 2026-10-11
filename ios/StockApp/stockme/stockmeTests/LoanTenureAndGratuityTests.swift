import XCTest
@testable import stockme

/// Loan offer tenure label keeps the month component, and an ineligible
/// gratuity result pays nothing while still carrying the would-be value.
final class LoanTenureAndGratuityTests: XCTestCase {

    private func offer(minTenure: Int, maxTenure: Int) throws -> LoanOfferDTO {
        let json = """
        {"id": 1, "nbfc_name": "Demo NBFC", "loan_type": "gold",
         "min_amount": 10000, "max_amount": 500000, "interest_rate_pct": 9.5,
         "min_tenure_months": \(minTenure), "max_tenure_months": \(maxTenure),
         "min_credit_score": 650, "processing_fee_pct": 1.0}
        """.data(using: .utf8)!
        return try JSONDecoder().decode(LoanOfferDTO.self, from: json)
    }

    func testTenureRangeSubYearShowsMonths() throws {
        XCTAssertEqual(try offer(minTenure: 3, maxTenure: 36).tenureRangeDisplay, "3–36 mo")
        XCTAssertEqual(try offer(minTenure: 6, maxTenure: 48).tenureRangeDisplay, "6–48 mo")
    }

    func testTenureRangeWholeYears() throws {
        XCTAssertEqual(try offer(minTenure: 12, maxTenure: 60).tenureRangeDisplay, "1–5 yrs")
    }

    func testGratuityUnderFiveYearsIneligibleKeepsEstimate() {
        // 4 yr 11 mo: still short of 5 years' continuous service.
        let r = GratuityCalculationResult.computeLocally(lastDrawnSalary: 50_000, yearsOfService: 4, months: 11)
        XCTAssertFalse(r.isEligible)
        XCTAssertFalse(r.isCapped)
        XCTAssertEqual(r.payableGratuity, 0, accuracy: 0.01)
        XCTAssertEqual(r.uncappedGratuity, 1_44_230.77, accuracy: 0.01)
    }
}
