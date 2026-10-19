import XCTest
@testable import stockme

/// UX-21 / UX-18: the Settings values map to the request fields as the user chose them.
@MainActor
final class AnalysisRequestTests: XCTestCase {

    func testFromMapsEnglishToNilLanguage() {
        let r = AnalysisRequest.from(ticker: "TCS", scanType: "extreme", deepScan: true, languageSetting: "English", roundsSetting: "2")
        XCTAssertNil(r.language)
        XCTAssertEqual(r.debateRounds, 2)
        XCTAssertEqual(r.scanType, "extreme")
        XCTAssertTrue(r.deepScan)
    }

    func testFromKeepsHindi() {
        let r = AnalysisRequest.from(ticker: "TCS", scanType: "standard", deepScan: false, languageSetting: "Hindi", roundsSetting: "1")
        XCTAssertEqual(r.language, "Hindi")
        XCTAssertEqual(r.debateRounds, 1)
    }
}
