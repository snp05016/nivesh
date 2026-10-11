import XCTest
@testable import stockme

/// UX-21 / UX-18: the run the user asked for (tier, language, debate rounds) is what is sent,
/// retried, and cancelled.
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

    func testCancelWithoutJobReturnsToIdle() {
        let vm = AnalysisViewModel()
        vm.isLoading = true
        vm.cancelAnalysis()
        XCTAssertFalse(vm.isLoading)
        XCTAssertNil(vm.errorInfo)
        XCTAssertNil(vm.jobId)
    }

    func testRetryLastWithoutRequestIsNoOp() {
        let vm = AnalysisViewModel()
        vm.retryLast(userId: nil, useMock: true, reportManager: LocalReportManager())
        XCTAssertFalse(vm.isLoading)
        XCTAssertNil(vm.lastRequest)
    }
}
