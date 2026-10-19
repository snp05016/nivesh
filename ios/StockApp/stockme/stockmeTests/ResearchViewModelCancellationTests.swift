import XCTest
@testable import stockme

/// A cancelled load (view disappeared mid-request) must not be treated as a failure,
/// so the next appearance reloads instead of showing an error or a stuck spinner.
@MainActor
final class ResearchViewModelCancellationTests: XCTestCase {
    func testCancellationErrorsAreRecognised() {
        XCTAssertTrue(ResearchViewModel.isCancellation(CancellationError()))
        XCTAssertTrue(ResearchViewModel.isCancellation(URLError(.cancelled)))
    }

    func testRealFailuresAreNotCancellation() {
        XCTAssertFalse(ResearchViewModel.isCancellation(URLError(.notConnectedToInternet)))
        XCTAssertFalse(ResearchViewModel.isCancellation(NetworkError.connectionFailed))
    }
}
