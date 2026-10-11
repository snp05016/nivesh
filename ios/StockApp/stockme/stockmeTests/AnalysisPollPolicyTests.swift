import XCTest
@testable import stockme

/// IOSCORE-16: a lost or foreign job (4xx) ends the poll loop; transient errors back off.
@MainActor
final class AnalysisPollPolicyTests: XCTestCase {

    private let lost = AnalysisViewModel.PollOutcome.terminal(AnalysisViewModel.jobLostMessage)

    func testLostJobStatusesAreTerminal() {
        for code in [401, 403, 404, 422] {
            XCTAssertEqual(AnalysisViewModel.pollOutcome(for: NetworkError.serverError(code, nil)), lost, "\(code)")
        }
        XCTAssertEqual(AnalysisViewModel.pollOutcome(for: NetworkError.unauthorized), lost)
    }

    func testTransientErrorsRetry() {
        XCTAssertEqual(AnalysisViewModel.pollOutcome(for: URLError(.notConnectedToInternet)), .retry)
        XCTAssertEqual(AnalysisViewModel.pollOutcome(for: NetworkError.serverError(502, nil)), .retry)
    }

    func testBackoffDoublesThenCaps() {
        let second: UInt64 = 1_000_000_000
        XCTAssertEqual(AnalysisViewModel.pollDelay(consecutiveFailures: 0), 2 * second)
        XCTAssertEqual(AnalysisViewModel.pollDelay(consecutiveFailures: 1), 4 * second)
        XCTAssertEqual(AnalysisViewModel.pollDelay(consecutiveFailures: 3), 15 * second)
        XCTAssertEqual(AnalysisViewModel.pollDelay(consecutiveFailures: 50), 15 * second)
        let delays = (0...10).map { AnalysisViewModel.pollDelay(consecutiveFailures: $0) }
        XCTAssertEqual(delays, delays.sorted())
    }
}
