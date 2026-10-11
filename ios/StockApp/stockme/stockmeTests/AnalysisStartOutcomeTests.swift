import XCTest
@testable import stockme

/// IOSUI-10 / IOSCORE-V1: the 409 ALREADY_RUNNING body has no `status`, and a malformed
/// cache hit used to decode to nil; both left the analysis screen blank.
@MainActor
final class AnalysisStartOutcomeTests: XCTestCase {

    private func decode(_ json: String) throws -> StartJobResponse {
        try JSONDecoder().decode(StartJobResponse.self, from: Data(json.utf8))
    }

    private let alreadyRunning = """
    {"error_code":"ALREADY_RUNNING","error_title":"Analysis Already Running",
     "error_detail":"You already have an analysis in progress (INFY, status RUNNING).",
     "error_type":"rate_limit","job_id":"j1","ticker":"INFY","suggested_action":"ATTACH_OR_CANCEL"}
    """

    func testAlreadyRunningSameTickerAttaches() throws {
        let start = try decode(alreadyRunning)
        XCTAssertEqual(start.errorCode, "ALREADY_RUNNING")
        XCTAssertNil(start.analysis)
        XCTAssertEqual(AnalysisViewModel.classify(start, ticker: "INFY"), .attach("j1"))
        XCTAssertEqual(AnalysisViewModel.classify(start, ticker: "infy"), .attach("j1"))
    }

    func testAlreadyRunningOtherTickerIsConflict() throws {
        let start = try decode(alreadyRunning)
        XCTAssertEqual(AnalysisViewModel.classify(start, ticker: "TCS"), .conflict("INFY"))
    }

    func testQueuedJobAttaches() throws {
        let start = try decode(#"{"job_id":"j2","status":"QUEUED","ticker":"INFY","scan_type":"standard"}"#)
        XCTAssertEqual(AnalysisViewModel.classify(start, ticker: "INFY"), .attach("j2"))
    }

    func testUnknownJobStatusIsUnexpected() throws {
        let start = try decode(#"{"job_id":"j3","status":"WEIRD"}"#)
        XCTAssertEqual(AnalysisViewModel.classify(start, ticker: "INFY"), .unexpected)
    }

    func testMalformedCacheHitThrows() {
        XCTAssertThrowsError(try decode(#"{"ticker":"INFY","foo":1}"#))
    }
}
