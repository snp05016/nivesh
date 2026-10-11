import XCTest
@testable import stockme

/// IOSCORE-22: the global engine watcher polls only while a job is in flight
/// (it used to hit GET /analyze/active every 3 s forever while idle).
@MainActor
final class EnginePollingPolicyTests: XCTestCase {

    private func job(_ status: String) -> JobStatus {
        JobStatus(jobId: "j1", userId: 1, ticker: "TCS", scanType: "standard", status: status,
                  stage: nil, progressPct: nil, checkpoints: nil, tokensUsed: nil, error: nil, result: nil)
    }

    func testNoActiveJobStopsPolling() {
        XCTAssertFalse(AnalysisEngineManager.shouldKeepPolling(nil))
    }

    func testRunningOrQueuedJobKeepsPolling() {
        XCTAssertTrue(AnalysisEngineManager.shouldKeepPolling(job("RUNNING")))
        XCTAssertTrue(AnalysisEngineManager.shouldKeepPolling(job("QUEUED")))
    }

    func testTerminalStatusesStopPolling() {
        for status in AnalysisEngineManager.terminalStatuses {
            XCTAssertFalse(AnalysisEngineManager.shouldKeepPolling(job(status)), status)
        }
        XCTAssertFalse(AnalysisEngineManager.shouldKeepPolling(job("WEIRD")))
    }

    func testRunningJobPollsEvery2sAndBacksOffTo15s() {
        let second: UInt64 = 1_000_000_000
        XCTAssertEqual(AnalysisViewModel.pollDelay(consecutiveFailures: 0), 2 * second)
        XCTAssertEqual(AnalysisViewModel.pollDelay(consecutiveFailures: 1), 4 * second)
        XCTAssertEqual(AnalysisViewModel.pollDelay(consecutiveFailures: 5), 15 * second)
    }
}
