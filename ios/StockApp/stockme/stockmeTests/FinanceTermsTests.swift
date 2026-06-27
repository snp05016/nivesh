import XCTest
@testable import stockme

final class FinanceTermsTests: XCTestCase {

    func testExactMatch() {
        let term = FinanceTerms.shared.lookup("P/E Ratio")
        XCTAssertNotNil(term)
        XCTAssertEqual(term?.term, "P/E Ratio")
    }

    func testFuzzyPunctuationMatch() {
        // "PE Ratio" missing the slash should still match "P/E Ratio"
        let term1 = FinanceTerms.shared.lookup("PE Ratio")
        XCTAssertNotNil(term1)
        XCTAssertEqual(term1?.term, "P/E Ratio")
        
        let term2 = FinanceTerms.shared.lookup("pe ratio")
        XCTAssertNotNil(term2)
        XCTAssertEqual(term2?.term, "P/E Ratio")
    }
    
    func testFuzzySpacingMatch() {
        // Spaces should be ignored
        let term = FinanceTerms.shared.lookup("  P / E  Ratio ")
        XCTAssertNotNil(term)
        XCTAssertEqual(term?.term, "P/E Ratio")
    }

    func testNewFoundationalTerms() {
        // Test a few newly added terms
        XCTAssertNotNil(FinanceTerms.shared.lookup("SEBI"))
        XCTAssertNotNil(FinanceTerms.shared.lookup("Demat Account"))
        XCTAssertNotNil(FinanceTerms.shared.lookup("SIP"))
        XCTAssertNotNil(FinanceTerms.shared.lookup("Mutual Fund"))
        XCTAssertNotNil(FinanceTerms.shared.lookup("NIFTY 50"))
    }
    
    func testContainsMatch() {
        // "NIFTY" should match "NIFTY 50" if no exact match is found
        let term = FinanceTerms.shared.lookup("NIFTY")
        XCTAssertNotNil(term)
        XCTAssertEqual(term?.term, "NIFTY 50")
    }

    func testUnknownTerm() {
        let term = FinanceTerms.shared.lookup("SomeUnknownTermXYZ")
        XCTAssertNil(term)
    }
}
